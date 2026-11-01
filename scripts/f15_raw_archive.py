#!/usr/bin/env python3
"""Opt-in, NON-DELETING archive of completed F15 supervised World/Auth raw output.

Default: dry run. Validates the owner-selected supervisor runs and prints a
plan; writes nothing. With --archive-owned-completed it COPIES the selected,
validated, completed runs' stdout.raw / stderr.raw (byte for byte) plus their
start/exit receipts into an independent, already existing private archive:

    <raw-archive-root>/runs/<run-id>/{stdout.raw, stderr.raw, start.json,
                                      exit.json, manifest.json}

Each run is staged in <raw-archive-root>/.staging/<run-id>-<token>/, verified
(SHA-256 while copying, then the copy is re-hashed) and published with one
atomic directory rename. A repeat call re-verifies an existing archive and
reports it; any mismatch is refused.

NEVER: deletes, truncates, rotates or rewrites originals or receipts; touches
PM2/tmux/systemd; schedules anything; starts processes; creates the archive
root; reads log contents into its report; or treats a nonzero exit as a
proven engine crash. Leftover staging from an interrupted run is reported,
not removed. Development code: an operator must verify the real host first.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from f15_operator_collector import Refused
from f15_supervised_retention import RUN_ID, SERVICES, START_FIELDS, EXIT_FIELDS, _receipt
from f15_supervised_storage_audit import existing_private_dir, _raw_stat, _observed_exit

STREAMS = ("stdout.raw", "stderr.raw")
LABELS = {"stdout.raw": "out", "stderr.raw": "err"}
RECEIPTS = ("start.json", "exit.json")
EXIT_KINDS = ("clean_exit", "nonzero_exit", "signaled_exit")
RETENTION = timedelta(days=30)
CHUNK = 1 << 20
MANIFEST_FIELDS = frozenset(("format", "run_id", "service", "exit_kind", "exit_code",
                             "exit_time_utc", "files"))
FILE_FIELDS = frozenset(("sha256", "size", "source_dev", "source_ino"))
FORMAT = "naxx-f15-raw-archive-v1"
NOTE = ("Copies only; originals are never deleted. Observed subprocess exit kind "
        "is not an engine crash diagnosis.")


def _separate(*roots):
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            if a == b or a in b.parents or b in a.parents:
                raise Refused("output, capture archive and raw archive roots must be separate and nonnested")


def _roots(output_root, archive_root, raw_archive_root):
    roots = tuple(existing_private_dir(p) for p in (output_root, archive_root, raw_archive_root))
    _separate(*roots)
    return roots


def validate_completed_run(output_root, archive_root, run_id, now):
    """All checks the supervisor's own receipts allow; refuse anything else."""
    if type(run_id) is not str or not RUN_ID.fullmatch(run_id):
        raise Refused("unknown supervisor run identifier")
    run = existing_private_dir(output_root / "runs" / run_id)
    capture = existing_private_dir(archive_root / "runs" / run_id)
    start = _receipt(run / "start.json", START_FIELDS)
    exit_path = run / "exit.json"
    if not exit_path.exists() and not exit_path.is_symlink():
        raise Refused("run is not complete: no observed exit receipt")
    ended = _receipt(exit_path, EXIT_FIELDS)
    for value in (start["service"], ended["service"], start["capture_root"],
                  ended["capture_root"], start["stdout"], start["stderr"]):
        if type(value) is not str:
            raise Refused("non-string supervisor receipt identity")
    service = start["service"]
    if (service not in SERVICES or start["state"] != "planned"
            or ended["service"] != service or ended["state"] != "exit_observed"
            or start["capture_root"] != str(capture) or ended["capture_root"] != str(capture)
            or start["stdout"] != str(run / STREAMS[0]) or start["stderr"] != str(run / STREAMS[1])):
        raise Refused("supervisor receipts do not match this run")
    if ended["capture"] != "complete_for_observed_run" or ended["capture_error_type"] is not None:
        raise Refused("run capture is not complete (fail_closed); refusing to archive")
    if (type(ended["pid"]) is not int or ended["pid"] <= 0
            or type(ended["exit_code"]) is not int or ended["exit_kind"] not in EXIT_KINDS):
        raise Refused("unverified supervisor exit receipt")
    exit_time = _observed_exit(ended["time_utc"], now)
    files = {}
    for name in STREAMS:
        raw = run / name
        info = _raw_stat(raw)
        origin = _receipt(capture / "records" / (service + "-" + LABELS[name]) / "origin.json",
                          {"path", "dev", "ino", "start"})
        if (origin["path"] != str(raw) or type(origin["dev"]) is not int
                or type(origin["ino"]) is not int or origin["dev"] != info.st_dev
                or origin["ino"] != info.st_ino):
            raise Refused("raw stream inode differs from its capture origin")
        files[name] = info
    return {"run": run, "service": service, "ended": ended, "exit_time": exit_time,
            "files": files}


