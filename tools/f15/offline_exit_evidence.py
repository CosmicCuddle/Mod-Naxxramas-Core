"""F15 S4 research: OFFLINE admission model for source-attributed exit evidence.

NOT a process observer, wrapper, supervisor, report publisher or trust broker.
Passing verified_actual_child=True in a synthetic fixture does NOT prove
real OS identity. A future trusted adapter must derive it independently and
must never map wrapper exit status or GDB transcript text into that field.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from offline_store import Incident

DIRECT_CHILD_WAIT = "direct-child-wait"
UNTRUSTED_SOURCES = frozenset({
    "starter-wrapper", "simple-restarter-text", "gdb-transcript",
    "systemd-summary", "journal-text", "unknown",
})


@dataclass(frozen=True)
class ExitEvidence:
    source: str
    service: str
    host: str = ""
    boot: str = ""
    invocation: str = ""
    pid: Optional[int] = None
    start_utc: str = ""
    end_utc: str = ""
    verified_actual_child: bool = False
    verified_unexpected: bool = False
    planned_stop: bool = False
    exit_code: Optional[int] = None
    signal: Optional[str] = None


@dataclass(frozen=True)
class Admission:
    status: str
    reason: str
    candidate: Optional[Incident] = None


def evaluate_exit_evidence(evidence: ExitEvidence) -> Admission:
    """Classify fixture evidence without publishing or asserting host trust.

    A candidate means the supplied synthetic direct-child claims would pass
    offline S2 policy if a separately reviewed OS adapter authenticated the
    source/child identity. It is never proof that the actual realm crashed.
    """
    if not isinstance(evidence, ExitEvidence):
        raise TypeError("ExitEvidence required")
    if type(evidence.verified_actual_child) is not bool or type(evidence.verified_unexpected) is not bool:
        return Admission("rejected", "boolean evidence fields required")
    if type(evidence.planned_stop) is not bool:
        return Admission("rejected", "planned_stop must be boolean")

    # Wrapper shell status is not the child's wait status. Under GDB, starter
    # can return 0 after child SIGSEGV; restarter text/GDB logs can be stale,
    # collided or unrelated. Reject even if caller falsely marks verified.
    if evidence.source != DIRECT_CHILD_WAIT:
        return Admission("unverified", "not an actual-child wait observation")
    if not evidence.verified_actual_child:
        return Admission("unverified", "actual-child identity not verified")

    try:
        incident = Incident(
            service=evidence.service,
            host=evidence.host,
            boot=evidence.boot,
            invocation=evidence.invocation,
            pid=evidence.pid,
            start_utc=evidence.start_utc,
            end_utc=evidence.end_utc,
            verified_actual_death=True,
            unexpected_death=evidence.verified_unexpected,
            planned_stop=evidence.planned_stop,
            signal=evidence.signal,
            exit_code=evidence.exit_code,
        )
        incident.checked()
    except (TypeError, ValueError) as exc:
        return Admission("rejected", "invalid actual-child fixture: " + str(exc))

    if not evidence.verified_unexpected:
        return Admission("ignored", "not independently classified unexpected")
    if not incident.is_reportable():
        return Admission("ignored", "expected stop/restart or insufficient fatal evidence")

    # Never guess SIGSEGV from exit 139: 139 may be a literal exit code.
    # The S2 report records the actual supplied termination kind only.
    return Admission("candidate", "requires independent OS-source authentication", incident)
