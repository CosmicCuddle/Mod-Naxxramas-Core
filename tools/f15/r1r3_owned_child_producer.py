#!/usr/bin/env python3
"""F15 R1/R3 producer prototype, launch mode A only: a supervisor that starts
a process itself and owns its stderr pipe. Linux only, Python standard library.

DRAFT, UNSELECTED and OFF. It must only ever observe disposable children that
its own tests spawn. It is not an owner launcher, is not installed, and must
not be run against a real Worldserver/Authserver (CS01 #143 6415818621).

What it establishes from the kernel rather than from text:
  R1  Which process incarnation ended, and how. Identity is
      (boot_id, pid, starttime, ppid). The child is pinned with a pidfd
      straight after spawn; because this producer is its parent and has not
      reaped it, the PID cannot be recycled in between, and the pinned
      process is cross-checked to be our own child. Death comes only from
      waitid(P_PIDFD, WEXITED): CLD_EXITED, CLD_KILLED and CLD_DUMPED stay
      distinct. Exit 139, printed "SIGSEGV" or a wrapper's 0 never becomes a
      signal death.
  R3  WARN/ERROR lines from the stderr pipe this producer created, bound to
      the same incarnation by the producer (never by the child's text). The
      pipe is ALWAYS drained in one nonblocking select loop: past the
      retention budget, bytes are dropped and counted. Stopping reads would
      fill the pipe and block the child's write(2).

It sends NO signals at all. A "planned stop" can only be a plan declared to
the producer before start by the test harness that will deliver it; any other
terminating signal is unplanned. Process-group membership is reported from a
read-only /proc scan, which can never prove that no descendant remains.
Restart (R2), report writing (R4), journal/file/GDB modes: out of scope.
"""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field

ATTEST_EXIT = "owned-child-waitid"
ATTEST_STREAM = "owned-stderr-pipe"
FATAL_SIGNALS = frozenset({signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS,
                           signal.SIGFPE, signal.SIGILL, signal.SIGSYS})
_PREFIXES = (("ERROR ", "ERROR"), ("WARN ", "WARN"), ("WARNING ", "WARN"))


class Unsupported(RuntimeError):
    """The kernel/Python lacks a required primitive: no attestation at all."""


def require_capabilities() -> None:
    if not (hasattr(os, "pidfd_open") and hasattr(os, "P_PIDFD")
            and hasattr(os, "waitid") and hasattr(os, "CLD_DUMPED")):
        raise Unsupported("pidfd_open / waitid(P_PIDFD) unavailable: "
                          "refusing to produce attested events")
    if not os.path.exists("/proc/sys/kernel/random/boot_id"):
        raise Unsupported("boot_id unavailable")


def read_boot_id() -> str:
    with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as f:
        return f.read().strip()


def read_stat(pid: int) -> tuple[int, int, int]:
    """(ppid, pgrp, starttime) from /proc/<pid>/stat."""
    with open(f"/proc/{pid}/stat", "rb") as f:
        raw = f.read()
    # comm may contain spaces/parentheses: split after the LAST ')'.
    rest = raw[raw.rindex(b")") + 2:].split()
    return int(rest[1]), int(rest[2]), int(rest[19])


@dataclass(frozen=True)
class Incarnation:
    boot_id: str
    pid: int
    starttime: int
    ppid: int
    pgid: int


@dataclass(frozen=True)
class ExitFact:
    incarnation: Incarnation
    attestation: str
    kind: str                 # "exited" | "killed" | "dumped"
    exit_code: int | None
    signal_number: int | None
    planned: bool
    classification: str       # normal_exit | nonzero_exit_not_signal |
                              # fatal_signal | planned_signal |
                              # signal_requires_policy


@dataclass(frozen=True)
class Record:
    severity: str
    message: str
    line: int
    truncated: bool


@dataclass
class StreamFact:
    incarnation: Incarnation
    attestation: str = ATTEST_STREAM
    eof: bool = False
    deadline_hit: bool = False      # EOF grace expired: SOURCE_INCOMPLETE
    bytes_drained: int = 0          # every byte read from the pipe
    bytes_retained: int = 0         # bytes that entered the bounded buffers
    bytes_framing: int = 0          # newline delimiters consumed
    bytes_dropped: int = 0          # drained - retained - framing
    lines_terminated: int = 0       # complete lines (newline seen)
    final_partial_line: bool = False
    lines_unclassified: int = 0     # severity unreadable: budget exhausted
    records_dropped: int = 0
    records: list[Record] = field(default_factory=list)

    @property
    def source_incomplete(self) -> bool:
        return self.deadline_hit and not self.eof


