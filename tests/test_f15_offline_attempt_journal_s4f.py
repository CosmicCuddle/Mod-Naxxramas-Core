"""Synthetic/private files ONLY; no actual process supervision or service actions."""
import multiprocessing
import os
import pathlib
import tempfile
import unittest
from offline_attempt_journal_s4f import OfflineAttemptJournal, UnsafeJournal

INC = "12345678-1234-1234-1234-123456789abc"


def contender(root, start, out):
    start.wait()
    with OfflineAttemptJournal(root) as journal:
        out.put(journal.begin("worldserver", INC, "attempt_one"))


class OfflineAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="f15-s4f-synthetic-")
        self.root = pathlib.Path(self.temp.name)
        self.root.chmod(0o700)

    def tearDown(self):
        self.temp.cleanup()

    def journal(self):
        return OfflineAttemptJournal(self.root)

    def test_single_reservation_and_duplicate_pending(self):
        with self.journal() as j:
            self.assertEqual(j.begin("worldserver", INC, "a"), "reserved")
            self.assertEqual(j.begin("worldserver", INC, "a"), "pending")

    def test_completion_is_immutable_and_survives_reopen(self):
        with self.journal() as j:
            self.assertEqual(j.begin("worldserver", INC, "a"), "reserved")
            self.assertEqual(j.complete_synthetic("worldserver", INC, "a", "succeeded"), "recorded:succeeded")
        with self.journal() as j:
            self.assertEqual(j.begin("worldserver", INC, "a"), "completed:succeeded")
            self.assertEqual(j.complete_synthetic("worldserver", INC, "a", "succeeded"), "already:succeeded")
            with self.assertRaisesRegex(UnsafeJournal, "terminal conflict"):
                j.complete_synthetic("worldserver", INC, "a", "failed")

    def test_pending_after_restart_not_retryable(self):
        with self.journal() as j:
            self.assertEqual(j.begin("worldserver", INC, "lost"), "reserved")
        with self.journal() as j:
            self.assertEqual(j.begin("worldserver", INC, "lost"), "pending")

    def test_two_services_and_attempts_independent(self):
        with self.journal() as j:
            self.assertEqual(j.begin("worldserver", INC, "a"), "reserved")
            self.assertEqual(j.begin("authserver", INC, "a"), "reserved")
            self.assertEqual(j.begin("worldserver", INC, "b"), "reserved")

    def test_finish_requires_pending_and_valid_state(self):
        with self.journal() as j:
            with self.assertRaisesRegex(UnsafeJournal, "no reserved"):
                j.complete_synthetic("worldserver", INC, "a", "succeeded")
            with self.assertRaisesRegex(UnsafeJournal, "invalid synthetic"):
                j.complete_synthetic("worldserver", INC, "a", "claimed by fake OS")

    def test_rejects_bad_identity_and_non_fixture_root(self):
        with self.journal() as j:
            for service, inc, attempt in [("shell", INC, "a"), ("worldserver", "NO", "a"), ("worldserver", INC, "../x")]:
                with self.assertRaises(UnsafeJournal):
                    j.begin(service, inc, attempt)
        with self.assertRaises(UnsafeJournal):
            OfflineAttemptJournal(self.root.parent)

    def test_symlinked_pending_not_followed_or_reaped(self):
        with self.journal() as j:
            j.begin("worldserver", INC, "a")
        pending = next(self.root.glob("*.pending"))
        pending.unlink()
        outside = self.root.parent / (self.root.name + "-outside")
        outside.write_text("outside", encoding="utf8")
        try:
            pending.symlink_to(outside)
            with self.journal() as j:
                with self.assertRaises(UnsafeJournal):
                    j.begin("worldserver", INC, "a")
            self.assertEqual(outside.read_text(encoding="utf8"), "outside")
            self.assertTrue(pending.is_symlink())
        finally:
            outside.unlink()

    def test_corrupt_or_public_pending_fails_closed(self):
        with self.journal() as j:
            j.begin("worldserver", INC, "a")
        pending = next(self.root.glob("*.pending"))
        pending.write_bytes(b"not-json\n")
        with self.journal() as j:
            with self.assertRaises(UnsafeJournal):
                j.begin("worldserver", INC, "a")
        pending.chmod(0o644)
        with self.journal() as j:
            with self.assertRaises(UnsafeJournal):
                j.begin("worldserver", INC, "a")

    def test_hardlink_alias_rejected_not_removed(self):
        with self.journal() as j:
            j.begin("worldserver", INC, "a")
        pending = next(self.root.glob("*.pending"))
        alias = self.root / "alias"
        os.link(pending, alias)
        with self.journal() as j:
            with self.assertRaises(UnsafeJournal):
                j.begin("worldserver", INC, "a")
        self.assertTrue(alias.exists())

    def test_orphan_done_is_not_accepted(self):
        with self.journal() as j:
            j.begin("worldserver", INC, "a")
            j.complete_synthetic("worldserver", INC, "a", "failed")
        next(self.root.glob("*.pending")).unlink()
        with self.journal() as j:
            with self.assertRaisesRegex(UnsafeJournal, "orphan"):
                j.begin("worldserver", INC, "a")

    def test_concurrent_processes_only_one_reserves(self):
        ctx = multiprocessing.get_context("spawn")
        start = ctx.Event()
        out = ctx.Queue()
        workers = [ctx.Process(target=contender, args=(str(self.root), start, out)) for _ in range(5)]
        for p in workers:
            p.start()
        start.set()
        results = [out.get(timeout=10) for _ in workers]
        for p in workers:
            p.join(timeout=10)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(results.count("reserved"), 1)
        self.assertEqual(results.count("pending"), 4)


if __name__ == "__main__":
    unittest.main()
