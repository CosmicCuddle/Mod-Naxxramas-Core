"""F15 report schema v1 tests. Reports are built from real observations of
disposable Python children (the #170 fixture); no Worldserver/Authserver,
host, service, network, file write or report path is used."""
import ast
import copy
import dataclasses
import json
import os
import signal
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "f15"))
import r1r3_owned_child_producer as m  # noqa: E402
import report_schema as rs  # noqa: E402

FIXTURE = str(Path(__file__).resolve().parent / "r1r3_fixture_child.py")
ALLOW = frozenset({os.path.realpath(sys.executable)})
SHA = "480e08d4d8f08c996718f9c6a8b25df026beef0a"
WHEN = "2026-10-26T15:00:00Z"
SCHEMA_SOURCE = (ROOT / "tools/f15/report_schema.py").read_text()


def observe(mode, *extra, prefix=False, stdin="devnull", **kw):
    kw.setdefault("role", "worldserver")
    p = m.OwnedChildProducer([sys.executable, "-I", FIXTURE, mode, *extra],
                             allowed_executables=ALLOW, prefix_loglevel=prefix,
                             stdin_mode=stdin, **kw)
    p.start()
    return p.observe()


def report_for(obs, prefix=False, stdin="devnull"):
    return rs.build_report(obs, prefix_loglevel=prefix, prefix_timestamp=False,
                           stdin_mode=stdin, producer_source_sha=SHA,
                           recorded_utc=WHEN)


def report(mode, *extra, prefix=False, stdin="devnull", **kw):
    return report_for(observe(mode, *extra, prefix=prefix, stdin=stdin, **kw),
                      prefix=prefix, stdin=stdin)


def walk_keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_keys(v)


