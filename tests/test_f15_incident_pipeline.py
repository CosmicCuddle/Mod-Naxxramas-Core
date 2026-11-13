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
        self.assertIn("FATAL_SIGNAL_EXIT", history)

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
