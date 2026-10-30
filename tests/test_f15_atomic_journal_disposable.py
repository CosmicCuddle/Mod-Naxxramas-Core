"""Positive synthetic crash recovery tests: Linux GitHub tempdir ONLY."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parent / "f15_disposable_atomic_journal_fixture.py"
spec = importlib.util.spec_from_file_location("f15_journal_fixture", SOURCE)
fx = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fx
spec.loader.exec_module(fx)


class DurableFixtureTests(unittest.TestCase):
    def setUp(self):
        self.j = fx.JournalFixture()
        self.addCleanup(self.j.close)

    def start(self, stream="Worldserver-out", initial=b"previous-days-history"):
        self.j.seed(stream, initial)
        return self.j.poll(stream)

    def test_01_initial_attachment_skips_legacy_bytes(self):
        event, data = self.start(initial=b"A" * 50_000)
        self.assertEqual((event, data), ("bootstrap-skipped", b""))
        self.assertFalse(self.j.published("Worldserver-out"))

    def test_02_initial_checkpoint_is_on_disk(self):
        self.start(initial=b"long old log")
        self.assertEqual(self.j.checkpoint("Worldserver-out")["offset"], len(b"long old log"))
        self.assertTrue((self.j.state / "Worldserver-out.json").exists())

    def test_03_new_stdout_written_as_immutable_chunk(self):
        self.start()
        self.j.append("Worldserver-out", b"new-out")
        event, data = self.j.poll("Worldserver-out")
        self.assertEqual((event, data), ("appended", b"new-out"))
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"new-out")

    def test_04_stdout_second_check_does_not_duplicate(self):
        self.start()
        self.j.append("Worldserver-out", b"same")
        self.j.poll("Worldserver-out")
        event, data = self.j.poll("Worldserver-out")
        self.assertEqual((event, data), ("unchanged", b""))
        self.assertEqual(len(self.j.published("Worldserver-out")), 1)

    def test_05_bound_64_byte_segments(self):
        self.start()
        self.j.append("Worldserver-out", b"Z" * 170)
        seen = [len(self.j.poll("Worldserver-out")[1]) for _ in range(3)]
        self.assertEqual(seen, [64, 64, 42])
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"Z" * 170)

    def test_06_three_distinct_process_streams(self):
        for stream in sorted(fx.STREAMS):
            self.start(stream)
            self.j.append(stream, stream.encode("ascii"))
            self.j.poll(stream)
            self.assertEqual(self.j.published_bytes(stream), stream.encode("ascii"))
        self.assertEqual(len(list(self.j.archive.glob("*.chunk"))), 3)

    def test_07_crash_before_segment_publication_can_retry(self):
        self.start()
        self.j.append("Worldserver-out", b"PENDING")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="before-publish")
        self.assertFalse(self.j.published("Worldserver-out"))
        self.assertEqual(self.j.checkpoint("Worldserver-out")["offset"],
                         len(b"previous-days-history"))
        event, data = self.j.poll("Worldserver-out")
        self.assertEqual((event, data), ("appended", b"PENDING"))
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"PENDING")

    def test_08_crash_after_segment_before_manifest_recovers(self):
        self.start()
        self.j.append("Worldserver-out", b"COMMITTED-FILE")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="after-publish")
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"COMMITTED-FILE")
        self.assertEqual(self.j.checkpoint("Worldserver-out")["offset"],
                         len(b"previous-days-history"))
        event, data = self.j.poll("Worldserver-out")
        self.assertEqual((event, data), ("recovered", b""))
        self.assertEqual(self.j.checkpoint("Worldserver-out")["offset"],
                         len(b"previous-days-historyCOMMITTED-FILE"))
        self.assertEqual(len(self.j.published("Worldserver-out")), 1)

    def test_09_after_checkpoint_crash_cannot_reappend(self):
        self.start()
        self.j.append("Worldserver-out", b"ONCE")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="after-checkpoint")
        event, data = self.j.poll("Worldserver-out")
        self.assertEqual((event, data), ("unchanged", b""))
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"ONCE")

    def test_10_stale_corrupted_segment_refuses_recovery(self):
        self.start()
        self.j.append("Worldserver-out", b"TRUSTED")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="after-publish")
        self.j.published("Worldserver-out")[0].write_bytes(b"CHANGED")
        with self.assertRaises(ValueError):
            self.j.poll("Worldserver-out")

    def test_11_corrupt_manifest_refuses_untrusted_offset(self):
        self.start()
        file = self.j.state / "Worldserver-out.json"
        file.write_bytes(file.read_bytes().replace(b"offset", b"offset-not"))
        with self.assertRaises((ValueError, KeyError)):
            self.j.poll("Worldserver-out")

    def test_12_orphan_temp_tampering_refuses_retry(self):
        self.start()
        self.j.append("Worldserver-out", b"ORIGINAL")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="before-publish")
        temp = next(self.j.archive.glob("*.pending"))
        temp.write_bytes(b"FORGED")
        with self.assertRaises(ValueError):
            self.j.poll("Worldserver-out")

    def test_13_inode_replacement_detected_and_new_bytes_captured(self):
        self.start()
        old = self.j._path("Worldserver-out")
        old.rename(self.j.source / "renamed-old-synthetic.log")
        self.j.seed("Worldserver-out", b"NEW-INCARNATION")
        event, data = self.j.poll("Worldserver-out")
        self.assertIn("source replaced", event)
        self.assertEqual(data, b"NEW-INCARNATION")

    def test_14_truncation_detected_and_new_bytes_captured(self):
        self.start()
        self.j._path("Worldserver-out").write_bytes(b"short")
        event, data = self.j.poll("Worldserver-out")
        self.assertIn("source truncated", event)
        self.assertEqual(data, b"short")

    def test_15_reject_unknown_stream(self):
        with self.assertRaises(ValueError):
            self.j.seed("../../worldserver", b"x")

    def test_16_reject_symlink_source(self):
        (self.j.source / "fake-target").write_bytes(b"x")
        self.j._path("Worldserver-out").symlink_to(self.j.source / "fake-target")
        with self.assertRaises(OSError):
            self.j.poll("Worldserver-out")

    def test_17_reject_hardlink_source(self):
        self.j.seed("Worldserver-out", b"x")
        os.link(self.j._path("Worldserver-out"), self.j.source / "also-owned-hardlink")
        with self.assertRaises(ValueError):
            self.j.poll("Worldserver-out")

    def test_18_segments_and_manifest_private(self):
        self.start()
        self.j.append("Worldserver-out", b"PRIVATE")
        self.j.poll("Worldserver-out")
        for path in self.j.published("Worldserver-out") + [self.j.state / "Worldserver-out.json"]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_19_binary_bytes_round_trip(self):
        self.start()
        payload = b"\x00\xfd\xff\x01\n"
        self.j.append("Worldserver-out", payload)
        self.j.poll("Worldserver-out")
        self.assertEqual(self.j.published_bytes("Worldserver-out"), payload)

    def test_20_new_bytes_after_recovered_transaction(self):
        self.start()
        self.j.append("Worldserver-out", b"FIRST")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="after-publish")
        self.j.append("Worldserver-out", b"SECOND")
        event, data = self.j.poll("Worldserver-out")
        self.assertEqual((event, data), ("recovered-and-append", b"SECOND"))
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"FIRSTSECOND")


    def test_21_crash_with_fsynced_pending_checkpoint_recovers_without_duplicate(self):
        self.start()
        self.j.append("Worldserver-out", b"JOURNAL-ONCE")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="before-checkpoint-publish")
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"JOURNAL-ONCE")
        self.assertTrue((self.j.state / "Worldserver-out.pending").exists())
        self.assertEqual(self.j.checkpoint("Worldserver-out")["offset"],
                         len(b"previous-days-history"))
        event, chunk = self.j.poll("Worldserver-out")
        self.assertEqual((event, chunk), ("recovered", b""))
        self.assertFalse((self.j.state / "Worldserver-out.pending").exists())
        self.assertEqual(len(self.j.published("Worldserver-out")), 1)
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"JOURNAL-ONCE")

    def test_22_modified_pending_checkpoint_fails_closed(self):
        self.start()
        self.j.append("Worldserver-out", b"ORIGINAL")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="before-checkpoint-publish")
        pending = self.j.state / "Worldserver-out.pending"
        pending.write_bytes(b"attacker-changed-pending-metadata")
        with self.assertRaises(ValueError):
            self.j.poll("Worldserver-out")
        self.assertEqual(self.j.published_bytes("Worldserver-out"), b"ORIGINAL")
        self.assertEqual(self.j.checkpoint("Worldserver-out")["offset"],
                         len(b"previous-days-history"))

    def test_23_pending_checkpoint_symlink_refused(self):
        self.start()
        self.j.append("Worldserver-out", b"ORIGINAL")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Worldserver-out", fail_at="before-checkpoint-publish")
        pending = self.j.state / "Worldserver-out.pending"
        pending.unlink()
        other = self.j.root / "separate-synthetic-protected"
        other.write_bytes(b"PROTECT")
        pending.symlink_to(other)
        with self.assertRaises(ValueError):
            self.j.poll("Worldserver-out")
        self.assertEqual(other.read_bytes(), b"PROTECT")

    def test_24_after_pending_recovery_can_append_new_bytes(self):
        self.start("Authserver-native")
        self.j.append("Authserver-native", b"FIRST")
        with self.assertRaises(fx.SyntheticCrash):
            self.j.poll("Authserver-native", fail_at="before-checkpoint-publish")
        self.j.append("Authserver-native", b"SECOND")
        event, payload = self.j.poll("Authserver-native")
        self.assertEqual((event, payload), ("recovered-and-append", b"SECOND"))
        self.assertEqual(self.j.published_bytes("Authserver-native"), b"FIRSTSECOND")
        self.assertEqual(self.j.checkpoint("Authserver-native")["offset"],
                         len(b"previous-days-historyFIRSTSECOND"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
