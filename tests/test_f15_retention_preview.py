"""F15 preview-only tests on disposable files; no live server or deletions."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from f15_operator_collector import Refused, collect_once
from f15_retention_preview import preview_once, main

OLD = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
DAY_END = datetime(2024, 1, 2, tzinfo=timezone.utc)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.root = self.home / "private"
        self.source = self.home / "world.out"
        self.source.write_bytes(b"UNPUBLISHED_SERVER_LOG_SENTINEL\n")
        self.sources = {"Worldserver-out": str(self.source)}
        collect_once(self.root, self.sources, now=OLD.timestamp(), include_existing=True)
        self.archive = self.root / "archives" / "Worldserver-out" / "20240101.txt"
        self.receipt = self.root / "archives" / "Worldserver-out" / "20240101.receipt.json"
        self.records = self.root / "records" / "Worldserver-out"

    def check(self, when):
        return preview_once(self.root, now=when.timestamp())

    def test_preview_matches_expiry_and_changes_no_owned_files(self):
        before = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob("*") if p.is_file()}
        rows = self.check(DAY_END + timedelta(days=31))
        self.assertEqual(rows, [{"service_stream": "Worldserver-out",
                                 "utc_day": "20240101",
                                 "journal_bytes": len(self.source.read_bytes()), "records": 1}])
        after = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        self.assertTrue(self.archive.exists())
        self.assertFalse((self.root / "retention-intent.json").exists())
        self.assertEqual(self.source.read_bytes(), b"UNPUBLISHED_SERVER_LOG_SENTINEL\n")

    def test_exact_cutoff_and_future_days_not_eligible(self):
        self.assertEqual(self.check(DAY_END + timedelta(days=30)), [])
        self.assertEqual(self.check(DAY_END + timedelta(days=30, seconds=-1)), [])
        self.assertEqual(len(self.check(DAY_END + timedelta(days=30, seconds=1))), 1)
        self.assertTrue(self.archive.exists())

    def test_oldest_expired_only_newer_day_is_preserved(self):
        with self.source.open("ab") as log:
            log.write(b"later\n")
        collect_once(self.root, self.sources,
                     now=(DAY_END + timedelta(days=24)).timestamp())
        rows = self.check(DAY_END + timedelta(days=31))
        self.assertEqual([r["utc_day"] for r in rows], ["20240101"])
        self.assertTrue((self.root / "archives" / "Worldserver-out" / "20240126.txt").exists())

    def test_corrupt_archive_and_missing_receipt_refuse_not_delete(self):
        self.archive.write_bytes(b"CORRUPT")
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertEqual(self.archive.read_bytes(), b"CORRUPT")
        self.assertTrue(self.receipt.exists())
        self.archive.write_bytes(self.source.read_bytes())
        self.receipt.unlink()
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertTrue(self.archive.exists())

    def test_symlink_and_unfinished_intent_refuse(self):
        original = self.archive.read_bytes()
        self.archive.unlink()
        foreign = self.home / "foreign"
        foreign.write_bytes(original)
        self.archive.symlink_to(foreign)
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertEqual(foreign.read_bytes(), original)
        self.archive.unlink()
        self.archive.write_bytes(original)
        (self.root / "retention-intent.json").write_text('{"unfinished":true}')
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertTrue(self.archive.exists())

    def test_untrusted_root_or_journal_refuse(self):
        with self.assertRaises((Refused, OSError)):
            preview_once(self.home / "new-directory", now=OLD.timestamp())
        self.assertFalse((self.home / "new-directory").exists())
        (self.records / "foreign.pending").write_bytes(b"unknown")
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertTrue(self.archive.exists())

    def test_explicit_cli_never_prints_private_source_or_log_contents(self):
        with self.assertRaises(SystemExit):
            main(["--root", str(self.root)])
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--root", str(self.root), "--preview"]), 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["eligible_stream_days"], 1)
        self.assertEqual(payload["candidates"][0]["service_stream"], "Worldserver-out")
        self.assertNotIn(str(self.source), out.getvalue())
        self.assertNotIn("UNPUBLISHED_SERVER_LOG_SENTINEL", out.getvalue())
        self.assertTrue(self.archive.exists())
        self.assertEqual(self.source.read_bytes(), b"UNPUBLISHED_SERVER_LOG_SENTINEL\n")


if __name__ == "__main__":
    unittest.main()
