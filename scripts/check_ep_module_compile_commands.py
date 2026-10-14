#!/usr/bin/env python3
"""Compile only Naxxramas EP tower translation unit using REAL pinned flags.

No database, worldserver process or live files are touched. Strictly require
the owner module path; do not substitute a fake/stub include tree.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compile-commands", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=240)
    a = ap.parse_args()
    cc = a.compile_commands.resolve()
    commands = json.loads(cc.read_text(encoding="utf-8"))
    expected = "mod-naxxramas-core/src/Systems/EasternPlaguelandsTowerLock.cpp"
    found = [
        x for x in commands
        if str(x.get("file", "")).replace("\\", "/").endswith(expected)
    ]
    if len(found) != 1:
        raise SystemExit(f"FAIL: expected 1 actual EP module compile command; found {len(found)}")

    record = found[0]
    args = record.get("arguments") or shlex.split(record["command"])
    if not any("EasternPlaguelandsTowerLock.cpp" in v for v in args):
        raise SystemExit("FAIL: compile command is missing the source file")
    cwd = Path(record["directory"]).resolve()
    print(f"Compiling EP module source against configured pinned headers: {record['file']}", flush=True)
    subprocess.run(args, cwd=cwd, check=True, timeout=a.timeout)
    print("PASS: real pinned AzerothCore EP module translation unit compilation.", flush=True)
    print("NOT a full link, runtime test or installed server verification.", flush=True)


if __name__ == "__main__":
    main()
