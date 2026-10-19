#!/usr/bin/env python3
"""Compile the one proposed IP translation unit in a disposable GitHub runner.

The requested source MUST belong to the separately checked-out IP working
tree. This script never mutates that checkout; the CI workflow intentionally
applies then restores the REVIEW patch in the same disposable runner.

A successful compilation proves only C++ translation-unit compatibility,
NOT full Worldserver link, correct live behavior, or module-only deployment.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-commands", type=Path, required=True)
    parser.add_argument("--ip-root", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=420)
    args = parser.parse_args()

    ip_root = args.ip_root.resolve()
    expected = (ip_root / "src/IndividualProgressionSpells.cpp").resolve()
    assert expected.is_file(), f"Missing exact pinned IP source: {expected}"
    commands = json.loads(args.compile_commands.resolve().read_text(encoding="utf-8"))
    matching = []
    for record in commands:
        path = Path(record.get("file", ""))
        if not path.is_absolute():
            path = Path(record["directory"]) / path
        if path.resolve() == expected:
            matching.append(record)
    if len(matching) != 1:
        raise SystemExit(
            "FAIL: expected exactly ONE configured C++ command for "
            f"the proposed IP translation unit, found {len(matching)}"
        )

    record = matching[0]
    argv = record.get("arguments") or shlex.split(record["command"])
    if not any("IndividualProgressionSpells.cpp" in str(v) for v in argv):
        raise SystemExit("FAIL: configured compiler arguments target another source")
    if not any(str(v).endswith("IndividualProgressionSpells.cpp") for v in argv):
        raise SystemExit("FAIL: no explicit IP translation unit compiler operand")

    print(f"CI ONLY: compiling modified disposable IP source {expected}", flush=True)
    subprocess.run(
        argv,
        cwd=Path(record["directory"]).resolve(),
        check=True,
        timeout=args.timeout,
    )
    print("PASS: proposed IP C++ translation unit compiled with pinned CMake flags.", flush=True)
    print("NOT a full Worldserver link, tested player preference, or runtime module-only fix.", flush=True)


if __name__ == "__main__":
    main()
