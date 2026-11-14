#!/usr/bin/env python3
"""F15 strict read-only host evidence probe.

The probe may execute only internally constructed read-only commands. It has no
start/stop/restart/kill/signal/attach operations. Tests inject a fake runner.
"""
from __future__ import annotations

import json
from pathlib import Path
import os
import shlex
import stat
import subprocess
from typing import Callable


class Refused(RuntimeError):
    pass


MAX_COMMAND_BYTES = 2 * 1024 * 1024
MAX_LOG_TAIL_BYTES = 32 * 1024


def _default_runner(argv: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=5, check=False,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    out, err = completed.stdout, completed.stderr
    if len(out.encode("utf-8", "replace")) > MAX_COMMAND_BYTES or len(err.encode("utf-8", "replace")) > MAX_COMMAND_BYTES:
        raise Refused("read-only command output exceeded bound")
    return completed.returncode, out, err


def _require_ok(result: tuple[int, str, str], label: str) -> str:
    rc, out, _err = result
    if rc != 0:
        raise Refused(f"{label} failed")
    return out


def probe_pm2(process_name: str, runner: Callable[[list[str]], tuple[int, str, str]] = _default_runner) -> tuple[str, dict]:
    if not process_name or len(process_name) > 128 or any(c.isspace() for c in process_name):
        raise Refused("invalid PM2 process name")
    raw = _require_ok(runner(["pm2", "jlist"]), "pm2 jlist")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Refused("invalid PM2 JSON") from exc
    matches = [x for x in data if isinstance(x, dict) and x.get("name") == process_name]
    if len(matches) != 1:
        raise Refused("expected exactly one PM2 process")
    proc = matches[0]
    env = proc.get("pm2_env")
    if not isinstance(env, dict):
        raise Refused("PM2 process missing pm2_env")
    summary = {
        "name": process_name,
        "pid": proc.get("pid"),
        "pm_id": proc.get("pm_id"),
        "status": env.get("status"),
        "restart_time": env.get("restart_time"),
        "unstable_restarts": env.get("unstable_restarts"),
        "pm_uptime": env.get("pm_uptime"),
        "created_at": env.get("created_at"),
        "exit_code": env.get("exit_code"),
        "out_log": env.get("pm_out_log_path"),
        "err_log": env.get("pm_err_log_path"),
    }
    return raw, summary


def _parse_ps(text: str) -> dict[int, dict]:
    rows = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 3:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        comm = parts[2]
        args = parts[3] if len(parts) == 4 else comm
        rows[pid] = {"pid": pid, "ppid": ppid, "comm": comm, "args": args}
    return rows


def _descendants(rows: dict[int, dict], root: int) -> set[int]:
    result = set()
    frontier = [root]
    while frontier:
        parent = frontier.pop()
        for pid, row in rows.items():
            if row["ppid"] == parent and pid not in result:
                result.add(pid)
                frontier.append(pid)
    return result


def _start_ticks_from_stat(stat_text: str) -> int:
    close = stat_text.rfind(")")
    if close < 0:
        raise Refused("invalid proc stat")
    tail = stat_text[close + 2:].split()
    if len(tail) <= 19:
        raise Refused("short proc stat")
    try:
        value = int(tail[19])
    except ValueError as exc:
        raise Refused("invalid proc start ticks") from exc
    if value < 0:
        raise Refused("invalid proc start ticks")
    return value


def probe_auth_tmux(session_name: str, runner: Callable[[list[str]], tuple[int, str, str]] = _default_runner,
                    read_text: Callable[[Path], str] | None = None) -> tuple[dict, bool]:
    if not session_name or len(session_name) > 128 or any(c in session_name for c in "\n\r\0"):
        raise Refused("invalid tmux session name")
    read_text = read_text or (lambda p: p.read_text("utf-8"))
    pane_result = runner(["tmux", "display-message", "-p", "-t", session_name, "#{pane_pid}"])
    if pane_result[0] != 0:
        err = str(pane_result[2] or "").lower()
        if "can't find session" in err or "no server running" in err:
            return {
                "pid": None, "start_ticks": None, "pane_pid": None,
                "tmux_probe_status": "session_absent",
            }, False
        raise Refused("tmux pane query failed")
    pane_out = pane_result[1].strip()
    try:
        pane_pid = int(pane_out)
    except ValueError as exc:
        raise Refused("invalid tmux pane pid") from exc
    if pane_pid <= 0:
        raise Refused("invalid tmux pane pid")
    ps = _require_ok(runner(["ps", "-eo", "pid=,ppid=,comm=,args="]), "ps process table")
    rows = _parse_ps(ps)
    if pane_pid not in rows:
        raise Refused("tmux pane pid absent from process table")
    candidates = []
    for pid in _descendants(rows, pane_pid):
        row = rows[pid]
        if row["comm"] == "authserver" or Path(shlex.split(row["args"])[0]).name == "authserver":
            candidates.append(pid)
    if len(candidates) > 1:
        raise Refused("expected at most one authserver descendant")
    if not candidates:
        return {
            "pid": None, "start_ticks": None, "pane_pid": pane_pid,
            "tmux_probe_status": "session_present_auth_absent",
        }, True
    pid = candidates[0]
    start_ticks = _start_ticks_from_stat(read_text(Path(f"/proc/{pid}/stat")))
    return {
        "pid": pid, "start_ticks": start_ticks, "pane_pid": pane_pid,
        "tmux_probe_status": "session_present_auth_present",
    }, True


def tail_private_source(path: str | Path, limit: int = MAX_LOG_TAIL_BYTES) -> str:
    if not (1 <= limit <= MAX_LOG_TAIL_BYTES):
        raise Refused("tail limit out of range")
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Refused("log source must be regular file")
        start = max(0, st.st_size - limit)
        data = os.pread(fd, st.st_size - start, start)
        return data.decode("utf-8", "replace")
    finally:
        os.close(fd)
