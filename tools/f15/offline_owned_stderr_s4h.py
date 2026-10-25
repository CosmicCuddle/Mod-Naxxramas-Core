#!/usr/bin/env python3
"""S4h: offline-only *owned disposable Python child* stderr pipe witness.

Never launch, attach, inspect or signal Worldserver/Authserver/GDB/systemd.
This is a test fixture, not a monitor, crash detector, writer or restart adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

ALLOWED_MODES = frozenset({
    "normal", "forged_crash", "exit139", "bad_utf8", "oversize",
    "flood", "byte_flood", "split", "info", "empty", "unterminated",
})


@dataclass(frozen=True)
class ErrorLine:
    severity: str
    message: str
    line: int
    truncated: bool


@dataclass(frozen=True)
class Capture:
    child_pid: int
    direct_child_exit_code: int
    lines_seen: int
    ignored_lines: int
    dropped_records: int
    clipped_lines: int
    bytes_read: int
    timed_out: bool
    records: tuple[ErrorLine, ...]
    byte_limit_exceeded: bool = False
    provenance: str = "parent-created-stderr-pipe-from-disposable-python-child"


class _BoundedFramer:
    def __init__(self, max_line_bytes: int, max_records: int):
        if not (1 <= max_line_bytes <= 4096 and 1 <= max_records <= 128):
            raise ValueError("invalid fixture bounds")
        self.max_line_bytes = max_line_bytes
        self.max_records = max_records
        self._pending = bytearray()
        self._clipped = False
        self._started = False
        self.records: list[ErrorLine] = []
        self.lines_seen = 0
        self.ignored_lines = 0
        self.dropped_records = 0
        self.clipped_lines = 0

    def feed(self, data: bytes) -> None:
        for value in data:
            if value == 10:  # LF; also accepts CRLF, removing CR below
                self._finish_line()
            else:
                self._started = True
                if len(self._pending) < self.max_line_bytes:
                    self._pending.append(value)
                else:
                    self._clipped = True

    def finish(self) -> None:
        if self._started:
            self._finish_line()

    def _finish_line(self) -> None:
        self.lines_seen += 1
        if self._clipped:
            self.clipped_lines += 1
        value = self._pending.decode("utf-8", "replace").rstrip("\r")
        severity = None
        for prefix, category in (("ERROR ", "ERROR"), ("WARN ", "WARN"), ("WARNING ", "WARN")):
            if value.startswith(prefix):
                severity = category
                value = value[len(prefix):]
                break
        if severity is None:
            self.ignored_lines += 1
        else:
            value = "".join(char if char.isprintable() else "?" for char in value)
            if len(self.records) < self.max_records:
                self.records.append(ErrorLine(severity, value, self.lines_seen, self._clipped))
            else:
                self.dropped_records += 1
        self._pending.clear()
        self._clipped = False
        self._started = False


def capture_disposable(mode: str, *, max_line_bytes: int = 256,
                       max_records: int = 8, max_total_bytes: int = 65536,
                       timeout_seconds: float = 3.0) -> Capture:
    """Start ONLY this module as a Python child; read its parent-created stderr pipe.

    A pipe identifies the parent's chosen endpoint, NOT the human source of
    text nor a trusted crash. Descendants could inherit it in other programs.
    """
    if (mode not in ALLOWED_MODES or not (0.5 <= timeout_seconds <= 15.0)
            or not (4096 <= max_total_bytes <= 1048576)):
        raise ValueError("only fixed disposable modes and bounded byte quotas are allowed")
    framer = _BoundedFramer(max_line_bytes, max_records)
    script = str(Path(__file__).resolve())
    cmd = [sys.executable, "-I", script, "--fixture", mode]
    # No shell, no external executable choice, no actual services or host logs.
    child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, close_fds=True)
    assert child.stderr is not None
    bytes_read = 0
    bytes_framed = 0
    byte_limit_exceeded = False
    timed_out = False
    eof = False
    deadline = time.monotonic() + timeout_seconds
    selector = selectors.DefaultSelector()
    try:
        os.set_blocking(child.stderr.fileno(), False)
        selector.register(child.stderr, selectors.EVENT_READ)
        while not eof:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                if child.poll() is None:
                    child.kill()  # exclusively the Python child this fixture started
                deadline = time.monotonic() + 1.0
            if timed_out and deadline - time.monotonic() <= 0:
                raise TimeoutError("disposable child pipe failed to close")
            for _, _ in selector.select(min(0.1, max(0.0, deadline - time.monotonic()))):
                data = os.read(child.stderr.fileno(), 4096)
                if data:
                    bytes_read += len(data)
                    remaining = max_total_bytes - bytes_framed
                    framer.feed(data[:remaining])
                    bytes_framed += min(len(data), remaining)
                    if len(data) > remaining:
                        # Stop processing a hostile endless stderr stream.
                        # Truncation is explicitly reported; it is NOT a
                        # health, service-crash or trusted-source verdict.
                        byte_limit_exceeded = True
                        if child.poll() is None:
                            child.kill()  # only this disposable Python child
                        eof = True
                else:
                    eof = True
                    break
        framer.finish()
        code = child.wait(timeout=1.0)
    finally:
        selector.close()
        if child.poll() is None:
            child.kill()
            child.wait(timeout=1.0)
        child.stderr.close()
    return Capture(child.pid, code, framer.lines_seen, framer.ignored_lines,
                   framer.dropped_records, framer.clipped_lines, bytes_read,
                   timed_out, tuple(framer.records), byte_limit_exceeded)


def _fixture(mode: str) -> None:
    # These are all deliberately disposable Python child *test inputs*.
    if mode == "normal":
        os.write(2, b"WARN short warning\nERROR short error\nINFO not error\n")
    elif mode == "forged_crash":
        os.write(2, b"ERROR FATAL SIGSEGV: definitely a real crash 139\n")
    elif mode == "exit139":
        os.write(2, b"ERROR I claim a segmentation fault\n")
        os._exit(139)
    elif mode == "bad_utf8":
        os.write(2, b"ERROR invalid \xff \x1b escape \x00 byte\n")
    elif mode == "oversize":
        os.write(2, b"ERROR " + b"A" * 20000 + b"\n")
    elif mode == "flood":
        for i in range(100):
            os.write(2, ("WARN synthetic %03d\n" % i).encode("ascii"))
    elif mode == "byte_flood":
        for _ in range(2000):
            os.write(2, b"ERROR " + b"x" * 1024 + b"\n")
    elif mode == "split":
        os.write(2, b"ERR")
        time.sleep(0.02)
        os.write(2, b"OR assembled\n")
    elif mode == "info":
        os.write(2, b"INFO informational\nDEBUG not an error\n")
    elif mode == "unterminated":
        os.write(2, b"ERROR no-final-LF")
    elif mode == "empty":
        pass


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture" and sys.argv[2] in ALLOWED_MODES:
        _fixture(sys.argv[2])
        return 0
    print("Offline-only S4h module; import capture_disposable from tests", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
