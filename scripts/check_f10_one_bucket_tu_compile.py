#!/usr/bin/env python3
"""Compile the real F10 one-bucket translation units from compile_commands.

The commands are the ones CMake generated for this module against the
configured Grimfeather core. This does not link worldserver, apply SQL,
or start a server.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

EXPECTED = (
    "mod-naxxramas-core/src/Events/HallowsEndShadeOfTheHorseman.cpp",
    "mod-naxxramas-core/src/Events/HallowsEndSoloFireConfig.cpp",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-commands", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    commands = json.loads(args.compile_commands.read_text(encoding="utf-8"))
    compiled = 0
    for suffix in EXPECTED:
        found = [
            record
            for record in commands
            if str(record.get("file", "")).replace("\\", "/").endswith(suffix)
        ]
        if len(found) != 1:
            raise SystemExit(f"FAIL: expected 1 compile command for {suffix}; found {len(found)}")
        record = found[0]
        argv = record.get("arguments") or shlex.split(record["command"])
        if not any(suffix.split("/")[-1] in part for part in argv):
            raise SystemExit(f"FAIL: compile command does not name {suffix}")
        if "-c" not in argv:
            raise SystemExit(f"FAIL: compile command for {suffix} is not a translation-unit compile")
        joined = " ".join(argv)
        playerbots = "mod-playerbots" in joined or "Playerbots" in joined
        print(
            f"TU {suffix} playerbots_include={'yes' if playerbots else 'no'}",
            flush=True,
        )
        cwd = Path(record["directory"]).resolve()
        subprocess.run(argv, cwd=cwd, check=True, timeout=args.timeout)
        compiled += 1
    if compiled != len(EXPECTED):
        raise SystemExit(f"FAIL: compiled {compiled}")
    print("TU_COMPILE_OK", flush=True)
    print("NOT_A_WORLDSERVER_LINK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"FAIL: compiler exit {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
