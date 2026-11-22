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

    def test_launcher_preserves_nonzero_status(self):
        result = self.cli("supervise", *self.cli_roots(), "--output-root", str(self.root / "output"),
                          "--archive-root", str(self.root / "archive"), "--service", "Authserver",
                          "--execute", "--launcher-mode", "--", sys.executable, "-c", "raise SystemExit(7)")
        self.assertEqual(result.returncode, 7, result.stderr)

    def test_launcher_forwards_stop_to_owned_child_and_reports_signal(self):
        self.check_launcher_stop(False)

    def test_launcher_timeout_escalates_only_after_stop_request(self):
        self.check_launcher_stop(True)

    def check_launcher_stop(self, ignore_stop):
        import subprocess
        import time
        ready = self.root / "ready"
        child_code = ("import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); " if ignore_stop else "") + "from pathlib import Path; import time; Path(" + repr(str(ready)) + ").touch(); time.sleep(10)"
        command = [sys.executable, str(Path(adapter.__file__)), "supervise", *self.cli_roots(),
                   "--output-root", str(self.root / "output"), "--archive-root", str(self.root / "archive"),
                   "--service", "Worldserver", "--execute", "--launcher-mode", *(["--stop-timeout", "0.1"] if ignore_stop else []), "--", sys.executable, "-c", child_code]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 137 if ignore_stop else 143, err)
            report = next((self.root / "Crash Logs").glob("*Worldserver*.txt"))
            self.assertIn("Signal name: " + ("SIGKILL" if ignore_stop else "SIGTERM"), report.read_text())
            if ignore_stop:
                self.assertIn("explicitly configured stop timeout", report.read_text())
            self.assertNotIn(str(self.root), out + err)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)

    def test_opt_in_signal_handlers_are_restored(self):
        before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        with adapter.supervisor.OwnedChildStops() as stops:
            stops.request(signal.SIGTERM, None)
            stops.request(signal.SIGTERM, None)
            self.assertEqual(stops.pending, [signal.SIGTERM])
        self.assertEqual(before, {sig: signal.getsignal(sig) for sig in before})

    def test_report_failure_preserves_observed_status_only_in_launcher_mode(self):
        import contextlib
        import io
        import json
        import f15_crash_report_renderer as renderer
        for index, (launcher, source, expected) in enumerate((
                (True, "raise SystemExit(7)", 7),
                (True, "pass", 0),
                (True, "import os,signal; os.kill(os.getpid(),signal.SIGTERM)", 143),
                (False, "raise SystemExit(7)", 2))):
            with self.subTest(launcher=launcher, expected=expected):
                err, out = io.StringIO(), io.StringIO()
                args = ["supervise", *self.cli_roots(), "--output-root", str(self.root / ("out" + str(index))),
                        "--archive-root", str(self.root / ("archive" + str(index))), "--service", "Authserver",
                        "--execute", *(["--launcher-mode"] if launcher else []), "--", sys.executable, "-c", source]
                with mock.patch.object(renderer, "ensure_report", side_effect=OSError("PRIVATE_SECRET_PATH")):
                    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                        status = adapter.main(args)
                self.assertEqual(status, expected)
                self.assertIn("publication failed", err.getvalue())
                self.assertNotIn("PRIVATE_SECRET_PATH", err.getvalue())
                self.assertNotIn("completed", out.getvalue())
                runs = list((self.root / ("out" + str(index)) / "runs").iterdir())
                self.assertEqual(len(runs), 1)
                receipt = json.loads((runs[0] / "exit.json").read_text())
                self.assertEqual(adapter.launcher_status(receipt["exit_code"]), expected if launcher else 7)

    def test_launcher_pre_exit_failure_does_not_fabricate_child_status(self):
        import contextlib
        import io
        with mock.patch.object(adapter.supervisor, "supervise", side_effect=OSError("PRIVATE_SECRET")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                status = adapter.main(["supervise", *self.cli_roots(), "--output-root", str(self.root / "out"),
                    "--archive-root", str(self.root / "archive"), "--service", "Authserver", "--execute",
                    "--launcher-mode", "--", sys.executable, "-c", "pass"])
        self.assertEqual(status, 2)
        self.assertNotIn("PRIVATE_SECRET", err.getvalue())

    def test_exit_receipt_failure_reports_memory_evidence_without_relaunch(self):
        import contextlib
        import io
        import json
        original = adapter.supervisor.atomic_write
        def fail_exit(path, data):
            if Path(path).name == "exit.json":
                raise OSError("PRIVATE_RECEIPT_PATH")
            return original(path, data)
        cases = ((True, "pass", 0), (True, "raise SystemExit(7)", 7),
                 (True, "import os,signal; os.kill(os.getpid(),signal.SIGTERM)", 143),
                 (False, "pass", 2))
        for index, (launcher, source, expected) in enumerate(cases):
            with self.subTest(expected=expected, launcher=launcher):
                err, out = io.StringIO(), io.StringIO()
                root = self.root / str(index)
                root.mkdir(mode=0o700)
                args = ["supervise", "--crash-root", str(root / "Crash Logs"),
                        "--raw-root", str(root / "Crash Logs" / "Raw Evidence"),
                        "--output-root", str(root / "output"), "--archive-root", str(root / "archive"),
                        "--service", "Authserver", "--execute", *(["--launcher-mode"] if launcher else []),
                        "--", sys.executable, "-c", source]
                with mock.patch.object(adapter.supervisor, "atomic_write", side_effect=fail_exit):
                    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                        status = adapter.main(args)
                self.assertEqual(status, expected)
                self.assertIn("receipt persistence failed", err.getvalue())
                self.assertNotIn("PRIVATE_RECEIPT_PATH", err.getvalue())
                runs = list((root / "output" / "runs").iterdir())
                self.assertEqual(len(runs), 1)
                self.assertFalse((runs[0] / "exit.json").exists())
                report = next((root / "Crash Logs").glob("*Authserver*.txt"))
                self.assertIn("recovered from memory", report.read_text())
                bundle = next((root / "Crash Logs" / "Raw Evidence").iterdir())
                receipt = json.loads((bundle / "supervisor-exit.json").read_text())
                self.assertEqual(receipt["exit_receipt_status"], "failed")

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
