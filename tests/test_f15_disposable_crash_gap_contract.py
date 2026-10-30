"""F15 known-failure *demonstration* tests against disposable-only fixture.

All assertions deliberately PASS while exposing omissions in PR #250.
These tests do not implement persistence, cleanup scheduling or PM2 capture.
Every file is owned by DisposableArchiveHarness's tempfile directory.
"""
from datetime import timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parent / "test_f15_archive_disposable_filesystem.py"
spec = importlib.util.spec_from_file_location("f15_temporary_fixture", SOURCE)
fixture = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixture
spec.loader.exec_module(fixture)

T = fixture.DAY


class KnownCrashAndRotationGaps(unittest.TestCase):
    def setUp(self):
        self.h = fixture.DisposableArchiveHarness()
        self.addCleanup(self.h.close)

    def test_unread_byte_span_lost_on_reset_checkpoint(self):
        self.h.seed("Worldserver-out", b"OLD")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"UNREAD")
        self.h.checkpoints.clear()  # simulated restart; no persisted journal
        event, chunk = self.h.ingest("Worldserver-out", T + timedelta(seconds=1))
        self.assertEqual((event, chunk), ("bootstrap-skip", b""))
        self.assertFalse(self.h.part_path("Worldserver-out").exists())

    def test_unread_error_span_lost_separately(self):
        self.h.seed("Worldserver-err", b"OLD")
        self.h.ingest("Worldserver-err")
        self.h.append_source("Worldserver-err", b"UNREAD-ERROR")
        self.h.checkpoints.clear()
        event, chunk = self.h.ingest("Worldserver-err", T + timedelta(seconds=1))
        self.assertEqual((event, chunk), ("bootstrap-skip", b""))

    def test_auth_native_bytes_lost_on_restart_before_poll(self):
        self.h.seed("Authserver-native", b"OLD")
        self.h.ingest("Authserver-native")
        self.h.append_source("Authserver-native", b"UNREAD-AUTH")
        self.h.checkpoints.clear()
        event, chunk = self.h.ingest("Authserver-native", T + timedelta(seconds=1))
        self.assertEqual((event, chunk), ("bootstrap-skip", b""))

    def test_archive_write_before_checkpoint_commit_can_duplicate(self):
        self.h.seed("Worldserver-out", b"OLD")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"NEW")
        # Deliberate crash failpoint: simulated archive write occurred,
        # while checkpoint remains at OLD offset.
        self.h.part_path("Worldserver-out").write_bytes(b"NEW")
        event, chunk = self.h.ingest("Worldserver-out", T + timedelta(seconds=1))
        self.assertEqual(event, "append")
        self.assertEqual(chunk, b"NEW")
        self.assertEqual(self.h.part_path("Worldserver-out").read_bytes(), b"NEWNEW")

    def test_truncation_can_destroy_unread_tail(self):
        self.h.seed("Worldserver-out", b"ORIGINAL")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"UNREAD-TAIL")
        self.h.source_path("Worldserver-out").write_bytes(b"X")
        event, seen = self.h.ingest("Worldserver-out", T + timedelta(seconds=1))
        self.assertEqual((event, seen), ("truncated", b"X"))
        self.assertNotIn(b"UNREAD-TAIL", seen)

    def test_source_inode_swap_does_not_recover_old_unread_tail(self):
        self.h.seed("Worldserver-out", b"ORIGINAL")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"UNREAD-OLD")
        old = self.h.input / "owned-rotated-old.log"
        self.h.source_path("Worldserver-out").rename(old)
        self.h.seed("Worldserver-out", b"NEW")
        event, seen = self.h.ingest("Worldserver-out", T + timedelta(seconds=1))
        self.assertEqual((event, seen), ("replaced", b"NEW"))
        self.assertIn(b"UNREAD-OLD", old.read_bytes())
        self.assertNotIn(b"UNREAD-OLD", seen)

    def test_no_automatic_midnight_rollover(self):
        self.h.seed("Worldserver-out", b"ORIGINAL")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"ONE")
        self.h.ingest("Worldserver-out", T + timedelta(minutes=1))
        self.h.append_source("Worldserver-out", b"TWO")
        self.h.ingest("Worldserver-out", T + timedelta(days=1))
        self.assertEqual(self.h.part_path("Worldserver-out").read_bytes(), b"ONETWO")
        self.assertEqual(list(self.h.output.glob("*-Console-*.txt")), [])

    def test_no_unattended_retention_scheduler(self):
        self.h.seed("Worldserver-out", b"ORIGINAL")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"ARCHIVE")
        self.h.ingest("Worldserver-out", T + timedelta(seconds=1))
        finished = self.h.seal("Worldserver-out", T + timedelta(days=1))
        # Model alone cannot schedule a daily cleanup; even 60 days
        # later, the archive remains unless a caller explicitly cleans up.
        self.assertTrue(finished.exists())
        self.assertEqual(len(self.h.expired_candidates(T + timedelta(days=62))), 1)
        self.assertTrue(finished.exists())

    def test_native_auth_file_does_not_prove_terminal_parity(self):
        self.h.seed("Authserver-native", b"FILE-ONLY")
        self.h.ingest("Authserver-native")
        self.h.append_source("Authserver-native", b"NEW-FILE")
        _, seen = self.h.ingest("Authserver-native", T + timedelta(seconds=1))
        self.assertEqual(seen, b"NEW-FILE")
        # The harness has no PTY/console capture adapter at all.
        self.assertFalse((self.h.input / "Authserver-pty.log").exists())

    def test_per_poll_limit_is_not_total_disk_quota(self):
        self.h.seed("Worldserver-out", b"ORIGINAL")
        self.h.ingest("Worldserver-out")
        self.h.append_source("Worldserver-out", b"A" * 9000)
        for n in range(3):
            self.h.ingest("Worldserver-out", T + timedelta(seconds=n + 1))
        self.assertEqual(self.h.part_path("Worldserver-out").stat().st_size, 9000)
        self.assertGreater(9000, fixture.CAP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
