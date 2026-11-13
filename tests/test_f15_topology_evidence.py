import importlib.util
import json
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "adapter", Path(__file__).resolve().parents[1] / "scripts" / "f15_topology_evidence.py"
)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)

def pm(name="worldserver", pid=10, restarts=1, exit_code=0, status="online", up=1000):
    return json.dumps([{
        "name": name,
        "pid": pid,
        "pm_id": 0,
        "pm2_env": {
            "status": status,
            "restart_time": restarts,
            "unstable_restarts": 0,
            "pm_uptime": up,
            "created_at": 900,
            "exit_code": exit_code,
        },
    }])

class TopologyEvidenceTests(unittest.TestCase):
    def test_no_restart_returns_none(self):
        self.assertIsNone(adapter.world_incident(pm(), pm(pid=10), "worldserver"))

    def test_pm2_restart_with_fatal_signal(self):
        manager = (
            "2026-11-13 App [worldserver:0] exited with code [0] "
            "via signal [SIGSEGV]"
        )
        incident = adapter.world_incident(
            pm(), pm(pid=11, restarts=2, exit_code=0, up=2000),
            "worldserver", manager
        )
        self.assertEqual(incident["classification"], "FATAL_SIGNAL_EXIT")
        self.assertEqual(incident["signal_name"], "SIGSEGV")

    def test_pm2_restart_with_nonzero_exit(self):
        incident = adapter.world_incident(
            pm(), pm(pid=11, restarts=2, exit_code=7), "worldserver"
        )
        self.assertEqual(incident["classification"], "NONZERO_EXIT")

    def test_pm2_restart_without_exit_evidence_is_not_guessed_as_crash(self):
        incident = adapter.world_incident(
            pm(), pm(pid=11, restarts=2, exit_code=0), "worldserver"
        )
        self.assertEqual(incident["classification"], "PM2_RESTART_OBSERVED")

    def test_wrong_pm2_name_refused(self):
        with self.assertRaises(adapter.Refused):
            adapter.world_incident(pm(), pm(), "other")

    def test_pm2_restart_counter_backwards_refused(self):
        with self.assertRaises(adapter.Refused):
            adapter.world_incident(
                pm(restarts=2), pm(restarts=1), "worldserver"
            )

    def test_auth_same_identity_returns_none(self):
        self.assertIsNone(adapter.auth_incident(
            {"pid": 30, "start_ticks": 100},
            {"pid": 30, "start_ticks": 100},
            True,
        ))

    def test_auth_disappearance_keeps_cause_unknown(self):
        incident = adapter.auth_incident(
            {"pid": 30, "start_ticks": 100},
            {"pid": None, "start_ticks": None},
            True,
        )
        self.assertEqual(
            incident["classification"],
            "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN",
        )
        self.assertIn(
            "tmux session still present",
            incident["classification_evidence"],
        )

    def test_auth_replacement_keeps_cause_unknown(self):
        incident = adapter.auth_incident(
            {"pid": 30, "start_ticks": 100},
            {"pid": 31, "start_ticks": 200},
            True,
        )
        self.assertEqual(incident["replacement_pid"], 31)
        self.assertEqual(
            incident["classification"],
            "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN",
        )

if __name__ == "__main__":
    unittest.main()
