#!/usr/bin/env python3
"""F15 private crash-report renderer/sink.

Consumes normalized incident facts only. It does not inspect, launch, signal,
restart or attach to Worldserver/Authserver. A later PM2/tmux adapter may feed
it. Output directory must be private (0700); reports/history are 0600.
"""
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import re
import signal
import stat

SERVICES = {"Worldserver", "Authserver"}
INCIDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
STAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")
MAX_CONTEXT_BYTES = 32768
MAX_FIELD_CHARS = 4096
SECRET_RE = re.compile(
    r"(?i)(password|passwd|token|authorization|api[_-]?key|secret)\s*[:=]\s*\S+"
)

class Refused(RuntimeError):
    pass

def _unknown(value):
    return "UNKNOWN" if value is None or value == "" else str(value)

def _clean(value, limit=MAX_FIELD_CHARS):
    if value is None:
        return "UNKNOWN"
    text = str(value).replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > limit:
        text = text[:limit] + "\n[TRUNCATED]"
    return text

def sanitize_context(value):
    text = _clean(value, MAX_CONTEXT_BYTES * 2)
    raw = text.encode("utf-8", "replace")
    prefix = ""
    if len(raw) > MAX_CONTEXT_BYTES:
        raw = raw[-MAX_CONTEXT_BYTES:]
        prefix = "[TRUNCATED TO MOST RECENT BYTES]\n"
    text = raw.decode("utf-8", "replace")
    return prefix + SECRET_RE.sub(lambda m: m.group(1) + "=[REDACTED]", text)

def _private_dir(path):
    path = Path(path)
    if path.is_symlink():
        raise Refused("crash-log directory may not be a symlink")
    if not path.exists():
        path.mkdir(mode=0o700, parents=False)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Refused("crash-log directory must be mode 0700")
    return path

def _exclusive_write(path, data):
    """Publish one complete private report without ever exposing partial final bytes."""
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    if pending.exists() or pending.is_symlink():
        raise Refused("unfinished crash report pending file requires review")

    flags = (
        os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    fd = os.open(pending, flags, 0o600)
    try:
        written = 0
        while written < len(data):
            n = os.write(fd, data[written:])
            if n <= 0:
                raise Refused("crash report write made no progress")
            written += n
        os.fsync(fd)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("pending crash report failed private regular-file validation")
    finally:
        os.close(fd)

    try:
        # Hard-link publish is no-replace: an existing final name wins rather
        # than being overwritten by a retry/race.
        os.link(pending, path, follow_symlinks=False)
    except FileExistsError as exc:
        raise Refused("crash report destination already exists") from exc

    pending.unlink()
    dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)

    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
        raise Refused("published crash report failed private regular-file validation")

