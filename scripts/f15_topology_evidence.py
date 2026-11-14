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
    if isinstance(pid, bool):
        raise Refused("invalid PM2 pid")
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

def _pm2_live(proc):
    pid = proc.get("pid")
    return (
        proc.get("status") == "online"
        and isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
    )


def world_incident(previous_snapshot, current_snapshot, process_name, manager_text=""):
    previous = _one_pm2(previous_snapshot, process_name)
    current = _one_pm2(current_snapshot, process_name)
    before = previous["restart_time"]
    after = current["restart_time"]
    if before is None or after is None:
        raise Refused("PM2 restart_time is required")
    if after < before:
        raise Refused("PM2 restart counter moved backwards")

    previous_live = _pm2_live(previous)
    current_live = _pm2_live(current)

    # Recovery/start after an already-observed stopped baseline is not itself a
    # crash incident. If more than one restart occurred while the service was
    # absent, retain that as an incident because intermediate failures cannot be
    # ruled out from endpoint-only PM2 evidence.
    if not previous_live and current_live and after <= before + 1:
        return None

    # PM2 can expose a stopped/errored identity without advancing restart_time.
    # Never silently consume a transition away from a live process merely
    # because the restart counter did not move.
    if after == before:
        if previous_live and current_live:
            if (
                previous["pid"] == current["pid"]
                and previous["pm_uptime"] == current["pm_uptime"]
                and previous["status"] == current["status"]
            ):
                return None
            classification = "PM2_PROCESS_IDENTITY_CHANGED_CAUSE_UNKNOWN"
            evidence = (
                f"PM2 live identity changed with restart_time unchanged at {after}; "
                f"pid={previous['pid']}->{current['pid']}; "
                f"status={previous['status']}->{current['status']}"
            )
        elif previous_live and not current_live:
            classification = "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN"
            evidence = (
                f"PM2 process ceased to be live with restart_time unchanged at {after}; "
                f"pid={previous['pid']}->{current['pid']}; "
                f"status={previous['status']}->{current['status']}"
            )
        else:
            # stopped/absent -> stopped/absent identity changes are not a new
            # crash; the checkpoint may advance to the latest observed state.
            return None

        return {
            "service": "Worldserver",
            "supervisor": "PM2",
            "pid": previous["pid"],
            "replacement_pid": current["pid"],
            "exit_code": current["exit_code"],
            "signal_name": None,
            "signal": None,
            "classification": classification,
            "classification_evidence": evidence,
            "restart_evidence": f"restart_time={after} (unchanged)",
            "process_start_epoch_ms": previous["pm_uptime"],
            "replacement_start_epoch_ms": current["pm_uptime"],
        }

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
    if not previous_live:
        evidence.append("previous checkpoint was not a live PM2 process")
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


def _auth_pair(snapshot, label):
    if not isinstance(snapshot, dict):
        raise Refused(f"{label} Auth snapshot must be a mapping")
    pid = snapshot.get("pid")
    start = snapshot.get("start_ticks")
    if (pid is None) != (start is None):
        raise Refused(f"{label} Auth pid/start identity must be both present or both absent")
    if pid is None:
        return None
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or not isinstance(start, int)
        or isinstance(start, bool)
        or start < 0
    ):
        raise Refused(f"invalid {label} Auth identity")
    return pid, start


def auth_incident(previous, current, tmux_alive):
    previous_pair = _auth_pair(previous, "previous")
    current_pair = _auth_pair(current, "current")

    # An already-absent Authserver later appearing is a recovery/start
    # transition, not a second crash incident. This also makes a baseline taken
    # while Auth is absent recover cleanly when Auth starts.
    if previous_pair is None:
        return None

    if current_pair == previous_pair:
        return None

    prev_pid, prev_start = previous_pair
    if current_pair is not None:
        cur_pid, cur_start = current_pair
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

