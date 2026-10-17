#!/usr/bin/env python3
"""Compile the actual HunterPetAutocastAudit.cpp unit with pinned CMake flags.

Offline only. No gameplay, database, real realm or worldserver process.
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
    options = parser.parse_args()

    records = json.loads(
        options.compile_commands.resolve().read_text(encoding="utf-8")
    )
    expected = "mod-naxxramas-core/src/Systems/HunterPetAutocastAudit.cpp"
    matches = [
        record for record in records
        if str(record.get("file", "")).replace("\\", "/").endswith(expected)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"FAIL: expected exactly one real HunterPetAutocastAudit compile command, found {len(matches)}"
        )

    record = matches[0]
    argv = record.get("arguments") or shlex.split(record["command"])
    if not any("HunterPetAutocastAudit.cpp" in token for token in argv):
        raise SystemExit("FAIL: wrong source file selected")

    print("Compiling actual pinned module unit", record["file"], flush=True)
    subprocess.run(
        argv,
        cwd=Path(record["directory"]).resolve(),
        check=True,
        timeout=options.timeout,
    )
    print("PASS: pinned Grimfeather HunterPetAutocastAudit translation unit", flush=True)
    print("No runtime autocast restoration or gameplay verified.", flush=True)


if __name__ == "__main__":
    main()
