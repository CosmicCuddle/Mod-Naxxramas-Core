"""Build and run the P4 H1 pickup harness against the pinned core (A04_CORE)."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A04 = ROOT / "tests" / "a04_native"
sys.path.insert(0, str(A04))
import build  # noqa: E402  (the #262 helpers, unchanged)


def run(core: Path, out: Path, header_include: Path = None, cxx=None):
    """Prepare the pinned bodies, compile pickup_harness.cpp, run it.

    header_include: directory holding the module headers (default: the
    module's src/Systems). Returns (compiled, returncode, output)."""
    build.prepare(core, out)
    cxx = cxx or os.environ.get("CXX", "g++")
    header_include = header_include or (ROOT / "src" / "Systems")
    exe = out / "p4_h1_pickup_harness"
    cmd = [cxx, "-std=c++20", "-O0", "-g", "-DFMT_HEADER_ONLY",
           "-I", str(header_include), "-I", str(out), "-I", str(A04), "-I", str(A04 / "stubs")]
    for inc in build.CORE_INCLUDES:
        cmd += ["-I", str(core / inc)]
    cmd += [str(out / "pinned_bodies.cpp"), str(HERE / "pickup_harness.cpp"), "-o", str(exe)]
    made = subprocess.run(cmd, capture_output=True, text=True)
    if made.returncode != 0:
        return False, None, made.stdout + made.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return True, ran.returncode, ran.stdout + ran.stderr


parse_checks = build.parse_checks
