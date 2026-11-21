"""Executable POSIX-only fault injection; never launches owner services."""
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import f15_supervised_incident as adapter


@unittest.skipUnless(os.name == "posix", "real private storage/wait status requires POSIX")
class SupervisedIncidents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def launch(self, source, service="Authserver"):
        return adapter.supervise_and_report(self.root / "output", self.root / "archive",
            self.root / "Crash Logs", self.root / "Crash Logs" / "Raw Evidence", service,
            [sys.executable, "-c", source], execute=True, poll_seconds=0.02,
            build_version="fixture-build", source_revision="fixture-sha")

    def test_off_by_default_does_not_spawn(self):
        with mock.patch.object(adapter.supervisor, "supervise") as spawn:
            with self.assertRaises(adapter.supervisor.Refused):
                adapter.supervise_and_report(None, None, None, None, "Authserver", [])
            spawn.assert_not_called()

    def test_clean_and_nonzero_exits_report_both_services(self):
        for service, code in (("Authserver", 0), ("Worldserver", 7)):
            run, outcome, report = self.launch("import sys; print('checkpoint'); print('password=SECRET_FIXTURE'); sys.exit(" + str(code) + ")", service)
            text = report.read_text()
            self.assertEqual(outcome["exit_code"], code)
            self.assertIn("CLEAN_EXIT" if code == 0 else "NONZERO_EXIT", text)
            self.assertIn("checkpoint", text)
            self.assertNotIn("SECRET_FIXTURE", text)
            self.assertIn("SECRET_FIXTURE", (run / "stdout.raw").read_text())
            self.assertIn("fixture-sha", text)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_signal_wait_status_is_not_guessed_crash_cause(self):
        _, outcome, report = self.launch("import os,signal; os.kill(os.getpid(),signal.SIGTERM)")
        self.assertEqual(outcome["exit_code"], -signal.SIGTERM)
        self.assertIn("Signal name: SIGTERM", report.read_text())
        self.assertIn("does not prove an engine defect", report.read_text())

    def test_oversized_stream_omitted_before_any_trim(self):
        run, _, report = self.launch("print('password=' + 'A'*70000 + 'SECRET_END')")
        text = report.read_text()
        self.assertNotIn("SECRET_END", text)
        self.assertIn("exceeds rendered-input bound", text)
        self.assertIn("SECRET_END", (run / "stdout.raw").read_text())


if __name__ == "__main__":
    unittest.main()
