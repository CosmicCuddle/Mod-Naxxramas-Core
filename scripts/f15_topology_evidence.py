#!/usr/bin/env python3
"""F15 pure topology evidence normalizer.

Parses already-supplied PM2/tmux/process snapshots. It runs no commands and
touches no process. A later read-only collector may obtain the snapshots.
"""
import json
import re
import signal

FATAL_SIGNALS = {"SIGSEGV", "SIGABRT", "SIGBUS", "SIGFPE", "SIGILL"}
PM2_EXIT_RE = re.compile(
    r"App \[(?P<name>[^:\]]+):(?P<id>\d+)\] exited with code "
    r"\[(?P<code>-?\d+)\] via signal \[(?P<signal>[A-Z0-9]+)\]"
)

class Refused(RuntimeError):
    pass

def _parse_jlist(payload):
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError as exc:
        raise Refused("invalid PM2 JSON") from exc
    if not isinstance(data, list):
        raise Refused("PM2 snapshot must be a list")
    return data

def _one_pm2(snapshot, name):
    matches = [
        proc for proc in _parse_jlist(snapshot)
        if isinstance(proc, dict) and proc.get("name") == name
    ]
    if len(matches) != 1:
        raise Refused("expected exactly one named PM2 process")
    proc = matches[0]
    env = proc.get("pm2_env")
    if not isinstance(env, dict):
        raise Refused("PM2 process missing pm2_env")

    def integer(key):
        value = env.get(key)
        if value is None:
            return None
        if isinstance(value, bool):
            raise Refused("invalid PM2 integer field")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise Refused("invalid PM2 integer field") from exc

    pid = proc.get("pid")
    try:
        pid = int(pid) if pid is not None else None
    except (TypeError, ValueError) as exc:
        raise Refused("invalid PM2 pid") from exc

    return {
        "name": name,
        "pid": pid,
        "pm_id": proc.get("pm_id"),
        "status": env.get("status"),
        "restart_time": integer("restart_time"),
        "unstable_restarts": integer("unstable_restarts"),
        "pm_uptime": integer("pm_uptime"),
        "created_at": integer("created_at"),
        "exit_code": integer("exit_code"),
    }

def _signal_number(name):
    if not name:
        return None
    try:
        return int(signal.Signals[name])
    except (KeyError, ValueError, TypeError):
        return None

def _last_pm2_exit(manager_text, name):
    found = None
    for line in str(manager_text or "").splitlines():
        match = PM2_EXIT_RE.search(line)
        if match and match.group("name") == name:
            found = {
                "exit_code": int(match.group("code")),
                "signal_name": match.group("signal"),
                "manager_line": line[-1024:],
            }
    return found

def world_incident(previous_snapshot, current_snapshot, process_name, manager_text=""):
    previous = _one_pm2(previous_snapshot, process_name)
    current = _one_pm2(current_snapshot, process_name)
    before = previous["restart_time"]
    after = current["restart_time"]
    if before is None or after is None:
        raise Refused("PM2 restart_time is required")
    if after < before:
        raise Refused("PM2 restart counter moved backwards")
    if after == before:
        return None

    event = _last_pm2_exit(manager_text, process_name)
    exit_code = event["exit_code"] if event else current["exit_code"]
    signal_name = event["signal_name"] if event else None

    if signal_name in FATAL_SIGNALS:
        classification = "FATAL_SIGNAL_EXIT"
    elif exit_code not in (None, 0):
        classification = "NONZERO_EXIT"
    elif signal_name:
        classification = "SIGNAL_EXIT_CAUSE_UNPROVEN"
    else:
        classification = "PM2_RESTART_OBSERVED"

    evidence = [
        f"PM2 restart_time advanced {before}->{after}",
        f"status={current['status'] if current['status'] is not None else 'UNKNOWN'}",
    ]
    if event:
        evidence.append("PM2 manager exit line matched process name")
    else:
        evidence.append("no matching PM2 manager exit line supplied")

    return {
        "service": "Worldserver",
        "supervisor": "PM2",
        "pid": previous["pid"],
        "replacement_pid": current["pid"],
        "exit_code": exit_code,
        "signal_name": signal_name,
        "signal": _signal_number(signal_name),
        "classification": classification,
        "classification_evidence": "; ".join(evidence),
        "restart_evidence": (
            f"restart_time={after}; "
            f"unstable_restarts={current['unstable_restarts']}"
        ),
        "process_start_epoch_ms": previous["pm_uptime"],
        "replacement_start_epoch_ms": current["pm_uptime"],
    }

def auth_incident(previous, current, tmux_alive):
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise Refused("Auth snapshots must be mappings")

    prev_pid = previous.get("pid")
    prev_start = previous.get("start_ticks")
    cur_pid = current.get("pid")
    cur_start = current.get("start_ticks")

    if (
        not isinstance(prev_pid, int)
        or prev_pid <= 0
        or not isinstance(prev_start, int)
        or prev_start < 0
    ):
        raise Refused("invalid previous Auth identity")

    if cur_pid is not None:
        if (
            not isinstance(cur_pid, int)
            or cur_pid <= 0
            or not isinstance(cur_start, int)
            or cur_start < 0
        ):
            raise Refused("invalid current Auth identity")
        if cur_pid == prev_pid and cur_start == prev_start:
            return None
        evidence = (
            f"Auth identity changed "
            f"({prev_pid}/{prev_start} -> {cur_pid}/{cur_start})"
        )
        replacement = cur_pid
    else:
        evidence = (
            f"previous Auth identity {prev_pid}/{prev_start} "
            f"no longer present"
        )
        replacement = None

    evidence += "; tmux session " + (
        "still present" if tmux_alive else "not present"
    )

    return {
        "service": "Authserver",
        "supervisor": "tmux/bash (observed externally)",
        "pid": prev_pid,
        "replacement_pid": replacement,
        "exit_code": None,
        "signal_name": None,
        "classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN",
        "classification_evidence": evidence,
        "restart_evidence": (
            "replacement process observed"
            if replacement else "no replacement process observed"
        ),
        "process_start_ticks": prev_start,
    }
