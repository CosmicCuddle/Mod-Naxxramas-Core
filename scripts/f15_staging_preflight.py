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

HOST_FACTS = (
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
)
PLANNED_FACTS = ("scheduling.observe_once", "scheduling.retain_once")
REQUIRED = HOST_FACTS + PLANNED_FACTS
PATH_KEYS = ("world.pm2_manager_log", "world.stdout_log", "world.stderr_log", "auth.log")
INT_KEYS = ("capacity.free_bytes", "capacity.projected_30d_bytes")
APPROVED_LOG_ROOT = "/root/cosmic_core/logs"


def _get(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _evidence(data: dict[str, Any], key: str) -> tuple[str, Any, str]:
    raw = _get(data, key)
    if raw is None:
        return "UNKNOWN", None, ""
    if not isinstance(raw, dict):
        return "MALFORMED", None, ""
    status = raw.get("status")
    value = raw.get("value")
    source = raw.get("source")
    if status not in ("VERIFIED", "PROPOSED", "UNKNOWN"):
        return "MALFORMED", value, ""
    if status == "UNKNOWN":
        return "UNKNOWN", None, str(source or "")
    if not isinstance(source, str) or not source.strip():
        return "MALFORMED", value, ""
    return status, value, source.strip()


def _valid_scalar(key: str, value: Any) -> bool:
    if key in INT_KEYS:
        return type(value) is int and value >= 0
    return isinstance(value, str) and bool(value.strip())


def _normalized_absolute(value: str) -> bool:
    try:
        p = PurePosixPath(value)
    except TypeError:
        return False
    return p.is_absolute() and ".." not in p.parts and str(p) == value


def _strictly_under(root: str, value: str) -> bool:
    if not _normalized_absolute(root) or not _normalized_absolute(value):
        return False
    r = PurePosixPath(root)
    p = PurePosixPath(value)
    return p != r and r in p.parents


def assess(data: dict[str, Any]) -> dict[str, Any]:
    root_raw = data.get("log_root", "/root/cosmic_core/logs")
    root = root_raw if isinstance(root_raw, str) else ""
    checks: list[dict[str, str]] = []
    blockers: list[str] = []
    unknown: list[str] = []
    values: dict[str, Any] = {}

    if not root or not _normalized_absolute(root):
        blockers.append("log_root must be an absolute normalized POSIX path")
    elif root != APPROVED_LOG_ROOT:
        blockers.append(
            "log_root must remain the owner-approved /root/cosmic_core/logs boundary"
        )

    for key in REQUIRED:
        status, value, _source = _evidence(data, key)
        allowed = {"VERIFIED"} if key in HOST_FACTS else {"VERIFIED", "PROPOSED"}
        if status == "MALFORMED":
            checks.append({"check": key, "status": "MALFORMED"})
            blockers.append(f"{key} evidence envelope is malformed or lacks provenance")
            continue
        if status == "UNKNOWN":
            checks.append({"check": key, "status": "UNKNOWN"})
            unknown.append(key)
            continue
        if status not in allowed:
            checks.append({"check": key, "status": "UNVERIFIED"})
            unknown.append(key)
            continue
        if not _valid_scalar(key, value):
            checks.append({"check": key, "status": "MALFORMED"})
            blockers.append(f"{key} has an invalid value type or value")
            continue
        checks.append({"check": key, "status": status})
        values[key] = value

    for key in PATH_KEYS:
        if key in values and not _strictly_under(root, values[key]):
            blockers.append(
                f"{key} must be a normalized absolute file path strictly below log_root"
            )

    free = values.get("capacity.free_bytes")
    projected = values.get("capacity.projected_30d_bytes")
    if type(free) is int and type(projected) is int and free < projected:
        blockers.append("free_bytes is below projected_30d_bytes")

    if "logging.snapshot_hook" in values and "logging.overwrite_owner" not in values:
        blockers.append("snapshot hook is supplied without a VERIFIED overwrite owner")

    auth = data.get("authorizations", {})
    if auth is not None and not isinstance(auth, dict):
        blockers.append("authorizations must be an object when supplied")
    elif isinstance(auth, dict) and auth.get("live_install") is True:
        blockers.append("manifest must not self-authorize live installation")

    status = "BLOCKED" if blockers else ("UNKNOWN" if unknown else "READY_FOR_OWNER_REVIEW")
    return {
        "status": status,
        "log_root": root,
        "checks": checks,
        "unknown": unknown,
        "blockers": blockers,
        "safe_next_step": (
            "resolve blockers/unknowns read-only"
            if status != "READY_FOR_OWNER_REVIEW"
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
