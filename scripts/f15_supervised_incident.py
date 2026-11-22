#!/usr/bin/env python3
"""Explicit disposable/new child supervision composed with private F15 reports.

Not an installed PM2/tmux adapter. Never attaches to or restarts a service.
"""
from datetime import datetime, timezone
from pathlib import Path

import f15_incident_pipeline as pipeline
import f15_process_supervisor as supervisor

MAX_STREAM_BYTES = 65536


class PostExitReportFailure(OSError):
    """Report failed after a directly observed child exit; public text is generic."""
    def __init__(self, exit_code):
        super().__init__("report publication failed after observed child exit")
        self.exit_code = exit_code


def launcher_status(exit_code):
    return exit_code if exit_code >= 0 else 128 - exit_code


def supervise_and_report(output_root, archive_root, crash_root, raw_root, service,
                         command, *, execute=False, poll_seconds=0.2,
                         build_version=None, source_revision=None, forward_stops=False, stop_timeout=None):
    if execute is not True:
        raise supervisor.Refused("explicit child execution authorization required")
    try:
        run, outcome = supervisor.supervise(output_root, archive_root, service,
                                            command, poll_seconds, forward_stops=forward_stops, stop_timeout=stop_timeout)
    except supervisor.ExitReceiptFailure as exc:
        # The wait was observed; try the independent bundle/report sink without
        # relaunching or falsely claiming the original receipt was durable.
        run, outcome = exc.run, exc.outcome
    import f15_raw_evidence_bundle as bundles
    import f15_crash_report_renderer as renderer
    started = _health_write(run, "started", outcome)
    try:
        result = _report_observed_run(run, outcome, crash_root, raw_root, service,
                                      build_version, source_revision)
        completed = _health_write(run, "report-complete", outcome)
        outcome["diagnostic_health_receipt_status"] = "complete" if started and completed else "failed"
        return result
    except (OSError, ValueError, bundles.Refused, renderer.Refused) as exc:
        _health_write(run, "report-failed", outcome)
        raise PostExitReportFailure(outcome["exit_code"]) from exc


def _health_write(run, state, outcome):
    """Independent immutable private receipt; failure never replaces child status."""
    import json
    import f15_crash_report_renderer as renderer
    try:
        renderer._private_dir(Path(run))
        data = {"version": 1, "state": state, "exit_code": outcome["exit_code"],
                "capture": outcome["capture"],
                "exit_receipt_status": outcome.get("exit_receipt_status", "complete")}
        renderer._exclusive_write(Path(run) / ("diagnostics-" + state + ".json"),
                                  (json.dumps(data, sort_keys=True) + "\n").encode("utf-8"))
        return True
    except (OSError, ValueError, renderer.Refused):
        return False


def _read_health_receipt(path):
    import os
    import stat
    import f15_crash_report_renderer as renderer
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > 4096:
            raise renderer.Refused("health receipt must be bounded private regular file")
        data = os.pread(fd, 4097, 0)
        if len(data) != st.st_size:
            raise renderer.Refused("health receipt changed during read")
        return data
    finally:
        os.close(fd)


def diagnostic_health(run):
    """No process liveness claim; report/receipt health only. Never creates files."""
    import json
    import f15_raw_evidence_bundle as bundles
    import f15_crash_report_renderer as renderer
    root = bundles._private_dir(Path(run), create=False)
    records = {}
    keys = {"version", "state", "exit_code", "capture", "exit_receipt_status"}
    for state in ("started", "report-complete", "report-failed"):
        path = root / ("diagnostics-" + state + ".json")
        if path.with_name(path.name + ".pending").exists() or path.with_name(path.name + ".pending").is_symlink():
            return "UNKNOWN_OR_PARTIAL", False
        if path.exists() or path.is_symlink():
            data = _read_health_receipt(path)
            if len(data) > 4096:
                return "UNKNOWN_OR_PARTIAL", False
            record = json.loads(data.decode("utf-8"))
            if (not isinstance(record, dict) or set(record) != keys or record["version"] != 1
                or type(record["version"]) is not int or record["state"] != state or type(record["exit_code"]) is not int):
                return "UNKNOWN_OR_PARTIAL", False
            records[state] = record
    started = records.get("started")
    completed = records.get("report-complete")
    failed = records.get("report-failed")
    if failed and completed:
        return "CONFLICTING_RECEIPTS", False
    if failed:
        return "REPORT_FAILED", False
    if not started or not completed:
        return "UNKNOWN_OR_PARTIAL", False
    if any(started[k] != completed[k] for k in keys - {"state"}):
        return "CONFLICTING_RECEIPTS", False
    if completed["capture"] != "complete_for_observed_run" or completed["exit_receipt_status"] != "complete":
        return "REPORT_COMPLETE_WITH_GAPS", False
    return "REPORT_COMPLETE", True


