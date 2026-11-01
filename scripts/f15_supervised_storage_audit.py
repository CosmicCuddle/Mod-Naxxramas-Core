#!/usr/bin/env python3
"""Read-only F15 supervised World/Auth raw-log storage audit.

No deletion, rotation, PM2/tmux access, process signals, log-content reads,
or host scheduling. All private run and receipt paths MUST already exist.
A run older than 30 days is counted as a capacity risk, NOT deleted.
Development-only: operator must verify actual owner host before adoption.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import stat
import sys

from f15_operator_collector import Refused
from f15_supervised_retention import (RUN_ID, SERVICES, START_FIELDS, EXIT_FIELDS,
                                       _receipt)

RETENTION = timedelta(days=30)
STREAMS = ("stdout.raw", "stderr.raw")


def existing_private_dir(path):
    """Do not call private_dir() here: that helper can CREATE missing paths."""
    path = Path(path)
    try:
        identity = path.lstat()
    except FileNotFoundError as exc:
        raise Refused("storage audit requires an existing private directory") from exc
    if not stat.S_ISDIR(identity.st_mode) or identity.st_mode & 0o077:
        raise Refused("storage audit requires an existing private 0700 directory")
    return path.resolve()


def _raw_stat(path):
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise Refused("supervised raw stream is missing") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_mode & 0o077):
        raise Refused("raw stream must be private regular single-link file")
    return info


def _observed_exit(value, now):
    if type(value) is not str:
        raise Refused("exit timestamp must be a string")
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused("invalid exit timestamp") from exc
    if when.tzinfo is None:
        raise Refused("exit timestamp must include timezone")
    when = when.astimezone(timezone.utc)
    if when > now + timedelta(minutes=5):
        raise Refused("exit timestamp unexpectedly in the future")
    return when


def inspect_raw_storage(output_root, archive_root, now=None):
    """Purely read owner-selected existing F15 receipts/stat metadata.

    Older-than-30-days is calculated since the observed subprocess EXIT,
    not filesystem mtime. We count old raw bytes but never delete anything.
    """
    output_root = existing_private_dir(output_root)
    archive_root = existing_private_dir(archive_root)
    if (output_root == archive_root or output_root in archive_root.parents
            or archive_root in output_root.parents):
        raise Refused("source and archive paths must be separate and nonnested")

    sources = existing_private_dir(output_root / "runs")
    captures = existing_private_dir(archive_root / "runs")
    source_names = {p.name for p in sources.iterdir()}
    capture_names = {p.name for p in captures.iterdir()}
    if source_names != capture_names:
        raise Refused("supervised raw and capture run directories disagree")

    instant = (datetime.now(timezone.utc) if now is None
               else datetime.fromtimestamp(now, timezone.utc))
    result = {service: {
        "runs": 0, "completed_runs": 0, "unfinished_runs": 0,
        "raw_bytes": 0, "older_than_30_days_completed_runs": 0,
        "older_than_30_days_raw_bytes": 0,
        "observed_exit_kinds": {"clean_exit": 0, "nonzero_exit": 0, "signaled_exit": 0},
    } for service in sorted(SERVICES)}

    for name in sorted(source_names):
        if not RUN_ID.fullmatch(name):
            raise Refused("unknown supervisor run identifier")
        run = existing_private_dir(sources / name)
        capture = existing_private_dir(captures / name)
        start = _receipt(run / "start.json", START_FIELDS)
        service = start["service"]
        if type(service) is not str or service not in SERVICES or start["state"] != "planned":
            raise Refused("unrecognized supervisor start receipt")
        if (start["capture_root"] != str(capture)
                or start["stdout"] != str(run / STREAMS[0])
                or start["stderr"] != str(run / STREAMS[1])):
            raise Refused("supervisor receipt paths do not match existing run")

        exit_receipt = run / "exit.json"
        if exit_receipt.exists() or exit_receipt.is_symlink():
            ended = _receipt(exit_receipt, EXIT_FIELDS)
            if (ended["service"] != service or ended["state"] != "exit_observed"
                    or ended["capture_root"] != str(capture)
                    or ended["capture"] != "complete_for_observed_run"
                    or ended["capture_error_type"] is not None
                    or type(ended["pid"]) is not int or ended["pid"] <= 0
                    or type(ended["exit_code"]) is not int
                    or ended["exit_kind"] not in result[service]["observed_exit_kinds"]):
                raise Refused("unverified supervisor exit receipt")
            exit_time = _observed_exit(ended["time_utc"], instant)
            completed = True
        else:
            completed, exit_time = False, None

        byte_count = 0
        for raw_name, label in zip(STREAMS, ("out", "err")):
            raw = run / raw_name
            raw_id = _raw_stat(raw)
            byte_count += raw_id.st_size
            if completed:
                origin_path = capture / "records" / (service + "-" + label) / "origin.json"
                origin = _receipt(origin_path, {"path", "dev", "ino", "start"})
                if (origin["path"] != str(raw)
                        or type(origin["dev"]) is not int or origin["dev"] != raw_id.st_dev
                        or type(origin["ino"]) is not int or origin["ino"] != raw_id.st_ino
                        or type(origin["start"]) is not int or origin["start"] < 0):
                    raise Refused("supervised source inode differs from capture origin")

        bucket = result[service]
        bucket["runs"] += 1
        bucket["raw_bytes"] += byte_count
        if completed:
            bucket["completed_runs"] += 1
            bucket["observed_exit_kinds"][ended["exit_kind"]] += 1
            if instant > exit_time + RETENTION:
                bucket["older_than_30_days_completed_runs"] += 1
                bucket["older_than_30_days_raw_bytes"] += byte_count
        else:
            bucket["unfinished_runs"] += 1

    return {
        "mode": "READ_ONLY_METADATA_AUDIT",
        "deletions": 0,
        "services": result,
        "warning": ("Raw stdout/stderr remain on disk beyond 30 days. "
                    "Archive retention does not automatically reclaim them. "
                    "Observed subprocess exit kind is not an engine crash diagnosis."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only supervised raw-log storage audit, NO DELETION")
    parser.add_argument("--output-root", required=True, help="existing private F15 supervisor output root")
    parser.add_argument("--archive-root", required=True, help="existing private F15 archive root")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(inspect_raw_storage(args.output_root, args.archive_root),
                         sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, TypeError) as exc:
        print("F15 STORAGE AUDIT REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
