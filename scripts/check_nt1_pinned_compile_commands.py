#!/usr/bin/env python3
"""Fail-closed compile of BotTalentImport.cpp with actual CMake-generated flags.

Runs the translation unit's real compiler command from AzerothCore's
compile_commands.json, replacing object emission with -fsyntax-only.
NOT a linked Worldserver build, gameplay test, backup or Apply permission.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


def real_nt1_entry(entries, core_root):
    expected = (core_root / "modules" / "mod-naxxramas-core" /
                "src" / "Systems" / "BotTalentImport.cpp").resolve()
    candidates = [
        entry for entry in entries
        if Path(entry["file"]).resolve() == expected
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one NT1 CMake compile command for {expected}, "
            f"found {len(candidates)}. No syntax check was performed."
        )
    return candidates[0]


def syntax_only_command(entry):
    argv = entry.get("arguments")
    if argv is None:
        argv = shlex.split(entry["command"])
    if not argv or not isinstance(argv, list):
        raise ValueError("Missing/invalid CMake compile command.")
    filtered = []
    i = 0
    skip_next = {"-o", "-MF", "-MT", "-MQ", "--output"}
    skip_single = {"-c", "-MD", "-MMD", "-MP"}
    while i < len(argv):
        token = argv[i]
        if token in skip_next:
            if i + 1 >= len(argv):
                raise ValueError("Truncated CMake compiler flag.")
            i += 2
            continue
        if token in skip_single:
            i += 1
            continue
        if token.startswith(("-o", "-MF", "-MT", "-MQ")) and len(token) > 3:
            i += 1
            continue
        filtered.append(token)
        i += 1
    if not filtered:
        raise ValueError("Empty compiler command after filtering.")
    filtered.append("-fsyntax-only")
    return filtered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-root", type=Path, required=True)
    parser.add_argument("--compile-commands", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    core_root = args.core_root.resolve()
    database = args.compile_commands.resolve()
    entries = json.loads(database.read_text(encoding="utf-8"))
    entry = real_nt1_entry(entries, core_root)
    argv = syntax_only_command(entry)
    directory = Path(entry["directory"]).resolve()
    if not directory.is_relative_to(core_root.parent):
        raise ValueError("Compile command directory outside checked-out source.")
    if args.timeout < 1 or args.timeout > 900:
        raise ValueError("Compile timeout must be between 1 and 900 seconds.")

    print("Pinned-header NT1 syntax check starting:", flush=True)
    print("Source:", entry["file"], flush=True)
    print("Working dir:", str(directory), flush=True)
    # Never print environment secrets, origin URLs or incidental credentials.
    outcome = subprocess.run(
        argv, cwd=directory, check=False, timeout=args.timeout,
    )
    if outcome.returncode:
        raise RuntimeError(
            "NT1 translation-unit C++ syntax check failed; "
            "draft PR must remain unmerged."
        )
    print(
        "PASS: actual CMake-flag NT1 translation-unit syntax check. "
        "NOT a complete linked Worldserver or equipment-safety test.",
        flush=True
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, KeyError, TypeError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
