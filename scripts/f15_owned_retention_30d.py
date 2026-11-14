#!/usr/bin/env python3
"""F15 30-day retention for F15-owned snapshots and crash reports only.

Never targets active source logs. Unknown/foreign files are preserved.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat


RETENTION = timedelta(days=30)
SNAPSHOT_KIND = "f15_preoverwrite_log_snapshot"
CRASH_RE = re.compile(
    r"^(?P<stamp>\d{8}T\d{6}Z)-(?P<service>Worldserver|Authserver)-"
    r"(?P<incident>[A-Za-z0-9][A-Za-z0-9._-]{0,95})\.txt$"
)
HISTORY_RE = re.compile(
    r"^(?P<stamp>\d{8}T\d{6}Z)\t(?:Worldserver|Authserver)\t"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\t.*\treport=(?P<report>[^\t\r\n]+)\n?$"
)


class Refused(RuntimeError):
    pass


def _aware_utc(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise Refused("retention time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _safe_regular(path: Path):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
        raise Refused("owned retention artifact must be one private regular file")
    return st


def _atomic_write(path: Path, data: bytes) -> None:
    pending = path.with_name(path.name + ".pending")
    fd = os.open(
        pending,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(pending, path)
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException:
        raise


def _read_json(path: Path) -> dict:
    _safe_regular(path)
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refused("invalid owned manifest JSON") from exc
    if not isinstance(value, dict):
        raise Refused("owned manifest must be an object")
    return value


def _expired(created: datetime, now: datetime) -> bool:
    return now > created + RETENTION


def _parse_iso_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Refused("invalid owned UTC timestamp") from exc
    if dt.tzinfo is None:
        raise Refused("owned timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def retain_snapshot_archive(snapshot_root: Path, now: datetime | None = None) -> int:
    """Delete only verified F15 snapshot .log + .json pairs older than 30 days."""
    root = Path(snapshot_root)
    if root.is_symlink() or not root.is_dir():
        raise Refused("snapshot root must be a real directory")
    current = _aware_utc(now)
    intent = root / "retention-intent.json"
    if intent.exists() or intent.is_symlink():
        raise Refused("unfinished snapshot retention intent requires review")

    removed = 0
    manifests = sorted(root.glob("*.json"))
    for manifest_path in manifests:
        if manifest_path.name == "retention-intent.json":
            continue
        manifest = _read_json(manifest_path)
        required = {
            "kind", "created_utc", "source_path", "source_dev", "source_ino",
            "source_size", "source_mtime_ns", "sha256", "snapshot_file",
            "retention_days",
        }
        if set(manifest) != required or manifest.get("kind") != SNAPSHOT_KIND:
            continue  # foreign JSON is preserved
        if manifest.get("retention_days") != 30:
            raise Refused("snapshot retention metadata changed")
        created = _parse_iso_utc(manifest["created_utc"])
        if not _expired(created, current):
            continue

        data_path = root / str(manifest["snapshot_file"])
        if data_path.parent != root or data_path.suffix != ".log":
            raise Refused("snapshot manifest points outside owned root")
        data_st = _safe_regular(data_path)
        manifest_st = _safe_regular(manifest_path)
        if data_st.st_size != int(manifest["source_size"]):
            raise Refused("snapshot size differs from manifest")
        if _hash_file(data_path) != manifest["sha256"]:
            raise Refused("snapshot hash differs from manifest")

        payload = {
            "kind": "f15_retention_30d_snapshot",
            "snapshot": data_path.name,
            "manifest": manifest_path.name,
            "created_utc": manifest["created_utc"],
        }
        _atomic_write(intent, (json.dumps(payload, sort_keys=True) + "\n").encode())

        # Recheck identities immediately before unlink.
        if _safe_regular(data_path).st_ino != data_st.st_ino:
            raise Refused("snapshot identity changed before retention")
        if _safe_regular(manifest_path).st_ino != manifest_st.st_ino:
            raise Refused("manifest identity changed before retention")
        data_path.unlink()
        manifest_path.unlink()
        intent.unlink()
        removed += 1
    return removed


def _crash_identity(name: str) -> tuple[datetime, str, str] | None:
    match = CRASH_RE.fullmatch(name)
    if not match:
        return None
    try:
        stamp = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise Refused("invalid crash-report timestamp") from exc
    return stamp, match.group("service"), match.group("incident")


def _history_owned_reports(history: Path) -> set[tuple[str, str, str, str]]:
    if not history.exists():
        return set()
    _safe_regular(history)
    owned = set()
    for line in history.read_text("utf-8").splitlines(keepends=True):
        match = HISTORY_RE.fullmatch(line)
        if not match:
            continue
        report_name = match.group("report")
        identity = _crash_identity(report_name)
        if identity is None:
            continue
        stamp, service, incident = identity
        history_stamp = match.group("stamp")
        if stamp.strftime("%Y%m%dT%H%M%SZ") != history_stamp:
            continue
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 4:
            continue
        if fields[1] != service or fields[2] != incident:
            continue
        owned.add((report_name, history_stamp, service, incident))
    return owned


def _report_matches_identity(path: Path, service: str, incident: str) -> bool:
    _safe_regular(path)
    data = path.read_bytes()
    if len(data) > 128 * 1024:
        return False
    text = data.decode("utf-8", "replace")
    if not text.startswith("Cosmic Core — Detailed Crash / Exit Report\n"):
        return False
    lines = set(text.splitlines())
    return (
        f"Incident ID: {incident}" in lines
        and f"Service: {service}" in lines
    )


def _rewrite_history(history: Path, crash_root: Path, now: datetime) -> int:
    if not history.exists():
        return 0
    _safe_regular(history)
    lines = history.read_text("utf-8").splitlines(keepends=True)
    kept = []
    dropped = 0
    for line in lines:
        match = HISTORY_RE.fullmatch(line)
        if not match:
            kept.append(line)  # unknown history format is preserved
            continue
        stamp = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        report = crash_root / match.group("report")
        if _expired(stamp, now) and not report.exists():
            dropped += 1
            continue
        kept.append(line)
    if dropped:
        _atomic_write(history, "".join(kept).encode("utf-8"))
    return dropped


def retain_crash_reports(crash_root: Path, now: datetime | None = None) -> tuple[int, int]:
    """Expire only recognized private F15 crash reports older than 30 days.

    Foreign files are preserved. Crash-History entries are pruned only after the
    referenced owned report no longer exists.
    """
    root = Path(crash_root)
    if root.is_symlink() or not root.is_dir():
        raise Refused("Crash Logs root must be a real directory")
    current = _aware_utc(now)
    intent = root / "retention-intent.json"
    if intent.exists() or intent.is_symlink():
        raise Refused("unfinished crash retention intent requires review")

    removed = 0
    for path in sorted(root.iterdir()):
        if path.name in {"Crash-History.txt", "retention-intent.json"}:
            continue
        identity = _crash_identity(path.name)
        if identity is None:
            continue
        stamp, service, incident = identity
        if not _expired(stamp, current):
            continue

        owned_history = _history_owned_reports(root / "Crash-History.txt")
        key = (path.name, stamp.strftime("%Y%m%dT%H%M%SZ"), service, incident)
        if key not in owned_history or not _report_matches_identity(path, service, incident):
            continue

        st = _safe_regular(path)
        payload = {
            "kind": "f15_retention_30d_crash_report",
            "report": path.name,
            "observed_stamp": stamp.strftime("%Y%m%dT%H%M%SZ"),
        }
        _atomic_write(intent, (json.dumps(payload, sort_keys=True) + "\n").encode())
        if _safe_regular(path).st_ino != st.st_ino:
            raise Refused("crash report identity changed before retention")
        path.unlink()
        intent.unlink()
        removed += 1

    history_dropped = _rewrite_history(root / "Crash-History.txt", root, current)
    return removed, history_dropped
