#!/usr/bin/env python3
"""Read-only checkout preflight for owner-approved Naxx Core staging.

Does NOT pull, install, rebuild, restart, enable settings, open a database,
inspect private account configuration, or authorize the running Worldserver.
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
# 3 pinned mismatch, 4 dirty tracked files, 5 unreadable/unverified binary.
INVALID, MISMATCH, DIRTY, BINARY_ERROR = 2, 3, 4, 5


def selected_pins(core: str | None = None, playerbots: str | None = None,
                  ip: str | None = None) -> dict[str, str]:
    """Build the caller-chosen source comparison only; NEVER discover or update.

    The historical pins remain defaults, and each separately supplied
    revision must be an exact Git SHA. An override is a request to compare,
    NOT evidence that this dependency combination has been built or tested.
    """
    requested = {
        "AzerothCore": core,
        "Playerbots": playerbots,
        "Individual Progression": ip,
    }
    for name, sha in requested.items():
        if sha is not None and not SHA40.fullmatch(sha):
            raise ValueError(f"{name}: expected revision must be a full 40-character Git SHA")
    return {name: requested[name].lower() if requested[name] is not None
            else existing for name, existing in PINS.items()}


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
        print(f"Expected comparison SHA: {expected}")
        if head.lower() != expected.lower():
            print("DIFFERENT: source differs from chosen comparison; compatibility NOT verified")
            errors.append(MISMATCH)
        else:
            print("MATCH: requested source revision (not proof of a compatible build)")
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



def check_running_worldserver_pid(pid: int, proc_root: Path = Path("/proc")) -> tuple[int, str | None]:
    """Hash the kernel's process executable handle; never touch its memory/config.

    This identifies the executable used by *that PID at inspection time*,
    not source provenance, module flags, migration state or runtime behavior.
    proc_root is injectable for disposable filesystem-only tests.
    """
    print("\n[Optional currently running Worldserver PID]")
    if pid <= 0:
        print("STOP: PID must be a positive process number")
        return BINARY_ERROR, None
    directory = proc_root / str(pid)
    executable = directory / "exe"
    try:
        name = (directory / "comm").read_text(encoding="utf-8").strip()
        if name != "worldserver":
            print("STOP: selected PID is not named worldserver")
            return BINARY_ERROR, None
        target = os.readlink(executable)
        if target.endswith(" (deleted)"):
            print("STOP: selected process still uses a deleted executable")
            return BINARY_ERROR, None
        before = executable.stat()
        digest = sha256_file(executable)
        after = executable.stat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            print("STOP: process executable identity changed during inspection")
            return BINARY_ERROR, None
    except (OSError, UnicodeError, ValueError):
        print("STOP: /proc executable handle is inaccessible or process exited")
        return BINARY_ERROR, None
    print(f"Inspected PID: {pid} (worldserver)")
    print(f"Executable basename: {Path(target).name}")
    print(f"Running-process executable SHA-256: {digest}")
    print("No /proc command line, environment, memory or open file descriptors read.")
    print("Does NOT certify linked modules, effective config, DB state or safe deployment.")
    return 0, digest


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only Naxx Core installed-checkout preflight"
    )
    ap.add_argument("--core", type=Path, required=True,
                    help="AzerothCore source checkout root, NOT its parent")
    ap.add_argument("--expected-core", type=str,
                    help="Optional exact 40-character AzerothCore comparison SHA")
    ap.add_argument("--expected-playerbots", type=str,
                    help="Optional exact 40-character Playerbots comparison SHA")
    ap.add_argument("--expected-ip", type=str,
                    help="Optional exact 40-character Individual Progression comparison SHA")
    ap.add_argument("--expected-naxx", type=str,
                    help="Optional exact 40-character Naxx Core candidate SHA")
    ap.add_argument("--worldserver", type=Path,
                    help="Optional path to an on-disk executable to hash only")
    ap.add_argument("--worldserver-pid", type=int,
                    help="Optional existing Linux Worldserver PID: hash /proc/PID/exe read-only")
    args = ap.parse_args()
    if args.expected_naxx and not SHA40.fullmatch(args.expected_naxx):
        ap.error("--expected-naxx must be an exact 40-character Git SHA")

    try:
        pins = selected_pins(args.expected_core, args.expected_playerbots,
                             args.expected_ip)
    except ValueError as error:
        ap.error(str(error))

    core = args.core.expanduser().resolve()
    roots = (
        ("AzerothCore", core, pins["AzerothCore"]),
        ("Playerbots", core / "modules/mod-playerbots", pins["Playerbots"]),
        ("Individual Progression", core / "modules/mod-individual-progression",
         pins["Individual Progression"]),
        ("Naxxramas Core", core / "modules/mod-naxxramas-core",
         args.expected_naxx),
    )
    outcomes = [check_checkout(*row) for row in roots]

    on_disk_sha = None
    if args.worldserver:
        binary = args.worldserver.expanduser().resolve()
        print("\n[Optional on-disk Worldserver file]")
        try:
            if not binary.is_file():
                raise OSError("not a file")
            print(f"File path: {binary}")
            on_disk_sha = sha256_file(binary)
            print(f"File SHA-256: {on_disk_sha}")
            print("This does NOT establish which executable a running process uses.")
        except (OSError, ValueError):
            print("STOP: cannot read optional binary file")
            outcomes.append(BINARY_ERROR)

    if args.worldserver_pid is not None:
        status, running_sha = check_running_worldserver_pid(args.worldserver_pid)
        if status:
            outcomes.append(status)
        elif on_disk_sha is not None and running_sha != on_disk_sha:
            print("STOP: selected on-disk and running Worldserver executables differ")
            outcomes.append(BINARY_ERROR)
        elif on_disk_sha is not None:
            print("MATCH: inspected file bytes equal this PID's executable bytes")
            print("Matching bytes alone does NOT prove source-build provenance.")

    print("\nNo source, config, data, SQL, DBC, binary or service was modified.")
    print("No account names, secrets, full config, or player data were read.")
    print("Chosen source SHA matches and optional PID checks do NOT prove compatibility, migrations or runtime behavior.")
    print("Check actual active config and backups separately with operator approval.")
    if any(outcomes):
        print("STOP: manual compatibility review required before ANY rollout.")
    else:
        print("PREFLIGHT CHECKS PASSED only; deployment is NOT approved.")
    return max(outcomes, default=0)


if __name__ == "__main__":
    raise SystemExit(main())
