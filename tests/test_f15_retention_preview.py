"""F15 preview-only tests on disposable files; no live server or deletions."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import fcntl
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

    def test_linked_archive_receipt_refuses_without_reading_outside_data(self):
        # Both symlinks and multi-linked receipts must be rejected by the
        # pre-existing strict retention validator, not followed by preview.
        archive_before = self.archive.read_bytes()
        source_before = self.source.read_bytes()
        receipt_before = self.receipt.read_bytes()
        other = self.home / "external-private-receipt.json"
        other.write_bytes(receipt_before)
        self.receipt.unlink()
        self.receipt.symlink_to(other)
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertEqual(other.read_bytes(), receipt_before)
        self.receipt.unlink()
        self.receipt.write_bytes(receipt_before)
        alias = self.home / "another-hardlink-to-receipt.json"
        os.link(self.receipt, alias)
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertEqual(alias.read_bytes(), receipt_before)
        self.assertEqual(self.receipt.read_bytes(), receipt_before)
        self.assertEqual(self.archive.read_bytes(), archive_before)
        self.assertEqual(self.source.read_bytes(), source_before)

    def test_unknown_stream_even_if_both_roots_agree_refuses(self):
        # Equal stream sets are necessary but not sufficient: a forged label
        # in BOTH roots must never be reported as a known World/Auth stream.
        archive_before = self.archive.read_bytes()
        for name in ("records", "archives"):
            (self.root / name / "UNKNOWN-STREAM").mkdir(mode=0o700)
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertEqual(self.archive.read_bytes(), archive_before)
        self.assertEqual(self.source.read_bytes(),
                         b"UNPUBLISHED_SERVER_LOG_SENTINEL\n")

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

    def test_archive_and_journal_stream_mismatch_refuses_without_mutation(self):
        original = self.archive.read_bytes()
        extra_archive = self.root / "archives" / "Authserver-out"
        extra_archive.mkdir(mode=0o700)
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        extra_archive.rmdir()
        extra_journal = self.root / "records" / "Authserver-out"
        extra_journal.mkdir(mode=0o700)
        with self.assertRaises(Refused):
            self.check(DAY_END + timedelta(days=31))
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertEqual(self.source.read_bytes(),
                         b"UNPUBLISHED_SERVER_LOG_SENTINEL\n")

    def test_symlinked_parent_refuses_before_archive_read(self):
        # Leaf is a real 0700 directory, but an earlier component is a symlink.
        alias = self.home / "alias"
        alias.symlink_to(self.home, target_is_directory=True)
        before = self.archive.read_bytes()
        with self.assertRaises(Refused):
            preview_once(alias / self.root.name,
                         now=(DAY_END + timedelta(days=31)).timestamp())
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(),
                         b"UNPUBLISHED_SERVER_LOG_SENTINEL\n")

    def test_busy_collector_lock_refuses_without_any_archive_change(self):
        # Independent descriptor holds the same cooperative lock.
        before = self.archive.read_bytes()
        with (self.root / "collector.lock").open("rb") as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with self.assertRaises(Refused):
                    self.check(DAY_END + timedelta(days=31))
            finally:
                fcntl.flock(held.fileno(), fcntl.LOCK_UN)
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertTrue(self.receipt.exists())

    def test_cli_missing_private_directory_does_not_expose_path(self):
        missing = self.home / "private_owner_name" / "missing_collector"
        self.assertFalse(missing.exists())
        out, errors = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(errors):
            self.assertEqual(main(["--root", str(missing), "--preview"]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("F15 RETENTION PREVIEW REFUSED", errors.getvalue())
        self.assertNotIn("private_owner_name", errors.getvalue())
        self.assertNotIn(str(missing), errors.getvalue())
        self.assertFalse(missing.exists())
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
