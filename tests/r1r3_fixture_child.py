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
