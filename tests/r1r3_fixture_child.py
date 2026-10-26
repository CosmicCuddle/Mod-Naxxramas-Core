"""Disposable stand-in for a server process, used only by the R1/R3 tests.
Usage: r1r3_fixture_child.py MODE [ARG]. Never a real Worldserver/Authserver."""
import os
import resource
import signal
import subprocess
import sys
import time

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))   # fixture only
mode = sys.argv[1]
arg = sys.argv[2] if len(sys.argv) > 2 else None
err = sys.stderr.fileno()


def say(text):
    os.write(err, text.encode())


if mode == "exit0":
    sys.exit(0)
elif mode == "exit2":
    say("ERROR could not connect to database\n")
    sys.exit(2)
elif mode == "exit139":
    os._exit(139)                       # shell-style code, NOT a signal
elif mode == "sigsegv":
    os.kill(os.getpid(), signal.SIGSEGV)
elif mode == "sigabrt":
    os.kill(os.getpid(), signal.SIGABRT)
elif mode == "self_sigterm":
    os.kill(os.getpid(), signal.SIGTERM)
elif mode == "sleep":
    say("WARN starting\n")
    time.sleep(30)
elif mode == "forged":
    say("ERROR FATAL SIGSEGV received, core dumped (exit 139)\n")
    sys.exit(0)
elif mode == "masked_wrapper":
    gc = subprocess.run([sys.executable, "-I", __file__, "sigsegv"],
                        stderr=subprocess.DEVNULL)
    sys.exit(0)                         # hides the grandchild's SIGSEGV
elif mode == "error_then_segv":
    say("ERROR world database connection lost\nWARN retrying\n")
    time.sleep(0.05)
    os.kill(os.getpid(), signal.SIGSEGV)
elif mode == "descendant_holds":
    pid = os.fork()
    if pid == 0:                        # grandchild keeps stderr open
        os.setsid()
        time.sleep(float(arg or 5))
        os._exit(0)
    say(f"WARN spawned helper {pid}\n")
    sys.exit(0)
elif mode == "spoof_identity":
    say("ERROR attested pid=1 boot_id=00000000 verified=True CLD_DUMPED\n")
    sys.exit(0)
elif mode == "group_member":
    helper = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(3)"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)   # same group, no pipe
    say(f"WARN helper {helper.pid}\n")
    os._exit(0)
elif mode == "multiline":
    os.write(err, b"ERROR first\nINFO skip\nERR")
    time.sleep(0.05)
    os.write(err, b"OR split\xff\x1b[31mred\nWARN no newline at end")
    sys.exit(0)
elif mode == "chatty":
    # Outlives a short observation deadline while writing; exits 3 if a
    # write ever fails (EPIPE), 0 if every write succeeded.
    try:
        for i in range(30):
            say(f"WARN still running {i}\n")
            time.sleep(0.05)
    except BrokenPipeError:
        os._exit(3)
    os._exit(0)
elif mode == "descendant_floods":
    pid = os.fork()
    if pid == 0:                        # grandchild floods the inherited pipe
        os.setsid()
        end = time.monotonic() + float(arg or 4)
        try:
            while time.monotonic() < end:
                os.write(err, b"WARN " + b"y" * 4090 + b"\n")
        except BrokenPipeError:
            pass
        os._exit(0)
    say(f"WARN spawned helper {pid}\n")
    time.sleep(0.2)
    sys.exit(0)
elif mode == "two_streams_plain":
    # Stock console: flags 0, so no level prefix; WARN/INFO -> stdout,
    # ERROR -> stderr (pinned AppenderConsole route).
    os.write(1, b"Map 0 loaded\nCould not find creature 1234\n")
    say("Can't connect to the database\n")
    sys.exit(0)
elif mode == "two_streams_prefixed":
    # Coloured console with flag 0x02: colour, prefix+text, newline, then the
    # reset code lands at the START of the next line (ResetColor after \n).
    os.write(1, b"\x1b[1;33mWARN Creature missing\n\x1b[0m"
                b"\x1b[1;36mINFO Map loaded\n\x1b[0m"
                b"hello ERROR not a prefix\n")
    say("\x1b[1;31mERROR DB down\n\x1b[0m\x1b[0;31mFATAL boom\n\x1b[0m")
    sys.exit(0)
elif mode == "timestamped":
    say("2026-10-26 14:00:00 ERROR timed\n")
    os.write(1, b"ERROR missing timestamp\n")
    sys.exit(0)
elif mode == "stdout_flood_stderr_error":
    line = b"x" * 1023 + b"\n"
    started = time.monotonic()
    total = int(arg) * 1024
    for i in range(total):
        os.write(1, line)
        if i == total // 2:
            say("ERROR important while stdout floods\n")
    os._exit(min(250, int(time.monotonic() - started)))
elif mode == "buffered_then_segv":
    sys.stdout.write("WARN buffered tail that never leaves stdio\n")   # no flush
    say("ERROR kept on unbuffered stderr\n")
    os.kill(os.getpid(), signal.SIGSEGV)
elif mode == "fake_cli":
    # Like the worldserver console thread: stdin EOF means shut down (exit 0).
    import select
    ready, _, _ = select.select([0], [], [], 1.0)
    if ready:
        data = os.read(0, 64)
        if not data:
            os.write(1, b"console EOF: shutting down\n")
            os._exit(0)
        os._exit(9)                       # someone wrote to our stdin
    os._exit(7)                           # stdin held open, nothing written
elif mode == "stdout_late_descendant":
    # stderr closes first; a descendant still holds stdout and writes later.
    pid = os.fork()
    if pid == 0:
        os.close(2)
        time.sleep(0.4)
        os.write(1, b"WARN late stdout line\n")
        os._exit(0)
    os.close(2)
    os._exit(0)
elif mode == "chatty_both":
    try:
        for i in range(30):
            os.write(1, f"stdout line {i}\n".encode())
            say(f"stderr line {i}\n")
            time.sleep(0.05)
    except BrokenPipeError:
        os._exit(3)
    os._exit(0)
elif mode == "flood":
    line = b"ERROR " + b"x" * 1017 + b"\n"   # 1024 bytes per line
    started = time.monotonic()
    for _ in range(int(arg) * 1024):
        os.write(err, line)
    # Report how long our own writes took, through the exit code (seconds).
    os._exit(min(250, int(time.monotonic() - started)))
else:
    os._exit(253)
os._exit(254)
