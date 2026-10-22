#!/usr/bin/env python3
"""Compile actual HunterAmmoProvision.cpp with pinned CMake compile commands.

No Worldserver process, DB writes, gameplay, or real character inventory use.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-commands", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()

    commands = json.loads(args.compile_commands.resolve().read_text(encoding="utf-8"))
    suffix = "mod-naxxramas-core/src/Systems/HunterAmmoProvision.cpp"
    found = [
        row for row in commands
        if str(row.get("file", "")).replace("\\", "/").endswith(suffix)
    ]
    if len(found) != 1:
        raise SystemExit(
            f"FAIL: expected one actual HunterAmmoProvision compile command, found {len(found)}"
        )

    entry = found[0]
    argv = entry.get("arguments") or shlex.split(entry["command"])
    if not any("HunterAmmoProvision.cpp" in part for part in argv):
        raise SystemExit("FAIL: compile command points to wrong source unit")

    print("Compiling actual pinned HunterAmmoProvision.cpp", flush=True)
    subprocess.run(
        argv, cwd=Path(entry["directory"]).resolve(), check=True,
        timeout=args.timeout
    )
    print("PASS: exact pinned HunterAmmoProvision C++ translation unit", flush=True)
    print("Not a live character inventory or ammo consumption test.", flush=True)


if __name__ == "__main__":
    main()
