"""Real F15 supervisor behavior, disposable child processes only. Never World/Auth."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest

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

    def test_cli_requires_explicit_execute(self):
        with self.assertRaises(SystemExit):
            sup.main(["--output-root",str(self.outputs),"--archive-root",str(self.archive),
                      "--service","Worldserver","--",sys.executable,"-c","pass"])
        self.assertFalse(self.outputs.exists())

if __name__=="__main__":unittest.main()
