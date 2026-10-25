"""F15 S4g: Linux-only owned-child waitpid witness, synthetic fixture ONLY.

This does NOT monitor Worldserver/Authserver, run GDB, restart daemons, write
reports, or accept a claim supplied by a log/wrapper/child. Never deploy it.
"""

from dataclasses import dataclass
import os
import signal
import time
import resource
import subprocess
import sys

MODES = frozenset(("exit0", "exit2", "exit139", "sigsegv", "sigabrt",
                   "unplanned_sigterm", "planned_sigterm", "masked_wrapper"))


@dataclass(frozen=True)
class WaitObservation:
    child_pid: int
    started_monotonic_ns: int
    ended_monotonic_ns: int
    kind: str
    exit_code: int | None
    signal_number: int | None
    planned_by_parent: bool
    classification: str


class OfflineKernelWaitFixture:
    """One self-spawned Python fixture child, then an owned kernel waitpid."""

    def __init__(self, mode):
        if os.name != "posix" or not hasattr(os, "waitpid") or mode not in MODES:
            raise ValueError("Linux/POSIX synthetic fixture mode required")
        self._mode = mode
        self._pid = None
        self._started = None
        self._observed = False
        self._origin_pid = os.getpid()
        self._planned = mode == "planned_sigterm"

    @staticmethod
    def _run_child(mode):
        # Exact script+allowed fixture mode only; no caller-supplied executable.
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if mode == "exit0":
            os._exit(0)
        if mode == "exit2":
            os._exit(2)
        if mode == "exit139":
            os._exit(139)  # shell-style 128+SIGSEGV does NOT prove SIGSEGV
        if mode == "masked_wrapper":
            # Python wrapper exits 0 after REAPING its own crashed grandchild.
            # The outer observer cannot attest that grandchild from the
            # wrapper's 0 status: exactly the ambiguity we need to expose.
            proc = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__),
                                     "--synthetic-child", "sigsegv"],
                                    stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            proc.wait(timeout=10)
            os._exit(0)
        sig = {"sigsegv": signal.SIGSEGV,
               "sigabrt": signal.SIGABRT,
               "planned_sigterm": signal.SIGTERM,
               "unplanned_sigterm": signal.SIGTERM}[mode]
        os.kill(os.getpid(), sig)
        os._exit(250)

    def launch(self):
        if os.getpid() != self._origin_pid or self._pid is not None:
            raise RuntimeError("already launched or process ownership mismatch")
        self._started = time.monotonic_ns()
        self._child = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__),
                                        "--synthetic-child", self._mode],
                                       stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        self._pid = self._child.pid
        return self._pid

    def observe(self):
        if os.getpid() != self._origin_pid or self._pid is None or self._observed:
            raise RuntimeError("no owned unconsumed child")
        self._observed = True  # no reaping this particular incarnation twice
        while True:
            try:
                got_pid, status = os.waitpid(self._pid, 0)
                break
            except InterruptedError:
                continue
        if got_pid != self._pid:
            raise RuntimeError("kernel waiter did not return owned child")
        # Popen's own reaper must not mistake our direct waitpid as a leak.
        if os.WIFEXITED(status):
            self._child.returncode = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            self._child.returncode = -os.WTERMSIG(status)
        ended = time.monotonic_ns()
        code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else None
        sig = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
        if sig is not None:
            kind = "kernel_signal"
            if sig in (signal.SIGSEGV, signal.SIGABRT):
                classification = "fatal_child_signal"
            elif sig == signal.SIGTERM and self._planned:
                classification = "planned_signal"
            else:
                classification = "signal_requires_policy"
        elif code is not None:
            kind = "kernel_exit"
            classification = "normal_exit" if code == 0 else "nonzero_exit_not_signal"
        else:
            kind, classification = "other_kernel_status", "unknown"
        return WaitObservation(self._pid, self._started, ended, kind, code,
                               sig, self._planned, classification)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--synthetic-child" or sys.argv[2] not in MODES:
        os._exit(253)
    OfflineKernelWaitFixture._run_child(sys.argv[2])
