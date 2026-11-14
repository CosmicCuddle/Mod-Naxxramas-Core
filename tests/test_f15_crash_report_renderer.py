import importlib.util
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

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

    def expected_report_path(self, incident=None):
        incident = incident or self.inc
        return self.root / (
            f"{incident['filename_timestamp']}-{incident['service']}-"
            f"{incident['incident_id']}.txt"
        )

    def create_report_only(self, incident=None):
        incident = incident or self.inc
        self.root.mkdir(mode=0o700, parents=False)
        path = self.expected_report_path(incident)
        f15._exclusive_write(path, f15.render_report(incident).encode("utf-8"))
        return path

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

    def test_ensure_report_retry_is_idempotent(self):
        path = f15.ensure_report(self.root, self.inc)
        first_report = path.read_bytes()
        f15.ensure_report(self.root, self.inc)
        self.assertEqual(path.read_bytes(), first_report)
        history = (self.root / "Crash-History.txt").read_text()
        line = f15._history_line(self.inc, path.name, self.inc["filename_timestamp"])
        self.assertEqual(history.splitlines(keepends=True).count(line), 1)

    def test_partial_report_without_history_is_repaired(self):
        path = self.create_report_only()
        before = path.read_bytes()
        f15.ensure_report(self.root, self.inc)
        self.assertEqual(path.read_bytes(), before)
        history = (self.root / "Crash-History.txt").read_text()
        line = f15._history_line(self.inc, path.name, self.inc["filename_timestamp"])
        self.assertEqual(history.splitlines(keepends=True).count(line), 1)

    def test_concurrent_partial_repair_appends_exactly_once(self):
        path = self.create_report_only()
        before = path.read_bytes()
        errors = []

        def run():
            try:
                f15.ensure_report(self.root, self.inc)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(path.read_bytes(), before)
        line = f15._history_line(self.inc, path.name, self.inc["filename_timestamp"])
        lines = (self.root / "Crash-History.txt").read_text().splitlines(keepends=True)
        self.assertEqual(lines.count(line), 1)

    def test_concurrent_report_creation_never_duplicates_history(self):
        errors = []
        paths = []

        def run():
            try:
                paths.append(f15.ensure_report(self.root, self.inc))
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(paths), 6)
        line = f15._history_line(
            self.inc, self.expected_report_path().name, self.inc["filename_timestamp"]
        )
        lines = (self.root / "Crash-History.txt").read_text().splitlines(keepends=True)
        self.assertEqual(lines.count(line), 1)

    def test_history_fields_are_single_line_and_retryable(self):
        incident = dict(self.inc)
        incident["classification"] = "BAD\tSTATE\nWITH BREAK"
        incident["exit_code"] = "7\nextra"
        path = f15.ensure_report(self.root, incident)
        f15.ensure_report(self.root, incident)
        lines = (self.root / "Crash-History.txt").read_text().splitlines(keepends=True)
        self.assertEqual(len(lines), 1)
        self.assertNotIn("\tSTATE\n", lines[0])
        self.assertIn("BAD STATE WITH BREAK", lines[0])
        self.assertEqual(
            lines.count(f15._history_line(
                incident, path.name, incident["filename_timestamp"]
            )),
            1,
        )

    def test_oversized_history_refused_without_modifying_report(self):
        path = self.create_report_only()
        report_before = path.read_bytes()
        history = self.root / "Crash-History.txt"
        history.write_bytes(b"x\n" * 64)
        history.chmod(0o600)
        with mock.patch.object(f15, "MAX_HISTORY_BYTES", 32):
            with self.assertRaises(f15.Refused):
                f15.ensure_report(self.root, self.inc)
        self.assertEqual(path.read_bytes(), report_before)
        self.assertEqual(history.read_bytes(), b"x\n" * 64)

    def test_append_that_would_cross_history_bound_is_refused(self):
        path = self.create_report_only()
        history = self.root / "Crash-History.txt"
        history.write_bytes(b"foreign\n")
        history.chmod(0o600)
        line = f15._history_line(self.inc, path.name, self.inc["filename_timestamp"])
        with mock.patch.object(f15, "MAX_HISTORY_BYTES", len(b"foreign\n") + len(line.encode()) - 1):
            with self.assertRaises(f15.Refused):
                f15.ensure_report(self.root, self.inc)
        self.assertEqual(history.read_bytes(), b"foreign\n")

    def test_history_symlink_refused_without_touching_target_or_report(self):
        path = self.create_report_only()
        before = path.read_bytes()
        target = Path(self.t.name) / "foreign-history"
        target.write_text("foreign\n")
        history = self.root / "Crash-History.txt"
        history.symlink_to(target)
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(target.read_text(), "foreign\n")
        self.assertEqual(path.read_bytes(), before)

    def test_insecure_history_refused_without_modifying_report(self):
        path = self.create_report_only()
        before = path.read_bytes()
        history = self.root / "Crash-History.txt"
        history.write_text("foreign\n")
        history.chmod(0o644)
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(history.read_text(), "foreign\n")

    def test_hardlinked_history_refused(self):
        self.create_report_only()
        history = self.root / "Crash-History.txt"
        history.write_text("foreign\n")
        history.chmod(0o600)
        other = Path(self.t.name) / "other-history"
        os.link(history, other)
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(history.read_text(), "foreign\n")
        self.assertEqual(other.read_text(), "foreign\n")

    def test_non_utf8_history_refused(self):
        self.create_report_only()
        history = self.root / "Crash-History.txt"
        history.write_bytes(b"foreign-\xff\n")
        history.chmod(0o600)
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(history.read_bytes(), b"foreign-\xff\n")

    def test_incomplete_trailing_history_line_refused(self):
        self.create_report_only()
        history = self.root / "Crash-History.txt"
        history.write_bytes(b"incomplete")
        history.chmod(0o600)
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(history.read_bytes(), b"incomplete")

    def test_duplicate_existing_history_line_is_refused(self):
        path = self.create_report_only()
        line = f15._history_line(self.inc, path.name, self.inc["filename_timestamp"])
        history = self.root / "Crash-History.txt"
        history.write_text(line + line)
        history.chmod(0o600)
        with self.assertRaises(f15.Refused):
            f15.ensure_report(self.root, self.inc)
        self.assertEqual(history.read_text(), line + line)

    def test_partial_history_os_write_is_completed(self):
        path = self.create_report_only()
        real_write = os.write
        first = {"yes": True}

        def partial(fd, data):
            if first["yes"] and len(data) > 1:
                first["yes"] = False
                half = max(1, len(data) // 2)
                return real_write(fd, data[:half])
            return real_write(fd, data)

        with mock.patch.object(f15.os, "write", side_effect=partial):
            f15.ensure_report(self.root, self.inc)

        line = f15._history_line(self.inc, path.name, self.inc["filename_timestamp"])
        self.assertEqual((self.root / "Crash-History.txt").read_text(), line)

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
