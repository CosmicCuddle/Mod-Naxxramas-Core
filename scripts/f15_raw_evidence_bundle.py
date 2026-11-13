#!/usr/bin/env python3
"""F15 owned raw crash-evidence bundles with 30-day retention metadata."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat


INCIDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
ARTIFACT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
RETENTION = timedelta(days=30)
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 4 * 1024 * 1024


class Refused(RuntimeError):
    pass


def _private_dir(path: Path, create: bool = True) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise Refused("bundle directory may not be a symlink")
    if not path.exists():
        if not create:
            raise Refused("bundle directory missing")
        path.mkdir(mode=0o700, parents=False)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Refused("bundle directory must be mode 0700")
    return path


def _safe_regular(path: Path):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
        raise Refused("bundle artifact must be one private regular file")
    return st


def _write_exclusive(path: Path, data: bytes) -> None:
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL |
        getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        raise


def _atomic_json(path: Path, obj: dict) -> None:
    pending = path.with_name(path.name + ".pending")
    _write_exclusive(pending, (json.dumps(obj, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(pending, path)
    dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise Refused("bundle timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", "replace")
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_bundle(raw_root: Path, incident_id: str, artifacts: dict[str, object],
                 created_utc: datetime | None = None,
                 provenance: dict[str, str] | None = None) -> Path:
    if not INCIDENT_RE.fullmatch(incident_id):
        raise Refused("invalid incident id")
    if not isinstance(artifacts, dict) or not artifacts:
        raise Refused("raw evidence bundle requires artifacts")

    root = _private_dir(Path(raw_root))
    when = _utc(created_utc)
    bundle_name = f"{when.strftime('%Y%m%dT%H%M%SZ')}-{incident_id}"
    bundle = root / bundle_name
    if bundle.exists() or bundle.is_symlink():
        raise Refused("raw evidence bundle collision")
    bundle.mkdir(mode=0o700)

    total = 0
    records = []
    try:
        for name in sorted(artifacts):
            if not ARTIFACT_RE.fullmatch(name):
                raise Refused("invalid evidence artifact name")
            data = _bytes(artifacts[name])
            if len(data) > MAX_ARTIFACT_BYTES:
                raise Refused("evidence artifact exceeds bound")
            total += len(data)
            if total > MAX_BUNDLE_BYTES:
                raise Refused("raw evidence bundle exceeds bound")
            path = bundle / name
            _write_exclusive(path, data)
            records.append({
                "name": name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })

        manifest = {
            "kind": "f15_raw_crash_evidence_bundle",
            "incident_id": incident_id,
            "created_utc": when.isoformat(),
            "retention_days": 30,
            "artifacts": records,
            "provenance": dict(sorted((provenance or {}).items())),
        }
        _atomic_json(bundle / "manifest.json", manifest)
        dfd = os.open(bundle, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        return bundle
    except BaseException:
        # Never pretend a partial bundle is complete. Preserve the partial
        # directory for review rather than recursively deleting evidence.
        raise


def _read_manifest(bundle: Path) -> dict:
    path = bundle / "manifest.json"
    _safe_regular(path)
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refused("invalid raw evidence manifest") from exc
    if not isinstance(value, dict):
        raise Refused("raw evidence manifest must be object")
    expected = {
        "kind", "incident_id", "created_utc", "retention_days",
        "artifacts", "provenance",
    }
    if set(value) != expected or value["kind"] != "f15_raw_crash_evidence_bundle":
        raise Refused("raw evidence manifest shape/kind mismatch")
    if value["retention_days"] != 30 or not INCIDENT_RE.fullmatch(str(value["incident_id"])):
        raise Refused("raw evidence manifest policy mismatch")
    if not isinstance(value["artifacts"], list) or not value["artifacts"]:
        raise Refused("raw evidence artifact list invalid")
    return value


def _verify_bundle(bundle: Path) -> tuple[dict, list[Path]]:
    _private_dir(bundle, create=False)
    manifest = _read_manifest(bundle)
    expected_names = {"manifest.json"}
    files = []
    for rec in manifest["artifacts"]:
        if not isinstance(rec, dict) or set(rec) != {"name", "size", "sha256"}:
            raise Refused("raw evidence artifact record invalid")
        name = rec["name"]
        if not isinstance(name, str) or not ARTIFACT_RE.fullmatch(name):
            raise Refused("raw evidence artifact name invalid")
        path = bundle / name
        st = _safe_regular(path)
        data = path.read_bytes()
        if st.st_size != rec["size"] or len(data) != rec["size"]:
            raise Refused("raw evidence artifact size mismatch")
        if hashlib.sha256(data).hexdigest() != rec["sha256"]:
            raise Refused("raw evidence artifact hash mismatch")
        expected_names.add(name)
        files.append(path)

    actual = {p.name for p in bundle.iterdir()}
    if actual != expected_names:
        raise Refused("unexpected file in raw evidence bundle")
    return manifest, files



def find_bundle(raw_root: Path, incident_id: str) -> Path | None:
    if not INCIDENT_RE.fullmatch(incident_id):
        raise Refused("invalid incident id")
    root = _private_dir(Path(raw_root))
    matches = []
    suffix = "-" + incident_id
    for path in root.iterdir():
        if path.is_dir() and not path.is_symlink() and path.name.endswith(suffix):
            matches.append(path)
    if len(matches) > 1:
        raise Refused("multiple raw evidence bundles for one incident")
    if not matches:
        return None
    manifest, _files = _verify_bundle(matches[0])
    if manifest["incident_id"] != incident_id:
        raise Refused("raw evidence bundle incident mismatch")
    return matches[0]


def ensure_bundle(raw_root: Path, incident_id: str, artifacts: dict[str, object],
                  created_utc: datetime | None = None,
                  provenance: dict[str, str] | None = None) -> Path:
    """Create once, or reuse one exact verified bundle for this incident.

    This makes report retries idempotent after a complete bundle was already
    published. A partial/unverified matching directory is never silently
    replaced.
    """
    existing = find_bundle(raw_root, incident_id)
    if existing is None:
        return write_bundle(raw_root, incident_id, artifacts, created_utc, provenance)

    manifest, files = _verify_bundle(existing)
    expected = []
    total = 0
    for name in sorted(artifacts):
        if not ARTIFACT_RE.fullmatch(name):
            raise Refused("invalid evidence artifact name")
        data = _bytes(artifacts[name])
        if len(data) > MAX_ARTIFACT_BYTES:
            raise Refused("evidence artifact exceeds bound")
        total += len(data)
        if total > MAX_BUNDLE_BYTES:
            raise Refused("raw evidence bundle exceeds bound")
        expected.append({
            "name": name,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    if manifest["artifacts"] != expected:
        raise Refused("existing raw evidence differs from retry evidence")
    if manifest["provenance"] != dict(sorted((provenance or {}).items())):
        raise Refused("existing raw evidence provenance differs from retry")
    return existing

def retain_bundles(raw_root: Path, now: datetime | None = None) -> int:
    root = _private_dir(Path(raw_root), create=False)
    current = _utc(now)
    intent = root / "retention-intent.json"
    if intent.exists() or intent.is_symlink():
        raise Refused("unfinished raw-evidence retention intent")

    removed = 0
    for bundle in sorted(root.iterdir(), key=lambda p: p.name):
        if bundle.name == "retention-intent.json":
            continue
        if bundle.is_symlink() or not bundle.is_dir():
            continue  # foreign root entries are preserved
        manifest, files = _verify_bundle(bundle)
        try:
            created = datetime.fromisoformat(manifest["created_utc"]).astimezone(timezone.utc)
        except (TypeError, ValueError) as exc:
            raise Refused("invalid raw evidence creation time") from exc
        if current <= created + RETENTION:
            continue

        intent_obj = {
            "kind": "f15_retention_30d_raw_evidence",
            "bundle": bundle.name,
            "incident_id": manifest["incident_id"],
            "created_utc": manifest["created_utc"],
        }
        _atomic_json(intent, intent_obj)

        identities = [(path, _safe_regular(path).st_ino) for path in files + [bundle / "manifest.json"]]
        for path, ino in identities:
            if _safe_regular(path).st_ino != ino:
                raise Refused("raw evidence file changed before retention")

        for path in files:
            path.unlink()
        (bundle / "manifest.json").unlink()
        bundle.rmdir()
        intent.unlink()
        removed += 1
    return removed
