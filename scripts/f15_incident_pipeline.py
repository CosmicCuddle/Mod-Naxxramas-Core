#!/usr/bin/env python3
"""F15 composition: evidence -> normalization -> checkpoint -> bundle -> report.

This module composes existing F15 primitives. It does not add process-control,
log-truncation, rotation, deletion, DB or server-management authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Callable

import f15_crash_report_renderer as renderer
import f15_expected_maintenance as expected_maintenance
import f15_incident_checkpoint as checkpoint
import f15_raw_evidence_bundle as raw_bundle
import f15_readonly_host_probe as probe
import f15_topology_evidence as topology


def _utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("pipeline timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decorate_common(incident: dict, now: datetime, recent_context: str,
                     capture_status: str, capture_gaps: str,
                     build_version: str | None, source_revision: str | None) -> None:
    incident["observed_utc"] = now.isoformat()
    incident["observed_local"] = now.astimezone().isoformat()
    incident["filename_timestamp"] = now.strftime("%Y%m%dT%H%M%SZ")
    incident["recent_context"] = recent_context
    incident["capture_status"] = capture_status
    incident["capture_gaps"] = capture_gaps
    incident["build_version"] = build_version
    incident["source_revision"] = source_revision


def _write_owned_incident(crash_root: Path, raw_root: Path, incident: dict,
                          now: datetime, artifacts: dict[str, object],
                          provenance: dict[str, str]) -> Path:
    renderer._private_dir(crash_root)
    artifacts = dict(artifacts)
    artifacts["report-input.json"] = dict(incident)
    bundle = raw_bundle.ensure_bundle(
        raw_root,
        incident["incident_id"],
        artifacts,
        created_utc=now,
        provenance=provenance,
    )
    try:
        stored = json.loads((bundle / "report-input.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise raw_bundle.Refused("stored report input is unavailable") from exc
    if not isinstance(stored, dict) or stored.get("incident_id") != incident["incident_id"] or stored.get("service") != incident["service"]:
        raise raw_bundle.Refused("stored report input does not match incident")
    incident.clear()
    incident.update(stored)
    incident["raw_evidence_ref"] = str(bundle)
    return renderer.ensure_report(crash_root, incident)


def world_cycle(state_root: Path, crash_root: Path, raw_root: Path,
                process_name: str, manager_text: str, recent_context: str,
                runner: Callable, now: datetime | None = None,
                build_version: str | None = None,
                source_revision: str | None = None) -> dict | None:
    """One read-only Worldserver observation cycle.

    The first call establishes a baseline. A later PM2 restart creates one raw
    evidence bundle + one detailed report before the checkpoint advances.
    """
    current_time = _utc(now)
    raw_pm2, _summary = probe.probe_pm2(process_name, runner)
    state = checkpoint.IncidentCheckpoint(state_root, "Worldserver")
    expected = expected_maintenance.ExpectedMaintenanceStore(state_root, "Worldserver")

    def evaluate_expected(previous: dict, current: dict, incident: dict):
        return expected.evaluate_unlocked(previous, current, incident, current_time)

    def finalize_expected(decision: dict):
        expected.finalize_expected_unlocked(decision)

    def render(incident: dict):
        _decorate_common(
            incident,
            current_time,
            recent_context,
            "pm2 snapshot + supplied bounded manager/context evidence",
            "native kernel/core evidence may be UNKNOWN unless separately supplied",
            build_version,
            source_revision,
        )
        artifacts = {
            "pm2-jlist.json": raw_pm2,
            "pm2-manager.txt": manager_text,
            "recent-context.txt": recent_context,
        }
        return _write_owned_incident(
            crash_root,
            raw_root,
            incident,
            current_time,
            artifacts,
            {"service": "Worldserver", "supervisor": "PM2", "process_name": process_name},
        )

    return state.process_world(
        raw_pm2,
        process_name,
        manager_text,
        topology._one_pm2,
        topology.world_incident,
        render,
        expected_evaluate=evaluate_expected,
        expected_finalize=finalize_expected,
    )


def auth_cycle(state_root: Path, crash_root: Path, raw_root: Path,
               session_name: str, recent_context: str,
               runner: Callable, read_text: Callable,
               now: datetime | None = None,
               build_version: str | None = None,
               source_revision: str | None = None) -> dict | None:
    """One read-only Authserver observation cycle.

    A live tmux pane with no authserver descendant is a valid absent-process
    observation. Exact exit cause remains UNKNOWN unless stronger evidence is
    supplied by a future authoritative source.
    """
    current_time = _utc(now)
    auth_snapshot, tmux_alive = probe.probe_auth_tmux(session_name, runner, read_text)
    state = checkpoint.IncidentCheckpoint(state_root, "Authserver")
    expected = expected_maintenance.ExpectedMaintenanceStore(state_root, "Authserver")

    def evaluate_expected(previous: dict, current: dict, incident: dict):
        return expected.evaluate_unlocked(previous, current, incident, current_time)

    def finalize_expected(decision: dict):
        expected.finalize_expected_unlocked(decision)

    def render(incident: dict):
        _decorate_common(
            incident,
            current_time,
            recent_context,
            "tmux/process identity + supplied bounded context",
            "external tmux observation has no authoritative child wait status",
            build_version,
            source_revision,
        )
        artifacts = {
            "auth-process.json": auth_snapshot,
            "recent-context.txt": recent_context,
        }
        return _write_owned_incident(
            crash_root,
            raw_root,
            incident,
            current_time,
            artifacts,
            {"service": "Authserver", "supervisor": "tmux/bash", "session_name": session_name},
        )

    return state.process_auth(
        auth_snapshot,
        tmux_alive,
        topology.auth_incident,
        render,
        expected_evaluate=evaluate_expected,
        expected_finalize=finalize_expected,
    )