@dataclass(frozen=True)
class Observation:
    exit: ExitFact
    stream: StreamFact
    group_members_seen_after_exit: tuple[int, ...]   # /proc scan; not proof


class _Framer:
    """Bounded line framing on whole chunks; never asks to stop reading."""

    def __init__(self, fact: StreamFact, max_line: int, max_records: int,
                 retain_bytes: int):
        self.fact, self.max_line = fact, max_line
        self.max_records, self.retain_left = max_records, retain_bytes
        self.pending, self.truncated, self.started = bytearray(), False, False

    def feed(self, data: bytes) -> None:
        self.fact.bytes_drained += len(data)
        start = 0
        while True:
            nl = data.find(b"\n", start)
            end = len(data) if nl < 0 else nl
            if end > start:
                self._append(data[start:end])
            if nl < 0:
                break
            self.fact.bytes_framing += 1
            self.fact.lines_terminated += 1
            self._line()
            start = nl + 1
        self._settle()

    def _append(self, seg: bytes) -> None:
        self.started = True
        room = max(0, min(self.max_line - len(self.pending), self.retain_left))
        take = seg[:room]
        self.pending += take
        self.retain_left -= len(take)
        self.fact.bytes_retained += len(take)
        if len(take) < len(seg):
            self.truncated = True

    def _settle(self) -> None:
        f = self.fact
        f.bytes_dropped = f.bytes_drained - f.bytes_retained - f.bytes_framing

    def finish(self) -> None:
        if self.started:
            self.fact.final_partial_line = True
            self._line()

    def _line(self) -> None:
        text = self.pending.decode("utf-8", "replace").rstrip("\r")
        truncated, empty = self.truncated, not self.pending
        number = self.fact.lines_terminated + (1 if self.fact.final_partial_line else 0)
        self.pending.clear()
        self.truncated = self.started = False
        if empty and truncated:
            # Budget exhausted before any byte was kept: severity unknown.
            self.fact.lines_unclassified += 1
            return
        for prefix, severity in _PREFIXES:
            if text.startswith(prefix):
                body = "".join(c if c.isprintable() else "?"
                               for c in text[len(prefix):])
                if len(self.fact.records) < self.max_records:
                    self.fact.records.append(Record(severity, body, number, truncated))
                else:
                    self.fact.records_dropped += 1
                return