class BuiltFromRealDisposableChildren(unittest.TestCase):
    def assertValidRoundTrip(self, doc):
        self.assertEqual(rs.validate(doc), [])
        self.assertEqual(rs.parse(rs.canonical_bytes(doc)), doc)

    def test_real_sigsegv_is_a_crash_from_the_kernel_attestation(self):
        doc = report("sigsegv")
        self.assertValidRoundTrip(doc)
        self.assertEqual(doc["event_types"], ["crash"])
        self.assertEqual((doc["exit"]["signal_number"], doc["exit"]["classification"],
                          doc["exit"]["attestation"]),
                         (signal.SIGSEGV.value, "fatal_signal", "owned-child-waitid"))
        self.assertTrue(doc["limits"]["stdout_tail_lost_on_crash_possible"])

    def test_real_sigabrt_is_a_crash(self):
        self.assertEqual(report("sigabrt")["event_types"], ["crash"])

    def test_startup_error_exit_is_unexpected_exit_not_crash(self):
        doc = report("exit2", prefix=True)
        self.assertValidRoundTrip(doc)
        self.assertEqual(doc["event_types"], ["exit_unexpected", "declared_error_lines"])

    def test_without_declared_prefix_the_error_line_is_unknown(self):
        doc = report("exit2")
        self.assertEqual(doc["event_types"], ["exit_unexpected"])
        rec = doc["streams"]["stderr"]["records"]
        self.assertEqual([(r["severity"], r["severity_source"], r["severity_hint"])
                          for r in rec],
                         [("unknown", "none", "error_or_fatal_candidate")])

    def test_exit_139_is_not_a_crash(self):
        doc = report("exit139")
        self.assertEqual(doc["event_types"], ["exit_unexpected"])
        self.assertEqual(doc["exit"]["exit_code"], 139)

    def test_forged_crash_text_never_makes_a_crash(self):
        self.assertIsNone(report("forged"))                   # exit 0, text only
        doc = report("forged", prefix=True)
        self.assertEqual(doc["event_types"], ["declared_error_lines"])

    def test_wrapper_hiding_a_grandchild_crash_has_no_event(self):
        self.assertIsNone(report("masked_wrapper"))

    def test_unplanned_sigterm_is_unexpected_and_planned_sigterm_is_no_event(self):
        doc = report("self_sigterm")
        self.assertEqual((doc["event_types"], doc["exit"]["classification"]),
                         (["exit_unexpected"], "signal_requires_policy"))
        self.assertIsNone(report("self_sigterm", planned_signal=signal.SIGTERM))

    def test_a_fatal_signal_declared_planned_is_refused(self):
        obs = observe("sigsegv", planned_signal=signal.SIGSEGV)
        self.assertEqual(obs.exit.classification, "planned_signal")
        with self.assertRaisesRegex(rs.ReportRefused, "SIGINT/SIGTERM"):
            report_for(obs)

    def test_error_then_crash_lists_every_supported_event(self):
        doc = report("error_then_segv", prefix=True)
        self.assertValidRoundTrip(doc)
        self.assertEqual(doc["event_types"],
                         ["crash", "declared_error_lines", "declared_warning_lines"])

    def test_descendant_holding_the_pipe_gives_source_incomplete(self):
        doc = report("descendant_holds", "1", eof_grace_seconds=0.3)
        self.assertValidRoundTrip(doc)
        self.assertEqual(doc["event_types"], ["source_incomplete"])
        self.assertTrue(doc["streams"]["stderr"]["deadline_hit"])

    def test_stream_hints_alone_never_make_an_event(self):
        self.assertIsNone(report("two_streams_plain"))

    def test_declared_coloured_console_gives_both_line_events(self):
        doc = report("two_streams_prefixed", prefix=True)
        self.assertValidRoundTrip(doc)
        self.assertEqual(doc["event_types"],
                         ["declared_error_lines", "declared_warning_lines"])
        self.assertGreater(doc["streams"]["stdout"]["ansi_sequences_stripped"], 0)
        self.assertEqual(doc["streams"]["stdout"]["lines_below_warn"], 1)

    def test_buffered_stdout_crash_flags_the_lost_tail(self):
        doc = report("buffered_then_segv")
        self.assertEqual(doc["event_types"], ["crash"])
        self.assertTrue(doc["limits"]["stdout_tail_lost_on_crash_possible"])

    def test_clean_exit_has_no_report(self):
        self.assertIsNone(report("exit0"))

    def test_role_and_stdin_are_recorded_as_caller_declarations(self):
        doc = report("fake_cli", stdin="held_open", role="authserver")
        self.assertEqual(doc["declared"], {
            "kind": "caller_declaration", "role": "authserver", "stdin_mode": "held_open",
            "prefix_loglevel": False, "prefix_timestamp": False})
        self.assertEqual(doc["event_types"], ["exit_unexpected"])   # exit 7

    def test_no_log_text_reaches_the_report(self):
        words = ("database", "DB down", "SIGSEGV received", "boom", "Creature",
                 "split", "Map loaded", "not a prefix", "connect")
        for mode, prefix in (("exit2", True), ("forged", True), ("multiline", True),
                             ("two_streams_prefixed", True), ("error_then_segv", True),
                             ("exit2", False)):
            with self.subTest(mode=mode, prefix=prefix):
                doc = report(mode, prefix=prefix)
                raw = rs.canonical_bytes(doc).decode()
                for word in words:
                    self.assertNotIn(word, raw)
                self.assertNotIn("message", set(walk_keys(doc)))
                self.assertEqual(doc["limits"]["text_policy"], "message_text_omitted")

    def test_message_length_is_the_only_trace_of_text(self):
        doc = report("exit2", prefix=True)
        rec = doc["streams"]["stderr"]["records"][0]
        self.assertEqual(rec["message_bytes"], len("could not connect to database"))


