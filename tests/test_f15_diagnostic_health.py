"""Real disposable children and filesystem faults; no owner files/processes."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import f15_supervised_incident as adapter
import f15_crash_report_renderer as renderer
import f15_raw_evidence_bundle as bundles

@unittest.skipUnless(os.name=="posix","private health receipts require POSIX")
class Health(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def launch(self,code="pass"):
        return adapter.supervise_and_report(self.root/"source",self.root/"archive",self.root/"Crash Logs",
                self.root/"Crash Logs"/"Raw Evidence","Authserver",[sys.executable,"-c",code],
                execute=True,poll_seconds=0.02)

    def run_dir(self):return next((self.root/"source"/"runs").iterdir())

    def test_clean_receipts_private_and_health_does_not_spawn(self):
        run,_,_=self.launch()
        with mock.patch.object(adapter.supervisor,"supervise",side_effect=AssertionError("must not spawn")):
            self.assertEqual(adapter.diagnostic_health(run),("REPORT_COMPLETE",True))
        for path in run.glob("diagnostics-*.json"):
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(len(list(run.glob("diagnostics-*.json"))),2)

    def test_failure_is_explicit_and_secret_exception_not_serialized(self):
        with mock.patch.object(renderer,"ensure_report",side_effect=OSError("PRIVATE_PASSWORD")):
            with self.assertRaises(adapter.PostExitReportFailure):self.launch()
        run=self.run_dir()
        self.assertEqual(adapter.diagnostic_health(run),("REPORT_FAILED",False))
        self.assertNotIn("PRIVATE_PASSWORD",(run/"diagnostics-report-failed.json").read_text())

    def test_missing_receipt_remains_unknown_without_creating_directory(self):
        missing=self.root/"missing"
        with self.assertRaises((OSError,bundles.Refused)):adapter.diagnostic_health(missing)
        self.assertFalse(missing.exists())
        self.assertEqual(adapter.diagnostic_health(self.root),("UNKNOWN_OR_PARTIAL",False))

    def test_partial_and_conflicting_receipts_are_unhealthy(self):
        run,outcome,_=self.launch()
        pending=run/"diagnostics-report-complete.json.pending";pending.touch(mode=0o600)
        self.assertEqual(adapter.diagnostic_health(run),("UNKNOWN_OR_PARTIAL",False));pending.unlink()
        self.assertTrue(adapter._health_write(run,"report-failed",outcome))
        self.assertEqual(adapter.diagnostic_health(run),("CONFLICTING_RECEIPTS",False))

    def test_health_writer_failure_does_not_replace_observed_child_status(self):
        with mock.patch.object(adapter,"_health_write",return_value=False):
            run,outcome,report=self.launch("raise SystemExit(7)")
        self.assertEqual(outcome["exit_code"],7)
        self.assertEqual(outcome["diagnostic_health_receipt_status"],"failed")
        self.assertTrue(report.exists())
        self.assertEqual(adapter.diagnostic_health(run),("UNKNOWN_OR_PARTIAL",False))

    def test_non_utf8_output_and_unknown_binary_text_do_not_break_health(self):
        run,_,report=self.launch("import sys;sys.stdout.buffer.write(b'checkpoint\\xff\\n')")
        self.assertEqual(adapter.diagnostic_health(run),("REPORT_COMPLETE",True))
        self.assertIn("checkpoint",report.read_text())

    def test_unreadable_console_preserves_original_and_marks_report_failed(self):
        real=adapter.supervisor.supervise
        def mutate(*args,**kwargs):
            run,outcome=real(*args,**kwargs);(run/"stdout.raw").chmod(0);return run,outcome
        try:
            with mock.patch.object(adapter.supervisor,"supervise",side_effect=mutate):
                with self.assertRaises(adapter.PostExitReportFailure):self.launch("print('checkpoint')")
            self.assertEqual(adapter.diagnostic_health(self.run_dir()),("REPORT_FAILED",False))
        finally:
            path=self.run_dir()/"stdout.raw";path.chmod(0o600)
        self.assertIn("checkpoint",path.read_text())

    def test_fifo_and_oversized_health_files_refused_without_blocking(self):
        run,_,_=self.launch();path=run/"diagnostics-started.json";path.unlink();os.mkfifo(path,0o600)
        with self.assertRaises(renderer.Refused):adapter.diagnostic_health(run)
        path.unlink();path.write_bytes(b'X'*4097);path.chmod(0o600)
        with self.assertRaises(renderer.Refused):adapter.diagnostic_health(run)

    def test_health_cli_distinguishes_receipts_from_child_success(self):
        run,_,_=self.launch()
        out=io.StringIO()
        with contextlib.redirect_stdout(out):status=adapter.main(["health","--run-root",str(run)])
        self.assertEqual(status,0);self.assertIn("REPORT_COMPLETE",out.getvalue())
        self.assertNotIn(str(run),out.getvalue())
        (run/"diagnostics-report-complete.json").unlink()
        with contextlib.redirect_stdout(io.StringIO()):status=adapter.main(["health","--run-root",str(run)])
        self.assertEqual(status,2)
