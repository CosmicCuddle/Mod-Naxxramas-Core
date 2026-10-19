#!/usr/bin/env python3
"""Read-only checkout preflight for owner-approved Naxx Core staging.

Does NOT pull, install, rebuild, restart, enable settings, open a database,
inspect private account configuration, or prove the running Worldserver.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess

PINS = {
    "AzerothCore": "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7",
    "Playerbots": "037c01418b5d01506917a3db9b44fd56ac5f965c",
    "Individual Progression": "4ff4b5fcc1480348f058c632573143e62d4e3a41",
}
SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
# Exit codes: 0 clean/pinned, 2 invalid/missing/not repository,
# 3 pinned mismatch, 4 dirty tracked files, 5 unreadable binary.
INVALID, MISMATCH, DIRTY, BINARY_ERROR = 2, 3, 4, 5


def git(path: Path, *arguments: str) -> str:
    # --no-optional-locks prevents normal status index refresh writes.
    command = ["git", "--no-optional-locks", "-C", str(path), *arguments]
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        command, capture_output=True, text=True, check=False,
        env=env, timeout=12,
    )
    if result.returncode:
        raise ValueError("Git metadata unavailable or command failed")
    return result.stdout.strip()


def check_checkout(label: str, root: Path, expected: str | None) -> int:
    requested = root.expanduser().resolve()
    print(f"\n[{label}]")
    print(f"Checkout directory: {requested}")
    if not requested.is_dir():
        print("STOP: checkout folder missing")
        return INVALID
    try:
        git_root = Path(git(requested, "rev-parse", "--show-toplevel")).resolve()
        if git_root != requested:
            print("STOP: nested path resolved to another repository")
            return INVALID
        head = git(requested, "rev-parse", "--verify", "HEAD")
        if not SHA40.fullmatch(head):
            print("STOP: Git HEAD is not a full 40-character SHA")
            return INVALID
        dirty = git(requested, "status", "--porcelain", "--untracked-files=no")
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print("STOP: source checkout cannot be verified")
        return INVALID
    print(f"Actual Git SHA: {head}")
    errors = []
    if expected:
        print(f"Pinned comparison SHA: {expected}")
        if head.lower() != expected.lower():
            print("DIFFERENT: pinned CI is NOT build proof for this installed source")
            errors.append(MISMATCH)
        else:
            print("MATCH: exact tested source revision")
    else:
        print("UNSPECIFIED EXPECTATION: Naxx Core revision recorded, NOT certified")
    if dirty:
        print("MODIFIED TRACKED FILES: present (names and content not displayed)")
        errors.append(DIRTY)
    else:
        print("Tracked source: clean (untracked files NOT inspected)")
    return max(errors, default=0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only Naxx Core installed-checkout preflight"
    )
    ap.add_argument("--core", type=Path, required=True,
                    help="AzerothCore source checkout root, NOT its parent")
    ap.add_argument("--expected-naxx", type=str,
                    help="Optional exact 40-character Naxx Core candidate SHA")
    ap.add_argument("--worldserver", type=Path,
                    help="Optional path to an on-disk executable to hash only")
    args = ap.parse_args()
    if args.expected_naxx and not SHA40.fullmatch(args.expected_naxx):
        ap.error("--expected-naxx must be an exact 40-character Git SHA")

    core = args.core.expanduser().resolve()
    roots = (
        ("AzerothCore", core, PINS["AzerothCore"]),
        ("Playerbots", core / "modules/mod-playerbots", PINS["Playerbots"]),
        ("Individual Progression", core / "modules/mod-individual-progression",
         PINS["Individual Progression"]),
        ("Naxxramas Core", core / "modules/mod-naxxramas-core",
         args.expected_naxx),
    )
    outcomes = [check_checkout(*row) for row in roots]

    if args.worldserver:
        binary = args.worldserver.expanduser().resolve()
        print("\n[Optional on-disk Worldserver file]")
        try:
            if not binary.is_file():
                raise OSError("not a file")
            print(f"File path: {binary}")
            print(f"File SHA-256: {sha256_file(binary)}")
            print("This does NOT establish which executable a running process uses.")
        except (OSError, ValueError):
            print("STOP: cannot read optional binary file")
            outcomes.append(BINARY_ERROR)

    print("\nNo source, config, data, SQL, DBC, binary or service was modified.")
    print("No account names, secrets, full config, or player data were read.")
    print("Git checks do NOT prove server process, migrations, or runtime behavior.")
    print("Check actual active config and backups separately with operator approval.")
    if any(outcomes):
        print("STOP: manual compatibility review required before ANY rollout.")
    else:
        print("SOURCE CHECK PASSED only; deployment is NOT approved.")
    return max(outcomes, default=0)


if __name__ == "__main__":
    raise SystemExit(main())
