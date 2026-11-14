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
            "replacement_pid": 456,
            "ppid": 2,
            "process_start_epoch_ms": 1700000000000,
            "replacement_start_epoch_ms": 1700000005000,
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
        self.assertIn("Replacement PID: 456", report)
        self.assertIn("Process start epoch ms: 1700000000000", report)
        self.assertIn("Replacement start epoch ms: 1700000005000", report)
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



    def test_ensure_report_retry_refuses_symlink_report(self):
        expected = self.root / "20261113T112000Z-Worldserver-inc-001.txt"
        self.root.mkdir(mode=0o700)
        target = self.root / "target.txt"
        target.write_bytes(f15.render_report(self.inc).encode("utf-8"))
        target.chmod(0o600)
        expected.symlink_to(target)
        with self.assertRaises((f15.Refused, OSError)):
            f15.ensure_report(self.root, self.inc)

    def test_private_report_reader_returns_exact_inode_and_bytes(self):
        path = f15.write_report(self.root, self.inc)
        data, inode = f15._read_private_report(path)
        self.assertEqual(data, path.read_bytes())
        self.assertEqual(inode, path.stat().st_ino)

    def test_ensure_report_retry_does_not_duplicate_history(self):
        first = f15.ensure_report(self.root, self.inc)
        second = f15.ensure_report(self.root, self.inc)
        self.assertEqual(first, second)
        history = (self.root / "Crash-History.txt").read_text().splitlines()
        self.assertEqual(len(history), 1)
        self.assertIn("inc-001", history[0])

    def test_duplicate_history_rows_are_refused_on_retry(self):
        path = f15.ensure_report(self.root, self.inc)
        history = self.root / "Crash-History.txt"
        line = history.read_text()
        history.write_text(line + line)
        history.chmod(0o600)
        self.assertTrue(path.exists())
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)

    def test_invalid_utf8_history_is_refused_without_append(self):
        self.root.mkdir(mode=0o700)
        history = self.root / "Crash-History.txt"
        history.write_bytes(b"\xff\xfe")
        history.chmod(0o600)
        before = history.read_bytes()
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(history.read_bytes(), before)


    def test_report_publish_leaves_no_pending_file_on_success(self):
        path = f15.write_report(self.root, self.inc)
        self.assertTrue(path.exists())
        self.assertFalse(path.with_name(path.name + ".pending").exists())

    def test_existing_pending_report_blocks_publish_without_final_file(self):
        self.root.mkdir(mode=0o700)
        final = self.root / "20261113T112000Z-Worldserver-inc-001.txt"
        pending = final.with_name(final.name + ".pending")
        pending.write_bytes(b"partial")
        pending.chmod(0o600)
        with self.assertRaises(f15.Refused):
            f15.write_report(self.root, self.inc)
        self.assertFalse(final.exists())
        self.assertEqual(pending.read_bytes(), b"partial")

    def test_publish_race_never_overwrites_existing_final(self):
        self.root.mkdir(mode=0o700)
        final = self.root / "20261113T112000Z-Worldserver-inc-001.txt"
        original = b"foreign-existing"
        final.write_bytes(original)
        final.chmod(0o600)
        with self.assertRaises(f15.Refused):
            f15.write_report(self.root, self.inc)
        self.assertEqual(final.read_bytes(), original)

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


    def test_crash_root_parent_symlink_refused(self):
        real = Path(self.t.name) / "real-parent"
        real.mkdir()
        link = Path(self.t.name) / "linked-parent"
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises(f15.Refused):
            f15.write_report(link / "Crash Logs", self.inc)

if __name__ == "__main__":
    unittest.main()