class ValidatorRejects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = report("error_then_segv", prefix=True)
        cls.exit2 = report("exit2", prefix=True)

    def rejects(self, change, needle, base=None, reseal=True):
        doc = copy.deepcopy(base or self.base)
        change(doc)
        try:
            if reseal:
                doc = rs.seal(doc)        # so only the targeted rule can fire
            raw = rs.canonical_bytes(doc)
        except rs.ReportRefused:
            raw = None                    # not even serialisable (e.g. a float)
        errors = rs.validate(doc)
        self.assertTrue(any(needle in e for e in errors),
                        f"{needle!r} not in {errors}")
        if raw is not None:
            with self.assertRaises(rs.ReportRefused):
                rs.parse(raw)

    def test_bases_are_valid(self):
        self.assertEqual(rs.validate(self.base), [])
        self.assertEqual(rs.validate(self.exit2), [])

    def test_closed_schema_unknown_and_missing_keys(self):
        self.rejects(lambda d: d.update(note="x"), "unexpected ['note']")
        self.rejects(lambda d: d["exit"].pop("planned"), "missing ['planned']")
        self.rejects(lambda d: d["streams"]["stderr"]["records"][0].update(message="x"),
                     "unexpected ['message']")
        self.rejects(lambda d: d["producer"].update(argv=["/x"]), "unexpected ['argv']")

    def test_types_are_strict(self):
        self.rejects(lambda d: d["incarnation"].update(starttime=1.5), "float")
        self.rejects(lambda d: d["incarnation"].update(pid=True), "incarnation.pid")
        self.rejects(lambda d: d["streams"]["stdout"].update(eof=1), "stdout.eof")

    def test_classification_is_recomputed_from_the_kernel_facts(self):
        self.rejects(lambda d: d["exit"].update(signal_number=15), "exit.classification")
        self.rejects(lambda d: d["exit"].update(kind="exited", signal_number=None,
                                                exit_code=139),
                     "exit.classification")

    def test_a_crash_cannot_be_omitted_or_invented(self):
        self.rejects(lambda d: d.update(event_types=["declared_error_lines",
                                                     "declared_warning_lines"]),
                     "event_types")
        self.rejects(lambda d: d.update(event_types=["crash", "exit_unexpected"]),
                     "event_types", base=self.exit2)
        self.rejects(lambda d: d.update(event_types=[]), "event_types")
        self.rejects(lambda d: d.update(event_types=["crash", "crash",
                                                     "declared_error_lines",
                                                     "declared_warning_lines"]),
                     "event_types")

    def test_planned_only_for_sigint_or_sigterm_signal_stops(self):
        def planned_segv(d):
            d["exit"].update(planned=True, classification="planned_signal")
        self.rejects(planned_segv, "SIGINT/SIGTERM")
        self.rejects(lambda d: d["exit"].update(planned=True), "only a signal stop",
                     base=self.exit2)

    def test_severity_needs_a_declared_prefix(self):
        self.rejects(lambda d: d["declared"].update(prefix_loglevel=False),
                     "without a declared prefix")
        self.rejects(lambda d: d["streams"]["stderr"]["records"][0].update(
            severity_source="none"), "declared_prefix, and only then")
        self.rejects(lambda d: d["declared"].update(prefix_timestamp=True,
                                                    prefix_loglevel=False),
                     "prefix_timestamp")

    def test_hint_and_stream_provenance_are_fixed(self):
        self.rejects(lambda d: d["streams"]["stderr"]["records"][0].update(
            severity_hint="below_error_candidate"), "severity_hint")
        self.rejects(lambda d: d["streams"]["stderr"]["records"][0].update(
            stream="stdout"), "records[0].stream")
        self.rejects(lambda d: d["streams"]["stdout"].update(
            attestation="owned-stderr-pipe"), "stdout.attestation")

    def test_byte_and_line_accounting(self):
        self.rejects(lambda d: d["streams"]["stderr"].update(
            bytes_dropped=d["streams"]["stderr"]["bytes_dropped"] + 1),
            "drained != retained")
        def claim_incomplete(d):          # event list kept consistent on purpose
            d["streams"]["stderr"].update(source_incomplete=True)
            d.update(event_types=rs.derive_event_types(d))
        self.rejects(claim_incomplete, "must equal deadline_hit and not eof")
        self.rejects(lambda d: d["streams"]["stderr"]["records"][1].update(line=1),
                     "must increase")
        self.rejects(lambda d: d["streams"]["stderr"]["records"][1].update(line=99),
                     "must increase")
        self.rejects(lambda d: d["streams"]["stdout"].update(lines_below_warn=2),
                     "lines_below_warn", base=report("exit2"))

    def test_no_report_can_claim_a_real_launch_mode(self):
        self.rejects(lambda d: d["producer"].update(launch_mode="real-worldserver"),
                     "launch_mode")
        self.rejects(lambda d: d["producer"].update(tool="/usr/bin/worldserver"),
                     "producer.tool")
        self.rejects(lambda d: d["incarnation"].update(pgid=d["incarnation"]["pid"] + 1),
                     "pgid == pid")

    def test_limits_cannot_overclaim(self):
        self.rejects(lambda d: d["limits"].update(stdout_tail_lost_on_crash_possible=False),
                     "stdout_tail_lost_on_crash_possible")
        self.rejects(lambda d: d["limits"].update(cross_stream_order="stderr_first"),
                     "cross_stream_order")
        self.rejects(lambda d: d["limits"].update(text_policy="raw"), "text_policy")
        self.rejects(lambda d: d["time"].update(recorded_utc="26/10/2026 15:00"),
                     "recorded_utc")
        self.rejects(lambda d: d.update(schema_version=2), "schema_version")

    def test_tampering_after_sealing_breaks_the_digest(self):
        self.rejects(lambda d: d["incarnation"].update(pid=d["incarnation"]["pid"] + 1),
                     "integrity.digest", reseal=False)
        self.rejects(lambda d: d["integrity"].update(proves="authenticity"),
                     "integrity.proves", reseal=False)

    def test_record_count_and_size_bounds(self):
        def many(d):
            rec = d["streams"]["stderr"]["records"][0]
            d["streams"]["stderr"]["records"] = [dict(rec, line=i + 1)
                                                 for i in range(rs.MAX_RECORDS + 1)]
        self.rejects(many, "records")
        big = copy.deepcopy(self.base)
        big["streams"]["stderr"]["records"] = [
            dict(big["streams"]["stderr"]["records"][0], line=i + 1)
            for i in range(9000)]
        self.assertEqual(rs.validate(big), ["$: report exceeds the size limit"])


class CanonicalFormAndParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = report("exit2", prefix=True)
        cls.raw = rs.canonical_bytes(cls.doc)

    def test_only_the_exact_canonical_bytes_parse(self):
        self.assertEqual(rs.parse(self.raw), self.doc)
        pretty = json.dumps(self.doc, indent=1, sort_keys=True).encode()
        with self.assertRaisesRegex(rs.ReportRefused, "canonical"):
            rs.parse(pretty)

    def test_duplicate_keys_floats_nan_and_non_objects_refused(self):
        dup = self.raw.replace(b'{"algorithm"', b'{"algorithm":"x","algorithm"', 1)
        for raw, needle in ((dup, "duplicate"),
                            (self.raw.replace(b'"schema_version":1', b'"schema_version":1.0'),
                             "non-integer"),
                            (self.raw.replace(b'"schema_version":1', b'"schema_version":NaN'),
                             "non-integer"),
                            (b"[]", "object"), (b"\xff", "not JSON")):
            with self.subTest(needle=needle), self.assertRaisesRegex(rs.ReportRefused, needle):
                rs.parse(raw)

    def test_oversized_input_refused_before_parsing(self):
        with self.assertRaisesRegex(rs.ReportRefused, "size limit"):
            rs.parse(b" " * (rs.MAX_REPORT_BYTES + 1))

    def test_digest_ignores_key_order_and_seal_is_stable(self):
        reordered = dict(reversed(list(self.doc.items())))
        self.assertEqual(rs.digest(reordered), self.doc["integrity"]["digest"])
        self.assertEqual(rs.seal(self.doc), self.doc)


