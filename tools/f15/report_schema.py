#!/usr/bin/env python3
"""F15 event report schema v1: a pure builder, canonical form and validator.

DRAFT, SOURCE-ONLY, UNSELECTED. It turns ONE observation from the disposable
mode-A producer (tools/f15/r1r3_owned_child_producer.py) into an in-memory
JSON document, and checks such documents. It writes nothing, opens nothing,
spawns nothing and sends nothing: there is no report path, broker, restart,
journal or file adapter here (R2/R4 and owner R0 gates, #162/#170).

Rules the validator enforces. They check INTERNAL CONSISTENCY only: whoever
can write a whole document can also write a fake attestation string, role,
prefix declaration, source_sha or time and recompute the digest, so
validate() cannot tell whether a kernel wait really happened or who wrote the
document. A trusted producer/writer boundary is future owner-gated R4 work.
Malformed or hostile input (bad UTF-8/JSON, over-long integers, nesting
deeper than MAX_DEPTH, cycles) is refused, never raised as another error:
  * Closed schema: every object has an exact key set; unknown keys, floats,
    NaN, duplicate JSON keys and non-canonical bytes are refused.
  * No log message text at all ("message_text_omitted"): records carry only
    position, stream, severity facts and the retained length. Log lines can
    contain player names, account data or paths; a redaction policy does not
    exist yet, so v1 has nowhere to put text.
  * `event_types` must EQUAL the set derived from the facts: a crash cannot
    be omitted and nothing unsupported can be listed.
  * `crash` only from the kernel exit attestation with a fatal signal, never
    from text. The exit classification is recomputed, not trusted. A fatal
    signal can never be declared "planned".
  * A severity other than "unknown" requires `severity_source ==
    "declared_prefix"` and the caller's DECLARED prefix mode; a stream hint
    never makes a severity and never makes an event.
  * `launch_mode` is "A-disposable" only: no document can claim a real
    Worldserver/Authserver launch mode (Q3/S4 closed).
  * `integrity.digest` is SHA-256 over the canonical bytes without the
    integrity block. It proves the bytes were not changed after sealing; it
    does NOT prove who sealed them (#151).
Burst/rate policy is NOT reimplemented here: the two `declared_*_lines`
events only say such lines exist in this observation. Rate limiting belongs
to the S4b model (#140).
"""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = "naxx-f15-event"
SCHEMA_VERSION = 1
LAUNCH_MODE = "A-disposable"
PRODUCER_TOOL = "tools/f15/r1r3_owned_child_producer.py"
CANONICALIZATION = "naxx-f15-json-v1"
MAX_REPORT_BYTES = 1024 * 1024
MAX_RECORDS = 4096
# Deepest legal path is $.streams.<name>.records[i].<key> (5 containers);
# anything deeper is refused before parsing or walking, never recursed into.
MAX_DEPTH = 8
# The producer keeps <= 8192 raw bytes per line; invalid bytes decode to
# U+FFFD (3 UTF-8 bytes each), so the retained length can reach 3x that.
MAX_MESSAGE_BYTES = 3 * 8192

# Mirrors of the producer's constants (a test checks they stay equal). The
# schema module deliberately does not import the producer.
ATTEST_EXIT = "owned-child-waitid"
ATTEST_STREAMS = {"stdout": "owned-stdout-pipe", "stderr": "owned-stderr-pipe"}
HINT_SOURCE = "pinned_console_route"
HINTS = {"stderr": "error_or_fatal_candidate", "stdout": "below_error_candidate"}
ROLES = ("worldserver", "authserver")
STDIN_MODES = ("devnull", "held_open")
# Linux numbers: SIGILL 4, SIGABRT 6, SIGBUS 7, SIGFPE 8, SIGSEGV 11, SIGSYS 31.
FATAL_SIGNAL_NUMBERS = frozenset({4, 6, 7, 8, 11, 31})
# The only signals a harness may declare as a planned stop: SIGINT, SIGTERM.
PLANNABLE_SIGNAL_NUMBERS = frozenset({2, 15})
RECORD_SEVERITIES = ("FATAL", "ERROR", "WARN", "unknown")
EVENT_ORDER = ("crash", "exit_unexpected", "source_incomplete",
               "declared_error_lines", "declared_warning_lines")
