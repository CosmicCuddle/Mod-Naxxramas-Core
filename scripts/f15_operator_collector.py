#!/usr/bin/env python3
"""F15 opt-in read-only log capture prototype (POSIX).

Archive AND raw-journal deletion occurs ONLY with explicit experimental --retention-30d;\nno original-log deletion, unattended launcher control or automatic rotation.
Captures only explicitly selected World/Auth regular single-link files.
All outputs are confined to a private 0700 collector root.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from datetime import datetime, timezone

LABELS = {"Worldserver-out", "Worldserver-err", "Authserver-out", "Authserver-err"}
RECORD = re.compile(r"^(\d{20})-(\d{20})-(\d{8})-([a-f0-9]{64})\.bin$")
MAX_CHUNK = 65536

class Refused(RuntimeError):
    pass

def digest(data):
    return hashlib.sha256(data).hexdigest()

def private_dir(path):
    path = Path(path)
    if path.is_symlink():
        raise Refused(f"symlink directory refused: {path}")
    if not path.exists():
        path.mkdir(mode=0o700)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Refused(f"directory must be private 0700: {path}")
    return path

def regular_file(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(fd)
        raise Refused(f"source must be one regular non-hardlinked file: {path}")
    return fd, st

def atomic_write(path, content):
    """Only overwrite our own validated output; never a foreign destination."""
    pending = path.with_name(path.name + ".pending")
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(pending, path)
        dirfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        # Never unlink a possibly ambiguous partial artifact automatically.
        raise

def read_receipt(path):
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise Refused("archive receipt is not a single regular file")
    try:
        obj = json.loads(path.read_text("utf-8"))
        if set(obj) != {"sha256", "size"} or not isinstance(obj["size"], int):
            raise ValueError("invalid receipt shape")
        return obj
    except (OSError, ValueError, TypeError) as exc:
        raise Refused("invalid archive receipt") from exc

def collect_once(root, sources, now=None, include_existing=False):
    """Poll one bounded chunk from each explicit file and rebuild changed UTC archives."""
    root = private_dir(root)
    if (root / "retention-intent.json").exists() or (root / "retention-intent.json").is_symlink():
        raise Refused("unfinished retention intent; refuse capture until manual review")
    record_root = private_dir(root / "records")
    archive_root = private_dir(root / "archives")
    lockpath = root / "collector.lock"
    lockfd = os.open(lockpath, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(lockfd).st_mode) or os.fstat(lockfd).st_nlink != 1:
            raise Refused("collector lock must be a single regular file")
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        opened, seen = [], set()
        try:
            for label, filename in sources.items():
                if label not in LABELS:
                    raise Refused(f"invalid label {label}")
                path = Path(filename).absolute()
                if root.resolve() == path or root.resolve() in path.parents:
                    raise Refused("source cannot be in collector root")
                fd, st = regular_file(path)
                if (st.st_dev, st.st_ino) in seen:
                    os.close(fd)
                    raise Refused("one physical source cannot be selected twice")
                seen.add((st.st_dev, st.st_ino))
                opened.append((label, path, fd, st))
            unread = {}
            for label, path, fd, st in opened:
                records = private_dir(record_root / label)
                archives = private_dir(archive_root / label)
                origin_path = records / "origin.json"
                if origin_path.exists():
                    if origin_path.is_symlink() or not origin_path.is_file() or origin_path.stat().st_nlink != 1:
                        raise Refused("invalid origin file")
                    origin = json.loads(origin_path.read_text("utf-8"))
                    if origin != {"path": str(path), "dev": st.st_dev, "ino": st.st_ino, "start": origin.get("start")}:
                        raise Refused(f"source replaced or origin changed for {label}")
                else:
                    if list(records.iterdir()):
                        raise Refused("missing origin with existing records")
                    origin = {"path": str(path), "dev": st.st_dev, "ino": st.st_ino, "start": 0 if include_existing else st.st_size}
                    atomic_write(origin_path, json.dumps(origin, sort_keys=True).encode("utf-8"))
                offset = origin["start"]
                days = {}
                tail_proof = None
                for part in sorted(records.iterdir()):
                    if part.name == "origin.json":
                        continue
                    match = RECORD.fullmatch(part.name)
                    if not match or part.is_symlink() or not part.is_file() or part.stat().st_nlink != 1:
                        raise Refused(f"unknown/untrusted record file: {part.name}")
                    begin, end, day, sha = match.groups()
                    begin, end = int(begin), int(end)
                    if begin != offset or end <= begin or end - begin > MAX_CHUNK:
                        raise Refused("record gap, overlap or impossible size")
                    data = part.read_bytes()
                    if len(data) != end - begin or digest(data) != sha:
                        raise Refused("record content changed")
                    days.setdefault(day, bytearray()).extend(data)
                    # A source writer could copytruncate then regrow the same
                    # inode past our saved cursor between polls. Retain the
                    # last authenticated journal chunk as continuity proof.
                    tail_proof = (begin, data)
                    offset = end
                if st.st_size < offset:
                    raise Refused(f"source truncated for {label}; manual admission required")
                if tail_proof is not None:
                    begin, expected_tail = tail_proof
                    observed_tail = os.pread(fd, len(expected_tail), begin)
                    if observed_tail != expected_tail:
                        raise Refused(f"source rewritten in place for {label}; manual admission required")
                chunk = b""
                if st.st_size > offset:
                    chunk = os.pread(fd, min(MAX_CHUNK, st.st_size - offset), offset)
                    if not chunk:
                        raise Refused("source shortened during poll")
                    if os.fstat(fd).st_size < offset + len(chunk):
                        raise Refused("source size changed during poll")
                # Report the snapshot's remaining source bytes to supervised
                # child-drain callers. All archive writes still occur first.
                unread[label] = st.st_size - offset - len(chunk)
                # Commit journal first; a published record is replayable on restart.
                if chunk:
                    day = datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).strftime("%Y%m%d")
                    history = root / "retention-history"
                    if history.exists() or history.is_symlink():
                        history = private_dir(history)
                        for old in history.iterdir():
                            if old.name.startswith(label + "-" + day + "-"):
                                # A backward wall-clock jump must not recreate an
                                # already-expired UTC observation day.
                                raise Refused("clock returned to an expired archive day")
                    name = f"{offset:020d}-{offset+len(chunk):020d}-{day}-{digest(chunk)}.bin"
                    dest = records / name
                    if dest.exists():
                        raise Refused("journal destination exists")
                    atomic_write(dest, chunk)
                    days.setdefault(day, bytearray()).extend(chunk)
                for day, payload in days.items():
                    content = bytes(payload)
                    archive = archives / f"{day}.txt"
                    receipt_path = archives / f"{day}.receipt.json"
                    receipt = read_receipt(receipt_path)
                    if receipt is not None:
                        if not archive.exists() or archive.is_symlink() or archive.stat().st_nlink != 1:
                            raise Refused("recorded archive missing/replaced")
                        existing = archive.read_bytes()
                        if digest(existing) != receipt["sha256"] or len(existing) != receipt["size"]:
                            # Recovery after archive publication before receipt update is
                            # allowed only if bytes exactly match the journal reconstruction.
                            if existing != content:
                                raise Refused("archive differs from recorded receipt")
                    elif archive.exists():
                        raise Refused("foreign archive without receipt")
                    if not archive.exists() or archive.read_bytes() != content:
                        atomic_write(archive, content)
                    current = {"sha256": digest(content), "size": len(content)}
                    if receipt != current:
                        atomic_write(receipt_path, json.dumps(current, sort_keys=True).encode("utf-8"))
            return unread
        finally:
            for _, _, fd, _ in opened:
                os.close(fd)
    except BlockingIOError as exc:
        raise Refused("collector is already running") from exc
    finally:
        os.close(lockfd)

def main(argv=None):
    parser = argparse.ArgumentParser(description="F15 opt-in capture; experimental explicit-only 30-day owned-archive retention")
    parser.add_argument("--root", required=True, help="private 0700 capture directory")
    parser.add_argument("--source", action="append", required=True, help="LABEL=/absolute/logfile; repeat for World/Auth out/err")
    parser.add_argument("--capture", action="store_true", help="explicitly enable read-only source capture")
    parser.add_argument("--include-existing-on-first-poll", action="store_true", help="EXPLICIT initial backfill; reads already-written source bytes (never resets an established cursor)")
    parser.add_argument("--retention-30d", action="store_true", help="EXPERIMENTAL: explicitly enable deletion of collector-owned archives AND raw journal records older than 30 UTC days; never originals")
    parser.add_argument("--once", action="store_true", help="poll once then exit")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)
    if not args.capture:
        parser.error("capture is OFF by default: supply --capture intentionally")
    if not args.once and not (0.2 <= args.interval <= 3600):
        parser.error("--interval must be between 0.2 and 3600 seconds")
    sources = {}
    for item in args.source:
        label, sep, filename = item.partition("=")
        if not sep or label not in LABELS or label in sources or not Path(filename).is_absolute():
            parser.error("each --source needs a unique Worldserver/Authserver out/err label and absolute path")
        sources[label] = filename
    try:
        while True:
            collect_once(args.root, sources, include_existing=args.include_existing_on_first_poll)
            if args.retention_30d:
                from f15_archive_retention import retain_once
                retain_once(args.root)
            if args.once:
                break
            time.sleep(args.interval)
    except (Refused, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"F15 capture REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
