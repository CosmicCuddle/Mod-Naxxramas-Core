#!/usr/bin/env python3
"""F15 pre-overwrite live-log snapshot helper.

Copies current regular log files into an independent private archive before a
launcher/rotation path overwrites them. It never truncates/renames/removes the
source. Production invocation timing is intentionally external to this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_FILE_BYTES = 1024 * 1024 * 1024
CHUNK = 1024 * 1024
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


class Refused(RuntimeError):
    pass


def _reject_symlink_ancestors(path: Path, label: str) -> None:
    """Refuse any existing symlink component above path."""
    current = Path(path).parent
    while True:
        if current.is_symlink():
            raise Refused(f"{label} ancestor may not be a symlink")
        parent = current.parent
        if parent == current:
            break
        current = parent


def _private_dir(path: Path) -> Path:
    path = Path(path)
    _reject_symlink_ancestors(path, "archive directory")
    if path.is_symlink():
        raise Refused("archive directory may not be a symlink")
    if not path.exists():
        path.mkdir(mode=0o700, parents=False)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Refused("archive directory must be mode 0700")
    return path


def _safe_name(name: str) -> str:
    value = SAFE.sub("_", name).strip("._")
    if not value:
        value = "log"
    return value[:160]


def _atomic_json(path: Path, obj: dict) -> None:
    pending = path.with_name(path.name + ".pending")
    fd = os.open(
        pending,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write((json.dumps(obj, sort_keys=True) + "\n").encode())
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


def _open_source(path: Path):
    try:
        pre = path.lstat()
    except OSError:
        raise
    if not stat.S_ISREG(pre.st_mode):
        raise Refused("source log must be regular file")
    if pre.st_nlink != 1:
        raise Refused("hardlinked source log refused")

    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    fd = os.open(path, flags)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise Refused("source log changed to non-regular file")
    if st.st_dev != pre.st_dev or st.st_ino != pre.st_ino:
        os.close(fd)
        raise Refused("source log identity changed during open")
    if st.st_nlink != 1:
        os.close(fd)
        raise Refused("hardlinked source log refused")
    if st.st_size > MAX_FILE_BYTES:
        os.close(fd)
        raise Refused("source log exceeds snapshot bound")
    return fd, st


def snapshot_file(source: Path, archive_root: Path, observed_utc: datetime | None = None) -> tuple[Path, Path]:
    source = Path(source)
    when = observed_utc or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise Refused("observation time must be timezone-aware")
    when = when.astimezone(timezone.utc)

    fd, before = _open_source(source)
    try:
        archive_root = _private_dir(Path(archive_root))
        stamp = when.strftime("%Y%m%dT%H%M%S.%fZ")
        label = _safe_name(source.name)
        nonce = f"{before.st_dev:x}-{before.st_ino:x}-{before.st_size:x}"
        base = f"{stamp}-{label}-{nonce}"
        data_path = archive_root / (base + ".log")
        manifest_path = archive_root / (base + ".json")
        if data_path.exists() or manifest_path.exists() or data_path.is_symlink() or manifest_path.is_symlink():
            raise Refused("snapshot destination collision")

        pending = data_path.with_name(data_path.name + ".pending")
        outfd = os.open(
            pending,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        digest = hashlib.sha256()
        copied = 0
        try:
            while copied < before.st_size:
                block = os.pread(fd, min(CHUNK, before.st_size - copied), copied)
                if not block:
                    raise Refused("source shortened during snapshot")
                os.write(outfd, block)
                digest.update(block)
                copied += len(block)
            os.fsync(outfd)
        finally:
            os.close(outfd)

        after = os.fstat(fd)
        fingerprint_before = (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        )
        fingerprint_after = (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        )
        if fingerprint_after != fingerprint_before:
            raise Refused("source changed during snapshot; pending copy retained for review")

        os.replace(pending, data_path)
        dfd = os.open(archive_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

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
        _atomic_json(manifest_path, manifest)
        return data_path, manifest_path
    finally:
        os.close(fd)


def snapshot_log_directory(log_root: Path, archive_root: Path, excluded_names: set[str] | None = None,
                           observed_utc: datetime | None = None) -> list[tuple[Path, Path]]:
    log_root = Path(log_root)
    if log_root.is_symlink() or not log_root.is_dir():
        raise Refused("log root must be a real directory")
    archive_root = Path(archive_root)
    exclusions = set(excluded_names or ())
    exclusions.update({"Crash Logs", archive_root.name})

    results = []
    for entry in sorted(log_root.iterdir(), key=lambda p: p.name):
        if entry.name in exclusions:
            continue
        if entry.is_symlink():
            raise Refused("symlink entry in log root refused")
        if entry.is_dir():
            continue
        results.append(snapshot_file(entry, archive_root, observed_utc))
    return results
