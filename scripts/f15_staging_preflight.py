#!/usr/bin/env python3
"""Offline F15 staging preflight.

Consumes operator-supplied JSON only. It never probes the host, executes commands,
or changes files. Unknown evidence stays UNKNOWN.
"""
from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
from typing import Any

REQUIRED = (
    "world.pm2_name",
    "world.pm2_manager_log",
    "world.stdout_log",
    "world.stderr_log",
    "auth.tmux_session",
    "auth.process_name",
    "auth.log",
    "logging.overwrite_owner",
    "logging.snapshot_hook",
    "security.run_user",
    "security.log_owner",
    "capacity.free_bytes",
    "capacity.projected_30d_bytes",
    "fingerprints.build_version_source",
    "fingerprints.source_revision_source",
    "scheduling.observe_once",
    "scheduling.retain_once",
)


def _get(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _known(value: Any) -> bool:
    return value not in (None, "", "UNKNOWN")


def _under(root: str, value: str) -> bool:
    try:
        r = PurePosixPath(root)
        p = PurePosixPath(value)
    except TypeError:
        return False
    return p == r or r in p.parents


def assess(data: dict[str, Any]) -> dict[str, Any]:
    root = str(data.get("log_root") or "/root/cosmic_core/logs")
    checks: list[dict[str, str]] = []
    blockers: list[str] = []
    unknown: list[str] = []

    for key in REQUIRED:
        value = _get(data, key)
        if _known(value):
            checks.append({"check": key, "status": "KNOWN"})
        else:
            checks.append({"check": key, "status": "UNKNOWN"})
            unknown.append(key)

    path_keys = (
        "world.pm2_manager_log", "world.stdout_log", "world.stderr_log", "auth.log"
    )
    for key in path_keys:
        value = _get(data, key)
        if _known(value) and not _under(root, str(value)):
            blockers.append(f"{key} is outside log_root")

    free = _get(data, "capacity.free_bytes")
    projected = _get(data, "capacity.projected_30d_bytes")
    if isinstance(free, int) and isinstance(projected, int):
        if free < 0 or projected < 0:
            blockers.append("capacity values must be non-negative integers")
        elif free < projected:
            blockers.append("free_bytes is below projected_30d_bytes")

    if _known(_get(data, "logging.snapshot_hook")) and not _known(_get(data, "logging.overwrite_owner")):
        blockers.append("snapshot hook is supplied without a verified overwrite owner")

    if data.get("authorizations", {}).get("live_install") is True:
        blockers.append("manifest must not self-authorize live installation")

    status = "BLOCKED" if blockers else ("UNKNOWN" if unknown else "READY_FOR_OWNER_REVIEW")
    return {
        "status": status,
        "log_root": root,
        "checks": checks,
        "unknown": unknown,
        "blockers": blockers,
        "safe_next_step": (
            "resolve blockers/unknowns read-only" if status != "READY_FOR_OWNER_REVIEW"
            else "prepare backup, rollback and staging plan for CosmicCuddle approval"
        ),
        "live_changes_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Offline F15 staging preflight")
    p.add_argument("manifest", help="operator-supplied JSON manifest")
    args = p.parse_args(argv)
    with open(args.manifest, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    result = assess(data)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_OWNER_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
