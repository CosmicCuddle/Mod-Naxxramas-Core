"""Part29 F15 source-only cross-stack semantic witness.

Two exact PUBLIC branches, no World/Auth or owner environment. This test
deliberately shows mismatches; it does NOT provide a storage adapter or
authenticate any subprocess. Only synthetic event inputs are constructed.
"""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
OFFLINE = ROOT / "tools" / "f15"
CANON = Path(os.environ.get(
    "F15_CANONICAL_PIN_ROOT", "canonical-pin"
)).resolve() / "tools" / "f15" / "report_schema.py"

sys.path.insert(0, str(OFFLINE))
from offline_store import Incident, report_bytes, SCHEMA, MAX_REPORT, UNKNOWN
from offline_error_reports import ERROR_SCHEMA, ErrorBurstObservation
from offline_error_bursts import (
    OfflineBurstTracker, LogEvidence, BurstAlert, LEVELS, STREAMS,
    SOURCE as FIXTURE_SOURCE,
)


def load_pinned_schema():
    if not CANON.is_file():
        raise AssertionError("Exact public #171 schema pin is required: " + str(CANON))
    spec = importlib.util.spec_from_file_location("f15_canonical_pinned", CANON)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_store_event(*, code=None, signal=None, planned=False,
                          actual=True, unexpected=True, service="worldserver"):
    return Incident(
        service=service,
        host="fictional-host",
        boot="fictional-boot",
        invocation="fictional-start",
        pid=12345,
        start_utc="2026-10-27T10:00:00Z",
        end_utc="2026-10-27T10:01:00Z",
        verified_actual_death=actual,
        unexpected_death=unexpected,
        planned_stop=planned,
        signal=signal,
        exit_code=code,
    )


class CrossStackSemanticProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_pinned_schema()

    def test_schema_identity_and_storage_encoding_are_distinct(self):
        self.assertEqual(self.canonical.SCHEMA, "naxx-f15-event")
        self.assertEqual(self.canonical.SCHEMA_VERSION, 1)
        self.assertEqual(SCHEMA, "F15-S2-OFFLINE-1")
        self.assertEqual(ERROR_SCHEMA, "F15-S4C-OFFLINE-ERROR-BURST-1")
        self.assertNotEqual(SCHEMA, self.canonical.SCHEMA)

    def test_nonzero_exit_139_is_not_a_kernel_fatal_signal_in_canonical(self):
        self.assertEqual(
            self.canonical.classify_exit("exited", 139, None, False),
            "nonzero_exit_not_signal",
        )
        incident = synthetic_store_event(code=139)
        self.assertTrue(incident.is_reportable())
        data = report_bytes(incident.metadata())
        self.assertTrue(data.startswith(b"COSMIC CORE - SERVER CRASH REPORT\n"))
        self.assertIn(b"Observed termination: exit 139\n", data)
        # The legacy headline says CRASH, but the canonical kernel
        # classification says only an unexpected NONSIGNAL exit.

    def test_nonzero_exit_1_is_also_reported_under_legacy_crash_heading(self):
        self.assertEqual(
            self.canonical.classify_exit("exited", 1, None, False),
            "nonzero_exit_not_signal",
        )
        incident = synthetic_store_event(code=1, service="authserver")
        self.assertTrue(incident.is_reportable())
        self.assertIn(
            b"COSMIC CORE - SERVER CRASH REPORT",
            report_bytes(incident.metadata()),
        )

    def test_worldserver_exit_2_has_different_admission_rules(self):
        self.assertEqual(
            self.canonical.classify_exit("exited", 2, None, False),
            "nonzero_exit_not_signal",
        )
        # Existing offline policy intentionally excludes Worldserver exit 2
        # from crash reports. Canonical has a different event classification.
        self.assertFalse(synthetic_store_event(code=2).is_reportable())
        self.assertTrue(synthetic_store_event(code=2,
                                              service="authserver").is_reportable())

    def test_unplanned_sigterm_is_policy_signal_not_canonical_crash(self):
        self.assertEqual(
            self.canonical.classify_exit("signaled", None, 15, False),
            "signal_requires_policy",
        )
        legacy = synthetic_store_event(signal="SIGTERM")
        self.assertTrue(legacy.is_reportable())
        self.assertIn(b"SERVER CRASH REPORT", report_bytes(legacy.metadata()))

    def test_planned_sigterm_is_not_legacy_reportable(self):
        self.assertEqual(
            self.canonical.classify_exit("signaled", None, 15, True),
            "planned_signal",
        )
        self.assertFalse(
            synthetic_store_event(signal="SIGTERM", planned=True).is_reportable()
        )

    def test_fatal_signal_source_is_distinct_from_caller_assertion(self):
        self.assertEqual(
            self.canonical.classify_exit("signaled", None, 11, False),
            "fatal_signal",
        )
        self.assertFalse(
            synthetic_store_event(signal="SIGSEGV", actual=False).is_reportable()
        )
        self.assertTrue(
            synthetic_store_event(signal="SIGSEGV", actual=True).is_reportable()
        )
        # This second Boolean is supplied by our *synthetic caller*, not
        # positive OS-process provenance; cannot promote it to attestation.
        self.assertEqual(self.canonical.ATTEST_EXIT, "owned-child-waitid")

    def test_canonical_validator_refuses_legacy_text_report(self):
        data = report_bytes(synthetic_store_event(code=139).metadata())
        with self.assertRaises(self.canonical.ReportRefused):
            self.canonical.parse(data)

    def test_legacy_metadata_cannot_claim_canonical_event_and_origin(self):
        meta = synthetic_store_event(code=139).metadata()
        self.assertNotIn("event_types", meta)
        self.assertNotIn("producer", meta)
        self.assertNotIn("incarnation", meta)
        self.assertNotIn("streams", meta)
        self.assertIn("termination", meta)
        self.assertIn("crash_cause", meta)
        self.assertEqual(meta["crash_cause"], UNKNOWN)

    def test_canonical_launch_mode_explicitly_disposable(self):
        self.assertEqual(self.canonical.LAUNCH_MODE, "A-disposable")
        self.assertEqual(self.canonical.TEXT_POLICY, "message_text_omitted")
        self.assertIn("worldserver", self.canonical.ROLES)
        self.assertIn("authserver", self.canonical.ROLES)
        # These role strings are not a kernel attestation of the installed
        # daemon and can't grant a file-write or incident-origin right.

    def test_formats_use_different_upper_report_size_limits(self):
        self.assertEqual(self.canonical.MAX_REPORT_BYTES, 1024 * 1024)
        self.assertEqual(MAX_REPORT, 16_384)
        self.assertGreater(self.canonical.MAX_REPORT_BYTES, MAX_REPORT)
        # Any future adapter must define oversize refusal, never silent
        # truncation of facts in order to fit the legacy text cap.

    def test_canonical_supports_multiple_events_not_one_legacy_category(self):
        self.assertEqual(
            self.canonical.EVENT_ORDER,
            ("crash", "exit_unexpected", "source_incomplete",
             "declared_error_lines", "declared_warning_lines"),
        )
        # A single authenticated observation might include a fatal signal,
        # warning records and incomplete capture. No mapping into one
        # current crash+error-burst legacy record is specified or tested.
        self.assertFalse(hasattr(self.canonical, "publish"))
        self.assertFalse(hasattr(self.canonical, "publish_error"))


