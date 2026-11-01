#!/usr/bin/env python3
"""F15 opt-in, read-only PM2 console observer (development draft).

Observes one exact PM2 process name via `pm2 jlist`. Never starts, kills,
restarts or reconfigures the running server. Captures only configured regular
Worldserver/Authserver console files using the F15 collector. PID changes are
UNCLASSIFIED lifecycle evidence, not proof of a game-engine crash.

INODE ROTATION IS NOT YET AUTOMATIC: collector refuses changed source identity
rather than silently discarding unread output. No host deployment approved.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

from f15_operator_collector import Refused, atomic_write, collect_once, private_dir
from f15_archive_retention import retain_once

SERVICES = frozenset(("Worldserver", "Authserver"))
STATES = frozenset(("online", "stopped", "stopping", "errored", "launching", "one-launch-status"))
STATE_KEYS = frozenset(("service", "pm2_name", "pid", "status", "stdout", "stderr"))


def select_process(payload, name, service):
    """Return only explicitly permitted fields; never persist PM2 env dumps."""
    if service not in SERVICES or not name or not isinstance(payload, list):
        raise Refused("invalid service/name or PM2 JSON root")
    matches = [row for row in payload if isinstance(row, dict) and row.get("name") == name]
    if len(matches) != 1:
        raise Refused("PM2 name must match exactly one process")
    row = matches[0]
    env = row.get("pm2_env")
    if not isinstance(env, dict) or env.get("status") not in STATES:
        raise Refused("PM2 selected process has an unsupported status")
    raw_pid = row.get("pid")
    if type(raw_pid) is not int or raw_pid < 0:
        raise Refused("invalid PM2 process PID")
    if env["status"] == "online" and raw_pid == 0:
        raise Refused("online PM2 process has no PID")
    paths = [env.get("pm_out_log_path"), env.get("pm_err_log_path")]
    if any(not isinstance(p, str) or not Path(p).is_absolute() for p in paths):
        raise Refused("PM2 process requires absolute out/err log paths")
    if paths[0] == paths[1]:
        raise Refused("PM2 out and err paths must differ")
    return dict(service=service, pm2_name=name, pid=raw_pid,
                status=env["status"], stdout=paths[0], stderr=paths[1])


def query_pm2(name, service):
    """Only the read-only PM2 list command; stderr/env are never archived."""
    try:
        completed = subprocess.run(("pm2", "jlist"), stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, timeout=10,
                                   check=True)
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError,
            UnicodeError, ValueError, TypeError) as exc:
        raise Refused("PM2 read-only query/JSON failed (no PM2 output persisted)") from exc
    return select_process(payload, name, service)


def _previous_state(path):
    if not path.exists() and not path.is_symlink():
        return None
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise Refused("untrusted PM2 state file")
    try:
        state = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise Refused("invalid PM2 state JSON") from exc
    if not isinstance(state, dict) or set(state) != STATE_KEYS:
        raise Refused("unexpected PM2 state shape")
    return state


def observe_once(root, name, service, snapshot=None, retention=False,
                 include_existing=False, now=None):
    """One locked, recoverable read-only observation of an existing service."""
    root = private_dir(root)
    lock_path = root / "pm2-observer.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT |
                      getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        lock_st = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_st.st_mode) or lock_st.st_nlink != 1:
            raise Refused("PM2 observer lock is not a private regular file")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        selected = query_pm2(name, service) if snapshot is None else select_process(
            snapshot, name, service)
        state_path = root / "pm2-observation.json"
        before = _previous_state(state_path)
        if before is not None and (before["pm2_name"], before["service"]) != (name, service):
            raise Refused("observer root belongs to another selected PM2 service")
        sources = {service + "-out": selected["stdout"],
                   service + "-err": selected["stderr"]}
        # The native collector rejects symlink/hardlink/duplicate inode,
        # foreign source, truncation and archive tampering. No PM2 operations.
        collect_once(root / "capture", sources, now=now,
                     include_existing=include_existing)
        if retention:
            retain_once(root / "capture", now=now)
        changed = before is None or (
            before["pid"], before["status"], before["stdout"], before["stderr"]) != (
            selected["pid"], selected["status"], selected["stdout"], selected["stderr"])
        if changed:
            events = private_dir(root / "events")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            event = {"service": service, "pm2_name": name,
                     "kind": "initial_observation" if before is None else "unclassified_process_change",
                     "before_pid": None if before is None else before["pid"],
                     "after_pid": selected["pid"],
                     "before_status": None if before is None else before["status"],
                     "after_status": selected["status"],
                     "observed_utc": datetime.now(timezone.utc).isoformat(),
                     "crash_proven": False}
            # O_EXCL in atomic_write refuses collision rather than overwriting.
            atomic_write(events / (stamp + "-" + str(os.getpid()) + ".json"),
                         json.dumps(event, sort_keys=True).encode("utf-8"))
        atomic_write(state_path, json.dumps(selected, sort_keys=True).encode("utf-8"))
        return {"service": service, "pid": selected["pid"],
                "status": selected["status"], "changed": changed,
                "crash_proven": False}
    except BlockingIOError as exc:
        raise Refused("PM2 observer already active") from exc
    finally:
        os.close(lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="F15 opt-in read-only observer of an existing PM2 process; DEVELOPMENT ONLY")
    parser.add_argument("--root", required=True, help="dedicated private 0700 archive root")
    parser.add_argument("--pm2-name", required=True, help="one exact existing PM2 process name")
    parser.add_argument("--service", choices=sorted(SERVICES), required=True)
    parser.add_argument("--observe", action="store_true", help="explicitly permit PM2 read-only query + log capture")
    parser.add_argument("--include-existing-on-first-poll", action="store_true",
                        help="explicit historic console backfill; default starts at EOF")
    parser.add_argument("--retention-30d", action="store_true",
                        help="EXPERIMENTAL explicit collector-owned 30-day deletion, never original logs")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)
    if not args.observe:
        parser.error("PM2 observation is OFF by default: supply --observe")
    if not args.once and not 0.2 <= args.interval <= 3600:
        parser.error("--interval must be within 0.2..3600 seconds")
    try:
        while True:
            result = observe_once(args.root, args.pm2_name, args.service,
                                  retention=args.retention_30d,
                                  include_existing=args.include_existing_on_first_poll)
            print(json.dumps(result, sort_keys=True), flush=True)
            if args.once:
                return 0
            time.sleep(args.interval)
    except (Refused, OSError, ValueError) as exc:
        print("F15 PM2 OBSERVER REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
