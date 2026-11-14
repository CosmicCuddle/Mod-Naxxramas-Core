#!/usr/bin/env python3
"""F15 30-day retention for F15-owned snapshots and crash reports only.

Never targets active source logs. Unknown/foreign files are preserved.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

import f15_crash_report_renderer as renderer


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


@contextmanager
def _history_lock(path: Path):
    try:
        with renderer._history_lock(path):
            yield
    except renderer.Refused as exc:
        raise Refused(str(exc)) from exc


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
    """Durably replace a private file without a fixed crash-blocking temp name."""
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.pending.", dir=path.parent)
    pending = Path(raw)
    replaced = False
    try:
        os.fchmod(fd, 0o600)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("pending retention file must be one private regular file")
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        replaced = True
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        if not replaced:
            try:
                pending.unlink()
            except FileNotFoundError:
                pass



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
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("owned retention artifact must be one private regular file")
        offset = 0
        while offset < st.st_size:
            block = os.pread(fd, min(1024 * 1024, st.st_size - offset), offset)
            if not block:
                raise Refused("owned retention artifact shortened during hash")
            h.update(block)
            offset += len(block)
        after = os.fstat(fd)
        if (
            after.st_dev != st.st_dev or after.st_ino != st.st_ino
            or after.st_size != st.st_size or after.st_mtime_ns != st.st_mtime_ns
            or after.st_nlink != st.st_nlink or after.st_mode != st.st_mode
        ):
            raise Refused("owned retention artifact changed during hash")
        return h.hexdigest()
    finally:
        os.close(fd)


def _identity(path: Path) -> dict:
    st = _safe_regular(path)
    return {
        "dev": st.st_dev,
        "ino": st.st_ino,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": _hash_file(path),
    }


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
            "version": 2,
            "kind": "f15_retention_30d_snapshot",
            "snapshot": data_path.name,
            "manifest": manifest_path.name,
            "created_utc": manifest["created_utc"],
            "snapshot_identity": _identity(data_path),
            "manifest_identity": _identity(manifest_path),
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


def _crash_stamp(name: str) -> datetime | None:
    match = CRASH_RE.fullmatch(name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise Refused("invalid crash-report timestamp") from exc


def _rewrite_history_locked(history: Path, crash_root: Path, now: datetime) -> int:
    if history.is_symlink():
        raise Refused("Crash-History.txt may not be a symlink")
    if not history.exists():
        return 0

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(history, flags)
    except OSError as exc:
        raise Refused("Crash-History.txt could not be opened safely") from exc
    try:
        try:
            data, _st = renderer._history_bytes_locked(fd)
        except renderer.Refused as exc:
            raise Refused(str(exc)) from exc
    finally:
        os.close(fd)

    try:
        lines = data.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise Refused("Crash-History.txt is not valid UTF-8") from exc

    kept = []
    dropped = 0
    for line in lines:
        match = HISTORY_RE.fullmatch(line)
        if not match:
            kept.append(line)
            continue
        stamp = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        report = crash_root / match.group("report")
        if _expired(stamp, now) and not report.exists():
            dropped += 1
            continue
        kept.append(line)

    if dropped:
        encoded = "".join(kept).encode("utf-8")
        if len(encoded) > renderer.MAX_HISTORY_BYTES:
            raise Refused("rewritten Crash-History.txt exceeds configured bound")
        _atomic_write(history, encoded)
    return dropped


def _rewrite_history(history: Path, crash_root: Path, now: datetime) -> int:
    with _history_lock(history):
        return _rewrite_history_locked(history, crash_root, now)



def retain_crash_reports(crash_root: Path, now: datetime | None = None) -> tuple[int, int]:
    """Expire only recognized private F15 crash reports older than 30 days.

    The stable Crash-History sidecar lock covers both report deletion and
    history pruning, so renderer publication cannot race an atomic history
    replacement and an unsafe lock is detected before destructive retention.
    """
    root = Path(crash_root)
    if root.is_symlink() or not root.is_dir():
        raise Refused("Crash Logs root must be a real directory")
    current = _aware_utc(now)
    intent = root / "retention-intent.json"
    if intent.exists() or intent.is_symlink():
        raise Refused("unfinished crash retention intent requires review")

    history = root / "Crash-History.txt"
    with _history_lock(history):
        removed = 0
        for path in sorted(root.iterdir()):
            if path.name in {"Crash-History.txt", "Crash-History.txt.lock", "retention-intent.json"}:
                continue
            stamp = _crash_stamp(path.name)
            if stamp is None:
                continue
            if not _expired(stamp, current):
                continue
            st = _safe_regular(path)
            payload = {
                "version": 2,
                "kind": "f15_retention_30d_crash_report",
                "report": path.name,
                "observed_stamp": stamp.strftime("%Y%m%dT%H%M%SZ"),
                "report_identity": _identity(path),
            }
            _atomic_write(intent, (json.dumps(payload, sort_keys=True) + "\n").encode())
            if _safe_regular(path).st_ino != st.st_ino:
                raise Refused("crash report identity changed before retention")
            path.unlink()
            intent.unlink()
            removed += 1

        history_dropped = _rewrite_history_locked(history, root, current)
        return removed, history_dropped

