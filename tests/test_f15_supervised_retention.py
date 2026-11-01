"""F15 supervised child run archive retention: disposable fake children only."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from unittest import mock
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import f15_process_supervisor as sup
import f15_supervised_retention as cleanup
from f15_operator_collector import Refused


class SupervisedRetentionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.source = self.base / "raw"
        self.archive = self.base / "archives"

    def launch(self, name):
        return sup.supervise(self.source, self.archive, "Worldserver",
                             [sys.executable, "-c", f"print({name!r}, flush=True)"],
                             poll_seconds=0.02)

    def expire(self, days=33):
        future = datetime.now(timezone.utc) + timedelta(days=days)
        return cleanup.expire_completed_runs_once(
            self.source, self.archive, now=future.timestamp())

    def test_two_completed_runs_expire_only_owned_archives_not_raw_logs(self):
        first, a = self.launch("first")
        second, b = self.launch("second")
        originals = {(run / "stdout.raw"): (run / "stdout.raw").read_bytes()
                     for run in (first, second)}
        roots = [Path(report["capture_root"]) for report in (a, b)]
        for root in roots:
            self.assertEqual(len(list((root / "archives" / "Worldserver-out").glob("*.txt"))), 1)
        result = self.expire()
        self.assertEqual(result["completed_runs"], 2)
        self.assertEqual(result["unfinished_runs"], 0)
        self.assertEqual(result["expired_stream_days"], 2)
        self.assertEqual(self.expire()["expired_stream_days"], 0)
        for file, original in originals.items():
            self.assertTrue(file.exists())
            self.assertEqual(file.read_bytes(), original)
        for root in roots:
            self.assertEqual(list((root / "archives" / "Worldserver-out").glob("*.txt")), [])
            self.assertTrue((root / "retention-history").exists())
        self.assertTrue((first / "exit.json").exists())
        self.assertTrue((second / "exit.json").exists())

    def test_unfinished_child_is_skipped_with_no_data_change(self):
        run, report = self.launch("safe")
        source = self.source / "runs" / ("20240101T010101-" + "f" * 16)
        source.mkdir()
        incomplete = self.archive / "runs" / source.name
        incomplete.mkdir()
        valid_archive = next((Path(report["capture_root"]) / "archives" /
                              "Worldserver-out").glob("*.txt"))
        result = self.expire(days=1)
        self.assertEqual(result, {"completed_runs": 1, "unfinished_runs": 1,
                                  "expired_stream_days": 0})
        self.assertTrue(valid_archive.exists())
        self.assertTrue((run / "stdout.raw").exists())

    def test_forged_receipt_blocks_all_expirations_before_change(self):
        first, a = self.launch("first")
        second, b = self.launch("second")
        target = second / "start.json"
        payload = json.loads(target.read_text())
        payload["capture_root"] = str(self.base / "foreign")
        target.write_text(json.dumps(payload))
        original_archives = [
            next((Path(state["capture_root"]) / "archives" /
                  "Worldserver-out").glob("*.txt"))
            for state in (a, b)
        ]
        with self.assertRaisesRegex(Refused, "receipts disagree"):
            self.expire()
        self.assertTrue(all(p.exists() for p in original_archives))
        self.assertTrue((first / "stdout.raw").exists())

    def test_foreign_archives_are_refused_and_not_deleted(self):
        run, state = self.launch("safe")
        foreign = self.archive / "runs" / "alien"
        foreign.mkdir()
        protected = next((Path(state["capture_root"]) / "archives" /
                          "Worldserver-out").glob("*.txt"))
        with self.assertRaisesRegex(Refused, "unknown archive"):
            self.expire()
        self.assertTrue(protected.exists())
        self.assertTrue((run / "stdout.raw").exists())

    def test_symlink_archive_root_is_refused(self):
        run, state = self.launch("safe")
        foreign = self.base / "foreign"
        foreign.mkdir()
        cap = Path(state["capture_root"])
        archived = cap / "archives" / "Worldserver-out"
        archived.rename(cap / "saved")
        archived.symlink_to(foreign, target_is_directory=True)
        with self.assertRaises(Refused):
            self.expire()
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertTrue((run / "stdout.raw").exists())

    def test_default_off_cli_does_not_create_workspace(self):
        with self.assertRaises(SystemExit):
            cleanup.main(["--output-root", str(self.source),
                          "--archive-root", str(self.archive), "--once"])
        self.assertFalse(self.source.exists())
        self.assertFalse(self.archive.exists())

    def test_exact_boundary_and_early_file_are_not_removed(self):
        run, state = self.launch("early")
        archive = next((Path(state["capture_root"]) / "archives" /
                        "Worldserver-out").glob("*.txt"))
        self.assertEqual(self.expire(days=29)["expired_stream_days"], 0)
        self.assertTrue(archive.exists())
        self.assertTrue((run / "stdout.raw").exists())


if __name__ == "__main__":
    unittest.main()
