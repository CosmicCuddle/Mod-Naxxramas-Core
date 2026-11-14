#!/usr/bin/env python3
"""F15 operational CLI: observe, snapshot-before-overwrite, retain.

No process-control commands are exposed. Observation is read-only with respect
to Worldserver/Authserver and their live source logs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Callable

import f15_incident_pipeline as pipeline
import f15_owned_retention_30d as retention
import f15_preoverwrite_log_snapshot as snapshot
import f15_raw_evidence_bundle as raw_bundle
import f15_readonly_host_probe as probe


DEFAULT_LOG_ROOT = Path("/root/cosmic_core/logs")
DEFAULT_CRASH_ROOT = DEFAULT_LOG_ROOT / "Crash Logs"
DEFAULT_ARCHIVE_ROOT = DEFAULT_LOG_ROOT / "Archived Logs"
DEFAULT_STATE_ROOT = DEFAULT_LOG_ROOT / ".f15-state"


class Refused(RuntimeError):
    pass


def _reject_symlink_ancestors(path: Path, label: str) -> None:
    """Refuse any existing symlink component above path."""
    current = Path(path).parent
    while True:
        if current.is_symlink():
            raise Refused(f"{label} ancestor may not be a symlink")
        parent = current.parent
        if parent == current:
            break
        current = parent


class FixedPm2Runner:
    """Replay exactly one already-observed pm2 jlist result into the pipeline."""
    def __init__(self, raw: str):
        self.raw = raw

    def __call__(self, argv):
        if argv != ["pm2", "jlist"]:
            raise Refused("fixed PM2 runner received unexpected command")
        return 0, self.raw, ""


def _approved_log_source(path: str | Path, log_root: Path) -> Path:
    """Require one source path to stay beneath the approved live-log root."""
    root = Path(log_root)
    source = Path(path)
    if not root.is_absolute() or not source.is_absolute():
        raise Refused("log root and source paths must be absolute")
    _reject_symlink_ancestors(root, "log root")
    _reject_symlink_ancestors(source, "log source")
    if root.is_symlink():
        raise Refused("log root may not be a symlink")
    try:
        relative = source.relative_to(root)
    except ValueError as exc:
        raise Refused("log source must be beneath approved log root") from exc
    if not relative.parts:
        raise Refused("log source may not equal log root")

    root_real = Path(os.path.realpath(root))
    source_real = Path(os.path.realpath(source))
    try:
        common = os.path.commonpath((str(root_real), str(source_real)))
    except ValueError as exc:
        raise Refused("log source/root path comparison failed") from exc
    if common != str(root_real) or source_real == root_real:
        raise Refused("log source resolves outside approved log root")

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise Refused("log source path may not contain symlinks")
    return source


def _tail_best_effort(path: str | Path | None, label: str, log_root: Path) -> str:
    if not path:
        return f"[{label}: source not configured]\n"
    source = _approved_log_source(path, log_root)
    try:
        text = probe.tail_private_source(source)
        return f"===== {label}: {source} =====\n{text}\n"
    except OSError as exc:
        return f"[{label}: unavailable: {type(exc).__name__}]\n"


def _world_context(summary: dict, manager_log: str | Path | None, log_root: Path) -> tuple[str, str]:
    manager = _tail_best_effort(manager_log, "PM2 manager", log_root)
    out = _tail_best_effort(summary.get("out_log"), "Worldserver stdout", log_root)
    err = _tail_best_effort(summary.get("err_log"), "Worldserver stderr", log_root)
    return manager, out + err


def _auth_context(auth_log: str | Path | None, log_root: Path) -> str:
    return _tail_best_effort(auth_log, "Authserver log", log_root)


def observe_once(state_root: Path, crash_root: Path,
                 log_root: Path = DEFAULT_LOG_ROOT,
                 world_pm2_name: str | None = None,
                 pm2_manager_log: str | Path | None = None,
                 auth_tmux_session: str | None = None,
                 auth_log: str | Path | None = None,
                 build_version: str | None = None,
                 source_revision: str | None = None,
                 runner: Callable = probe._default_runner,
                 read_text: Callable[[Path], str] | None = None,
                 now: datetime | None = None) -> list[dict]:
    if not world_pm2_name and not auth_tmux_session:
        raise Refused("observe-once requires Worldserver and/or Authserver target")
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise Refused("observation time must be timezone-aware")
    when = when.astimezone(timezone.utc)
    raw_root = Path(crash_root) / "Raw Evidence"
    emitted = []

    if world_pm2_name:
        raw_pm2, summary = probe.probe_pm2(world_pm2_name, runner)
        manager_text, recent_context = _world_context(summary, pm2_manager_log, Path(log_root))
        event = pipeline.world_cycle(
            Path(state_root),
            Path(crash_root),
            raw_root,
            world_pm2_name,
            manager_text,
            recent_context,
            FixedPm2Runner(raw_pm2),
            now=when,
            build_version=build_version,
            source_revision=source_revision,
        )
        if event:
            emitted.append({
                "service": event["service"],
                "incident_id": event["incident_id"],
                "classification": event["classification"],
            })

    if auth_tmux_session:
        reader = read_text or (lambda p: p.read_text("utf-8"))
        recent_context = _auth_context(auth_log, Path(log_root))
        event = pipeline.auth_cycle(
            Path(state_root),
            Path(crash_root),
            raw_root,
            auth_tmux_session,
            recent_context,
            runner,
            reader,
            now=when,
            build_version=build_version,
            source_revision=source_revision,
        )
        if event:
            emitted.append({
                "service": event["service"],
                "incident_id": event["incident_id"],
                "classification": event["classification"],
            })

    return emitted


def snapshot_before_overwrite(log_root: Path, archive_root: Path,
                              now: datetime | None = None) -> list[tuple[Path, Path]]:
    log_root = Path(log_root)
    archive_root = Path(archive_root)
    if archive_root.parent != log_root:
        raise Refused("archive root must be a direct child of log root")
    return snapshot.snapshot_log_directory(log_root, archive_root, observed_utc=now)


def retain_once(archive_root: Path, crash_root: Path,
                now: datetime | None = None) -> dict:
    archive_root = Path(archive_root)
    crash_root = Path(crash_root)
    raw_root = crash_root / "Raw Evidence"
    result = {
        "archived_log_sets_removed": 0,
        "raw_evidence_bundles_removed": 0,
        "crash_reports_removed": 0,
        "crash_history_entries_removed": 0,
    }
    if archive_root.exists():
        result["archived_log_sets_removed"] = retention.retain_snapshot_archive(archive_root, now)
    if raw_root.exists():
        result["raw_evidence_bundles_removed"] = raw_bundle.retain_bundles(raw_root, now)
    if crash_root.exists():
        reports, history = retention.retain_crash_reports(crash_root, now)
        result["crash_reports_removed"] = reports
        result["crash_history_entries_removed"] = history
    return result


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cosmic Core F15 crash/log evidence operations")
    sub = p.add_subparsers(dest="command", required=True)

    observe = sub.add_parser("observe-once", help="read current process/log evidence once")
    observe.add_argument("--world-pm2-name")
    observe.add_argument("--pm2-manager-log", type=Path)
    observe.add_argument("--auth-tmux-session")
    observe.add_argument("--auth-log", type=Path)
    observe.add_argument("--build-version")
    observe.add_argument("--source-revision")

    snap = sub.add_parser("snapshot-before-overwrite", help="copy live logs before approved overwrite")

    retain = sub.add_parser("retain-once", help="expire verified F15-owned artifacts older than 30 days")

    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "observe-once":
            result = observe_once(
                DEFAULT_STATE_ROOT,
                DEFAULT_CRASH_ROOT,
                world_pm2_name=args.world_pm2_name,
                pm2_manager_log=args.pm2_manager_log,
                auth_tmux_session=args.auth_tmux_session,
                auth_log=args.auth_log,
                build_version=args.build_version,
                source_revision=args.source_revision,
            )
        elif args.command == "snapshot-before-overwrite":
            pairs = snapshot_before_overwrite(DEFAULT_LOG_ROOT, DEFAULT_ARCHIVE_ROOT)
            result = {"snapshots_created": len(pairs)}
        elif args.command == "retain-once":
            result = retain_once(DEFAULT_ARCHIVE_ROOT, DEFAULT_CRASH_ROOT)
        else:
            raise Refused("unknown command")
    except (Refused, probe.Refused, pipeline.raw_bundle.Refused,
            snapshot.Refused, retention.Refused, raw_bundle.Refused) as exc:
        print(f"F15 REFUSED: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"F15 I/O ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
