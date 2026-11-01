"""Disposable F15 raw-storage audit tests: synthetic subprocesses only."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import f15_process_supervisor as supervisor  # noqa: E402
import f15_supervised_storage_audit as audit  # noqa: E402
from f15_operator_collector import Refused  # noqa: E402


class StorageAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.raw = self.base / "raw"
        self.archive = self.base / "archives"

    def launch(self, service, text="SECRET_NOT_IN_REPORT", exit_code=0):
        command = [sys.executable, "-c",
                   "import sys; print(" + repr(text) +
                   ", flush=True); sys.exit(" + str(exit_code) + ")"]
        return supervisor.supervise(self.raw, self.archive, service, command,
                                    poll_seconds=0.02)

    def report(self, days=0):
        future = datetime.now(timezone.utc) + timedelta(days=days)
        return audit.inspect_raw_storage(self.raw, self.archive,
                                         now=future.timestamp())

    def test_world_auth_separate_only_sizes_and_exit_evidence(self):
        w, _ = self.launch("Worldserver", exit_code=0)
        a, _ = self.launch("Authserver", exit_code=3)
        original = [(p, p.read_bytes()) for run in (w, a)
                    for p in (run / "stdout.raw", run / "stderr.raw")]
        data = self.report()
        self.assertEqual(data["mode"], "READ_ONLY_METADATA_AUDIT")
        self.assertEqual(data["deletions"], 0)
        self.assertEqual(data["services"]["Worldserver"]["completed_runs"], 1)
        self.assertEqual(data["services"]["Authserver"]["completed_runs"], 1)
        self.assertEqual(data["services"]["Worldserver"]["observed_exit_kinds"]["clean_exit"], 1)
        self.assertEqual(data["services"]["Authserver"]["observed_exit_kinds"]["nonzero_exit"], 1)
        self.assertGreater(data["services"]["Worldserver"]["raw_bytes"], 0)
        self.assertGreater(data["services"]["Authserver"]["raw_bytes"], 0)
        self.assertNotIn("SECRET_NOT_IN_REPORT", json.dumps(data))
        for path, content in original:
            self.assertEqual(path.read_bytes(), content)

    def test_age_boundary_reports_but_never_deletes_raw(self):
        run, _ = self.launch("Worldserver", "safe")
        original = (run / "stdout.raw").read_bytes()
        self.assertEqual(self.report(days=29)["services"]["Worldserver"]
                         ["older_than_30_days_completed_runs"], 0)
        after = self.report(days=31)
        self.assertEqual(after["services"]["Worldserver"]["older_than_30_days_completed_runs"], 1)
        self.assertGreater(after["services"]["Worldserver"]["older_than_30_days_raw_bytes"], 0)
        self.assertEqual(after["deletions"], 0)
        self.assertEqual((run / "stdout.raw").read_bytes(), original)
        self.assertTrue((run / "exit.json").exists())

    def test_incomplete_run_never_classified_as_expired(self):
        run, _ = self.launch("Worldserver")
        (run / "exit.json").unlink()  # synthetic temp fixture ONLY
        result = self.report(days=45)["services"]["Worldserver"]
        self.assertEqual(result["unfinished_runs"], 1)
        self.assertEqual(result["completed_runs"], 0)
        self.assertEqual(result["older_than_30_days_completed_runs"], 0)
        self.assertTrue((run / "stdout.raw").exists())

    def test_raw_symlink_refused_without_reading_external_content(self):
        run, _ = self.launch("Worldserver")
        external = self.base / "external.txt"
        external.write_text("EXTERNAL_SECRET")
        (run / "stdout.raw").unlink()  # synthetic fixture ONLY
        (run / "stdout.raw").symlink_to(external)
        with self.assertRaises(Refused):
            self.report(days=40)
        self.assertEqual(external.read_text(), "EXTERNAL_SECRET")

    def test_raw_hardlink_refused(self):
        run, _ = self.launch("Worldserver")
        os.link(run / "stderr.raw", self.base / "extra-hardlink")
        with self.assertRaises(Refused):
            self.report()

    def test_forged_capture_receipt_is_rejected(self):
        run, _ = self.launch("Worldserver")
        start = run / "start.json"
        fields = json.loads(start.read_text())
        fields["capture_root"] = str(self.base / "foreign")
        start.write_text(json.dumps(fields))
        with self.assertRaises(Refused):
            self.report()

    def test_missing_roots_are_not_created(self):
        with self.assertRaises(Refused):
            self.report()
        self.assertFalse(self.raw.exists())
        self.assertFalse(self.archive.exists())


if __name__ == "__main__":
    unittest.main()