TEXT_POLICY = "message_text_omitted"

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

KEYS = {
    "": {"schema", "schema_version", "event_types", "producer", "declared",
         "incarnation", "exit", "streams", "limits", "time", "integrity"},
    "producer": {"tool", "source_sha", "launch_mode"},
    "declared": {"kind", "role", "stdin_mode", "prefix_loglevel", "prefix_timestamp"},
    "incarnation": {"boot_id", "pid", "starttime", "ppid", "pgid"},
    "exit": {"attestation", "kind", "exit_code", "signal_number", "planned",
             "classification"},
    "streams": {"stdout", "stderr"},
    "stream": {"attestation", "stream", "eof", "deadline_hit", "source_incomplete",
               "bytes_drained", "bytes_retained", "bytes_framing", "bytes_dropped",
               "ansi_sequences_stripped", "lines_terminated", "final_partial_line",
               "lines_unclassified", "lines_below_warn", "lines_blank",
               "records_dropped", "records"},
    "record": {"line", "stream", "severity", "severity_source", "severity_hint",
               "hint_source", "truncated", "message_bytes"},
    "limits": {"cross_stream_order", "stdout_may_be_block_buffered",
               "stdout_tail_lost_on_crash_possible", "group_scan_complete",
               "group_members_seen_after_exit", "text_policy"},
    "time": {"recorded_utc", "use"},
    "integrity": {"algorithm", "canonicalization", "digest", "proves"},
}
_COUNTERS = ("bytes_drained", "bytes_retained", "bytes_framing", "bytes_dropped",
             "ansi_sequences_stripped", "lines_terminated", "lines_unclassified",
             "lines_below_warn", "lines_blank", "records_dropped")


class ReportRefused(ValueError):
    """The observation cannot be expressed as a valid v1 report."""


# ---------------------------------------------------------------- canonical form
def _check_json_types(value, path="$", depth=0):
    if value is None or isinstance(value, (bool, str)):
        return
    if type(value) is int:
        return
    if isinstance(value, (list, dict)) and depth >= MAX_DEPTH:
        # Also stops a self-referencing object: no unbounded recursion.
        raise ReportRefused(f"{path}: nesting deeper than {MAX_DEPTH}")
    if isinstance(value, list):
        for i, item in enumerate(value):
            _check_json_types(item, f"{path}[{i}]", depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ReportRefused(f"{path}: non-string key")
            _check_json_types(item, f"{path}.{key}", depth + 1)
        return
    raise ReportRefused(f"{path}: type {type(value).__name__} is not allowed")


def _max_nesting(raw: bytes) -> int:
    """Deepest [ / { nesting in JSON bytes, ignoring brackets inside strings.
    Iterative, so hostile input cannot exhaust the Python stack."""
    depth = deepest = 0
    in_string = escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:            # backslash
                escaped = True
            elif byte == 0x22:            # closing quote
                in_string = False
        elif byte == 0x22:
            in_string = True
        elif byte in (0x5B, 0x7B):        # [ {
            depth += 1
            deepest = max(deepest, depth)
        elif byte in (0x5D, 0x7D):        # ] }
            depth -= 1
    return deepest


def canonical_bytes(doc: dict) -> bytes:
    """Sorted keys, no whitespace, UTF-8, integers only."""
    _check_json_types(doc)
    return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(doc: dict) -> str:
    body = {k: v for k, v in doc.items() if k != "integrity"}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def seal(doc: dict) -> dict:
    sealed = {k: v for k, v in doc.items() if k != "integrity"}
    sealed["integrity"] = {"algorithm": "sha256", "canonicalization": CANONICALIZATION,
                           "digest": digest(sealed), "proves": "integrity_only"}
    return sealed


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReportRefused(f"duplicate key {key!r}")
        out[key] = value
    return out


def _no_float(text):
    raise ReportRefused(f"non-integer number {text!r}")


def parse(raw: bytes) -> dict:
    """Strictly parse stored bytes; they must be the exact canonical form of a
    valid document."""
    if not isinstance(raw, bytes) or len(raw) > MAX_REPORT_BYTES:
        raise ReportRefused("report must be bytes within the size limit")
    if _max_nesting(raw) > MAX_DEPTH:
        raise ReportRefused(f"nesting deeper than {MAX_DEPTH}")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                         parse_float=_no_float, parse_constant=_no_float)
    except ReportRefused:
        raise
    except (ValueError, RecursionError) as exc:
        # Malformed input only: bad UTF-8 or JSON (both ValueError), an
        # over-long integer literal (ValueError from the int digit limit),
        # or nesting the pre-scan missed (RecursionError, fail closed).
        raise ReportRefused(f"not JSON: {type(exc).__name__}") from exc
    if not isinstance(doc, dict):
        raise ReportRefused("top level must be an object")
    errors = validate(doc)
    if errors:
        raise ReportRefused("; ".join(errors))
    if canonical_bytes(doc) != raw:
        raise ReportRefused("bytes are not the canonical form")
    return doc


