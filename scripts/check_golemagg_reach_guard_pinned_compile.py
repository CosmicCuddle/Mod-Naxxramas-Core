#!/usr/bin/env python3
"""Compile only the real BotGolemaggReachGuard C++ translation unit.

Uses the CMake-generated arguments for an exact pinned AzerothCore,
Playerbots and Individual Progression checkout. Does not link or start
Worldserver, touch SQL or run gameplay.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

SUFFIX = "mod-naxxramas-core/src/Systems/BotGolemaggReachGuard.cpp"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-commands", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()

    records = json.loads(args.compile_commands.resolve().read_text(encoding="utf-8"))
    matches = [
        record for record in records
        if str(record.get("file", "")).replace("\\", "/").endswith(SUFFIX)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"FAIL: expected one Golemagg reach guard compile command, got {len(matches)}"
        )

    record = matches[0]
    argv = record.get("arguments") or shlex.split(record["command"])
    if not any(token.endswith("BotGolemaggReachGuard.cpp") for token in argv):
        raise SystemExit("FAIL: selected command does not compile the guard file")

    print("Compiling Golemagg reach guard unit:", record["file"], flush=True)
    subprocess.run(argv, cwd=Path(record["directory"]).resolve(), check=True, timeout=args.timeout)
    print("PASS: Golemagg reach guard translation unit compiled", flush=True)


if __name__ == "__main__":
    main()
