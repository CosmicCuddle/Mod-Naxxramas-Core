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

    def failed_run(self):
        import f15_crash_report_renderer as renderer
        with mock.patch.object(renderer, "ensure_report", side_effect=OSError("injected report failure")):
            with self.assertRaises(OSError):
                self.launch("print('retained checkpoint')")
        raw = self.root / "Crash Logs" / "Raw Evidence"
        import json
        bundle = next(raw.iterdir())
        iid = json.loads((bundle / "manifest.json").read_text())["incident_id"]
        return raw, bundle, iid

    def test_recovery_never_respawns_and_is_idempotent(self):
        raw, _, iid = self.failed_run()
        with mock.patch.object(adapter.supervisor, "supervise", side_effect=AssertionError("must not spawn")):
            report = adapter.recover_report(self.root / "Crash Logs", raw, iid)
            first = report.read_bytes()
            self.assertEqual(adapter.recover_report(self.root / "Crash Logs", raw, iid), report)
            self.assertEqual(first, report.read_bytes())
        self.assertIn("retained checkpoint", report.read_text())
        rows = (self.root / "Crash Logs" / "Crash-History.txt").read_text().splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].split("\t")[2], iid)

    def test_recovery_refuses_tampered_input(self):
        raw, bundle, iid = self.failed_run()
        (bundle / "report-input.json").write_text("{}")
        import f15_raw_evidence_bundle as bundles
        with self.assertRaises(bundles.Refused) as caught:
            adapter.recover_report(self.root / "Crash Logs", raw, iid)
        self.assertIn("mismatch", str(caught.exception))
        self.assertFalse((self.root / "Crash Logs" / "Crash-History.txt").exists())

    def test_recovery_finishes_history_after_report_publication(self):
        import f15_crash_report_renderer as renderer
        import json
        with mock.patch.object(renderer, "_ensure_history_once", side_effect=OSError("injected history failure")):
            with self.assertRaises(OSError):
                self.launch("print('history recovery')")
        raw = self.root / "Crash Logs" / "Raw Evidence"
        bundle = next(raw.iterdir())
        iid = json.loads((bundle / "manifest.json").read_text())["incident_id"]
        existing = next((self.root / "Crash Logs").glob("*Authserver*.txt"))
        original = existing.read_bytes()
        self.assertEqual(adapter.recover_report(self.root / "Crash Logs", raw, iid), existing)
        self.assertEqual(existing.read_bytes(), original)
        rows = (self.root / "Crash Logs" / "Crash-History.txt").read_text().splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].split("\t")[2], iid)

    def test_recovery_missing_evidence_never_spawns(self):
        import f15_raw_evidence_bundle as bundles
        raw = self.root / "raw"
        raw.mkdir(mode=0o700)
        with mock.patch.object(adapter.supervisor, "supervise") as spawn:
            with self.assertRaises(bundles.Refused):
                adapter.recover_report(self.root / "Crash Logs", raw, "missing")
            spawn.assert_not_called()

    def cli(self, *args):
        import subprocess
        return subprocess.run([sys.executable, str(Path(adapter.__file__)), *args],
                              capture_output=True, text=True, timeout=15)

    def cli_roots(self):
        return ["--crash-root", str(self.root / "Crash Logs"),
                "--raw-root", str(self.root / "Crash Logs" / "Raw Evidence")]

    def test_cli_requires_explicit_execution_without_child_side_effect(self):
        marker = self.root / "unexpected"
        result = self.cli("supervise", *self.cli_roots(), "--output-root", str(self.root / "output"),
                          "--archive-root", str(self.root / "archive"), "--service", "Authserver", "--",
                          sys.executable, "-c", "open(" + repr(str(marker)) + ", 'w').close()")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "output").exists())

    def test_cli_executes_argument_vector_without_shell_and_hides_paths(self):
        code = "import sys; print(sys.argv[1])"
        literal = "$(touch nope); literal value"
        result = self.cli("supervise", *self.cli_roots(), "--output-root", str(self.root / "output"),
                          "--archive-root", str(self.root / "archive"), "--service", "Worldserver",
                          "--execute", "--", sys.executable, "-c", code, literal)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        run = next((self.root / "output" / "runs").iterdir())
        self.assertEqual((run / "stdout.raw").read_text().strip(), literal)

    def test_cli_nonzero_child_is_diagnostic_failure_with_report_retained(self):
        result = self.cli("supervise", *self.cli_roots(), "--output-root", str(self.root / "output"),
                          "--archive-root", str(self.root / "archive"), "--service", "Authserver",
                          "--execute", "--", sys.executable, "-c", "raise SystemExit(7)")
        self.assertEqual(result.returncode, 2)
        report = next((self.root / "Crash Logs").glob("*Authserver*.txt"))
        self.assertIn("Exit code: 7", report.read_text())
        self.assertIn("NONZERO_EXIT", report.read_text())

    def test_cli_recovers_and_sanitizes_missing_evidence_error(self):
        raw, _, iid = self.failed_run()
        result = self.cli("recover", *self.cli_roots(), "--incident-id", iid)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("recover", *self.cli_roots(), "--incident-id", "missing")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(str(raw), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_oversized_stream_omitted_before_any_trim(self):
        run, _, report = self.launch("print('password=' + 'A'*70000 + 'SECRET_END')")
        text = report.read_text()
        self.assertNotIn("SECRET_END", text)
        self.assertIn("exceeds rendered-input bound", text)
        self.assertIn("SECRET_END", (run / "stdout.raw").read_text())


if __name__ == "__main__":
    unittest.main()
