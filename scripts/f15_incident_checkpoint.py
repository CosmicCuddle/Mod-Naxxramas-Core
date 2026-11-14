#!/usr/bin/env python3
"""F15 restart-safe incident checkpoint/orchestration.

Purely processes supplied snapshots/evidence and writes private checkpoint/report
state. It executes no process-manager commands and never signals/restarts a daemon.
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
import stat
import tempfile
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
    """Durably replace one private JSON file without a fixed crash-blocking temp name."""
    fd, pending_name = tempfile.mkstemp(
        prefix=f".{path.name}.pending.",
        dir=path.parent,
    )
    pending = Path(pending_name)
    replaced = False
    try:
        os.fchmod(fd, 0o600)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("pending checkpoint must be one private regular file")
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            data = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        replaced = True
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        if not replaced:
            try:
                pending.unlink()
            except FileNotFoundError:
                pass


@contextmanager
def _exclusive_lock(path: Path):
    """Serialize one service's read/normalize/render/commit transaction.

    The lock file is persistent, but a process crash releases the kernel lock.
    A stale lock inode therefore does not wedge later observations.
    """
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise Refused("cannot open checkpoint lock safely") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("checkpoint lock must be one private regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("checkpoint lock changed while locked")
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _read_json(path: Path) -> dict[str, Any] | None:
    if path.is_symlink():
        raise Refused("checkpoint may not be a symlink")
    if not path.exists():
        return None
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
    if pid is not None and (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0):
        raise Refused("invalid Auth pid")
    if start is not None and (not isinstance(start, int) or isinstance(start, bool) or start < 0):
        raise Refused("invalid Auth start ticks")
    if (pid is None) != (start is None):
        raise Refused("Auth pid/start identity must be both present or both absent")
    return {"kind": "auth", "pid": pid, "start_ticks": start, "tmux_alive": bool(tmux_alive)}


def _incident_id(service: str, sequence: int) -> str:
    return f"{service.lower()}-{sequence:08d}"


class IncidentCheckpoint:
    """One durable state file per service.

    Each service transaction is serialized by a private flock. The checkpoint
    advances only after a report callback succeeds. Therefore a renderer/disk
    failure cannot silently consume an incident, and a stale temp file from a
    killed writer cannot permanently block later commits.
    """

    def __init__(self, state_root: Path, service: str):
        if service not in {"Worldserver", "Authserver"}:
            raise Refused("unsupported service")
        self.root = _private_dir(Path(state_root))
        self.service = service
        self.path = self.root / f"{service}.checkpoint.json"
        self.lock_path = self.root / f"{service}.checkpoint.lock"

    def _state_unlocked(self) -> dict[str, Any] | None:
        return _read_json(self.path)

    def state(self) -> dict[str, Any] | None:
        with _exclusive_lock(self.lock_path):
            return self._state_unlocked()

    def _initialize_unlocked(self, identity: dict[str, Any]) -> dict[str, Any]:
        current = self._state_unlocked()
        if current is not None:
            return current
        state = {"version": 1, "service": self.service, "sequence": 0, "identity": identity}
        _atomic_json(self.path, state)
        return state

    def initialize(self, identity: dict[str, Any]) -> dict[str, Any]:
        with _exclusive_lock(self.lock_path):
            return self._initialize_unlocked(identity)

    def _commit_unlocked(self, identity: dict[str, Any], sequence: int) -> None:
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
        with _exclusive_lock(self.lock_path):
            state = self._initialize_unlocked(current_identity)
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
                self._commit_unlocked(current_identity, int(state["sequence"]))
                return None
            sequence = int(state["sequence"]) + 1
            incident = dict(incident)
            incident["incident_id"] = _incident_id(self.service, sequence)
            render(incident)
            self._commit_unlocked(current_identity, sequence)
            return incident

    def process_auth(self, current_snapshot: dict[str, Any], tmux_alive: bool,
                     normalize: Callable[[dict[str, Any], dict[str, Any], bool], dict[str, Any] | None],
                     render: Callable[[dict[str, Any]], Any]) -> dict[str, Any] | None:
        current_identity = _auth_identity(current_snapshot, tmux_alive)
        with _exclusive_lock(self.lock_path):
            state = self._initialize_unlocked(current_identity)
            previous = state["identity"]
            if previous == current_identity:
                return None
            incident = normalize(
                {"pid": previous.get("pid"), "start_ticks": previous.get("start_ticks")},
                {"pid": current_identity.get("pid"), "start_ticks": current_identity.get("start_ticks")},
                tmux_alive,
            )
            if incident is None:
                self._commit_unlocked(current_identity, int(state["sequence"]))
                return None
            sequence = int(state["sequence"]) + 1
            incident = dict(incident)
            incident["incident_id"] = _incident_id(self.service, sequence)
            render(incident)
            self._commit_unlocked(current_identity, sequence)
            return incident

