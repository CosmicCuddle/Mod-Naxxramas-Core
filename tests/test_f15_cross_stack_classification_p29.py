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
from offline_error_reports import ERROR_SCHEMA


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
