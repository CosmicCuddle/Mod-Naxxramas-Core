#!/usr/bin/env python3
"""Emit private opt-in manager plans; never execute a manager or payload."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys


def wrapper_argv(root, service, command):
    root = Path(root)
    if not root.is_absolute() or service not in ("Worldserver", "Authserver"):
        raise ValueError("absolute root and known service required")
    if not command or any(not isinstance(x, str) or not x or "\0" in x for x in command):
        raise ValueError("explicit argument vector required")
    return [sys.executable, str(Path(__file__).with_name("f15_supervised_incident.py")),
            "supervise", "--execute", "--launcher-mode", "--service", service,
            "--output-root", str(root / (service + "-source")),
            "--archive-root", str(root / (service + "-archive")),
            "--crash-root", str(root / "Crash Logs"),
            "--raw-root", str(root / "Crash Logs" / "Raw Evidence"), "--", *command]


def pm2_plan(root, command):
    argv = wrapper_argv(root, "Worldserver", command)
    return {"apps": [{"name": "f15-proposed-worldserver", "script": argv[0],
             "args": argv[1:], "interpreter": "none", "exec_mode": "fork",
             "instances": 1, "autorestart": False, "stop_exit_codes": [0],
             "treekill": False, "kill_timeout": 60000,
             "out_file": str(Path(root) / "pm2-out.log"),
             "error_file": str(Path(root) / "pm2-error.log")}]}


def tmux_plan(root, command, socket):
    if not socket or not all(c.isalnum() or c in "-_" for c in socket):
        raise ValueError("dedicated socket name required")
    return {"argv": ["tmux", "-L", socket, "-f", "/dev/null", "new-session", "-d",
                     "-s", "f15-proposed-authserver", *wrapper_argv(root, "Authserver", command)]}


def write_plan(root, plan, name):
    root = Path(root)
    if not root.is_absolute():
        raise ValueError("absolute private root required")
    for part in (root, *root.parents):
        if part.is_symlink():
            raise ValueError("symlink paths refused")
    mode = root.stat().st_mode
    if not stat.S_ISDIR(mode) or mode & 0o077:
        raise ValueError("existing private root required")
    # No overwrite or automatic activation; command may contain private args.
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--manager", choices=("pm2", "tmux"), required=True)
    p.add_argument("--socket")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args(argv)
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    try:
        plan = pm2_plan(a.root, command) if a.manager == "pm2" else tmux_plan(a.root, command, a.socket)
        write_plan(a.root, plan, a.manager + "-proposed.json")
    except (OSError, ValueError):
        print("F15 plan refused; private details withheld", file=sys.stderr)
        return 2
    print("F15 private proposed plan written; nothing activated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