def _open_verified(path, expected):
    """Open without following links; the descriptor must be the validated inode."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077
                or st.st_dev != expected.st_dev or st.st_ino != expected.st_ino):
            raise Refused("source changed identity after validation")
    except BaseException:
        os.close(fd)
        raise
    return fd, st


def _hash_file(path):
    h = hashlib.sha256()
    size = 0
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        while True:
            chunk = os.read(fd, CHUNK)
            if not chunk:
                return h.hexdigest(), size
            h.update(chunk)
            size += len(chunk)
    finally:
        os.close(fd)


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _copy_verified(source, dest, expected):
    """Copy one file into a new 0600 destination; return (sha256, size)."""
    src_fd, before = _open_verified(source, expected)
    h = hashlib.sha256()
    size = 0
    try:
        out_fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            while True:
                chunk = os.read(src_fd, CHUNK)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(out_fd, view)
                    view = view[written:]
            os.fsync(out_fd)
        finally:
            os.close(out_fd)
        after = os.fstat(src_fd)
    finally:
        os.close(src_fd)
    if (size != before.st_size or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns):
        raise Refused("source changed while it was being copied")
    digest = h.hexdigest()
    if _hash_file(dest) != (digest, size):
        raise Refused("archived copy does not match the source digest")
    return digest, size


def _manifest_for(info, run_id, digests):
    ended = info["ended"]
    return {
        "format": FORMAT, "run_id": run_id, "service": info["service"],
        "exit_kind": ended["exit_kind"], "exit_code": ended["exit_code"],
        "exit_time_utc": ended["time_utc"],
        "files": {name: {"sha256": digests[name][0], "size": digests[name][1],
                         "source_dev": info["files"][name].st_dev,
                         "source_ino": info["files"][name].st_ino}
                  for name in STREAMS},
    }


def _verify_published(final, info, run_id):
    """Re-verify an existing archive against its manifest and the live source."""
    existing_private_dir(final)
    names = {p.name for p in final.iterdir()}
    if names != set(STREAMS) | set(RECEIPTS) | {"manifest.json"}:
        raise Refused("existing archive has unexpected contents; manual review")
    manifest = _receipt(final / "manifest.json", MANIFEST_FIELDS)
    if (manifest["format"] != FORMAT or manifest["run_id"] != run_id
            or manifest["service"] != info["service"]
            or manifest["exit_kind"] != info["ended"]["exit_kind"]
            or not isinstance(manifest["files"], dict) or set(manifest["files"]) != set(STREAMS)):
        raise Refused("existing archive manifest does not match this run")
    for name in STREAMS:
        entry = manifest["files"][name]
        if not isinstance(entry, dict) or set(entry) != FILE_FIELDS:
            raise Refused("existing archive manifest entry is malformed")
        copy = final / name
        cst = copy.lstat()
        if not stat.S_ISREG(cst.st_mode) or cst.st_nlink != 1 or cst.st_mode & 0o077:
            raise Refused("existing archived stream is not a private single-link file")
        if _hash_file(copy) != (entry["sha256"], entry["size"]):
            raise Refused("existing archived stream digest mismatch; manual review")
        src = info["files"][name]
        if (entry["source_dev"] != src.st_dev or entry["source_ino"] != src.st_ino):
            raise Refused("existing archive came from a different source inode")
        if _hash_file(info["run"] / name) != (entry["sha256"], entry["size"]):
            raise Refused("source no longer matches its archive; manual review")
    for name in RECEIPTS:
        if (final / name).read_bytes() != (info["run"] / name).read_bytes():
            raise Refused("archived receipt differs from the supervisor receipt")


def _stale_staging(raw_archive_root):
    staging = raw_archive_root / ".staging"
    if not staging.exists() and not staging.is_symlink():
        return 0
    existing_private_dir(staging)
    return sum(1 for _ in staging.iterdir())


def _private_subdir(path):
    """Create (0700) or accept an existing private subdirectory we own."""
    if not path.exists() and not path.is_symlink():
        os.mkdir(path, 0o700)
    return existing_private_dir(path)


def archive_run(output_root, archive_root, raw_archive_root, run_id, now, interrupt_after=None):
    info = validate_completed_run(output_root, archive_root, run_id, now)
    runs = _private_subdir(raw_archive_root / "runs")
    final = runs / run_id
    if final.exists() or final.is_symlink():
        _verify_published(final, info, run_id)
        return "already_archived"
    staging_root = _private_subdir(raw_archive_root / ".staging")
    stage = staging_root / (run_id + "-" + secrets.token_hex(8))
    os.mkdir(stage, 0o700)
    digests = {}
    for count, name in enumerate(STREAMS):
        if interrupt_after is not None and count >= interrupt_after:
            raise KeyboardInterrupt("test interruption")  # staging stays for review
        digests[name] = _copy_verified(info["run"] / name, stage / name, info["files"][name])
    for name in RECEIPTS:
        src = info["run"] / name
        expected = src.lstat()
        _copy_verified(src, stage / name, expected)
    manifest = json.dumps(_manifest_for(info, run_id, digests), sort_keys=True).encode()
    fd = os.open(stage / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, manifest)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(stage)
    if final.exists() or final.is_symlink():
        raise Refused("archive destination appeared during copy; manual review")
    os.rename(stage, final)
    _fsync_dir(runs)
    _fsync_dir(staging_root)
    return "archived"


def plan(output_root, archive_root, raw_archive_root, run_ids, now=None,
         execute=False, interrupt_after=None):
    output_root, archive_root, raw_archive_root = _roots(output_root, archive_root, raw_archive_root)
    if not run_ids:
        raise Refused("select at least one supervisor run with --run")
    if len(set(run_ids)) != len(run_ids):
        raise Refused("duplicate --run selection")
    instant = (datetime.now(timezone.utc) if now is None
               else datetime.fromtimestamp(now, timezone.utc))
    report = {"mode": "ARCHIVE_COPY" if execute else "DRY_RUN_READ_ONLY",
              "deletions": 0, "runs": [], "note": NOTE}
    # Validate every selection before copying anything.
    validated = {rid: validate_completed_run(output_root, archive_root, rid, instant) for rid in run_ids}
    for rid in run_ids:
        info = validated[rid]
        entry = {"run_id": rid, "service": info["service"],
                 "exit_kind": info["ended"]["exit_kind"],
                 "raw_bytes": sum(info["files"][n].st_size for n in STREAMS),
                 "older_than_30_days": instant > info["exit_time"] + RETENTION}
        if execute:
            entry["result"] = archive_run(output_root, archive_root, raw_archive_root, rid,
                                          instant, interrupt_after=interrupt_after)
        else:
            published = raw_archive_root / "runs" / rid
            entry["result"] = ("would_verify_existing" if published.exists() or published.is_symlink()
                               else "would_archive")
        report["runs"].append(entry)
    report["stale_staging_entries"] = _stale_staging(raw_archive_root)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="F15 completed supervised raw output archive; COPY ONLY, NO DELETION, dry run by default")
    parser.add_argument("--output-root", required=True, help="existing private supervisor output root")
    parser.add_argument("--archive-root", required=True, help="existing private supervisor capture archive root")
    parser.add_argument("--raw-archive-root", required=True, help="existing, separate private destination for raw copies")
    parser.add_argument("--run", action="append", default=[], help="owner-selected supervisor run id (repeatable)")
    parser.add_argument("--archive-owned-completed", action="store_true",
                        help="actually copy the selected validated completed runs (default: dry run)")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(plan(args.output_root, args.archive_root, args.raw_archive_root,
                              args.run, execute=args.archive_owned_completed), sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, TypeError) as exc:
        print("F15 RAW ARCHIVE REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