# ---------------------------------------------------------------- derivations
def classify_exit(kind: str, exit_code, signal_number, planned: bool) -> str:
    if kind == "exited":
        return "normal_exit" if exit_code == 0 else "nonzero_exit_not_signal"
    if planned:
        return "planned_signal"
    if signal_number in FATAL_SIGNAL_NUMBERS:
        return "fatal_signal"
    return "signal_requires_policy"


def derive_event_types(doc: dict) -> list[str]:
    """The only event set the facts support, in EVENT_ORDER."""
    found = set()
    cls = doc["exit"]["classification"]
    if cls == "fatal_signal":
        found.add("crash")
    elif cls in ("nonzero_exit_not_signal", "signal_requires_policy"):
        found.add("exit_unexpected")
    for name in ("stdout", "stderr"):
        s = doc["streams"][name]
        if s["source_incomplete"]:
            found.add("source_incomplete")
        for r in s["records"]:
            if r["severity"] in ("ERROR", "FATAL"):
                found.add("declared_error_lines")
            elif r["severity"] == "WARN":
                found.add("declared_warning_lines")
    return [e for e in EVENT_ORDER if e in found]


# ---------------------------------------------------------------- validator
def _keys(errors, obj, kind, path):
    if not isinstance(obj, dict):
        errors.append(f"{path}: must be an object")
        return False
    want = KEYS[kind]
    if set(obj) != want:
        extra, missing = sorted(set(obj) - want), sorted(want - set(obj))
        errors.append(f"{path}: keys differ (unexpected {extra}, missing {missing})")
        return False
    return True


