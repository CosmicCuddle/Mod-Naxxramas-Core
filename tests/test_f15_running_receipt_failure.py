"""Real finite children; inject only post-spawn receipt storage failures."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import f15_process_supervisor as supervisor
import f15_supervised_incident as adapter
import f15_supervised_retention as retention

PARENT = "854879f9cae3939cd0dc3123ff3ba91758f65ebf"
SENTINEL = "SYNTHETIC_PRIVATE_RECEIPT_FAILURE"
CHILD = "import sys,time; print('before',flush=True); time.sleep(.08); print('after'); sys.exit(7)"


@unittest.skipUnless(os.name == "posix", "real private POSIX storage and wait status")
class RunningReceiptFailures(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.children = []
        # Always reap the finite test payload, including historical failure.
        self.addCleanup(self.reap)

    def reap(self):
        for child in self.children:
            child.wait(timeout=10)

    @contextlib.contextmanager
    def fail_running(self, module=supervisor, partial=False, capture_failure=False, published=False):
        real_write, real_popen = module.atomic_write, subprocess.Popen

        def write(path, data):
            if path.name == "running.json":
                if published:
                    real_write(path, data)
                if partial:
                    pending = path.with_name(path.name + ".pending")
                    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(b'{"partial":')
                raise OSError(SENTINEL)
            return real_write(path, data)

        def spawn(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            self.children.append(child)
            return child

        with mock.patch.object(module, "atomic_write", side_effect=write), \
             mock.patch.object(module.subprocess, "Popen", side_effect=spawn):
            if capture_failure:
                with mock.patch.object(module, "collect_once", side_effect=ValueError(SENTINEL)):
                    yield
            else:
                yield

    def supervise(self, module=supervisor):
        return module.supervise(self.root / "source", self.root / "archive", "Authserver",
                                [sys.executable, "-c", CHILD], poll_seconds=0.02)

    def report(self):
        return adapter.supervise_and_report(
            self.root / "source", self.root / "archive", self.root / "Crash Logs",
            self.root / "Crash Logs" / "Raw Evidence", "Worldserver",
            [sys.executable, "-c", CHILD], execute=True, poll_seconds=0.02)

    def test_exact_parent_abandons_wait_on_post_spawn_storage_error(self):
        source = subprocess.check_output(
            ["git", "show", PARENT + ":scripts/f15_process_supervisor.py"], cwd=ROOT).decode("utf-8")
        historical = types.ModuleType("historical_f15_supervisor")
        exec(compile(source, "historical_f15_supervisor.py", "exec"), historical.__dict__)
        with self.fail_running(historical):
            with self.assertRaisesRegex(OSError, SENTINEL):
                self.supervise(historical)
        self.assertEqual(len(self.children), 1)
        self.assertFalse(list((self.root / "source").rglob("exit.json")))
        self.children[0].wait(timeout=10)
        self.assertEqual(self.children[0].returncode, 7)

    def test_failure_keeps_owned_child_wait_capture_and_fail_closed_exit(self):
        with self.fail_running(partial=True):
            run, outcome = self.supervise()
        self.assertEqual(len(self.children), 1)
        self.assertEqual(self.children[0].returncode, 7)
        self.assertEqual(outcome["exit_code"], 7)
        self.assertEqual(outcome["capture"], "fail_closed")
        self.assertEqual(outcome["capture_error_type"], "RunningReceiptPersistenceFailure")
        self.assertEqual((run / "stdout.raw").read_text(), "before\nafter\n")
        self.assertEqual((run / "running.json.pending").read_bytes(), b'{"partial":')
        self.assertEqual(json.loads((run / "exit.json").read_bytes()), outcome)
        archived = Path(outcome["capture_root"]) / "archives" / "Authserver-out"
        self.assertEqual(next(archived.glob("*.txt")).read_text(), "before\nafter\n")
        with self.assertRaises(retention.Refused):
            retention.expire_completed_runs_once(self.root / "source", self.root / "archive")
        self.assertTrue((run / "stdout.raw").exists())

    def test_composed_report_and_health_keep_diagnostic_gap_and_private_failure(self):
        with self.fail_running():
            run, outcome, report = self.report()
        self.assertEqual(outcome["exit_code"], 7)
        text = report.read_text()
        self.assertIn("RunningReceiptPersistenceFailure", text)
        self.assertIn("before", text)
        self.assertIn("after", text)
        self.assertNotIn(SENTINEL, text)
        self.assertEqual(adapter.diagnostic_health(run), ("REPORT_COMPLETE_WITH_GAPS", False))

    def test_post_publication_error_preserves_running_receipt_and_wait_evidence(self):
        # Atomic publication can rename successfully before directory fsync fails.
        with self.fail_running(published=True):
            run, outcome = self.supervise()
        started = json.loads((run / "running.json").read_bytes())
        self.assertEqual(started["pid"], outcome["pid"])
        self.assertEqual(started["state"], "started")
        self.assertEqual(outcome["exit_code"], 7)
        self.assertEqual(outcome["capture_error_type"], "RunningReceiptPersistenceFailure")
        self.assertFalse((run / "running.json.pending").exists())

    def test_console_sink_error_remains_authoritative_when_both_sinks_fail(self):
        with self.fail_running(capture_failure=True):
            run, outcome = self.supervise()
        self.assertEqual(outcome["exit_code"], 7)
        self.assertEqual(outcome["capture_error_type"], "ValueError")
        self.assertEqual((run / "stdout.raw").read_text(), "before\nafter\n")

    def test_launcher_preserves_child_status_and_diagnostic_cli_fails(self):
        for launcher, expected in ((True, 7), (False, 2)):
            with self.subTest(launcher=launcher):
                # Independent roots avoid reusing any lifecycle artifacts.
                original = self.root
                self.root = original / str(launcher)
                self.root.mkdir(mode=0o700)
                args = ["supervise", "--output-root", str(self.root / "source"),
                        "--archive-root", str(self.root / "archive"),
                        "--crash-root", str(self.root / "Crash Logs"),
                        "--raw-root", str(self.root / "Crash Logs" / "Raw Evidence"),
                        "--service", "Authserver", "--execute"]
                if launcher:
                    args.append("--launcher-mode")
                out, err = io.StringIO(), io.StringIO()
                try:
                    with self.fail_running(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        code = CHILD if launcher else CHILD.replace("sys.exit(7)", "sys.exit(0)")
                        status = adapter.main(args + ["--", sys.executable, "-c", code])
                    self.assertEqual(status, expected)
                    self.assertNotIn(SENTINEL, out.getvalue() + err.getvalue())
                finally:
                    self.root = original
