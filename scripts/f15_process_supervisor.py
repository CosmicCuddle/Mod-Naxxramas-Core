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
import signal
import stat
import subprocess
import sys
import time

from f15_operator_collector import Refused, atomic_write, collect_once, private_dir

SERVICES = {"Worldserver", "Authserver"}
# Bound post-exit reconciliation; leave raw originals and fail closed if the
# final output exceeds this limit. The collector copies at most 64 KiB/stream
# each pass; no "complete" receipt is written while unread bytes remain.
MAX_FINAL_DRAIN_POLLS = 1024

class ExitReceiptFailure(OSError):
    """Observed wait evidence survived in memory, but its receipt was not durable."""
    def __init__(self, run, outcome):
        super().__init__("observed child exit receipt could not be persisted")
        self.run = run
        self.outcome = dict(outcome, exit_receipt_status="failed")


def utc_now():
    return datetime.now(timezone.utc).isoformat()

def _new_log(path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "wb", buffering=0)

class OwnedChildStops:
    """Optional main-thread stop forwarding, limited to the unreaped owned child."""
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.deadline = None
        self.escalated = False
        self.pending = []
        self.previous = {}

    def __enter__(self):
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                self.previous[sig] = signal.signal(sig, self.request)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def request(self, sig, frame):
        if sig not in self.pending:
            self.pending.append(sig)

    def forward(self, child):
        pending, self.pending = self.pending, []
        if pending and self.deadline is None and self.timeout is not None:
            self.deadline = time.monotonic() + self.timeout
        for sig in pending:
            if child.poll() is None:
                child.send_signal(sig)
        if self.deadline is not None and time.monotonic() >= self.deadline and not self.escalated:
            if child.poll() is None:
                child.kill()
                self.escalated = True

    def __exit__(self, *args):
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)


def supervise(output_root, archive_root, service, command, poll_seconds=0.2, *, forward_stops=False, stop_timeout=None):
    if stop_timeout is not None and (not forward_stops or not isinstance(stop_timeout, (int, float)) or not 0.1 <= stop_timeout <= 300):
        raise Refused("stop timeout requires forwarding and a finite 0.1..300 seconds")
    if forward_stops:
        with OwnedChildStops(stop_timeout) as stops:
            return _supervise(output_root, archive_root, service, command, poll_seconds, stops)
    return _supervise(output_root, archive_root, service, command, poll_seconds)


def _supervise(output_root, archive_root, service, command, poll_seconds=0.2, stops=None):
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
    # Every child run uses new raw file inodes. A shared capture origin
    # would reject the second run as source replacement and lose its logs.
    capture_root = private_dir(private_dir(archive_root / "runs") / run.name)
    stdout_path, stderr_path = run / "stdout.raw", run / "stderr.raw"
    intent = {"service": service, "time_utc": utc_now(), "state": "planned",
              "stdout": str(stdout_path), "stderr": str(stderr_path),
              "capture_root": str(capture_root)}
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
        running_receipt_failed = False
        try:
            atomic_write(run / "running.json", json.dumps(
                {"service": service, "time_utc": utc_now(), "state": "started",
                 "pid": child.pid}, sort_keys=True).encode())
        except (OSError, ValueError, Refused):
            # Popen succeeded: a diagnostic sink failure must not abandon the
            # directly owned child or replace its eventual observed status.
            # Keep collecting; retain any ambiguous .pending receipt untouched.
            running_receipt_failed = True
        capture_error = None
        try:
            while True:
                if stops is not None:
                    stops.forward(child)
                if capture_error is None:
                    try:
                        collect_once(capture_root, sources, include_existing=True)
                    except (Refused, OSError, ValueError) as exc:
                        # Do not kill/restart the child on an archive failure.
                        capture_error = type(exc).__name__
                result = child.poll()
                if result is not None:
                    break
                time.sleep(poll_seconds)
            if capture_error is None:
                try:
                    # The collector copies at most one 64-KiB chunk per stream
                    # on every call. A single final poll can leave most of a
                    # short-lived server's last console burst uncaptured.
                    for _ in range(MAX_FINAL_DRAIN_POLLS):
                        unread = collect_once(capture_root, sources, include_existing=True)
                        if set(unread) != set(sources):
                            raise Refused("collector did not report both console streams")
                        if not any(unread.values()):
                            break
                    else:
                        # Save exit evidence without ever misreporting capture
                        # as complete; all original .raw bytes stay untouched.
                        capture_error = "UncapturedConsoleBytes"
                except (Refused, OSError, ValueError) as exc:
                    capture_error = type(exc).__name__
        except KeyboardInterrupt:
            atomic_write(run / "supervisor-interrupted.json", json.dumps(
                {"service": service, "time_utc": utc_now(),
                 "state": "supervisor_interrupted", "last_known_pid": child.pid}, sort_keys=True).encode())
            # No claim that child exited; no unapproved kill signal.
            raise Refused("supervisor interrupted; child exit unobserved; review private run files")
    if running_receipt_failed and capture_error is None:
        # Existing fail-closed schema also prevents automatic retention from
        # treating incomplete lifecycle evidence as a fully verified run.
        capture_error = "RunningReceiptPersistenceFailure"
    classification = "clean_exit" if result == 0 else ("signaled_exit" if result < 0 else "nonzero_exit")
    outcome = {"service": service, "time_utc": utc_now(), "state": "exit_observed",
               "exit_code": result, "exit_kind": classification,
               "capture": "complete_for_observed_run" if capture_error is None else "fail_closed",
               "capture_error_type": capture_error, "pid": child.pid,
               "capture_root": str(capture_root)}
    if stops is not None:
        outcome["stop_escalated"] = stops.escalated
    try:
        atomic_write(run / "exit.json", json.dumps(outcome, sort_keys=True).encode())
    except (OSError, ValueError, Refused) as exc:
        raise ExitReceiptFailure(run, outcome) from exc
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
    except (Refused, OSError, ValueError):
        # Public CLI stderr must never interpolate an exception: Refused
        # and OSError may contain private output/archive paths. Keep the
        # existing private run/launch evidence intact and preserve exit 2.
        print("F15 supervisor REFUSED: operation rejected; details withheld", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
