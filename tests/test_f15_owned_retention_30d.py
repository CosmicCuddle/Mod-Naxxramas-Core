import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name, rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

snap=load("snap","scripts/f15_preoverwrite_log_snapshot.py")
ret=load("ret","scripts/f15_owned_retention_30d.py")

OLD=datetime(2026,10,1,12,0,0,tzinfo=timezone.utc)
BOUNDARY=OLD+timedelta(days=30)

class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name)
        self.logs=self.base/"logs"
        self.logs.mkdir()
        self.arch=self.logs/"Archived Logs"
        self.crash=self.logs/"Crash Logs"
        self.crash.mkdir(mode=0o700)

    def make_snapshot(self):
        src=self.logs/"world.log"
        src.write_text("old world log")
        return snap.snapshot_file(src,self.arch,OLD)

    def test_snapshot_kept_at_exact_30_day_boundary(self):
        data,manifest=self.make_snapshot()
        self.assertEqual(ret.retain_snapshot_archive(self.arch,BOUNDARY),0)
        self.assertTrue(data.exists())
        self.assertTrue(manifest.exists())

    def test_snapshot_removed_after_30_days_source_untouched(self):
        data,manifest=self.make_snapshot()
        src=self.logs/"world.log"
        before=src.read_text()
        self.assertEqual(ret.retain_snapshot_archive(self.arch,BOUNDARY+timedelta(seconds=1)),1)
        self.assertFalse(data.exists())
        self.assertFalse(manifest.exists())
        self.assertEqual(src.read_text(),before)

    def test_snapshot_hash_mismatch_refuses_and_preserves(self):
        data,manifest=self.make_snapshot()
        data.write_text("tampered")
        with self.assertRaises(ret.Refused):
            ret.retain_snapshot_archive(self.arch,BOUNDARY+timedelta(days=1))
        self.assertTrue(data.exists())
        self.assertTrue(manifest.exists())

    def test_foreign_snapshot_json_is_preserved(self):
        self.arch.mkdir(mode=0o700)
        foreign=self.arch/"foreign.json"
        foreign.write_text('{"hello":"world"}')
        foreign.chmod(0o600)
        self.assertEqual(ret.retain_snapshot_archive(self.arch,BOUNDARY+timedelta(days=1)),0)
        self.assertTrue(foreign.exists())

    def write_crash(self, stamp, incident="one"):
        name=f"{stamp}-Worldserver-{incident}.txt"
        p=self.crash/name
        p.write_text("report")
        p.chmod(0o600)
        return p

    def test_crash_report_kept_at_boundary_then_removed(self):
        report=self.write_crash("20261001T120000Z")
        history=self.crash/"Crash-History.txt"
        history.write_text(
            f"20261001T120000Z\tWorldserver\tone\tFATAL_SIGNAL_EXIT\texit=-11\tsignal=11\treport={report.name}\n"
        )
        history.chmod(0o600)
        self.assertEqual(ret.retain_crash_reports(self.crash,BOUNDARY),(0,0))
        self.assertTrue(report.exists())
        removed,dropped=ret.retain_crash_reports(self.crash,BOUNDARY+timedelta(seconds=1))
        self.assertEqual((removed,dropped),(1,1))
        self.assertFalse(report.exists())
        self.assertEqual(history.read_text(),"")

    def test_recent_crash_and_history_are_preserved(self):
        report=self.write_crash("20261020T120000Z","recent")
        history=self.crash/"Crash-History.txt"
        history.write_text(
            f"20261020T120000Z\tWorldserver\trecent\tNONZERO_EXIT\texit=7\tsignal=UNKNOWN\treport={report.name}\n"
        )
        history.chmod(0o600)
        self.assertEqual(ret.retain_crash_reports(self.crash,BOUNDARY+timedelta(seconds=1)),(0,0))
        self.assertTrue(report.exists())
        self.assertIn("recent",history.read_text())

    def test_foreign_crash_file_and_unknown_history_line_preserved(self):
        foreign=self.crash/"manual-note.txt"
        foreign.write_text("keep me")
        foreign.chmod(0o600)
        history=self.crash/"Crash-History.txt"
        history.write_text("manual history note\n")
        history.chmod(0o600)
        self.assertEqual(ret.retain_crash_reports(self.crash,BOUNDARY+timedelta(days=5)),(0,0))
        self.assertEqual(foreign.read_text(),"keep me")
        self.assertEqual(history.read_text(),"manual history note\n")

    def test_unfinished_intent_blocks_retention(self):
        self.make_snapshot()
        intent=self.arch/"retention-intent.json"
        intent.write_text("{}")
        intent.chmod(0o600)
        with self.assertRaises(ret.Refused):
            ret.retain_snapshot_archive(self.arch,BOUNDARY+timedelta(days=5))

if __name__=="__main__":
    unittest.main()