class WarningErrorBoundaryProof(unittest.TestCase):
    """Canonical line classification is NOT S4b's multi-event burst policy."""

    @classmethod
    def setUpClass(cls):
        cls.canonical = load_pinned_schema()

    @staticmethod
    def line_events(levels):
        # Source-shaped call to actual canonical derivation helper;
        # deliberately NOT a complete validated/attested schema document.
        return load_pinned_schema().derive_event_types({
            "exit": {"classification": "normal_exit"},
            "streams": {
                "stdout": {
                    "source_incomplete": False,
                    "records": [{"severity": x} for x in levels],
                },
                "stderr": {"source_incomplete": False, "records": []},
            },
        })

    @staticmethod
    def event(*, level="WARN", code="fictional-category", seq=1, uptime=0,
              stream="stdout", source=FIXTURE_SOURCE, verified=True):
        return LogEvidence(
            service="worldserver", instance="fictional-incarnation",
            stream=stream, level=level, code=code, seq=seq,
            uptime_ms=uptime, source=source, verified_stream=verified,
        )

    def test_single_declared_warn_line_is_not_a_s4b_burst(self):
        self.assertEqual(self.line_events(["WARN"]), ["declared_warning_lines"])
        tracker = OfflineBurstTracker(threshold=3, window_ms=60_000)
        decision = tracker.observe(self.event())
        self.assertEqual(decision.status, "ignored")
        self.assertIsNone(decision.alert)

    def test_three_same_code_warn_lines_make_one_fixture_burst(self):
        self.assertEqual(
            self.line_events(["WARN", "WARN", "WARN"]),
            ["declared_warning_lines"],
        )
        tracker = OfflineBurstTracker(threshold=3, window_ms=60_000)
        result = [
            tracker.observe(self.event(seq=i + 1, uptime=i * 1000))
            for i in range(4)
        ]
        self.assertEqual([x.status for x in result],
                         ["ignored", "ignored", "alert", "ignored"])
        self.assertEqual(result[2].alert.level, "WARN")
        self.assertEqual(result[2].alert.threshold, 3)
        self.assertEqual(result[2].alert.window_ms, 60_000)

    def test_three_different_categories_do_not_form_one_burst(self):
        self.assertEqual(self.line_events(["ERROR"] * 3),
                         ["declared_error_lines"])
        tracker = OfflineBurstTracker(threshold=3)
        decisions = [
            tracker.observe(self.event(
                level="ERROR", code=f"category-{i}", seq=i + 1,
                uptime=i * 1000))
            for i in range(3)
        ]
        self.assertEqual([x.status for x in decisions], ["ignored"] * 3)
        self.assertEqual(tracker.counts(), (1, 3))

    def test_fatal_line_is_canonical_error_but_legacy_burst_rejects_fatal(self):
        self.assertEqual(self.line_events(["FATAL"]),
                         ["declared_error_lines"])
        self.assertIn("FATAL", self.canonical.RECORD_SEVERITIES)
        self.assertNotIn("FATAL", LEVELS)
        with self.assertRaisesRegex(ValueError, "not a warning or error"):
            self.event(level="FATAL").checked()

    def test_unknown_severity_is_not_a_declared_warning_or_burst(self):
        self.assertEqual(self.line_events(["unknown"]), [])
        self.assertIn("unknown", self.canonical.RECORD_SEVERITIES)
        with self.assertRaisesRegex(ValueError, "not a warning or error"):
            self.event(level="unknown").checked()

    def test_fixture_stream_claim_is_not_positive_provenance(self):
        tracker = OfflineBurstTracker(threshold=3)
        missing = tracker.observe(self.event(verified=False))
        self.assertEqual(missing.status, "unverified")
        forged = tracker.observe(self.event(source="unverified-text"))
        self.assertEqual(forged.status, "unverified")
        self.assertEqual(tracker.counts(), (0, 0))
        # Fixture source token and Boolean can be minted by a caller.
        self.assertEqual(FIXTURE_SOURCE, "verified-stream-fixture")

    def test_legacy_file_log_stream_has_no_canonical_pipe_equivalent(self):
        self.assertEqual(set(self.canonical.ATTEST_STREAMS),
                         {"stdout", "stderr"})
        self.assertTrue({"world-log", "auth-log"}.issubset(STREAMS))
        self.assertNotIn("world-log", self.canonical.KEYS["streams"])
        self.assertNotIn("auth-log", self.canonical.KEYS["streams"])

    def test_burst_sequence_and_uptime_cannot_be_inferred_from_line_number(self):
        tracker = OfflineBurstTracker(threshold=3)
        self.assertEqual(
            tracker.observe(self.event(seq=5, uptime=12345)).status, "ignored")
        self.assertEqual(
            tracker.observe(self.event(seq=5, uptime=12346)).status, "rejected")
        self.assertEqual(
            tracker.observe(self.event(seq=6, uptime=12344)).status, "rejected")
        self.assertEqual(tracker.counts(), (1, 1))
        self.assertNotIn("uptime_ms", self.canonical.KEYS["record"])
        self.assertNotIn("code", self.canonical.KEYS["record"])
        self.assertNotIn("seq", self.canonical.KEYS["record"])
        self.assertIn("line", self.canonical.KEYS["record"])

    def test_s4c_accepts_caller_verified_fixture_with_no_trusted_adapter(self):
        alert = BurstAlert(
            "worldserver", "fictional-incarnation", "stdout", "WARN",
            "fictional-category", 3, 60_000, 3000,
        )
        obs = ErrorBurstObservation(alert, "2026-10-27T12:00:00Z", True)
        self.assertIs(obs.checked(), obs)
        meta = obs.info()
        self.assertTrue(meta["verified"])
        self.assertEqual(meta["threshold"], 3)
        self.assertEqual(meta["window_ms"], 60_000)
        self.assertNotIn("producer", meta)
        self.assertNotIn("incarnation", meta)
        self.assertNotIn("attestation", meta)


if __name__ == "__main__":
    unittest.main(verbosity=2)
