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