class HostileInputIsRefusedNotRaised(unittest.TestCase):
    """CS01 #171 review: malformed input must end in ReportRefused (parse) or
    an error list (validate), never RecursionError/ValueError escaping."""

    def test_deep_nesting_is_refused_by_parse(self):
        for raw in (b"[" * 10000 + b"0" + b"]" * 10000,      # CS01's 20,001 bytes
                    b'{"a":' * 5000 + b"0" + b"}" * 5000,
                    b"[" * (rs.MAX_DEPTH + 1) + b"]" * (rs.MAX_DEPTH + 1)):
            with self.subTest(size=len(raw)), \
                    self.assertRaisesRegex(rs.ReportRefused, "nesting deeper"):
                rs.parse(raw)

    def test_brackets_inside_strings_are_not_nesting(self):
        # Brackets on both sides of an escaped quote, all inside one string.
        raw = b'{"a":"' + b"[{" * 50 + b'\\"' + b"[{" * 5000 + b'"}'
        with self.assertRaises(rs.ReportRefused) as caught:
            rs.parse(raw)                    # refused, but by the schema rules
        self.assertNotIn("nesting", str(caught.exception))

    def test_overlong_integer_literal_is_refused_by_parse(self):
        with self.assertRaisesRegex(rs.ReportRefused, "not JSON: ValueError"):
            rs.parse(b'{"a":' + b"1" * 5000 + b"}")          # CS01's 5 KiB input

    def test_validate_returns_errors_for_deep_cyclic_and_huge_values(self):
        deep = cursor = []
        for _ in range(5000):
            cursor.append([])
            cursor = cursor[0]
        cyclic = {}
        cyclic["self"] = cyclic
        doc = report("exit2", prefix=True)
        doc["incarnation"]["starttime"] = 10 ** 5000          # over the digit limit
        for value, needle in ((deep, "nesting deeper"), (cyclic, "nesting deeper"),
                              (doc, "ValueError")):
            with self.subTest(needle=needle):
                errors = rs.validate(value)
                self.assertEqual(len(errors), 1)
                self.assertIn(needle, errors[0])


class Boundaries(unittest.TestCase):
    def test_schema_module_is_pure(self):
        tree = ast.parse(SCHEMA_SOURCE)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "__import__",
                                                "compile", "print"})
        self.assertEqual(imported, {"__future__", "hashlib", "json", "re"})

    def test_mirrored_constants_match_the_producer(self):
        self.assertEqual(rs.ATTEST_EXIT, m.ATTEST_EXIT)
        self.assertEqual(rs.ATTEST_STREAMS, m.ATTEST_STREAMS)
        self.assertEqual((rs.HINT_SOURCE, rs.HINTS), (m.HINT_SOURCE, m.HINTS))
        self.assertEqual(set(rs.ROLES), set(m.ROLES))
        self.assertEqual(set(rs.STDIN_MODES), set(m.STDIN_MODES))
        self.assertEqual(rs.FATAL_SIGNAL_NUMBERS, {int(s) for s in m.FATAL_SIGNALS})
        self.assertEqual(set(rs.RECORD_SEVERITIES), set(m.REPORTED_LEVELS) | {"unknown"})

    def test_report_fields_track_the_producer_dataclasses(self):
        stream_fields = {f.name for f in dataclasses.fields(m.StreamFact)}
        self.assertEqual(rs.KEYS["stream"],
                         (stream_fields - {"incarnation", "role"}) | {"source_incomplete"})
        record_fields = {f.name for f in dataclasses.fields(m.Record)}
        self.assertEqual(rs.KEYS["record"], (record_fields - {"message"}) | {"message_bytes"})
        exit_fields = {f.name for f in dataclasses.fields(m.ExitFact)}
        self.assertEqual(rs.KEYS["exit"], exit_fields - {"incarnation"})

    def test_builder_refuses_unbound_or_single_stream_observations(self):
        obs = observe("exit2")
        other = dataclasses.replace(obs.exit.incarnation, starttime=obs.exit.incarnation.starttime + 1)
        stray = dataclasses.replace(obs.stdout, incarnation=other)
        with self.assertRaisesRegex(rs.ReportRefused, "one attested incarnation"):
            report_for(dataclasses.replace(obs, stdout=stray))
        with self.assertRaisesRegex(rs.ReportRefused, "both owned streams"):
            report_for(dataclasses.replace(obs, stdout=None))
        forged = dataclasses.replace(obs, exit=dataclasses.replace(obs.exit,
                                                                   attestation="text"))
        with self.assertRaisesRegex(rs.ReportRefused, "one attested incarnation"):
            report_for(forged)


if __name__ == "__main__":
    unittest.main()
