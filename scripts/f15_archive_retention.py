#!/usr/bin/env python3
"""F15 experimental 30-day archive + journal retention.

DISABLED unless explicit --retention-30d in the operator CLI.
A durable intent is written before any unlink. Interrupted cleanup stops all
capture/retention for manual review; NEVER labels unexplained loss expired.
Not production-safe against a hostile same-UID writer or arbitrary power loss.
"""
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat

from f15_operator_collector import (LABELS, RECORD, Refused, atomic_write,
                                    digest, private_dir, read_receipt)

DAY = re.compile(r"^\d{8}$")
RETENTION = timedelta(days=30)

def _safe_file(path):
    try:
        st = path.lstat()
    except FileNotFoundError as exc:
        raise Refused("missing owned retention file; manual review required") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise Refused("nonregular/hardlinked retention file refused")
    return st

def _check_same(path, old):
    now = _safe_file(path)
    if (now.st_dev, now.st_ino, now.st_size) != (old.st_dev, old.st_ino, old.st_size):
        raise Refused("retention file identity changed before unlink")

def _read_strict_json(path, keys):
    _safe_file(path)
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise Refused("invalid collector state JSON") from exc
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Refused("collector state shape differs from expected")
    return value

def _day_end_utc(day):
    try:
        parsed = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise Refused("invalid record observation UTC day") from exc
    return parsed + timedelta(days=1)

def _listing_records(folder, start):
    result = []
    offset = start
    last_day = ""
    for path in sorted(folder.iterdir()):
        if path.name == "origin.json":
            continue
        match = RECORD.fullmatch(path.name)
        if not match:
            raise Refused("unexpected journal entry; retention stopped")
        a, b, day, sha = match.groups()
        a, b = int(a), int(b)
        if a != offset or b <= a or b - a > 65536 or day < last_day:
            raise Refused("journal gap, overlap, day reversal or unbounded record")
        _day_end_utc(day)
        st = _safe_file(path)
        data = path.read_bytes()
        if len(data) != b - a or digest(data) != sha:
            raise Refused("journal record does not verify")
        result.append((path, st, day, data, b))
        offset, last_day = b, day
    return result

def retain_once(root, now=None):
    """Expire only validated COMPLETE oldest day prefixes; never touch sources.

    Returns count of completed day expirations. An interrupted intent is a hard
    stop, *including* after both files vanished: no guessed expired success.
    """
    root = private_dir(root)
    record_root = private_dir(root / "records")
    archive_root = private_dir(root / "archives")
    lock = root / "collector.lock"
    lockfd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        _safe_file(lock)
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        intent_path = root / "retention-intent.json"
        if intent_path.exists() or intent_path.is_symlink():
            raise Refused("unfinished retention intent; manual review, no automatic recovery")
        current = datetime.now(timezone.utc) if now is None else datetime.fromtimestamp(now, timezone.utc)
        count = 0
        for label_dir in sorted(record_root.iterdir()):
            if label_dir.name not in LABELS:
                raise Refused("unknown label in collector journal")
            label = label_dir.name
            record_dir = private_dir(label_dir)
            archive_dir = private_dir(archive_root / label)
            origin_path = record_dir / "origin.json"
            origin = _read_strict_json(origin_path, {"path", "dev", "ino", "start"})
            if not isinstance(origin["start"], int) or origin["start"] < 0:
                raise Refused("invalid collector cursor")
            records = _listing_records(record_dir, origin["start"])
            # Only the oldest complete UTC day may be compacted, never a day
            # with interleaved later/earlier records.
            while records:
                day = records[0][2]
                if current <= _day_end_utc(day) + RETENTION:
                    break
                same_day = [r for r in records if r[2] == day]
                if records[len(same_day):] and any(r[2] == day for r in records[len(same_day):]):
                    raise Refused("interleaved retained day")
                payload = b"".join(rec[3] for rec in same_day)
                archive = archive_dir / (day + ".txt")
                receipt_path = archive_dir / (day + ".receipt.json")
                archive_stat = _safe_file(archive)
                receipt_stat = _safe_file(receipt_path)
                receipt = read_receipt(receipt_path)
                if receipt != {"size": len(payload), "sha256": digest(payload)}:
                    raise Refused("archive receipt differs from original verified journal")
                if archive.read_bytes() != payload:
                    raise Refused("archive differs from its immutable verified journal")
                # Persist a durable deletion intent (only current collector root).
                end = same_day[-1][4]
                intent = {"kind": "retention_30d", "label": label, "day": day,
                          "old_start": origin["start"], "next_start": end,
                          "sha256": digest(payload),
                          "records": [r[0].name for r in same_day]}
                atomic_write(intent_path, json.dumps(intent, sort_keys=True).encode())
                # Any interruption from this point must be reviewed manually.
                _check_same(archive, archive_stat)
                _check_same(receipt_path, receipt_stat)
                for file, st, _, _, _ in same_day:
                    _check_same(file, st)
                archive.unlink()
                receipt_path.unlink()
                for file, _, _, _, _ in same_day:
                    file.unlink()
                # Advance replay cursor only AFTER all old raw bytes are gone.
                origin["start"] = end
                atomic_write(origin_path, json.dumps(origin, sort_keys=True).encode())
                # A durable receipt distinguishes completed removal from
                # an unrelated missing archive. It stores only hashes/offsets.
                history = private_dir(root / "retention-history")
                completed = history / (label + "-" + day + "-" + str(end) + ".json")
                if completed.exists():
                    raise Refused("duplicate retention completion record")
                atomic_write(completed, json.dumps(intent, sort_keys=True).encode())
                _check_same(intent_path, _safe_file(intent_path))
                intent_path.unlink()
                count += 1
                records = records[len(same_day):]
        return count
    except BlockingIOError as exc:
        raise Refused("collector active; retention refused") from exc
    finally:
        os.close(lockfd)
