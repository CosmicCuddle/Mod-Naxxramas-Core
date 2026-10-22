#!/usr/bin/env python3
"""Compile only the real GolemaggActionAudit C++ translation unit.

Uses CMake-generated arguments for the exact pinned AzerothCore/Playerbots/IP
checkout. Does NOT start or link Worldserver, alter SQL or run gameplay.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-commands", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()

    records = json.loads(args.compile_commands.resolve().read_text(encoding="utf-8"))
    suffix = "mod-naxxramas-core/src/Systems/BotGolemaggActionAudit.cpp"
    matches = [
        record for record in records
        if str(record.get("file", "")).replace("\\", "/").endswith(suffix)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"FAIL: expected one real Golemagg action audit compile command, got {len(matches)}"
        )

    record = matches[0]
    argv = record.get("arguments") or shlex.split(record["command"])
    if not any("BotGolemaggActionAudit.cpp" in token for token in argv):
        raise SystemExit("FAIL: selected command does not compile the audit file")

    print("Compiling exactly pinned Golemagg action observer unit:", record["file"], flush=True)
    subprocess.run(argv, cwd=Path(record["directory"]).resolve(), check=True, timeout=args.timeout)
    print("PASS: actual pinned Golemagg action audit translation unit compiled", flush=True)
    print("No Worldserver link, live installation, gameplay or movement fix verified.", flush=True)


if __name__ == "__main__":
    main()
