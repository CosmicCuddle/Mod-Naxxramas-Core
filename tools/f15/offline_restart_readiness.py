"""F15 S4d OFFLINE restart-readiness evidence state machine.

Synthetic-only. No process spawn/wait, systemd, gdb, probe, timer, sockets,
disk I/O, or incident/restart sidecar writer. Claimed source and verified
flags are model inputs, NOT OS authentication. A real adapter must derive
child identity and a SERVICE-READINESS probe from independent trusted APIs.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import uuid

from offline_store import safe_name, utc

SUPERVISOR = "supervisor-fixture"
READY_PROBE = "readiness-probe-fixture"
REAL_WAIT = "child-wait-fixture"
MONOTONIC = "monotonic-timeout-fixture"
KINDS = frozenset(("ready", "exited", "timeout"))


@dataclass(frozen=True)
class ChildRef:
    service: str
    host: str
    boot: str
    invocation: str
    pid: int
    start_utc: str

    def checked(self):
        if self.service not in ("worldserver", "authserver"):
            raise ValueError("unsupported service")
        for x in (self.host, self.boot, self.invocation):
            safe_name(x)
        if type(self.pid) is not int or not 0 < self.pid < (1 << 31):
            raise ValueError("invalid actual child PID")
        utc(self.start_utc)
        return self


@dataclass(frozen=True)
class RestartStart:
    incident_id: str
    attempt: str
    previous: ChildRef
    replacement: ChildRef
    death_utc: str
    timeout_ms: int
    verified_supervisor: bool
    source: str

    def checked(self):
        try:
            parsed = uuid.UUID(self.incident_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("invalid incident ID") from exc
        if str(parsed) != self.incident_id:
            raise ValueError("noncanonical incident ID")
        safe_name(self.attempt)
        if not isinstance(self.previous, ChildRef) or not isinstance(self.replacement, ChildRef):
            raise ValueError("child references required")
        old, new = self.previous.checked(), self.replacement.checked()
        if old.service != new.service or old.host != new.host:
            raise ValueError("service/host mismatch")
        if (old.boot, old.invocation, old.pid, old.start_utc) == (
                new.boot, new.invocation, new.pid, new.start_utc):
            raise ValueError("same child cannot be restart")
        if utc(self.death_utc) < old.start_utc:
            raise ValueError("death before previous child start")
        if new.start_utc < self.death_utc:
            raise ValueError("replacement predates old death")
        if type(self.timeout_ms) is not int or not 1000 <= self.timeout_ms <= 600_000:
            raise ValueError("invalid bounded readiness deadline")
        if type(self.verified_supervisor) is not bool:
            raise ValueError("verified_supervisor must be bool")
        return self


@dataclass(frozen=True)
class RestartSignal:
    incident_id: str
    attempt: str
    child: ChildRef
    kind: str
    elapsed_ms: int
    verified: bool
    source: str

    def checked(self):
        if not isinstance(self.incident_id, str) or not isinstance(self.attempt, str):
            raise ValueError("invalid attempt reference")
        if not isinstance(self.child, ChildRef):
            raise ValueError("missing child identity")
        self.child.checked()
        if not isinstance(self.kind, str) or self.kind not in KINDS:
            raise ValueError("unknown signal")
        if type(self.elapsed_ms) is not int or not 0 <= self.elapsed_ms < (1 << 63):
            raise ValueError("invalid monotonic elapsed")
        if type(self.verified) is not bool:
            raise ValueError("verified signal must be bool")
        return self


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    outcome: str | None = None


@dataclass
class _Pending:
    start: RestartStart
    last_elapsed: int = 0


class OfflineRestartReadiness:
    """Fail-closed offline process-and-readiness gate with bounded memory.

    An actual-child launch is not success: only independently observed,
    invocation-matching service readiness before a monotonic deadline
    qualifies. Exit, expired readiness, or trusted deadline = failure.
    """

    def __init__(self, *, max_pending: int = 64, max_finished: int = 128):
        if (type(max_pending) is not int or type(max_finished) is not int or
                not 1 <= max_pending <= 4096 or
                not 1 <= max_finished <= 8192):
            raise ValueError("invalid memory limits")
        self.max_pending = max_pending
        self.max_finished = max_finished
        self._pending: dict[tuple[str, str], _Pending] = {}
        self._finished: OrderedDict[tuple[str, str], str] = OrderedDict()

    def begin(self, start: RestartStart) -> Decision:
        if not isinstance(start, RestartStart):
            return Decision("rejected", "invalid start object")
        try:
            start.checked()
        except (ValueError, TypeError) as exc:
            return Decision("rejected", str(exc))
        if start.source != SUPERVISOR or not start.verified_supervisor:
            return Decision("unverified", "real supervisor and new child not attested")
        key = (start.incident_id, start.attempt)
        if key in self._finished:
            return Decision("duplicate", "already finalized", self._finished[key])
        if key in self._pending:
            if self._pending[key].start != start:
                return Decision("rejected", "conflicting same-attempt start")
            return Decision("duplicate", "attempt already active")
        if len(self._pending) >= self.max_pending:
            return Decision("capacity", "too many unclosed restart attempts")
        self._pending[key] = _Pending(start)
        return Decision("pending", "fresh actual-child fixture; awaiting readiness")

    def observe(self, signal: RestartSignal) -> Decision:
        if not isinstance(signal, RestartSignal):
            return Decision("rejected", "invalid observation type")
        try:
            signal.checked()
        except (TypeError, ValueError) as exc:
            return Decision("rejected", str(exc))
        key = (signal.incident_id, signal.attempt)
        if key in self._finished:
            return Decision("duplicate", "attempt already finalized", self._finished[key])
        state = self._pending.get(key)
        if state is None:
            return Decision("rejected", "unknown or expired restart attempt")
        if signal.child != state.start.replacement:
            return Decision("rejected", "old/wrong-child or wrong-service signal")
        expected = {"ready": READY_PROBE, "exited": REAL_WAIT, "timeout": MONOTONIC}[signal.kind]
        if signal.source != expected or not signal.verified:
            return Decision("unverified", "not an attested source of this event kind")
        if signal.elapsed_ms < state.last_elapsed:
            return Decision("rejected", "out-of-order elapsed observation")
        if signal.kind == "timeout" and signal.elapsed_ms < state.start.timeout_ms:
            return Decision("rejected", "premature timeout cannot declare failure")
        state.last_elapsed = signal.elapsed_ms
        if signal.kind == "ready" and signal.elapsed_ms <= state.start.timeout_ms:
            return self._finish(key, "succeeded", "same-child readiness confirmed in fixture")
        if signal.kind == "exited":
            return self._finish(key, "failed", "replacement exited before ready")
        if signal.kind == "timeout" or signal.elapsed_ms > state.start.timeout_ms:
            return self._finish(key, "failed", "readiness deadline exceeded")
        return Decision("rejected", "unsupported transition")

    def _finish(self, key, outcome, reason):
        del self._pending[key]
        self._finished[key] = outcome
        if len(self._finished) > self.max_finished:
            self._finished.popitem(last=False)
        return Decision("completed", reason, outcome)

    def counts(self):
        return len(self._pending), len(self._finished)
