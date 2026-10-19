#!/usr/bin/env python3
"""Compile the real QuestLootProtection translation unit using pinned core flags.

Does not run or modify the Worldserver, gameplay data, or owner VM.
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
    opts = parser.parse_args()

    commands = json.loads(
        opts.compile_commands.resolve().read_text(encoding="utf-8")
    )
    expected = "mod-naxxramas-core/src/Systems/QuestLootProtection.cpp"
    matches = [
        entry for entry in commands
        if str(entry.get("file", "")).replace("\\", "/").endswith(expected)
    ]
    if len(matches) != 1:
        raise SystemExit(
            "FAIL: expected exactly one real QuestLootProtection compile "
            f"command, found {len(matches)}"
        )

    record = matches[0]
    args = record.get("arguments") or shlex.split(record["command"])
    if not any("QuestLootProtection.cpp" in part for part in args):
        raise SystemExit("FAIL: wrong source file in compilation command")

    print(f"Compiling actual pinned module source {record['file']}",
          flush=True)
    subprocess.run(args, cwd=Path(record["directory"]).resolve(),
                   check=True, timeout=opts.timeout)
    print("PASS: pinned Grimfeather QuestLootProtection translation unit",
          flush=True)
    print("No full Worldserver link or gameplay verified.", flush=True)


if __name__ == "__main__":
    main()
