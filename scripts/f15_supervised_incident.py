#!/usr/bin/env python3
"""Explicit disposable/new child supervision composed with private F15 reports.

Not an installed PM2/tmux adapter. Never attaches to or restarts a service.
"""
from datetime import datetime, timezone
from pathlib import Path

import f15_incident_pipeline as pipeline
import f15_process_supervisor as supervisor

MAX_STREAM_BYTES = 65536


def supervise_and_report(output_root, archive_root, crash_root, raw_root, service,
                         command, *, execute=False, poll_seconds=0.2,
                         build_version=None, source_revision=None):
    if execute is not True:
        raise supervisor.Refused("explicit child execution authorization required")
    run, outcome = supervisor.supervise(output_root, archive_root, service,
                                        command, poll_seconds)
    # Only the newly created, privately owned run is read. Never read owner logs.
    context, gaps = [], []
    for name in ("stdout.raw", "stderr.raw"):
        with (run / name).open("rb") as stream:
            data = stream.read(MAX_STREAM_BYTES + 1)
        if len(data) > MAX_STREAM_BYTES:
            # Do not trim before redaction: an unlabelled secret fragment could
            # survive. Keep the full original privately and report the gap.
            gaps.append(name + " exceeds rendered-input bound; original retained")
        else:
            context.append(name + ":\n" + data.decode("utf-8", "replace"))
    code = outcome["exit_code"]
    now = datetime.now(timezone.utc)
    incident = {
        "service": service, "incident_id": service.lower() + "-" + run.name,
        "pid": outcome["pid"], "exit_code": code if code >= 0 else None,
        "signal": -code if code < 0 else None,
        "classification": "SIGNAL_EXIT" if code < 0 else ("CLEAN_EXIT" if code == 0 else "NONZERO_EXIT"),
        "classification_evidence": "direct child wait status; signal/nonzero alone does not prove an engine defect",
        "supervisor": "F15 explicit child supervisor (not PM2/tmux installed integration)",
        "restart_evidence": "no restart requested or performed",
        "notes": "Original console and lifecycle receipts retained in private supervised run: " + str(run),
    }
    pipeline._decorate_common(incident, now, "\n".join(context), outcome["capture"],
                              "; ".join(gaps + ([outcome["capture_error_type"]] if outcome["capture_error_type"] else [])) or "none observed",
                              build_version, source_revision)
    report = pipeline._write_owned_incident(Path(crash_root), Path(raw_root), incident, now,
                                            {"supervisor-exit.json": outcome},
                                            {"service": service, "source": "explicit-child-wait"})
    return run, outcome, report


def recover_report(crash_root, raw_root, incident_id):
    """Retry publication from completed private evidence only; never spawn.

    Does not recover an incomplete bundle or a failure before bundle publication.
    Existing mismatched reports and pending files retain fail-closed semantics.
    """
    import hashlib
    import json
    import f15_raw_evidence_bundle as bundles
    import f15_crash_report_renderer as renderer

    bundle = bundles.find_bundle(Path(raw_root), incident_id)
    if bundle is None:
        raise bundles.Refused("completed incident bundle required")
    manifest, _ = bundles._verify_bundle(bundle)
    if manifest.get("provenance", {}).get("source") != "explicit-child-wait":
        raise bundles.Refused("supervised incident provenance required")
    records = [rec for rec in manifest["artifacts"] if rec["name"] == "report-input.json"]
    if len(records) != 1 or records[0]["size"] > bundles.MAX_ARTIFACT_BYTES:
        raise bundles.Refused("one bounded report input required")
    # Descriptor-bound private read; compare the bytes actually used against
    # the verified manifest rather than trusting a later pathname reread.
    data, _ = renderer._read_private_report(bundle / "report-input.json")
    if len(data) != records[0]["size"] or hashlib.sha256(data).hexdigest() != records[0]["sha256"]:
        raise bundles.Refused("report input changed during recovery")
    incident = json.loads(data.decode("utf-8"))
    renderer.validate_incident(incident)
    if incident["incident_id"] != incident_id or incident["service"] != manifest["provenance"].get("service"):
        raise bundles.Refused("incident identity differs from provenance")
    if not renderer.STAMP_RE.fullmatch(str(incident.get("filename_timestamp", ""))):
        raise bundles.Refused("original report timestamp required")
    incident["raw_evidence_ref"] = str(bundle)
    return renderer.ensure_report(Path(crash_root), incident)