def _report_observed_run(run, outcome, crash_root, raw_root, service,
                         build_version, source_revision):
    # Only the newly created, privately owned run is read. Never read owner logs.
    context, gaps = [], []
    if outcome.get("stop_escalated"):
        gaps.append("owned child killed after explicitly configured stop timeout")
    if outcome.get("exit_receipt_status") == "failed":
        gaps.append("supervisor exit receipt persistence failed; wait evidence recovered from memory")
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


def main(argv=None):
    """Operator entry point; deliberately separate from observation-only CLI."""
    import argparse
    import sys
    import f15_raw_evidence_bundle as bundles
    import f15_crash_report_renderer as renderer
    import f15_operator_collector as collector

    parser = argparse.ArgumentParser(description="F15 explicit new-child diagnostics or completed-report recovery; no service installation")
    modes = parser.add_subparsers(dest="mode", required=True)
    launch = modes.add_parser("supervise")
    launch.add_argument("--output-root", required=True)
    launch.add_argument("--archive-root", required=True)
    launch.add_argument("--crash-root", required=True)
    launch.add_argument("--raw-root", required=True)
    launch.add_argument("--service", choices=sorted(supervisor.SERVICES), required=True)
    launch.add_argument("--execute", action="store_true")
    launch.add_argument("--launcher-mode", action="store_true", help="forward TERM/INT to owned child; return child status (not installed service integration)")
    launch.add_argument("--stop-timeout", type=float, help="opt-in seconds before killing owned child after TERM/INT; requires launcher mode")
    launch.add_argument("--build-version")
    launch.add_argument("--source-revision")
    launch.add_argument("command", nargs=argparse.REMAINDER)
    recover = modes.add_parser("recover")
    recover.add_argument("--crash-root", required=True)
    recover.add_argument("--raw-root", required=True)
    recover.add_argument("--incident-id", required=True)
    health = modes.add_parser("health")
    health.add_argument("--run-root", required=True)
    args = parser.parse_args(argv)
    if args.mode == "supervise":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not args.execute or not command:
            print("F15 REFUSED: explicit --execute and child command required", file=sys.stderr)
            return 2
    try:
        if args.mode == "health":
            label, ok = diagnostic_health(args.run_root)
            print("F15 diagnostics: " + label)
            return 0 if ok else 2
        if args.mode == "recover":
            recover_report(args.crash_root, args.raw_root, args.incident_id)
            print("F15 report recovery completed")
            return 0
        _, outcome, _ = supervise_and_report(args.output_root, args.archive_root,
            args.crash_root, args.raw_root, args.service, command, execute=True,
            build_version=args.build_version, source_revision=args.source_revision,
            forward_stops=args.launcher_mode, stop_timeout=args.stop_timeout)
        print("F15 supervised exit report completed")
        receipt_failed = outcome.get("exit_receipt_status") == "failed"
        if receipt_failed:
            print("F15 exit receipt persistence failed; inspect retained private evidence", file=sys.stderr)
        health_failed = outcome.get("diagnostic_health_receipt_status") == "failed"
        if health_failed:
            print("F15 diagnostic health receipt failed; inspect retained private evidence", file=sys.stderr)
        if args.launcher_mode:
            return launcher_status(outcome["exit_code"])
        # Diagnostic tool status, matching the existing supervisor CLI. This is
        # not a transparent launcher replacement for PM2/tmux child exit codes.
        return 0 if outcome["exit_code"] == 0 and outcome["capture_error_type"] is None and not receipt_failed and not health_failed else 2
    except PostExitReportFailure as exc:
        print("F15 report publication failed; inspect retained private evidence", file=sys.stderr)
        return launcher_status(exc.exit_code) if args.mode == "supervise" and args.launcher_mode else 2
    except (OSError, ValueError, bundles.Refused, renderer.Refused, collector.Refused):
        print("F15 REFUSED: operation rejected; inspect retained private evidence", file=sys.stderr)
        return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
