#!/usr/bin/env python3
"""F15 pre-overwrite live-log snapshot helper.

Copies current regular log files into an independent private archive before a
launcher/rotation path overwrites them. It never truncates/renames/removes the
source. Production invocation timing is intentionally external to this module.

Directory snapshots use a two-phase contract:
1. pre-scan/classify the whole direct log root before creating snapshot data;
2. prepare and verify every eligible copy privately;
3. publish prepared copies only after every preparation succeeded.

A failure never authorizes the overwrite owner to continue. A crash during the
final publication phase can leave partial evidence, but cannot return success.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

MAX_FILE_BYTES = 1024 * 1024 * 1024
CHUNK = 1024 * 1024
SAFE = re.compile(r"[^A-Za-z0-9._-]+")
F15_EXCLUDED_DIRS = {"Crash Logs", "Archived Logs", ".f15-state"}


class Refused(RuntimeError):
    pass


@dataclass(frozen=True)
class _SourcePlan:
    path: Path
    fingerprint: tuple[int, int, int, int, int]


@dataclass(frozen=True)
class _PreparedSnapshot:
    pending_data: Path
    pending_manifest: Path
    data_path: Path
    manifest_path: Path


def _private_dir(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise Refused("archive directory may not be a symlink")
    if not path.exists():
        path.mkdir(mode=0o700, parents=False)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Refused("archive directory must be mode 0700")
    return path


@contextmanager
def _archive_lock(archive_root: Path):
    """Serialize one archive root's scan/prepare/publish transaction.

    The persistent lock inode is foreign to retention ownership and is never a
    snapshot manifest. A process crash releases the kernel lock automatically.
    """
    lock_path = archive_root / ".f15-snapshot.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise Refused("cannot open snapshot lock safely") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("snapshot lock must be one private regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("snapshot lock changed while locked")
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _safe_name(name: str) -> str:
    value = SAFE.sub("_", name).strip("._")
    if not value:
        value = "log"
    return value[:160]


def _utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise Refused("observation time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _fingerprint(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_nlink)


def _open_source(path: Path, expected: tuple[int, int, int, int, int] | None = None):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise Refused("source log could not be opened safely") from exc
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise Refused("source log must be regular file")
    if st.st_nlink != 1:
        os.close(fd)
        raise Refused("hardlinked source log refused")
    if st.st_size > MAX_FILE_BYTES:
        os.close(fd)
        raise Refused("source log exceeds snapshot bound")
    if expected is not None and _fingerprint(st) != expected:
        os.close(fd)
        raise Refused("source changed after pre-scan")
    return fd, st


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write while preparing snapshot")
        view = view[written:]


def _new_pending(root: Path, prefix: str) -> tuple[int, Path]:
    fd, raw = tempfile.mkstemp(prefix=prefix, dir=root)
    path = Path(raw)
    os.fchmod(fd, 0o600)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
        os.close(fd)
        raise Refused("pending snapshot artifact must be one private regular file")
    return fd, path


def _prepare_snapshot(source: Path, archive_root: Path, when: datetime,
                      expected: tuple[int, int, int, int, int] | None = None) -> _PreparedSnapshot:
    fd, before = _open_source(source, expected)
    try:
        stamp = when.strftime("%Y%m%dT%H%M%S.%fZ")
        label = _safe_name(source.name)
        nonce = f"{before.st_dev:x}-{before.st_ino:x}-{before.st_size:x}"
        base = f"{stamp}-{label}-{nonce}"
        data_path = archive_root / (base + ".log")
        manifest_path = archive_root / (base + ".json")
        for final in (data_path, manifest_path):
            if final.exists() or final.is_symlink():
                raise Refused("snapshot destination collision")

        outfd, pending_data = _new_pending(archive_root, f".{base}.log.pending.")
        digest = hashlib.sha256()
        copied = 0
        try:
            while copied < before.st_size:
                block = os.pread(fd, min(CHUNK, before.st_size - copied), copied)
                if not block:
                    raise Refused("source shortened during snapshot")
                _write_all(outfd, block)
                digest.update(block)
                copied += len(block)
            os.fsync(outfd)
        finally:
            os.close(outfd)

        after = os.fstat(fd)
        if _fingerprint(after) != _fingerprint(before):
            raise Refused("source changed during snapshot; pending copy retained for review")

        manifest = {
            "kind": "f15_preoverwrite_log_snapshot",
            "created_utc": when.isoformat(),
            "source_path": str(source),
            "source_dev": before.st_dev,
            "source_ino": before.st_ino,
            "source_size": before.st_size,
            "source_mtime_ns": before.st_mtime_ns,
            "sha256": digest.hexdigest(),
            "snapshot_file": data_path.name,
            "retention_days": 30,
        }
        mfd, pending_manifest = _new_pending(archive_root, f".{base}.json.pending.")
        try:
            _write_all(mfd, (json.dumps(manifest, sort_keys=True) + "\n").encode())
            os.fsync(mfd)
        finally:
            os.close(mfd)

        return _PreparedSnapshot(
            pending_data=pending_data,
            pending_manifest=pending_manifest,
            data_path=data_path,
            manifest_path=manifest_path,
        )
    finally:
        os.close(fd)


def _ensure_publish_targets_free(prepared: list[_PreparedSnapshot]) -> None:
    for item in prepared:
        for final in (item.data_path, item.manifest_path):
            if final.exists() or final.is_symlink():
                raise Refused("snapshot destination collision before publication")


def _publish_all(prepared: list[_PreparedSnapshot], archive_root: Path) -> list[tuple[Path, Path]]:
    _ensure_publish_targets_free(prepared)
    published: list[tuple[Path, Path]] = []
    for item in prepared:
        # Publication is deliberately after every source has been copied and
        # verified. Any failure here propagates; the overwrite owner must stop.
        os.replace(item.pending_data, item.data_path)
        os.replace(item.pending_manifest, item.manifest_path)
        published.append((item.data_path, item.manifest_path))
    dfd = os.open(archive_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return published


def _scan_log_root(log_root: Path, archive_root: Path,
                   excluded_names: set[str] | None = None) -> list[_SourcePlan]:
    if log_root.is_symlink() or not log_root.is_dir():
        raise Refused("log root must be a real directory")

    exclusions = set(excluded_names or ())
    exclusions.update(F15_EXCLUDED_DIRS)
    exclusions.add(archive_root.name)

    plans: list[_SourcePlan] = []
    for entry in sorted(log_root.iterdir(), key=lambda p: p.name):
        try:
            st = entry.lstat()
        except OSError as exc:
            raise Refused("log root entry could not be classified") from exc

        if entry.name in exclusions:
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
                raise Refused("excluded F15 path must be a real directory")
            continue

        if stat.S_ISLNK(st.st_mode):
            raise Refused("symlink entry in log root refused")
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode):
            raise Refused("unsupported non-regular entry in log root")
        if st.st_nlink != 1:
            raise Refused("hardlinked source log refused")
        if st.st_size > MAX_FILE_BYTES:
            raise Refused("source log exceeds snapshot bound")

        plans.append(_SourcePlan(entry, _fingerprint(st)))
    return plans


def _revalidate_sources(plans: list[_SourcePlan]) -> None:
    """Require every source to still match the complete-root pre-scan.

    This closes the gap where an early source changes while later files are
    being prepared. The overwrite owner must still prevent writes between a
    successful return from this helper and the destructive overwrite itself.
    """
    for plan in plans:
        fd, current = _open_source(plan.path, plan.fingerprint)
        try:
            if _fingerprint(current) != plan.fingerprint:
                raise Refused("source changed before batch publication")
        finally:
            os.close(fd)


def snapshot_file(source: Path, archive_root: Path, observed_utc: datetime | None = None) -> tuple[Path, Path]:
    source = Path(source)
    when = _utc(observed_utc)
    archive_root = _private_dir(Path(archive_root))
    with _archive_lock(archive_root):
        prepared = _prepare_snapshot(source, archive_root, when)
        return _publish_all([prepared], archive_root)[0]


def snapshot_log_directory(log_root: Path, archive_root: Path, excluded_names: set[str] | None = None,
                           observed_utc: datetime | None = None) -> list[tuple[Path, Path]]:
    log_root = Path(log_root)
    archive_root = _private_dir(Path(archive_root))
    when = _utc(observed_utc)

    # The archive lock serializes the full root classification, preparation and
    # publication transaction. Creating the private archive/lock is harmless;
    # no snapshot data is created before the complete root pre-scan succeeds.
    with _archive_lock(archive_root):
        # Phase 1: classify the entire direct root before creating snapshot data.
        plans = _scan_log_root(log_root, archive_root, excluded_names)

        # Phase 2: prepare every eligible copy privately. No final .log/.json
        # snapshot is published until every source has passed open/stability/hash.
        prepared: list[_PreparedSnapshot] = []
        for plan in plans:
            prepared.append(_prepare_snapshot(plan.path, archive_root, when, plan.fingerprint))

        # Recheck the complete source set after the last copy was prepared.
        # An early source changing while a later one is copied invalidates the
        # batch before any final snapshot pair is published.
        _revalidate_sources(plans)

        # Phase 3: publish only after the full preparation/revalidation phase succeeded.
        return _publish_all(prepared, archive_root)