def _int(errors, value, path, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        errors.append(f"{path}: must be an integer in [{lo}, {hi}]")
        return False
    return True


def _bool(errors, value, path):
    if type(value) is not bool:
        errors.append(f"{path}: must be a boolean")
        return False
    return True


def _const(errors, value, expected, path):
    if type(value) is not type(expected) or value != expected:
        errors.append(f"{path}: must be {expected!r}")
        return False
    return True


def _enum(errors, value, options, path):
    if not isinstance(value, str) or value not in options:
        errors.append(f"{path}: must be one of {list(options)}")
        return False
    return True


def _match(errors, value, pattern, path):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        errors.append(f"{path}: bad format")
        return False
    return True


def _stream(errors, s, name, declared_prefix):
    p = f"streams.{name}"
    if not _keys(errors, s, "stream", p):
        return False
    ok = _const(errors, s["attestation"], ATTEST_STREAMS[name], f"{p}.attestation")
    ok &= _const(errors, s["stream"], name, f"{p}.stream")
    for flag in ("eof", "deadline_hit", "source_incomplete", "final_partial_line"):
        ok &= _bool(errors, s[flag], f"{p}.{flag}")
    for counter in _COUNTERS:
        ok &= _int(errors, s[counter], f"{p}.{counter}", 0, 2 ** 53)
    if not ok:
        return False
    if s["source_incomplete"] != (s["deadline_hit"] and not s["eof"]):
        errors.append(f"{p}.source_incomplete: must equal deadline_hit and not eof")
    if s["bytes_drained"] != s["bytes_retained"] + s["bytes_framing"] + s["bytes_dropped"]:
        errors.append(f"{p}: drained != retained + framing + dropped")
    if s["bytes_framing"] != s["lines_terminated"]:
        errors.append(f"{p}: one framing byte per terminated line")
    if s["lines_below_warn"] and not declared_prefix:
        errors.append(f"{p}.lines_below_warn: levels are only decoded in declared prefix mode")
    records = s["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        errors.append(f"{p}.records: must be a list of at most {MAX_RECORDS}")
        return False
    last_line = s["lines_terminated"] + (1 if s["final_partial_line"] else 0)
    previous = 0
    for i, r in enumerate(records):
        rp = f"{p}.records[{i}]"
        if not _keys(errors, r, "record", rp):
            continue
        rok = _int(errors, r["line"], f"{rp}.line", 1, 2 ** 53)
        rok &= _const(errors, r["stream"], name, f"{rp}.stream")
        rok &= _enum(errors, r["severity"], RECORD_SEVERITIES, f"{rp}.severity")
        rok &= _enum(errors, r["severity_source"], ("declared_prefix", "none"),
                     f"{rp}.severity_source")
        rok &= _const(errors, r["severity_hint"], HINTS[name], f"{rp}.severity_hint")
        rok &= _const(errors, r["hint_source"], HINT_SOURCE, f"{rp}.hint_source")
        rok &= _bool(errors, r["truncated"], f"{rp}.truncated")
        rok &= _int(errors, r["message_bytes"], f"{rp}.message_bytes", 0, MAX_MESSAGE_BYTES)
        if not rok:
            continue
        if not previous < r["line"] <= last_line:
            errors.append(f"{rp}.line: must increase and lie within the stream's lines")
        previous = r["line"]
        decoded = r["severity"] != "unknown"
        if decoded != (r["severity_source"] == "declared_prefix"):
            errors.append(f"{rp}: a severity needs severity_source declared_prefix, and only then")
        if decoded and not declared_prefix:
            errors.append(f"{rp}: severity decoded without a declared prefix mode")
    return True


def validate(doc) -> list[str]:
    """All violations found; an empty list means valid."""
    errors: list[str] = []
    try:
        size = len(canonical_bytes(doc))
    except (ReportRefused, ValueError, TypeError, RecursionError) as exc:
        return [f"$: {type(exc).__name__}: {exc}"]
    if size > MAX_REPORT_BYTES:
        return ["$: report exceeds the size limit"]
    if not _keys(errors, doc, "", "$"):
        return errors
    _const(errors, doc["schema"], SCHEMA, "schema")
    _const(errors, doc["schema_version"], SCHEMA_VERSION, "schema_version")

    prod = doc["producer"]
    if _keys(errors, prod, "producer", "producer"):
        _const(errors, prod["tool"], PRODUCER_TOOL, "producer.tool")
        _match(errors, prod["source_sha"], _HEX40, "producer.source_sha")
        _const(errors, prod["launch_mode"], LAUNCH_MODE, "producer.launch_mode")

    declared_prefix = False
    dec = doc["declared"]
    if _keys(errors, dec, "declared", "declared"):
        _const(errors, dec["kind"], "caller_declaration", "declared.kind")
        _enum(errors, dec["role"], ROLES, "declared.role")
        _enum(errors, dec["stdin_mode"], STDIN_MODES, "declared.stdin_mode")
        if _bool(errors, dec["prefix_loglevel"], "declared.prefix_loglevel"):
            declared_prefix = dec["prefix_loglevel"]
        if (_bool(errors, dec["prefix_timestamp"], "declared.prefix_timestamp")
                and dec["prefix_timestamp"] and not declared_prefix):
            errors.append("declared.prefix_timestamp: needs declared prefix_loglevel")

    inc = doc["incarnation"]
    if _keys(errors, inc, "incarnation", "incarnation"):
        _match(errors, inc["boot_id"], _UUID, "incarnation.boot_id")
        ok = _int(errors, inc["pid"], "incarnation.pid", 1, 4194304)
        _int(errors, inc["starttime"], "incarnation.starttime", 0, 2 ** 63)
        _int(errors, inc["ppid"], "incarnation.ppid", 1, 4194304)
        ok &= _int(errors, inc["pgid"], "incarnation.pgid", 1, 4194304)
        if ok and inc["pgid"] != inc["pid"]:
            errors.append("incarnation.pgid: mode A starts a new session, so pgid == pid")

    exit_ok = False
    ex = doc["exit"]
    if _keys(errors, ex, "exit", "exit"):
        exit_ok = _const(errors, ex["attestation"], ATTEST_EXIT, "exit.attestation")
        exit_ok &= _enum(errors, ex["kind"], ("exited", "killed", "dumped"), "exit.kind")
        exit_ok &= _bool(errors, ex["planned"], "exit.planned")
        if exit_ok and ex["kind"] == "exited":
            exit_ok &= _int(errors, ex["exit_code"], "exit.exit_code", 0, 255)
            exit_ok &= _const(errors, ex["signal_number"], None, "exit.signal_number")
            if ex["planned"]:
                errors.append("exit.planned: only a signal stop can be planned")
                exit_ok = False
        elif exit_ok:
            exit_ok &= _const(errors, ex["exit_code"], None, "exit.exit_code")
            exit_ok &= _int(errors, ex["signal_number"], "exit.signal_number", 1, 64)
            if exit_ok and ex["planned"] and ex["signal_number"] not in PLANNABLE_SIGNAL_NUMBERS:
                errors.append("exit.planned: only SIGINT/SIGTERM may be declared planned")
                exit_ok = False
        if exit_ok:
            expected = classify_exit(ex["kind"], ex["exit_code"], ex["signal_number"],
                                     ex["planned"])
            if ex["classification"] != expected:
                errors.append(f"exit.classification: facts give {expected!r}")
                exit_ok = False

    streams_ok = False
    st = doc["streams"]
    if _keys(errors, st, "streams", "streams"):
        before = len(errors)
        for name in ("stdout", "stderr"):
            _stream(errors, st[name], name, declared_prefix)
        streams_ok = len(errors) == before

    lim = doc["limits"]
    if _keys(errors, lim, "limits", "limits"):
        _const(errors, lim["cross_stream_order"], "unknown", "limits.cross_stream_order")
        _const(errors, lim["stdout_may_be_block_buffered"], True,
               "limits.stdout_may_be_block_buffered")
        if (_bool(errors, lim["stdout_tail_lost_on_crash_possible"],
                  "limits.stdout_tail_lost_on_crash_possible") and exit_ok
                and lim["stdout_tail_lost_on_crash_possible"]
                != (ex["kind"] in ("killed", "dumped"))):
            errors.append("limits.stdout_tail_lost_on_crash_possible: true exactly "
                          "for a signal death")
        _bool(errors, lim["group_scan_complete"], "limits.group_scan_complete")
        _int(errors, lim["group_members_seen_after_exit"],
             "limits.group_members_seen_after_exit", 0, 4194304)
        _const(errors, lim["text_policy"], TEXT_POLICY, "limits.text_policy")

    tm = doc["time"]
    if _keys(errors, tm, "time", "time"):
        _match(errors, tm["recorded_utc"], _UTC, "time.recorded_utc")
        _const(errors, tm["use"], "display_only", "time.use")

    events = doc["event_types"]
    if (not isinstance(events, list) or not events
            or not all(isinstance(e, str) for e in events)):
        errors.append("event_types: must be a non-empty list of names")
    elif exit_ok and streams_ok:
        expected = derive_event_types(doc)
        if events != expected:
            errors.append(f"event_types: facts support exactly {expected}")

    integ = doc["integrity"]
    if _keys(errors, integ, "integrity", "integrity"):
        _const(errors, integ["algorithm"], "sha256", "integrity.algorithm")
        _const(errors, integ["canonicalization"], CANONICALIZATION,
               "integrity.canonicalization")
        _const(errors, integ["proves"], "integrity_only", "integrity.proves")
        if (_match(errors, integ["digest"], _HEX64, "integrity.digest")
                and integ["digest"] != digest(doc)):
            errors.append("integrity.digest: does not match the canonical body")
    return errors


# ---------------------------------------------------------------- builder
def _stream_doc(fact) -> dict:
    return {
        "attestation": fact.attestation, "stream": fact.stream, "eof": fact.eof,
        "deadline_hit": fact.deadline_hit, "source_incomplete": fact.source_incomplete,
        **{c: getattr(fact, c) for c in _COUNTERS},
        "final_partial_line": fact.final_partial_line,
        "records": [{
            "line": r.line, "stream": r.stream, "severity": r.severity,
            "severity_source": r.severity_source, "severity_hint": r.severity_hint,
            "hint_source": r.hint_source, "truncated": r.truncated,
            # Length only: the text itself never enters the report.
            "message_bytes": len(r.message.encode("utf-8")),
        } for r in fact.records],
    }


def build_report(observation, *, prefix_loglevel: bool, prefix_timestamp: bool,
                 stdin_mode: str, producer_source_sha: str,
                 recorded_utc: str) -> dict | None:
    """A sealed v1 document for one producer Observation, or None when the
    facts support no event (e.g. a clean exit with no declared WARN+ line).
    The prefix and stdin arguments are the caller's declarations, recorded
    as such. Pure: no I/O."""
    ex, err, out = observation.exit, observation.stderr, observation.stdout
    if out is None:
        raise ReportRefused("v1 needs both owned streams")
    inc = ex.incarnation
    if ex.attestation != ATTEST_EXIT or err.incarnation != inc or out.incarnation != inc:
        raise ReportRefused("exit and streams are not bound to one attested incarnation")
    if ex.planned and ex.signal_number not in PLANNABLE_SIGNAL_NUMBERS:
        raise ReportRefused("only SIGINT/SIGTERM may be declared planned")
    doc = {
        "schema": SCHEMA, "schema_version": SCHEMA_VERSION, "event_types": [],
        "producer": {"tool": PRODUCER_TOOL, "source_sha": producer_source_sha,
                     "launch_mode": LAUNCH_MODE},
        "declared": {"kind": "caller_declaration", "role": observation.role,
                     "stdin_mode": stdin_mode, "prefix_loglevel": prefix_loglevel,
                     "prefix_timestamp": prefix_timestamp},
        "incarnation": {"boot_id": inc.boot_id, "pid": inc.pid,
                        "starttime": inc.starttime, "ppid": inc.ppid, "pgid": inc.pgid},
        "exit": {"attestation": ex.attestation, "kind": ex.kind,
                 "exit_code": ex.exit_code, "signal_number": ex.signal_number,
                 "planned": ex.planned, "classification": ex.classification},
        "streams": {"stdout": _stream_doc(out), "stderr": _stream_doc(err)},
        "limits": {
            "cross_stream_order": observation.cross_stream_order,
            "stdout_may_be_block_buffered": observation.stdout_may_be_block_buffered,
            "stdout_tail_lost_on_crash_possible":
                observation.stdout_tail_lost_on_crash_possible,
            "group_scan_complete": observation.group_scan_complete,
            "group_members_seen_after_exit":
                len(observation.group_members_seen_after_exit),
            "text_policy": TEXT_POLICY},
        "time": {"recorded_utc": recorded_utc, "use": "display_only"},
    }
    try:
        doc["event_types"] = derive_event_types(doc)
    except (KeyError, TypeError) as exc:
        raise ReportRefused(f"malformed observation: {exc}") from exc
    if not doc["event_types"]:
        return None
    sealed = seal(doc)
    errors = validate(sealed)
    if errors:
        raise ReportRefused("; ".join(errors))
    return sealed
