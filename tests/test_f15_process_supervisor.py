"""Real F15 supervisor behavior, disposable child processes only. Never World/Auth."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import f15_process_supervisor as sup

class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.outputs = self.base / "source"
        self.archive = self.base / "archive"

    def launch(self, service, code):
        return sup.supervise(self.outputs, self.archive, service,
                             [sys.executable, "-c", code], poll_seconds=0.03)

    def archived(self, run, label):
        return self.archive / "runs" / run.name / "archives" / label

    def test_consecutive_runs_have_independent_archive_origins(self):
        first, first_report = self.launch("Worldserver", "print('first-run', flush=True)")
        second, second_report = self.launch("Worldserver", "print('second-run', flush=True)")
        self.assertNotEqual(first, second)
        self.assertEqual(first_report["capture"], "complete_for_observed_run")
        self.assertEqual(second_report["capture"], "complete_for_observed_run")
        self.assertEqual(Path(first_report["capture_root"]), self.archive / "runs" / first.name)
        self.assertEqual(Path(second_report["capture_root"]), self.archive / "runs" / second.name)
        first_bytes = next(self.archived(first, "Worldserver-out").glob("*.txt")).read_bytes()
        second_bytes = next(self.archived(second, "Worldserver-out").glob("*.txt")).read_bytes()
        self.assertEqual(first_bytes, b"first-run\n")
        self.assertEqual(second_bytes, b"second-run\n")
        self.assertEqual(len(list((self.archive / "runs").iterdir())), 2)

    def test_large_final_console_burst_is_fully_archived(self):
        # Child exits quickly with far more than one 64-KiB read per stream.
        out_size = 3 * 65536 + 17
        err_size = 2 * 65536 + 37
        code = (
            "import sys; "
            f"sys.stdout.buffer.write(b\'A\'*{out_size}); "
            f"sys.stderr.buffer.write(b\'B\'*{err_size})"
        )
        run, report = self.launch("Worldserver", code)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["capture"], "complete_for_observed_run")
        self.assertIsNone(report["capture_error_type"])
        self.assertEqual((run / "stdout.raw").read_bytes(), b"A" * out_size)
        self.assertEqual((run / "stderr.raw").read_bytes(), b"B" * err_size)
        self.assertEqual(next(self.archived(run, "Worldserver-out").glob("*.txt")).read_bytes(), b"A" * out_size)
        self.assertEqual(next(self.archived(run, "Worldserver-err").glob("*.txt")).read_bytes(), b"B" * err_size)

    def test_final_drain_limit_never_claims_complete(self):
        # Simulate a source that cannot be fully caught up by the bound.
        with mock.patch.object(sup, "MAX_FINAL_DRAIN_POLLS", 2):
            with mock.patch.object(sup, "collect_once", return_value={
                    "Authserver-out": 1, "Authserver-err": 0}):
                run, report = self.launch("Authserver", "print(123, flush=True)")
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["capture"], "fail_closed")
        self.assertEqual(report["capture_error_type"], "UncapturedConsoleBytes")
        self.assertEqual(json.loads((run / "exit.json").read_text())["capture"], "fail_closed")
        self.assertEqual((run / "stdout.raw").read_bytes(), b"123\n")

    def test_clean_exit_with_both_console_streams(self):
        run, report = self.launch("Worldserver",
            "import sys; print('world out',flush=True); sys.stderr.write('world err\\n')")
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["exit_kind"], "clean_exit")
        self.assertEqual(report["capture"], "complete_for_observed_run")
        self.assertEqual((run/"stdout.raw").read_bytes(),b"world out\n")
        self.assertEqual((run/"stderr.raw").read_bytes(),b"world err\n")
        self.assertEqual(len(list(self.archived(run, "Worldserver-out").glob("*.txt"))),1)
        self.assertEqual(next(self.archived(run, "Worldserver-out").glob("*.txt")).read_bytes(),b"world out\n")
        self.assertEqual(next(self.archived(run, "Worldserver-err").glob("*.txt")).read_bytes(),b"world err\n")
        self.assertEqual(json.loads((run/"exit.json").read_text())["exit_kind"],"clean_exit")

    def test_nonzero_is_not_mislabelled_crash(self):
        run, report = self.launch("Authserver", "import sys; print('before failure',flush=True); sys.exit(7)")
        self.assertEqual(report["exit_code"],7)
        self.assertEqual(report["exit_kind"],"nonzero_exit")
        self.assertEqual(report["capture"],"complete_for_observed_run")
        self.assertEqual(next(self.archived(run, "Authserver-out").glob("*.txt")).read_bytes(), b"before failure\n")
        self.assertNotIn("crash", (run/"exit.json").read_text())

    @unittest.skipUnless(os.name == "posix", "signal status is POSIX-specific")
    def test_signal_exit_is_recorded_without_guessing_crash(self):
        run, report = self.launch("Worldserver",
            "import os,signal;os.kill(os.getpid(),signal.SIGTERM)")
        self.assertEqual(report["exit_code"], -signal.SIGTERM)
        self.assertEqual(report["exit_kind"], "signaled_exit")
        self.assertTrue((run/"exit.json").exists())

    def test_refuse_overlapping_source_and_archive_roots(self):
        with self.assertRaises(sup.Refused):
            sup.supervise(self.outputs, self.outputs/"archive", "Worldserver",
                          [sys.executable,"-c","print('should not launch')"],poll_seconds=0.03)

    def test_refuse_invalid_service_before_launch(self):
        with self.assertRaises(sup.Refused):
            sup.supervise(self.outputs, self.archive, "Other",
                          [sys.executable,"-c","print('should not launch')"])

    def test_failed_launch_is_recorded(self):
        with self.assertRaises(sup.Refused):
            sup.supervise(self.outputs, self.archive, "Authserver",
                          [str(self.base/"nonexistent-executable")],poll_seconds=0.03)
        runs = list((self.outputs/"runs").iterdir())
        self.assertEqual(len(runs), 1)
        self.assertEqual(json.loads((runs[0]/"launch-failed.json").read_text())["state"],"launch_failed")
        self.assertFalse((runs[0]/"exit.json").exists())

    def _refused_cli(self, output_root):
        # Deliberate non-executable argv. Popen must never run in these
        # rejected prelaunch cases; no real service or operator files used.
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sup.subprocess, "Popen",
                               side_effect=AssertionError("unexpected child launch")) as spawn:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = sup.main([
                    "--output-root", str(output_root),
                    "--archive-root", str(self.archive),
                    "--service", "Worldserver", "--execute", "--",
                    str(self.base / "NEVER_LAUNCH_CHILD")])
            spawn.assert_not_called()
        self.assertEqual(rc, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(),
                         "F15 supervisor REFUSED: operation rejected; details withheld\\n")
        self.assertNotIn("SECRET_SENTINEL", out.getvalue() + err.getvalue())
        self.assertFalse((output_root / "runs" / "running.json").exists())

    @unittest.skipUnless(os.name == "posix", "private 0700 and symlinks are POSIX-specific")
    def test_cli_symlink_private_root_does_not_leak_path(self):
        link = self.base / "SECRET_SENTINEL_symlink"
        link.symlink_to(self.base, target_is_directory=True)
        self._refused_cli(link)
        self.assertFalse((self.base / "runs").exists())

    @unittest.skipUnless(os.name == "posix", "private 0700 is POSIX-specific")
    def test_cli_insecure_root_mode_does_not_leak_path(self):
        insecure = self.base / "SECRET_SENTINEL_mode0755"
        insecure.mkdir(mode=0o755)
        insecure.chmod(0o755)
        self._refused_cli(insecure)
        self.assertFalse((insecure / "runs").exists())

    @unittest.skipUnless(os.name == "posix", "missing parent error is POSIX-specific")
    def test_cli_missing_parent_oserror_does_not_leak_path(self):
        missing = self.base / "SECRET_SENTINEL_missing_parent" / "output"
        self._refused_cli(missing)
        self.assertFalse(missing.exists())

    def test_cli_caught_value_error_and_oserror_are_redacted(self):
        argv = ["--output-root", str(self.outputs),
                "--archive-root", str(self.archive),
                "--service", "Authserver", "--execute", "--",
                str(self.base / "NEVER_LAUNCH_CHILD")]
        errors = [
            ValueError("SECRET_SENTINEL_configuration"),
            FileNotFoundError(2, "SECRET_SENTINEL_os_file",
                              str(self.base / "SECRET_SENTINEL_missing.dat")),
            sup.Refused("SECRET_SENTINEL_rejection"),
        ]
        for err in errors:
            with self.subTest(type=type(err).__name__):
                out, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(sup, "supervise", side_effect=err) as call:
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(stderr):
                        rc = sup.main(argv)
                    call.assert_called_once()
                self.assertEqual(rc, 2)
                self.assertEqual(out.getvalue(), "")
                self.assertEqual(stderr.getvalue(),
                    "F15 supervisor REFUSED: operation rejected; details withheld\\n")
                self.assertNotIn("SECRET_SENTINEL", out.getvalue() + stderr.getvalue())
                self.assertFalse(self.outputs.exists())

    def test_cli_successful_run_json_is_not_silently_redacted(self):
        run = self.base / "INTENDED_VISIBLE_SUCCESS_RUN_PATH"
        outcome = {"exit_code": 0, "capture_error_type": None}
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sup, "supervise", return_value=(run, outcome)) as call:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = sup.main([
                    "--output-root", str(self.outputs),
                    "--archive-root", str(self.archive),
                    "--service", "Worldserver", "--execute", "--",
                    str(self.base / "NEVER_LAUNCH_CHILD")])
            call.assert_called_once()
        self.assertEqual(rc, 0)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(json.loads(out.getvalue())["run"], str(run))
        self.assertFalse(self.outputs.exists())

    def test_cli_requires_explicit_execute(self):
        with self.assertRaises(SystemExit):
            sup.main(["--output-root",str(self.outputs),"--archive-root",str(self.archive),
                      "--service","Worldserver","--",sys.executable,"-c","pass"])
        self.assertFalse(self.outputs.exists())

if __name__=="__main__":unittest.main()
