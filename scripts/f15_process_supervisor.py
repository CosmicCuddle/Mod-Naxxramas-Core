#!/usr/bin/env python3
"""F15 experimental POSIX process supervision + console capture.

Never attach to or restart an existing service. NO host deployment approval.
A child program is started only with explicit --execute and command after --.
The child exit code/signal is recorded; neither stderr nor nonzero proves a crash.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time

from f15_operator_collector import Refused, atomic_write, collect_once, private_dir

SERVICES = {"Worldserver", "Authserver"}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def _new_log(path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "wb", buffering=0)

def supervise(output_root, archive_root, service, command, poll_seconds=0.2):
    if service not in SERVICES:
        raise Refused("service must be Worldserver or Authserver")
    if not command:
        raise Refused("explicit executable command required")
    if not (0.02 <= poll_seconds <= 60):
        raise Refused("poll interval out of range")
    output_root = private_dir(output_root).resolve()
    archive_root = private_dir(archive_root).resolve()
    if output_root == archive_root or archive_root in output_root.parents or output_root in archive_root.parents:
        raise Refused("output and archive roots must be separate, non-nested directories")
    runs_root = private_dir(output_root / "runs")
    run = private_dir(runs_root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(8)))
    stdout_path, stderr_path = run / "stdout.raw", run / "stderr.raw"
    intent = {"service": service, "time_utc": utc_now(), "state": "planned",
              "stdout": str(stdout_path), "stderr": str(stderr_path)}
    atomic_write(run / "start.json", json.dumps(intent, sort_keys=True).encode())
    sources = {service + "-out": str(stdout_path), service + "-err": str(stderr_path)}
    with _new_log(stdout_path) as stdout, _new_log(stderr_path) as stderr:
        # Inherit no interactive server console. No shell interpolation, no user host service management.
        try:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout,
                                     stderr=stderr, close_fds=True, start_new_session=True)
        except (OSError, ValueError) as exc:
            atomic_write(run / "launch-failed.json", json.dumps(
                {"service": service, "time_utc": utc_now(), "state": "launch_failed",
                 "error_type": type(exc).__name__}, sort_keys=True).encode())
            raise Refused("explicit child launch failed (details retained privately)") from exc
        atomic_write(run / "running.json", json.dumps(
            {"service": service, "time_utc": utc_now(), "state": "started",
             "pid": child.pid}, sort_keys=True).encode())
        capture_error = None
        try:
            while True:
                if capture_error is None:
                    try:
                        collect_once(archive_root, sources, include_existing=True)
                    except (Refused, OSError, ValueError) as exc:
                        # Do not kill/restart the child on an archive failure.
                        capture_error = type(exc).__name__
                result = child.poll()
                if result is not None:
                    break
                time.sleep(poll_seconds)
            if capture_error is None:
                try:
                    collect_once(archive_root, sources, include_existing=True)
                except (Refused, OSError, ValueError) as exc:
                    capture_error = type(exc).__name__
        except KeyboardInterrupt:
            atomic_write(run / "supervisor-interrupted.json", json.dumps(
                {"service": service, "time_utc": utc_now(),
                 "state": "supervisor_interrupted", "last_known_pid": child.pid}, sort_keys=True).encode())
            # No claim that child exited; no unapproved kill signal.
            raise Refused("supervisor interrupted; child exit unobserved; review private run files")
    classification = "clean_exit" if result == 0 else ("signaled_exit" if result < 0 else "nonzero_exit")
    outcome = {"service": service, "time_utc": utc_now(), "state": "exit_observed",
               "exit_code": result, "exit_kind": classification,
               "capture": "complete_for_observed_run" if capture_error is None else "fail_closed",
               "capture_error_type": capture_error, "pid": child.pid}
    atomic_write(run / "exit.json", json.dumps(outcome, sort_keys=True).encode())
    return run, outcome

def main(argv=None):
    parser = argparse.ArgumentParser(description="F15 opt-in supervised process output and exit-code evidence; not PM2 integration")
    parser.add_argument("--output-root", required=True, help="private source output directory")
    parser.add_argument("--archive-root", required=True, help="separate private journal/archive directory")
    parser.add_argument("--service", choices=sorted(SERVICES), required=True)
    parser.add_argument("--poll-seconds", type=float, default=0.2)
    parser.add_argument("--execute", action="store_true", help="operator must explicitly authorize child launch")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("supervisor OFF by default; --execute is required")
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        parser.error("pass a child command after --")
    try:
        run, outcome = supervise(args.output_root, args.archive_root, args.service,
                                 command, args.poll_seconds)
        print(json.dumps({"run": str(run), "outcome": outcome}, sort_keys=True))
        return 0 if outcome["exit_code"] == 0 and outcome["capture_error_type"] is None else 2
    except (Refused, OSError, ValueError) as exc:
        print(f"F15 supervisor REFUSED: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
