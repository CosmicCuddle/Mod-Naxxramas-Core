#!/usr/bin/env python3
"""Opt-in 30-day retention for archives of separately supervised child runs.

Never touches raw stdout/stderr, installed World/Auth services, PM2 or config.
Requires --retention-30d; intended for a private operator-owned workspace.
Each run must have matching durable supervisor start/exit receipts.
This is development code, NOT approved for a real host/scheduler.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from f15_operator_collector import Refused, private_dir
from f15_archive_retention import retain_once

RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}-[0-9a-f]{16}$")
SERVICES = frozenset(("Worldserver", "Authserver"))
START_FIELDS = frozenset(("service", "time_utc", "state", "stdout", "stderr", "capture_root"))
EXIT_FIELDS = frozenset(("service", "time_utc", "state", "exit_code", "exit_kind",
                         "capture", "capture_error_type", "pid", "capture_root"))


def _receipt(path, required):
    """Read a supervisor-owned single-link receipt; reject foreign state."""
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise Refused("supervisor receipt is not a private regular file")
    try:
        data = json.loads(path.read_bytes())
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise Refused("unreadable supervisor receipt") from exc
    if not isinstance(data, dict) or set(data) != required:
        raise Refused("unexpected supervisor receipt schema")
    return data


def _validated_runs(output_root, archive_root):
    """Validate all candidates BEFORE ANY deletion, including unknown paths."""
    output_root = private_dir(output_root).resolve()
    archive_root = private_dir(archive_root).resolve()
    if (output_root == archive_root or output_root in archive_root.parents
            or archive_root in output_root.parents):
        raise Refused("source and collector roots must be separate and nonnested")
    source_runs = private_dir(output_root / "runs")
    capture_runs = private_dir(archive_root / "runs")

    sources = {p.name: p for p in source_runs.iterdir()}
    captures = {p.name: p for p in capture_runs.iterdir()}
    for name, run_path in sources.items():
        if not RUN_ID.fullmatch(name):
            raise Refused("foreign source run identifier; manual review")
        private_dir(run_path)
    for name, run_path in captures.items():
        if not RUN_ID.fullmatch(name) or name not in sources:
            raise Refused("unknown archive run; manual review")
        private_dir(run_path)

    completed = []
    skipped = 0
    for name, run_path in sorted(sources.items()):
        # A failed or still-running child must NEVER trigger archival expiry.
        exit_path = run_path / "exit.json"
        if not exit_path.exists() and not exit_path.is_symlink():
            skipped += 1
            continue
        start = _receipt(run_path / "start.json", START_FIELDS)
        exit_state = _receipt(exit_path, EXIT_FIELDS)
        capture = captures.get(name)
        if capture is None:
            raise Refused("completed child has no archived collector root")
        expected = str(capture.resolve())
        # JSON can carry arrays/maps where a string is expected. Reject them
        # explicitly instead of allowing unhashable values to raise TypeError.
        for value in (start["service"], exit_state["service"],
                      start["capture_root"], exit_state["capture_root"],
                      start["stdout"], start["stderr"]):
            if type(value) is not str:
                raise Refused("non-string supervisor receipt identity")
        if (start["service"] not in SERVICES
                or exit_state["service"] != start["service"]
                or start["state"] != "planned"
                or exit_state["state"] != "exit_observed"
                or start["capture_root"] != expected
                or exit_state["capture_root"] != expected
                or exit_state["capture"] != "complete_for_observed_run"
                or exit_state["capture_error_type"] is not None
                or type(exit_state["pid"]) is not int
                or exit_state["pid"] <= 0
                or type(exit_state["exit_code"]) is not int
                or exit_state["exit_kind"] not in
                    ("clean_exit", "nonzero_exit", "signaled_exit")
                or start["stdout"] != str(run_path / "stdout.raw")
                or start["stderr"] != str(run_path / "stderr.raw")):
            raise Refused("supervisor receipts disagree; manual review")
        expected_labels = {start["service"] + "-out": start["stdout"],
                           start["service"] + "-err": start["stderr"]}
        for label, source_path in expected_labels.items():
            origin = _receipt(capture / "records" / label / "origin.json",
                              {"path", "dev", "ino", "start"})
            if (origin["path"] != source_path or type(origin["start"]) is not int
                    or origin["start"] < 0
                    or type(origin["dev"]) is not int
                    or type(origin["ino"]) is not int):
                raise Refused("archive origin does not match supervised stream")
        completed.append(capture)
    return completed, skipped


def expire_completed_runs_once(output_root, archive_root, now=None):
    """Expire owned journal days only for validated, fully exited child runs.

    Source-side raw .raw logs and start/running/exit receipts are NEVER deleted.
    Foreign run identities and receipts are rejected before any deletion.
    Per-root archive integrity is checked by retain_once when processed;
    a later corrupt root can stop the sweep after earlier valid expirations.
    """
    completed, skipped = _validated_runs(output_root, archive_root)
    deleted_days = 0
    for capture in completed:
        deleted_days += retain_once(capture, now=now)
    return {"completed_runs": len(completed), "unfinished_runs": skipped,
            "expired_stream_days": deleted_days}


def main(argv=None):
    parser = argparse.ArgumentParser(description="F15 opt-in supervised child archive expiry; DEVELOPMENT ONLY")
    parser.add_argument("--output-root", required=True, help="supervisor's private raw output directory")
    parser.add_argument("--archive-root", required=True, help="supervisor's separate private archive directory")
    parser.add_argument("--retention-30d", action="store_true", help="explicitly permit deletion of verified expired owned archives/journal only")
    parser.add_argument("--once", action="store_true", help="run one retention cycle and exit")
    parser.add_argument("--interval", type=float, default=3600.0, help="seconds between cycles, only when not --once")
    args = parser.parse_args(argv)
    if not args.retention_30d:
        parser.error("retention is OFF: explicit --retention-30d required")
    if not args.once and not 60 <= args.interval <= 86400:
        parser.error("retention --interval must be between 60 and 86400 seconds")
    try:
        while True:
            print(json.dumps(expire_completed_runs_once(args.output_root, args.archive_root),
                             sort_keys=True), flush=True)
            if args.once:
                return 0
            time.sleep(args.interval)
    except (Refused, OSError, ValueError) as exc:
        print("F15 SUPERVISED RETENTION REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
