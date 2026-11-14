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

    def test_unconfirmed_marker_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        store.arm("op-1", "restart", before, self.now, self.now + timedelta(minutes=5))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertFalse(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_confirmed_exact_world_restart_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        store.arm("op-2", "restart", before, self.now, self.now + timedelta(minutes=5))
        store.confirm("op-2", self.now + timedelta(seconds=10))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_confirmed_world_stop_matches_same_counter(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(0, 4, status="stopped", up=1000)
        store.arm("op-3", "stop", before, self.now, self.now + timedelta(minutes=5))
        store.confirm("op-3", self.now + timedelta(seconds=10))
        incident = {"classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", "exit_code": 0, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_fatal_or_nonzero_world_exit_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        store.arm("op-4", "restart", before, self.now, self.now + timedelta(minutes=5))
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
        store.arm("op-5", "restart", armed, self.now, self.now + timedelta(minutes=5))
        store.confirm("op-5", self.now + timedelta(seconds=10))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertFalse(store.matches_expected(actual_before, after, incident, self.now + timedelta(minutes=1)))

    def test_expired_marker_never_matches(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4, up=1000)
        after = world_identity(11, 5, up=2000)
        store.arm("op-6", "restart", before, self.now, self.now + timedelta(minutes=1))
        store.confirm("op-6", self.now + timedelta(seconds=10))
        incident = {"classification": "PM2_RESTART_OBSERVED", "exit_code": 0, "signal_name": None}
        self.assertFalse(store.matches_expected(before, after, incident, self.now + timedelta(minutes=2)))

    def test_auth_restart_requires_confirmed_exact_identity_change(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Authserver")
        before = auth_identity(30, 100)
        after = auth_identity(31, 200)
        store.arm("auth-r1", "restart", before, self.now, self.now + timedelta(minutes=5))
        store.confirm("auth-r1", self.now + timedelta(seconds=5))
        incident = {"classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", "exit_code": None, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_auth_stop_requires_confirmed_present_to_absent(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Authserver")
        before = auth_identity(30, 100)
        after = {"kind": "auth", "pid": None, "start_ticks": None, "tmux_alive": True}
        store.arm("auth-s1", "stop", before, self.now, self.now + timedelta(minutes=5))
        store.confirm("auth-s1", self.now + timedelta(seconds=5))
        incident = {"classification": "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", "exit_code": None, "signal_name": None}
        self.assertTrue(store.matches_expected(before, after, incident, self.now + timedelta(minutes=1)))

    def test_wrong_operation_id_confirmation_refused(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        before = world_identity(10, 4)
        store.arm("op-7", "stop", before, self.now, self.now + timedelta(minutes=5))
        with self.assertRaises(expected.Refused):
            store.confirm("wrong", self.now + timedelta(seconds=5))

    def test_window_longer_than_30_minutes_refused(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        with self.assertRaises(expected.Refused):
            store.arm("op-8", "stop", world_identity(10, 4), self.now, self.now + timedelta(minutes=31))

    def test_existing_marker_cannot_be_silently_replaced(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        store.arm("op-9", "stop", world_identity(10, 4), self.now, self.now + timedelta(minutes=5))
        with self.assertRaises(expected.Refused):
            store.arm("op-10", "restart", world_identity(10, 4), self.now, self.now + timedelta(minutes=5))

    def test_symlink_marker_refused(self):
        store = expected.ExpectedMaintenanceStore(self.root, "Worldserver")
        target = self.root / "target.json"
        target.write_text("{}")
        target.chmod(0o600)
        store.path.symlink_to(target)
        with self.assertRaises(expected.Refused):
            store.read()


if __name__ == "__main__":
    unittest.main()
