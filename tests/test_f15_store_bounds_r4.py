"""F15 R4 offline quota and bounded-lock tests. Disposable fixtures ONLY.

No daemon, systemd, log, real report path, root, or server interaction.
These limits are backpressure, NOT a retention/deletion policy.
"""
import fcntl
import multiprocessing
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_store import Incident, report_bytes
from offline_error_reports import ErrorBurstObservation, OfflineErrorReportStore
from offline_error_bursts import BurstAlert


def crash(n=1, service="worldserver"):
    return Incident(
        service=service, host="synthetic-host", boot="boot-fixture",
        invocation=f"run-{n}", pid=9000 + n,
        start_utc="2026-10-25T00:00:00Z",
        end_utc="2026-10-25T00:01:00Z",
        verified_actual_death=True, unexpected_death=True,
        exit_code=1,
    )


def burst(n=1, service="worldserver"):
    alert = BurstAlert(
        service, "fixture-incarnation", "stderr", "ERROR",
        "SYNTHETIC_TIMEOUT", 3, 60000, n * 61000,
    )
    return ErrorBurstObservation(alert, "2026-10-25T00:02:00Z", True)


def lock_holder(directory, started, release):
    """Only an owned throwaway flock, NEVER a real server."""
    fd = os.open(str(Path(directory) / ".f15.offline.lock"),
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        started.set()
        release.wait(5)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class OfflineStoreBounds(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Crash Logs"
        self.root.mkdir(mode=0o700)
        self.store = OfflineErrorReportStore(self.root)
        self.addCleanup(self.store.close)

    def finals(self):
        return sorted(p for p in self.root.glob("*.txt")
                      if "-crash-" in p.name or p.name.startswith("error-burst-"))

    def test_bounded_report_count_keeps_both_daemons_and_both_types(self):
        with patch("offline_store.MAX_TOTAL_REPORTS", 4), \
                patch("offline_store.MAX_REPORTS_PER_KIND", 3), \
                patch("offline_store.MAX_REPORTS_PER_SERVICE_KIND", 2):
            self.assertTrue(self.store.publish_error(burst(1)))
            self.assertTrue(self.store.publish_error(burst(2)))
            first = self.finals()[0].read_bytes()
            with self.assertRaisesRegex(OverflowError, "capacity"):
                self.store.publish_error(burst(3))
            self.assertTrue(self.store.publish(crash(1)))
            self.assertTrue(self.store.publish(crash(2, "authserver")))
            self.assertEqual(len(self.finals()), 4)
            self.assertEqual(self.finals()[0].read_bytes(), first)
            with self.assertRaisesRegex(OverflowError, "capacity"):
                self.store.publish_error(burst(4, "authserver"))
            self.assertIn("Total bursts: 2", (self.root / "Error-History.txt").read_text())
            self.assertIn("Total: 2", (self.root / "Crash-History.txt").read_text())

    def test_error_burst_lane_cannot_consume_crash_lane(self):
        with patch("offline_store.MAX_REPORTS_PER_KIND", 2):
            self.assertTrue(self.store.publish_error(burst(1)))
            self.assertTrue(self.store.publish_error(burst(2, "authserver")))
            with self.assertRaises(OverflowError):
                self.store.publish_error(burst(3))
            self.assertTrue(self.store.publish(crash(1)))
            self.assertEqual(len(self.finals()), 3)

    def test_bytes_limit_declines_without_deleting_first_crash(self):
        first = crash(1)
        limit = len(report_bytes(first.metadata()))
        with patch("offline_store.MAX_TOTAL_REPORT_BYTES", limit):
            self.assertTrue(self.store.publish(first))
            original = next(self.root.glob("*-crash-*.txt")).read_bytes()
            with self.assertRaises(OverflowError):
                self.store.publish_error(burst(1))
            self.assertEqual(next(self.root.glob("*-crash-*.txt")).read_bytes(), original)
            self.assertFalse((self.root / "Error-History.txt").exists())

    def test_duplicates_still_idempotent_when_capacity_full(self):
        with patch("offline_store.MAX_REPORTS_PER_SERVICE_KIND", 1):
            self.assertTrue(self.store.publish(crash(1)))
            self.assertFalse(self.store.publish(crash(1)))
            with self.assertRaises(OverflowError):
                self.store.publish(crash(2))
            self.assertTrue(self.store.publish_error(burst(1)))
            self.assertFalse(self.store.publish_error(burst(1)))
            self.assertEqual(len(self.finals()), 2)

    def test_invalid_named_report_conservatively_uses_quota(self):
        hostile = self.root / ("error-burst-worldserver-" + "f" * 36 + ".txt")
        hostile.write_text("not a verified report", encoding="utf-8")
        with patch("offline_store.MAX_REPORTS_PER_SERVICE_KIND", 1):
            with self.assertRaises(OverflowError):
                self.store.publish_error(burst(1))
            self.assertTrue(self.store.publish(crash(1)))
        self.assertEqual(hostile.read_text(), "not a verified report")

    def test_stalled_lock_times_out_and_leaves_no_report(self):
        started = multiprocessing.Event()
        release = multiprocessing.Event()
        process = multiprocessing.Process(
            target=lock_holder, args=(str(self.root), started, release),
        )
        process.start()
        try:
            self.assertTrue(started.wait(3), "disposable lock holder did not start")
            with patch("offline_store.LOCK_WAIT_SECONDS", 0.06), \
                    patch("offline_store.LOCK_POLL_SECONDS", 0.005):
                with self.assertRaisesRegex(TimeoutError, "deadline"):
                    self.store.publish(crash(1))
            self.assertEqual(self.finals(), [])
        finally:
            release.set()
            process.join(3)
        self.assertFalse(process.is_alive(), "disposable lock process did not exit")
        self.assertTrue(self.store.publish(crash(1)))


if __name__ == "__main__":
    unittest.main()
