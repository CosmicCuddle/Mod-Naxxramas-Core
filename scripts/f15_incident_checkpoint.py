#!/usr/bin/env python3
"""F15 restart-safe incident checkpoint/orchestration.

Purely processes supplied snapshots/evidence and writes private checkpoint/report
state. It executes no process-manager commands and never signals/restarts a daemon.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any, Callable


class Refused(RuntimeError):
    pass


def _private_dir(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise Refused("state directory may not be a symlink")
    if not path.exists():
        path.mkdir(mode=0o700, parents=False)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Refused("state directory must be mode 0700")
    return path


def _atomic_json(path: Path, obj: dict[str, Any]) -> None:
    pending = path.with_name(path.name + ".pending")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(pending, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            data = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(pending, path)
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException:
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise Refused("checkpoint may not be a symlink")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
        raise Refused("checkpoint must be one private regular file")
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refused("invalid checkpoint JSON") from exc
    if not isinstance(value, dict):
        raise Refused("checkpoint must be a mapping")
    return value


def _world_identity(snapshot: Any, process_name: str, parser: Callable[[Any, str], dict[str, Any]]) -> dict[str, Any]:
    proc = parser(snapshot, process_name)
    return {
        "kind": "pm2",
        "name": process_name,
        "pid": proc.get("pid"),
        "restart_time": proc.get("restart_time"),
        "pm_uptime": proc.get("pm_uptime"),
        "status": proc.get("status"),
    }


def _auth_identity(snapshot: dict[str, Any], tmux_alive: bool) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise Refused("Auth snapshot must be a mapping")
    pid = snapshot.get("pid")
    start = snapshot.get("start_ticks")
    pane_pid = snapshot.get("pane_pid")
    if pid is not None and (not isinstance(pid, int) or pid <= 0):
        raise Refused("invalid Auth pid")
    if start is not None and (not isinstance(start, int) or start < 0):
        raise Refused("invalid Auth start ticks")
    if (pid is None) != (start is None):
        raise Refused("Auth pid/start identity must be both present or both absent")
    if not isinstance(pane_pid, int) or pane_pid <= 0:
        raise Refused("invalid Auth tmux pane pid")
    return {
        "kind": "auth", "pid": pid, "start_ticks": start,
        "pane_pid": pane_pid, "tmux_alive": bool(tmux_alive),
    }


def _incident_id(service: str, sequence: int) -> str:
    return f"{service.lower()}-{sequence:08d}"


class IncidentCheckpoint:
    """One durable state file per service.

    The checkpoint advances only after a report callback succeeds. Therefore a
    renderer/disk failure cannot silently consume an incident.
    """

    def __init__(self, state_root: Path, service: str):
        if service not in {"Worldserver", "Authserver"}:
            raise Refused("unsupported service")
        self.root = _private_dir(Path(state_root))
        self.service = service
        self.path = self.root / f"{service}.checkpoint.json"

    def state(self) -> dict[str, Any] | None:
        return _read_json(self.path)

    def initialize(self, identity: dict[str, Any]) -> dict[str, Any]:
        current = self.state()
        if current is not None:
            return current
        state = {"version": 1, "service": self.service, "sequence": 0, "identity": identity}
        _atomic_json(self.path, state)
        return state

    def _commit(self, identity: dict[str, Any], sequence: int) -> None:
        _atomic_json(self.path, {
            "version": 1,
            "service": self.service,
            "sequence": sequence,
            "identity": identity,
        })

    def process_world(self, current_snapshot: Any, process_name: str, manager_text: str,
                      parse_pm2: Callable[[Any, str], dict[str, Any]],
                      normalize: Callable[[Any, Any, str, str], dict[str, Any] | None],
                      render: Callable[[dict[str, Any]], Any]) -> dict[str, Any] | None:
        current_identity = _world_identity(current_snapshot, process_name, parse_pm2)
        state = self.initialize(current_identity)
        previous = state["identity"]
        if previous == current_identity:
            return None

        def as_snapshot(identity: dict[str, Any]) -> list[dict[str, Any]]:
            return [{
                "name": identity["name"],
                "pid": identity.get("pid"),
                "pm_id": 0,
                "pm2_env": {
                    "status": identity.get("status"),
                    "restart_time": identity.get("restart_time"),
                    "unstable_restarts": 0,
                    "pm_uptime": identity.get("pm_uptime"),
                    "created_at": None,
                    "exit_code": None,
                },
            }]

        incident = normalize(as_snapshot(previous), current_snapshot, process_name, manager_text)
        if incident is None:
            self._commit(current_identity, int(state["sequence"]))
            return None
        sequence = int(state["sequence"]) + 1
        incident = dict(incident)
        incident["incident_id"] = _incident_id(self.service, sequence)
        render(incident)
        self._commit(current_identity, sequence)
        return incident

    def process_auth(self, current_snapshot: dict[str, Any], tmux_alive: bool,
                     normalize: Callable[[dict[str, Any], dict[str, Any], bool], dict[str, Any] | None],
                     render: Callable[[dict[str, Any]], Any]) -> dict[str, Any] | None:
        current_identity = _auth_identity(current_snapshot, tmux_alive)
        state = self.initialize(current_identity)
        previous = state["identity"]
        if previous == current_identity:
            return None
        incident = normalize(
            {
                "pid": previous.get("pid"),
                "start_ticks": previous.get("start_ticks"),
                "pane_pid": previous.get("pane_pid"),
            },
            {
                "pid": current_identity.get("pid"),
                "start_ticks": current_identity.get("start_ticks"),
                "pane_pid": current_identity.get("pane_pid"),
            },
            tmux_alive,
        )
        if incident is None:
            self._commit(current_identity, int(state["sequence"]))
            return None
        sequence = int(state["sequence"]) + 1
        incident = dict(incident)
        incident["incident_id"] = _incident_id(self.service, sequence)
        render(incident)
        self._commit(current_identity, sequence)
        return incident
