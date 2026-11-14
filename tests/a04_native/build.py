"""Shared build/run helpers for the A04 extracted-pinned-source harness."""
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Pinned core include directories (relative to the core checkout).
CORE_INCLUDES = [
    "src/server/game/Loot",
    "src/server/game/Entities/Item",
    "src/server/game/Entities/Object",
    "src/server/game/Server",
    "src/server/game/Server/Protocol",
    "src/server/shared",
    "src/server/shared/Packets",
    "src/server/shared/DataStores",
    "src/common",
    "src/common/Dynamic",
    "src/common/Dynamic/LinkedReference",
    "src/common/Utilities",
    "src/common/Debugging",
    "src/common/Logging",
    "deps/fmt/include",
]


def prepare(core: Path, out: Path, mutant=None) -> str:
    cmd = [sys.executable, "-I", str(HERE / "prepare_pinned.py"), "--core", str(core), "--out", str(out)]
    if mutant:
        cmd += ["--mutant", mutant]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(run.stdout + run.stderr)
    return run.stdout


def compile_and_run(core: Path, out: Path, cxx=None):
    """Returns (compile_ok, run_returncode, stdout+stderr)."""
    cxx = cxx or os.environ.get("CXX", "g++")
    exe = out / "a04_harness"
    # The generated stub ConditionMgr.h must win over the real one.
    cmd = [cxx, "-std=c++20", "-O0", "-g", "-DFMT_HEADER_ONLY",
           "-I", str(out), "-I", str(HERE), "-I", str(HERE / "stubs")]
    for inc in CORE_INCLUDES:
        cmd += ["-I", str(core / inc)]
    cmd += [str(out / "pinned_bodies.cpp"), str(HERE / "harness.cpp"), "-o", str(exe)]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode != 0:
        return False, None, build.stdout + build.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return True, run.returncode, run.stdout + run.stderr


def parse_checks(output: str):
    return re.findall(r"^CHECK (PASS|FAIL) (\S+)$", output, re.M)
