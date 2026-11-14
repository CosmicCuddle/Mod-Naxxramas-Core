import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("snap",ROOT/"scripts/f15_preoverwrite_log_snapshot.py")
snap=importlib.util.module_from_spec(spec)
spec.loader.exec_module(snap)

NOW=datetime(2026,11,13,12,0,0,tzinfo=timezone.utc)

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name)
        self.logs=self.base/"logs"
        self.logs.mkdir()
        self.archive=self.logs/"Archived Logs"

    def test_snapshot_copies_independent_bytes_and_manifest(self):
        src=self.logs/"world.log"
        src.write_bytes(b"before overwrite\n")
        data,manifest=snap.snapshot_file(src,self.archive,NOW)
        self.assertEqual(data.read_bytes(),b"before overwrite\n")
        meta=json.loads(manifest.read_text())
        self.assertEqual(meta["retention_days"],30)
        self.assertEqual(meta["source_path"],str(src))
        self.assertEqual(src.read_bytes(),b"before overwrite\n")
        src.write_bytes(b"new contents\n")
        self.assertEqual(data.read_bytes(),b"before overwrite\n")
        self.assertEqual(os.stat(data).st_ino == os.stat(src).st_ino,False)

    def test_directory_snapshots_regular_logs_but_not_crash_or_archive_dirs(self):
        (self.logs/"world.log").write_text("w")
        (self.logs/"auth.log").write_text("a")
        (self.logs/"Crash Logs").mkdir()
        self.archive.mkdir(mode=0o700)
        result=snap.snapshot_log_directory(self.logs,self.archive,observed_utc=NOW)
        self.assertEqual(len(result),2)
        manifests=[json.loads(m.read_text()) for _,m in result]
        self.assertEqual({Path(x["source_path"]).name for x in manifests},{"world.log","auth.log"})

    def test_source_symlink_refused(self):
        target=self.logs/"target.log"
        target.write_text("x")
        link=self.logs/"link.log"
        link.symlink_to(target)
        with self.assertRaises(OSError):
            snap.snapshot_file(link,self.archive,NOW)


    def test_fifo_source_refused_without_open_block(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        fifo=self.logs/"pipe.log"
        os.mkfifo(fifo,0o600)
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(fifo,self.archive,NOW)
        self.assertFalse(self.archive.exists())

    def test_directory_snapshot_refuses_fifo_entry(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        (self.logs/"world.log").write_text("w")
        fifo=self.logs/"pipe.log"
        os.mkfifo(fifo,0o600)
        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(self.logs,self.archive,observed_utc=NOW)

    def test_hardlinked_source_refused(self):
        src=self.logs/"world.log"
        src.write_text("x")
        os.link(src,self.logs/"other.log")
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src,self.archive,NOW)

    def test_insecure_archive_directory_refused(self):
        self.archive.mkdir(mode=0o755)
        self.archive.chmod(0o755)
        src=self.logs/"world.log"
        src.write_text("x")
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src,self.archive,NOW)

    def test_source_change_during_copy_refused_and_source_untouched(self):
        src=self.logs/"world.log"
        src.write_bytes(b"A"*4096)
        real_fstat=os.fstat
        calls={"n":0}
        def fake_fstat(fd):
            st=real_fstat(fd)
            calls["n"]+=1
            if calls["n"]>=2:
                class Changed:
                    st_dev=st.st_dev
                    st_ino=st.st_ino
                    st_size=st.st_size
                    st_mtime_ns=st.st_mtime_ns+1
                    st_mode=st.st_mode
                    st_nlink=st.st_nlink
                return Changed()
            return st
        with mock.patch.object(snap.os,"fstat",side_effect=fake_fstat):
            with self.assertRaises(snap.Refused):
                snap.snapshot_file(src,self.archive,NOW)
        self.assertEqual(src.read_bytes(),b"A"*4096)
        self.assertTrue(list(self.archive.glob("*.pending")))
        self.assertFalse(list(self.archive.glob("*.log")))

    def test_collision_refused(self):
        src=self.logs/"world.log"
        src.write_text("x")
        snap.snapshot_file(src,self.archive,NOW)
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src,self.archive,NOW)

    def test_naive_observation_time_refused(self):
        src=self.logs/"world.log"
        src.write_text("x")
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src,self.archive,datetime(2026,11,13,12,0,0))

if __name__=="__main__":
    unittest.main()
