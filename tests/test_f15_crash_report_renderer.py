import importlib.util
import stat
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "f15", Path(__file__).resolve().parents[1] / "scripts" / "f15_crash_report_renderer.py"
)
f15 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f15)

class RendererTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name) / "Crash Logs"
        self.inc = {
            "service": "Worldserver",
            "incident_id": "inc-001",
            "filename_timestamp": "20261113T112000Z",
            "observed_utc": "2026-11-13T11:20:00+00:00",
            "observed_local": "2026-11-13T11:20:00+00:00",
            "exit_code": -11,
            "classification_evidence": "PM2 exit event + kernel status",
            "pid": 123,
            "ppid": 2,
            "supervisor": "PM2",
            "process_start": "2026-11-13T10:00:00Z",
            "uptime_seconds": 4800,
            "build_version": "AC dev",
            "source_revision": "abc123",
            "last_checkpoint": "journal 77",
            "capture_status": "complete",
            "capture_gaps": "none",
            "restart_evidence": "PM2 restart #4",
            "native_crash_evidence": "core dump unavailable",
            "raw_evidence_ref": "private/run/77",
            "recent_context": "line1\nERROR boom\n",
            "notes": "fixture only",
        }

    def test_detailed_signal_report_and_private_files(self):
        path = f15.write_report(self.root, self.inc)
        report = path.read_text()
        self.assertIn("Signal name: SIGSEGV", report)
        self.assertIn("PM2 restart #4", report)
        self.assertIn("ERROR boom", report)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        history = self.root / "Crash-History.txt"
        self.assertEqual(stat.S_IMODE(history.stat().st_mode), 0o600)
        self.assertIn("SIGNAL_EXIT", history.read_text())

    def test_redacts_secret_values_but_keeps_database_error(self):
        incident = dict(self.inc)
        incident["incident_id"] = "inc-002"
        incident["recent_context"] = (
            "database connection failed\npassword=hunter2\ntoken: abcdef\nworld"
        )
        report = f15.write_report(self.root, incident).read_text()
        self.assertIn("database connection failed", report)
        self.assertNotIn("hunter2", report)
        self.assertNotIn("abcdef", report)
        self.assertIn("password=[REDACTED]", report)
        self.assertIn("token=[REDACTED]", report)

    def test_collision_refused(self):
        f15.write_report(self.root, self.inc)
        with self.assertRaises(f15.Refused):
            f15.write_report(self.root, self.inc)

    def test_insecure_directory_refused(self):
        self.root.mkdir()
        self.root.chmod(0o755)
        with self.assertRaises(f15.Refused):
            f15.write_report(self.root, self.inc)

    def test_path_traversal_incident_refused(self):
        incident = dict(self.inc)
        incident["incident_id"] = "../oops"
        with self.assertRaises(f15.Refused):
            f15.write_report(self.root, incident)

    def test_nonzero_exit_not_guessed_as_signal_crash(self):
        incident = dict(self.inc)
        incident.update(incident_id="inc-003", exit_code=7)
        report = f15.write_report(self.root, incident).read_text()
        self.assertIn("Classification: NONZERO_EXIT", report)
        self.assertIn("Signal name: UNKNOWN", report)

    def test_missing_facts_are_explicit_unknown(self):
        incident = {
            "service": "Authserver",
            "incident_id": "inc-004",
            "filename_timestamp": "20261113T112001Z",
        }
        report = f15.write_report(self.root, incident).read_text()
        self.assertIn("PID: UNKNOWN", report)
        self.assertIn("Classification: UNKNOWN", report)

    def test_context_is_bounded_to_recent_bytes(self):
        incident = dict(self.inc)
        incident["incident_id"] = "inc-005"
        incident["recent_context"] = "x" * 100000
        report = f15.write_report(self.root, incident).read_text()
        self.assertIn("TRUNCATED TO MOST RECENT BYTES", report)
        self.assertLess(len(report.encode()), 40000)

if __name__ == "__main__":
    unittest.main()