def _ensure_history_once(path, line):
    """Atomically validate, deduplicate and append one history row under one lock."""
    flags = (
        os.O_RDWR | os.O_APPEND | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    fd = os.open(path, flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("Crash-History.txt must be one private regular file")

        raw = os.pread(fd, st.st_size, 0)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Refused("Crash-History.txt is not valid UTF-8") from exc

        rows = text.splitlines(keepends=True)
        count = sum(1 for row in rows if row == line)
        if count > 1:
            raise Refused("duplicate crash history entry")
        if count == 1:
            return

        payload = line.encode("utf-8")
        written = 0
        while written < len(payload):
            n = os.write(fd, payload[written:])
            if n <= 0:
                raise Refused("Crash-History append made no progress")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)

def _signal_number(incident):
    value = incident.get("signal")
    if value in (None, "", 0, "0"):
        try:
            code = int(incident.get("exit_code"))
            return -code if code < 0 else None
        except (TypeError, ValueError):
            return None
    try:
        return abs(int(value))
    except (TypeError, ValueError):
        return None

def _signal_name(number):
    if not number:
        return "UNKNOWN"
    try:
        return signal.Signals(int(number)).name
    except (ValueError, TypeError):
        return "UNKNOWN"

def classification(incident):
    explicit = incident.get("classification")
    if explicit:
        return _clean(explicit, 128)
    if _signal_number(incident):
        return "SIGNAL_EXIT"
    try:
        code = int(incident.get("exit_code"))
    except (TypeError, ValueError):
        return "UNKNOWN"
    if code == 0:
        return "CLEAN_EXIT"
    return "NONZERO_EXIT"

def validate_incident(incident):
    if not isinstance(incident, dict):
        raise Refused("incident must be a mapping")
    if incident.get("service") not in SERVICES:
        raise Refused("service must be Worldserver or Authserver")
    iid = incident.get("incident_id")
    if not isinstance(iid, str) or not INCIDENT_RE.fullmatch(iid):
        raise Refused("invalid incident_id")

def render_report(incident):
    validate_incident(incident)
    sig = _signal_number(incident)
    fields = [
        ("Incident ID", incident["incident_id"]),
        ("Service", incident["service"]),
        ("Observed UTC", _unknown(incident.get("observed_utc"))),
        ("Observed local", _unknown(incident.get("observed_local"))),
        ("Classification", classification(incident)),
        ("Confidence / evidence", _unknown(incident.get("classification_evidence"))),
        ("Exit code", _unknown(incident.get("exit_code"))),
        ("Signal", _unknown(sig)),
        ("Signal name", _signal_name(sig)),
        ("PID", _unknown(incident.get("pid"))),
        ("Replacement PID", _unknown(incident.get("replacement_pid"))),
        ("Parent PID", _unknown(incident.get("ppid"))),
        ("Supervisor", _unknown(incident.get("supervisor"))),
        ("Supervisor pane PID", _unknown(incident.get("supervisor_pane_pid"))),
        ("Replacement supervisor pane PID", _unknown(incident.get("replacement_supervisor_pane_pid"))),
        ("Supervisor probe status", _unknown(incident.get("supervisor_probe_status"))),
        ("Replacement supervisor probe status", _unknown(incident.get("replacement_supervisor_probe_status"))),
        ("Process start", _unknown(incident.get("process_start"))),
        ("Process start epoch ms", _unknown(incident.get("process_start_epoch_ms"))),
        ("Process start ticks", _unknown(incident.get("process_start_ticks"))),
        ("Replacement start ticks", _unknown(incident.get("replacement_start_ticks"))),
        ("Replacement start epoch ms", _unknown(incident.get("replacement_start_epoch_ms"))),
        ("Uptime seconds", _unknown(incident.get("uptime_seconds"))),
        ("Executable", _unknown(incident.get("executable"))),
        ("Build/version", _unknown(incident.get("build_version"))),
        ("Source revision", _unknown(incident.get("source_revision"))),
        ("Last healthy checkpoint", _unknown(incident.get("last_checkpoint"))),
        ("Capture completeness", _unknown(incident.get("capture_status"))),
        ("Capture gaps", _unknown(incident.get("capture_gaps"))),
        ("Restart evidence", _unknown(incident.get("restart_evidence"))),
        ("Native crash evidence", _unknown(incident.get("native_crash_evidence"))),
        ("Raw evidence reference", _unknown(incident.get("raw_evidence_ref"))),
    ]
    lines = ["Cosmic Core — Detailed Crash / Exit Report", "=" * 43, ""]
    lines.extend(f"{name}: {_clean(value)}" for name, value in fields)
    lines += [
        "", "Recent bounded diagnostic context", "-" * 33,
        sanitize_context(incident.get("recent_context")),
        "", "Notes", "-----", _clean(incident.get("notes")), "",
        "This report records observed evidence only. UNKNOWN means the fact was not proven.", ""
    ]
    return "\n".join(lines)


def _history_line(incident, filename, stamp):
    return (
        f"{stamp}\t{incident['service']}\t{incident['incident_id']}\t"
        f"{classification(incident)}\texit={_unknown(incident.get('exit_code'))}\t"
        f"signal={_unknown(_signal_number(incident))}\treport={filename}\n"
    )


def ensure_report(crash_dir, incident):
    """Create report/history once, or reuse exact completed pieces on retry."""
    validate_incident(incident)
    root = _private_dir(crash_dir)
    stamp = incident.get("filename_timestamp")
    if not isinstance(stamp, str) or not STAMP_RE.fullmatch(stamp):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{stamp}-{incident['service']}-{incident['incident_id']}.txt"
    report_path = root / filename
    expected = render_report(incident).encode("utf-8")
    if report_path.exists() or report_path.is_symlink():
        st = report_path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
            raise Refused("existing crash report is not one private regular file")
        if report_path.read_bytes() != expected:
            raise Refused("existing crash report differs from retry")
    else:
        _exclusive_write(report_path, expected)
    history = root / "Crash-History.txt"
    _ensure_history_once(history, _history_line(incident, filename, stamp))
    return report_path

def write_report(crash_dir, incident):
    validate_incident(incident)
    root = _private_dir(crash_dir)
    stamp = incident.get("filename_timestamp")
    if not isinstance(stamp, str) or not STAMP_RE.fullmatch(stamp):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{stamp}-{incident['service']}-{incident['incident_id']}.txt"
    report_path = root / filename
    if report_path.exists() or report_path.is_symlink():
        raise Refused("crash report destination already exists")
    _exclusive_write(report_path, render_report(incident).encode("utf-8"))
    history = root / "Crash-History.txt"
    _ensure_history_once(history, _history_line(incident, filename, stamp))
    return report_path
