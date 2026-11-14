import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

topology = load("f15_topology", "scripts/f15_topology_evidence.py")
renderer = load("f15_renderer", "scripts/f15_crash_report_renderer.py")

def pm(pid, restarts, exit_code=0, up=1000):
    return json.dumps([{
        "name": "worldserver",
        "pid": pid,
        "pm_id": 0,
        "pm2_env": {
            "status": "online",
            "restart_time": restarts,
            "unstable_restarts": 0,
            "pm_uptime": up,
            "created_at": 900,
            "exit_code": exit_code,
        },
    }])

class PipelineTests(unittest.TestCase):
    def test_pm2_sigsegv_reaches_detailed_report_and_history(self):
        manager = (
            "2026-11-13 App [worldserver:0] exited with code [0] "
            "via signal [SIGSEGV]"
        )
        incident = topology.world_incident(
            pm(100, 4), pm(101, 5, up=2000), "worldserver", manager
        )
        self.assertEqual(incident["signal"], 11)
        incident.update({
            "incident_id": "fixture-pm2-sigsegv",
            "filename_timestamp": "20261113T112000Z",
            "observed_utc": "2026-11-13T11:20:00+00:00",
            "observed_local": "2026-11-13T11:20:00+00:00",
            "capture_status": "fixture_complete",
            "capture_gaps": "none in fixture",
            "recent_context": "ERROR segmentation test fixture\n",
            "raw_evidence_ref": "fixture-only",
        })
        with tempfile.TemporaryDirectory() as tmp:
            crash_dir = Path(tmp) / "Crash Logs"
            report_path = renderer.write_report(crash_dir, incident)
            report = report_path.read_text()
            history = (crash_dir / "Crash-History.txt").read_text()
        self.assertIn("Classification: FATAL_SIGNAL_EXIT", report)
        self.assertIn("Signal: 11", report)
        self.assertIn("Signal name: SIGSEGV", report)
        self.assertIn("PM2 restart_time advanced 4->5", report)
        self.assertIn("PID: 100", report)
        self.assertIn("Replacement PID: 101", report)
        self.assertIn("Process start epoch ms: 1000", report)
        self.assertIn("Replacement start epoch ms: 2000", report)
        self.assertIn("FATAL_SIGNAL_EXIT", history)


    def test_auth_process_start_ticks_reach_detailed_report(self):
        incident = topology.auth_incident(
            {"pid": 300, "start_ticks": 12345, "pane_pid": 20, "tmux_probe_status": "session_present_auth_present"},
            {"pid": 301, "start_ticks": 23456, "pane_pid": 20, "tmux_probe_status": "session_present_auth_present"},
            True,
        )
        incident.update({
            "incident_id": "fixture-auth-replaced",
            "filename_timestamp": "20261113T112002Z",
        })
        with tempfile.TemporaryDirectory() as tmp:
            report = renderer.write_report(Path(tmp) / "Crash Logs", incident).read_text()
        self.assertIn("PID: 300", report)
        self.assertIn("Replacement PID: 301", report)
        self.assertIn("Process start ticks: 12345", report)
        self.assertIn("Replacement start ticks: 23456", report)
        self.assertIn("Supervisor pane PID: 20", report)
        self.assertIn("Replacement supervisor pane PID: 20", report)
        self.assertIn("Supervisor probe status: session_present_auth_present", report)
        self.assertIn("Replacement supervisor probe status: session_present_auth_present", report)
        self.assertIn("Classification: PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", report)


    def test_auth_tmux_session_disappearance_reaches_detailed_report(self):
        incident = topology.auth_incident(
            {"pid": 400, "start_ticks": 34567, "pane_pid": 30, "tmux_probe_status": "session_present_auth_present"},
            {"pid": None, "start_ticks": None, "pane_pid": None, "tmux_probe_status": "session_absent"},
            False,
        )
        incident.update({
            "incident_id": "fixture-auth-tmux-gone",
            "filename_timestamp": "20261113T112003Z",
        })
        with tempfile.TemporaryDirectory() as tmp:
            report = renderer.write_report(Path(tmp) / "Crash Logs", incident).read_text()
        self.assertIn("Classification: PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", report)
        self.assertIn("Replacement supervisor pane PID: UNKNOWN", report)
        self.assertIn("Replacement supervisor probe status: session_absent", report)
        self.assertIn("tmux session not present", report)

    def test_pm2_restart_without_cause_stays_unproven_in_report(self):
        incident = topology.world_incident(
            pm(200, 1), pm(201, 2, exit_code=0, up=3000), "worldserver"
        )
        incident.update({
            "incident_id": "fixture-pm2-unknown",
            "filename_timestamp": "20261113T112001Z",
        })
        with tempfile.TemporaryDirectory() as tmp:
            report = renderer.write_report(Path(tmp) / "Crash Logs", incident).read_text()
        self.assertIn("Classification: PM2_RESTART_OBSERVED", report)
        self.assertIn("Signal name: UNKNOWN", report)
        self.assertNotIn("FATAL_SIGNAL_EXIT", report)

if __name__ == "__main__":
    unittest.main()
