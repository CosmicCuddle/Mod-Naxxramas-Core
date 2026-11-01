#!/usr/bin/env python3
"""F15 read-only preview of eligible collector-owned 30-day archive days.

DEVELOPMENT DRAFT, OFF unless --preview is supplied. Uses the *same* pinned
journal validation and UTC cutoff as retain_once, but never creates, changes,
truncates or deletes a file. Does not read original World/Auth log sources.
This is not a substitute for revalidation at the time deletion is approved.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import sys

from f15_operator_collector import LABELS, Refused, digest, read_receipt
from f15_archive_retention import (
    RETENTION, _day_end_utc, _listing_records, _read_strict_json, _safe_file,
)


def existing_private_dir(path):
    """Require a pre-existing 0700 leaf with no symlinked path ancestors.

    This is read-only path validation, not a same-UID TOCTOU security boundary.
    """
    path = Path(path).absolute()
    if ".." in path.parts:
        raise Refused("preview refuses parent-directory traversal")
    for ancestor in (path, *path.parents):
        st = ancestor.lstat()
        if not stat.S_ISDIR(st.st_mode):
            raise Refused("preview refuses symlinked/non-directory ancestor")
    if path.lstat().st_mode & 0o077:
        raise Refused("preview needs an existing private 0700 directory")
    return path


def preview_once(root, now=None):
    """Return verified eligible UTC-day metadata; make absolutely no writes.

    The lock prevents racing the cooperative collector/retention worker.
    Previews can become stale after the lock is released; retain_once must
    independently recheck every source and archive before any future removal.
    """
    root = existing_private_dir(root)
    record_root = existing_private_dir(root / "records")
    archive_root = existing_private_dir(root / "archives")
    lock_path = root / "collector.lock"
    _safe_file(lock_path)
    fd = os.open(lock_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (root / "retention-intent.json").exists() or (root / "retention-intent.json").is_symlink():
            raise Refused("unfinished retention intent; preview refused pending manual review")

        current = datetime.now(timezone.utc) if now is None else datetime.fromtimestamp(now, timezone.utc)
        eligible = []
        for label_path in sorted(record_root.iterdir()):
            if label_path.name not in LABELS:
                raise Refused("unexpected collector journal label")
            label = label_path.name
            record_dir = existing_private_dir(label_path)
            archive_dir = existing_private_dir(archive_root / label)
            origin = _read_strict_json(record_dir / "origin.json", {"path", "dev", "ino", "start"})
            if type(origin["start"]) is not int or origin["start"] < 0:
                raise Refused("invalid journal origin cursor")
            records = _listing_records(record_dir, origin["start"])
            while records:
                day = records[0][2]
                if current <= _day_end_utc(day) + RETENTION:
                    break
                same_day = [r for r in records if r[2] == day]
                if records[len(same_day):] and any(r[2] == day for r in records[len(same_day):]):
                    raise Refused("interleaved retained UTC day")
                payload = b"".join(r[3] for r in same_day)
                archive = archive_dir / (day + ".txt")
                receipt_path = archive_dir / (day + ".receipt.json")
                _safe_file(archive)
                _safe_file(receipt_path)
                receipt = read_receipt(receipt_path)
                if receipt != {"size": len(payload), "sha256": digest(payload)}:
                    raise Refused("archive receipt differs from verified journal")
                if archive.read_bytes() != payload:
                    raise Refused("archive differs from original verified journal")
                eligible.append({"service_stream": label, "utc_day": day,
                                 "journal_bytes": len(payload), "records": len(same_day)})
                records = records[len(same_day):]
        return eligible
    except BlockingIOError as exc:
        raise Refused("collector or retention worker already holds lock") from exc
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="F15 read-only preview of 30-day OWNED archive expiry; DEVELOPMENT ONLY")
    parser.add_argument("--root", required=True, help="existing 0700 collector root")
    parser.add_argument("--preview", action="store_true", help="explicit read-only preview; never deletes")
    args = parser.parse_args(argv)
    if not args.preview:
        parser.error("preview is OFF by default: supply --preview")
    try:
        rows = preview_once(args.root)
        # Only aggregate metadata. Never print original source paths or log contents.
        print(json.dumps({"eligible_stream_days": len(rows), "candidates": rows}, sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, TypeError) as exc:
        print("F15 RETENTION PREVIEW REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