class OwnedChildProducer:
    """Spawn one disposable child and observe it. Single use. Sends no signals."""

    def __init__(self, argv: list[str], *, allowed_executables: frozenset[str],
                 planned_signal: int | None = None,
                 max_line_bytes: int = 512, max_records: int = 64,
                 retain_bytes: int = 256 * 1024, eof_grace_seconds: float = 2.0):
        require_capabilities()
        if not argv or os.path.realpath(argv[0]) not in allowed_executables:
            raise ValueError("executable is not in the reviewed allowlist")
        if not (1 <= max_line_bytes <= 8192 and 1 <= max_records <= 4096
                and 4096 <= retain_bytes <= 16 * 1024 * 1024
                and 0.1 <= eof_grace_seconds <= 60.0):
            raise ValueError("bounds out of range")
        self._argv = list(argv)
        self._limits = (max_line_bytes, max_records, retain_bytes)
        self._grace = eof_grace_seconds
        # Declared by the harness BEFORE start; the producer never delivers it.
        self._planned = planned_signal
        self._proc: subprocess.Popen | None = None
        self._pidfd: int | None = None
        self._incarnation: Incarnation | None = None
        self._done = False

    @property
    def incarnation(self) -> Incarnation:
        if self._incarnation is None:
            raise RuntimeError("not started")
        return self._incarnation

    def start(self) -> Incarnation:
        if self._proc is not None:
            raise RuntimeError("single use")
        boot = read_boot_id()
        self._proc = subprocess.Popen(
            self._argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
        pid = self._proc.pid
        # No PID-reuse window: the child is ours and unreaped (at worst a
        # zombie), so `pid` cannot name another process until WE wait on it.
        self._pidfd = os.pidfd_open(pid)
        ppid, pgrp, start = read_stat(pid)
        if ppid != os.getpid() or read_boot_id() != boot:
            # Release only what we own; the process itself is not signalled.
            os.close(self._pidfd)
            self._pidfd = None
            self._proc.stderr.close()
            self._done = True
            raise RuntimeError("pinned process is not our own child")
        self._incarnation = Incarnation(boot, pid, start, ppid, pgrp)
        return self._incarnation

    def matches(self, claimed: Incarnation) -> bool:
        """True only if `claimed` is exactly the live process we pinned.
        Read-only: a pidfd becomes readable when its process exits."""
        if self._pidfd is None or claimed != self._incarnation:
            return False
        sel = selectors.DefaultSelector()
        try:
            sel.register(self._pidfd, selectors.EVENT_READ)
            if sel.select(0):
                return False                      # already exited
        finally:
            sel.close()
        try:
            return read_stat(claimed.pid)[2] == claimed.starttime
        except FileNotFoundError:
            return False

    def observe(self, deadline_seconds: float = 30.0) -> Observation:
        if self._proc is None or self._done:
            raise RuntimeError("not started or already observed")
        self._done = True
        fact = StreamFact(self.incarnation)
        framer = _Framer(fact, *self._limits)
        out = self._proc.stderr.fileno()
        os.set_blocking(out, False)
        sel = selectors.DefaultSelector()
        sel.register(out, selectors.EVENT_READ, "stream")
        sel.register(self._pidfd, selectors.EVENT_READ, "exit")
        exit_fact = None
        hard_deadline = time.monotonic() + deadline_seconds
        eof_deadline = None
        try:
            # One nonblocking loop: the pipe keeps draining whether or not
            # the child has exited. Exit and EOF are separate facts; either
            # may come first. Two single-shot deadlines bound the wait.
            while not (exit_fact is not None and fact.eof):
                now = time.monotonic()
                if exit_fact is None and now >= hard_deadline:
                    raise TimeoutError("owned child did not exit in time")
                if eof_deadline is not None and now >= eof_deadline:
                    fact.deadline_hit = True     # no signal is ever sent
                    break
                limit = eof_deadline if exit_fact else hard_deadline
                for key, _ in sel.select(max(0.0, min(0.2, limit - now))):
                    if key.data == "stream":
                        self._drain(out, framer, fact)
                        if fact.eof:
                            sel.unregister(out)
                    elif exit_fact is None:
                        exit_fact = self._reap()
                        sel.unregister(self._pidfd)
                        eof_deadline = time.monotonic() + self._grace
            framer.finish()
        finally:
            sel.close()
            self._proc.stderr.close()   # closes ONLY our own read end
            # Forget the number too: a closed fd number can be reused.
            pidfd, self._pidfd = self._pidfd, None
            os.close(pidfd)
        if exit_fact is None:
            raise RuntimeError("stream ended but exit not observed")
        return Observation(exit_fact, fact,
                           _scan_group(self.incarnation.pgid, self.incarnation.pid))

    @staticmethod
    def _drain(fd: int, framer: _Framer, fact: StreamFact) -> None:
        while True:
            try:
                data = os.read(fd, 65536)
            except BlockingIOError:
                return
            if not data:
                fact.eof = True
                return
            framer.feed(data)

    def _reap(self) -> ExitFact:
        info = os.waitid(os.P_PIDFD, self._pidfd, os.WEXITED)
        if info is None or info.si_pid != self.incarnation.pid:
            raise RuntimeError("kernel did not report the owned child")
        code = info.si_code
        if code == os.CLD_EXITED:
            self._proc.returncode = info.si_status
            status = info.si_status
            return ExitFact(self.incarnation, ATTEST_EXIT, "exited", status,
                            None, False,
                            "normal_exit" if status == 0
                            else "nonzero_exit_not_signal")
        if code in (os.CLD_KILLED, os.CLD_DUMPED):
            sig = info.si_status
            self._proc.returncode = -sig
            planned = self._planned is not None and sig == self._planned
            if planned:
                cls = "planned_signal"
            elif sig in FATAL_SIGNALS:
                cls = "fatal_signal"
            else:
                cls = "signal_requires_policy"
            kind = "dumped" if code == os.CLD_DUMPED else "killed"
            return ExitFact(self.incarnation, ATTEST_EXIT, kind, None, sig,
                            planned, cls)
        raise RuntimeError(f"unexpected waitid si_code {code}")


def _scan_group(pgid: int, leader: int) -> tuple[int, ...]:
    """Read-only /proc scan for processes still in the child's process group.
    An empty result is NOT proof: a descendant can leave the group with
    setsid(), and processes can appear or vanish during the scan."""
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == leader:
            continue
        try:
            if read_stat(int(name))[1] == pgid:
                found.append(int(name))
        except (FileNotFoundError, ProcessLookupError, ValueError):
            continue
    return tuple(sorted(found))
