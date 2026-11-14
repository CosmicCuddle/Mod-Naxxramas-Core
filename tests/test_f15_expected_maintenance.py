#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checkpoint = load("checkpoint_for_expected", "scripts/f15_incident_checkpoint.py")
import sys
sys.modules["f15_incident_checkpoint"] = checkpoint
expected = load("expected", "scripts/f15_expected_maintenance.py")


def world_identity(pid, restarts, status="online", up=1000):
    return {
        "kind": "pm2",
        "name": "worldserver",
        "pid": pid,
        "restart_time": restarts,
        "pm_uptime": up,
        "status": status,
    }


def auth_identity(pid, start):
    return {"kind": "auth", "pid": pid, "start_ticks": start, "tmux_alive": True}


class ExpectedMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "state"
        self.root.mkdir(mode=0o700)
        self.now = datetime(2026, 11, 14, 11, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self, service, identity):
        checkpoint._atomic_json(
            self.root / f"{service}.checkpoint.json",
            {"version": 1, "service": service, "sequence": 0, "identity": identity},
        )

    def test_unconfirmed_marker_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        store.arm("op-1", "restart", self.now, self.now + timedelta(minutes=5))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertFalse(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_confirmed_exact_world_restart_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        store.arm("op-2", "restart", self.now, self.now + timedelta(minutes=5))
        store.confirm("op-2", self.now + timedelta(seconds=10))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_confirmed_world_stop_matches_same_counter(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(0, 4, status="stopped", up=1000)
        self.seed("Worldserver", before)
        store.arm("op-3", "stop", self.now, self.now + timedelta(minutes=5))
        store.confirm("op-3", self.now + timedelta(seconds=10))
        incident = {"classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", "exit_code": 0, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_fatal_or_nonzero_world_exit_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        store.arm("op-4", "restart", self.now, self.now + timedelta(minutes=5))
        store.confirm("op-4", self.now + timedelta(seconds=10))
        fatal = {"classification": "FATAL_SIGNAL_EXIT", "exit_code": 0, "signal_name": "SIGSEGV"}
        nonzero = {"classification": "NONZERO_EXIT", "exit_code": 1, "signal_name": None}
        self.assertFalse(store.matches_expected(before, after, fatal, self.now + timedelta(minutes=1)))
        self.assertFalse(store.matches_expected(before, after, nonzero, self.now + timedelta(minutes=1)))

    def test_wrong_before_identity_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        armed = world_identity(10, 4, up=1000)
        actual_before = world_identity(12, 7, up=3000)
        after = world_identity(13, 8, up=4000)
        self.seed("Worldserver", armed)
        store.arm("op-5", "restart", self.now, self.now + timedelta(minutes=5))
        store.confirm("op-5", self.now + timedelta(seconds=10))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertFalse(store.matches_expected(actual_before, after, incident, self.now + timedelta(minutes=1)))

    def test_expired_marker_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        store.arm("op-6", "restart", self.now, self.now + timedelta(minutes=1))
        store.confirm("op-6", self.now + timedelta(seconds=10))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertFalse(store.matches_expected(before, after, incident, self.now + timedelta(minutes=2)))

    def test_auth_restart_requires_confirmed_exact_identity_change(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Authserver")
        before = auth_identity(30, 100)
        after = auth_identity(31, 200)
        self.seed("Authserver", before)
        store.arm("auth-r1", "restart", self.now, self.now + timedelta(minutes=5))
        store.confirm("auth-r1", self.now + timedelta(seconds=5))
        incident = {"classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", "exit_code": None, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_auth_stop_requires_confirmed_present_to_absent(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Authserver")
        before = auth_identity(30, 100)
        after = {"kind": "auth", "pid": None, "start_ticks": None, "tmux_alive": True}
        self.seed("Authserver", before)
        store.arm("auth-s1", "stop", self.now, self.now + timedelta(minutes=5))
        store.confirm("auth-s1", self.now + timedelta(seconds=5))
        incident = {"classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", "exit_code": None, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_wrong_operation_id_confirmation_refused(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4)
        self.seed("Worldserver", before)
        store.arm("op-7", "stop", self.now, self.now + timedelta(minutes=5))
        with self.assertRaises(expected.Refused):
            store.confirm("wrong", self.now + timedelta(seconds=5))

    def test_window_longer_than_30_minutes_refused(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        with self.assertRaises(expected.Refused):
            self.seed("Worldserver", world_identity(10, 4))
            store.arm("op-8", "stop", self.now, self.now + timedelta(minutes=31))

    def test_existing_marker_cannot_be_silently_replaced(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        self.seed("Worldserver", world_identity(10, 4))
        store.arm("op-9", "stop", self.now, self.now + timedelta(minutes=5))
        with self.assertRaises(expected.Refused):
            store.arm("op-10", "restart", self.now, self.now + timedelta(minutes=5))

    def test_symlink_marker_refused(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        target = self.root / "target.json"
        target.write_text("{}")
        target.chmod(0o600)
        store.path.symlink_to(target)
        with self.assertRaises(expected.Refused):
            store.read()


    def test_recovery_classifier_clean_and_audit_only(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4)
        self.seed("Worldserver", before)
        self.assertEqual(store.classify_recovery()["status"], "CLEAN")
        checkpoint._atomic_json(
            self.root / "Worldserver.last-expected-maintenance.json",
            {
                "version": 1,
                "service": "Worldserver",
                "operation_id": "done-1",
                "transition": "restart",
                "created_utc": self.now.isoformat(),
                "confirmed_utc": (self.now + timedelta(seconds=1)).isoformat(),
                "observed_utc": (self.now + timedelta(seconds=2)).isoformat(),
                "result": "EXPECTED_TRANSITION_CONFIRMED",
            },
        )
        result = store.classify_recovery()
        self.assertEqual(result["status"], "AUDIT_ONLY_CLEAN")
        self.assertEqual(result["operation_id"], "done-1")

    def test_recovery_classifier_stale_confirmed_marker_after_checkpoint(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        store.arm("stale-1", "restart", self.now, self.now + timedelta(minutes=5))
        store.confirm("stale-1", self.now + timedelta(seconds=1))
        checkpoint._atomic_json(
            self.root / "Worldserver.checkpoint.json",
            {"version": 1, "service": "Worldserver", "sequence": 0, "identity": after},
        )
        result = store.classify_recovery()
        self.assertEqual(result["status"], "STALE_CONFIRMED_MARKER_AFTER_CHECKPOINT")
        self.assertTrue(result["checkpoint_advanced"])
        self.assertTrue(store.path.exists(), "classifier must not mutate stale marker")

    def test_recovery_classifier_marker_audit_mismatch(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4)
        self.seed("Worldserver", before)
        store.arm("marker-op", "stop", self.now, self.now + timedelta(minutes=5))
        store.confirm("marker-op", self.now + timedelta(seconds=1))
        checkpoint._atomic_json(
            self.root / "Worldserver.last-expected-maintenance.json",
            {
                "version": 1,
                "service": "Worldserver",
                "operation_id": "other-op",
                "transition": "stop",
                "created_utc": self.now.isoformat(),
                "confirmed_utc": (self.now + timedelta(seconds=1)).isoformat(),
                "observed_utc": (self.now + timedelta(seconds=2)).isoformat(),
                "result": "EXPECTED_TRANSITION_CONFIRMED",
            },
        )
        result = store.classify_recovery()
        self.assertEqual(result["status"], "MARKER_AUDIT_MISMATCH")

    def test_recovery_classifier_missing_checkpoint(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        self.assertEqual(
            store.classify_recovery()["status"],
            "CHECKPOINT_INVALID_OR_MISSING",
        )

    def test_confirm_retry_same_operation_is_idempotent_with_different_timestamp(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4)
        self.seed("Worldserver", before)
        store.arm("retry-confirm", "restart", self.now, self.now + timedelta(minutes=5))
        first = store.confirm("retry-confirm", self.now + timedelta(seconds=5))
        second = store.confirm("retry-confirm", self.now + timedelta(seconds=25))
        self.assertEqual(second, first)
        self.assertEqual(second["confirmed_utc"], first["confirmed_utc"])

    def test_clean_sigint_sigterm_can_match_exact_confirmed_world_restart(self):
        for signal_name in ("SIGINT", "SIGTERM"):
            with self.subTest(signal=signal_name):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                root = Path(tmp.name) / "state"
                root.mkdir(mode=0o700)
                store = expected.ExpectedMaintenanceStore(root, "Worldserver")
                before = world_identity(10, 4, up=1000)
                after = world_identity(11, 5, up=2000)
                checkpoint._atomic_json(
                    root / "Worldserver.checkpoint.json",
                    {"version": 1, "service": "Worldserver", "sequence": 0, "identity": before},
                )
                store.arm("clean-signal", "restart", self.now, self.now + timedelta(minutes=5))
                store.confirm("clean-signal", self.now + timedelta(seconds=5))
                incident = {
                    "classification": "SIGNAL_EXIT_CAUSE_UNPROVEN",
                    "exit_code": 0,
                    "signal_name": signal_name,
                }
                self.assertTrue(
                    store.matches_expected(before, after, incident, self.now + timedelta(seconds=10))
                )

    def test_sigkill_and_fatal_signals_never_match_expected_maintenance(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        store.arm("bad-signal", "restart", self.now, self.now + timedelta(minutes=5))
        store.confirm("bad-signal", self.now + timedelta(seconds=5))
        for incident in (
            {"classification": "SIGNAL_EXIT_CAUSE_UNPROVEN", "exit_code": 0, "signal_name": "SIGKILL"},
            {"classification": "FATAL_SIGNAL_EXIT", "exit_code": 0, "signal_name": "SIGSEGV"},
            {"classification": "NONZERO_EXIT", "exit_code": 7, "signal_name": "SIGTERM"},
        ):
            with self.subTest(incident=incident):
                self.assertFalse(
                    store.matches_expected(before, after, incident, self.now + timedelta(seconds=10))
                )

    def test_invalid_marker_has_no_suppression_authority_but_admin_read_stays_strict(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        self.seed("Worldserver", before)
        target = self.root / "foreign-marker.json"
        target.write_text("{}")
        target.chmod(0o600)
        store.path.symlink_to(target)
        incident = {
            "classification": "PM2_RESTART_OBSERVED",
            "exit_code": 0,
            "signal_name": None,
        }
        self.assertFalse(
            store.matches_expected(before, after, incident, self.now + timedelta(seconds=10))
        )
        with self.assertRaises(expected.Refused):
            store.read()
        result = store.classify_recovery()
        self.assertEqual(result["status"], "MARKER_INVALID_OR_UNSAFE")
        self.assertTrue(store.path.is_symlink())
        self.assertEqual(target.read_text(), "{}")

    def test_invalid_audit_is_classified_not_raised(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4)
        self.seed("Worldserver", before)
        audit = self.root / "Worldserver.last-expected-maintenance.json"
        audit.write_text("{bad json")
        audit.chmod(0o600)
        result = store.classify_recovery()
        self.assertEqual(result["status"], "AUDIT_INVALID_OR_UNSAFE")
        self.assertTrue(audit.exists())

    def test_standalone_marker_consume_api_is_not_exposed(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        self.assertFalse(hasattr(store, "consume"))

if __name__ == "__main__":
    unittest.main()
