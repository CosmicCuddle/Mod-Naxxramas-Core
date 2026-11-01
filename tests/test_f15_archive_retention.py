"""Actual F15 collector 30-day archive+raw-journal retention (fake disposable files)."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
from unittest import mock
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from f15_operator_collector import Refused, collect_once, main
from f15_archive_retention import retain_once

OLD = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
DAY_END = datetime(2024, 1, 2, tzinfo=timezone.utc)
def timestamp(dt):
    return dt.timestamp()

class RetentionTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = Path(t.name)
        self.root = self.base/"archive-root"
        self.source = self.base/"world.log"
        self.source.write_bytes(b"original not to be deleted")
        self.input = {"Worldserver-out":str(self.source)}
        collect_once(self.root, self.input, now=timestamp(OLD), include_existing=True)
        self.arch = self.root/"archives"/"Worldserver-out"/"20240101.txt"
        self.receipt = self.root/"archives"/"Worldserver-out"/"20240101.receipt.json"
        self.records = self.root/"records"/"Worldserver-out"
        self.origin = self.records/"origin.json"
        self.before = self.source.read_bytes()

    def expire(self, at=None):
        return retain_once(self.root, now=timestamp(at or DAY_END + timedelta(days=31)))

    def test_aged_owned_archive_and_raw_journal_are_expired(self):
        self.assertEqual(self.expire(), 1)
        self.assertFalse(self.arch.exists())
        self.assertFalse(self.receipt.exists())
        self.assertEqual(list(self.records.glob("*.bin")), [])
        self.assertEqual(json.loads(self.origin.read_text())["start"], len(self.before))
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual(self.expire(), 0)
        collect_once(self.root, self.input, now=timestamp(OLD), include_existing=True)
        self.assertFalse(self.arch.exists())
        self.assertTrue(list((self.root/"retention-history").iterdir()))

    def test_clock_rewind_cannot_republish_expired_day(self):
        self.assertEqual(self.expire(), 1)
        before = self.source.read_bytes()
        with self.source.open("ab") as fp: fp.write(b"later bytes")
        with self.assertRaisesRegex(Refused, "clock returned"):
            collect_once(self.root,self.input,now=timestamp(OLD))
        self.assertFalse(self.arch.exists())
        self.assertEqual(list(self.records.glob("*.bin")), [])
        self.assertEqual(self.source.read_bytes(), before+b"later bytes")

    def test_retention_at_exact_boundary_does_not_delete(self):
        self.assertEqual(self.expire(DAY_END+timedelta(days=30)),0)
        self.assertEqual(self.expire(DAY_END+timedelta(days=30)-timedelta(seconds=1)),0)
        self.assertTrue(self.arch.exists())
        self.assertEqual(self.source.read_bytes(),self.before)
        self.assertEqual(self.expire(DAY_END+timedelta(days=30,seconds=1)),1)

    def test_newer_day_kept_and_replay_continuity(self):
        with self.source.open("ab") as f: f.write(b"new-day")
        collect_once(self.root,self.input,now=timestamp(DAY_END+timedelta(days=24)))
        newer = self.root/"archives"/"Worldserver-out"/"20240126.txt"
        self.assertEqual(newer.read_bytes(),b"new-day")
        self.assertEqual(self.expire(DAY_END+timedelta(days=31)),1)
        self.assertFalse(self.arch.exists())
        self.assertEqual(newer.read_bytes(),b"new-day")
        collect_once(self.root,self.input)
        self.assertEqual(newer.read_bytes(),b"new-day")

    def test_unexpected_old_missing_is_unknown_not_expired(self):
        self.arch.unlink()
        with self.assertRaises(Refused): self.expire()
        self.assertTrue(self.receipt.exists())
        self.assertEqual(len(list(self.records.glob("*.bin"))),1)
        self.assertFalse((self.root/"retention-intent.json").exists())
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_corrupt_receipt_or_archive_refused(self):
        self.arch.write_bytes(b"bad")
        with self.assertRaises(Refused): self.expire()
        self.assertTrue(self.arch.exists())
        self.assertEqual(len(list(self.records.glob("*.bin"))),1)

    def test_archive_symlink_and_hardlink_never_deleted(self):
        self.arch.unlink()
        foreign=self.base/"foreign"
        foreign.write_bytes(b"FOREIGN")
        self.arch.symlink_to(foreign)
        with self.assertRaises(Refused): self.expire()
        self.assertEqual(foreign.read_bytes(),b"FOREIGN")
        self.arch.unlink()
        self.arch.write_bytes(self.before)
        os.link(self.arch,self.base/"other-hardlink")
        with self.assertRaises(Refused): self.expire()
        self.assertTrue(self.arch.exists())

    def test_unknown_pending_file_never_deleted(self):
        odd=self.records/"66001.pending"
        odd.write_bytes(b"FOREIGN")
        with self.assertRaises(Refused): self.expire()
        self.assertEqual(odd.read_bytes(),b"FOREIGN")
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_interrupted_intent_blocks_all_future_collection(self):
        obj={"kind":"retention_30d"}
        (self.root/"retention-intent.json").write_text(json.dumps(obj))
        with self.assertRaises(Refused): self.expire()
        with self.assertRaises(Refused): collect_once(self.root,self.input)
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_crash_between_archive_delete_and_cursor_update_fails_closed(self):
        original = Path.unlink
        def interrupted(path,*args,**kwargs):
            if path == self.receipt:
                raise OSError("simulated stop mid-delete")
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,"unlink",interrupted):
            with self.assertRaises(OSError): self.expire()
        self.assertFalse(self.arch.exists())
        self.assertTrue((self.root/"retention-intent.json").exists())
        with self.assertRaises(Refused): self.expire()
        with self.assertRaises(Refused): collect_once(self.root,self.input)
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_invalid_observation_time_does_not_qualify(self):
        self.assertEqual(self.expire(OLD+timedelta(days=12)),0)
        self.assertTrue(self.arch.exists())

    def test_expiry_is_disabled_without_explicit_flag(self):
        rc=main(["--root",str(self.root),"--source",f"Worldserver-out={self.source}",
                 "--capture","--once"])
        self.assertEqual(rc,0)
        self.assertTrue(self.arch.exists())

    def test_expiry_opt_in_cli_removes_only_owned_archive(self):
        rc=main(["--root",str(self.root),"--source",f"Worldserver-out={self.source}",
                 "--capture","--once","--retention-30d"])
        self.assertEqual(rc,0)
        self.assertFalse(self.arch.exists())
        self.assertEqual(self.source.read_bytes(), self.before)

if __name__ == "__main__":
    unittest.main()
