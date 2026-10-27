"""F15 R4 offline quota and bounded-lock tests. Disposable fixtures ONLY.

No daemon, systemd, log, real report path, root, or server interaction.
These limits are backpressure, NOT a retention/deletion policy.
"""
import errno
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



def concurrent_publisher(folder, index, gate, result):
    """Separate disposable process uses its own fd and shared flock."""
    store = OfflineErrorReportStore(Path(folder))
    try:
        if not gate.wait(5):
            result.put(("missing-start", index))
            return
        # Both kinds and services deliberately race over one global cap.
        observation = (crash(index, "worldserver" if index % 2 else "authserver")
                       if index % 3 else
                       burst(index, "worldserver" if index % 2 else "authserver"))
        with patch("offline_store.MAX_TOTAL_REPORTS", 3):
            try:
                if isinstance(observation, Incident):
                    success = store.publish(observation)
                else:
                    success = store.publish_error(observation)
                result.put(("published" if success else "duplicate", index))
            except OverflowError:
                result.put(("at-capacity", index))
    except BaseException as exc:
        result.put((type(exc).__name__, index))
    finally:
        store.close()


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
            first_path = self.finals()[0]
            first = first_path.read_bytes()
            with self.assertRaisesRegex(OverflowError, "capacity"):
                self.store.publish_error(burst(3))
            self.assertTrue(self.store.publish(crash(1)))
            self.assertTrue(self.store.publish(crash(2, "authserver")))
            self.assertEqual(len(self.finals()), 4)
            self.assertEqual(first_path.read_bytes(), first)
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
            self.assertEqual(self.store.offline_rejections(),
                             {"capacity": 0, "lock_timeout": 1})
        finally:
            release.set()
            process.join(3)
        self.assertFalse(process.is_alive(), "disposable lock process did not exit")
        self.assertTrue(self.store.publish(crash(1)))

    def test_rejection_counters_saturate_and_remain_in_memory(self):
        with patch("offline_store.MAX_TOTAL_REPORTS", 0):
            for _ in range(260):
                with self.assertRaises(OverflowError):
                    self.store.publish(crash(1))
        self.assertEqual(self.store.offline_rejections(),
                         {"capacity": 255, "lock_timeout": 0})
        self.assertFalse((self.root / "offline-status.json").exists())
        other = OfflineErrorReportStore(self.root)
        try:
            self.assertEqual(other.offline_rejections(),
                             {"capacity": 0, "lock_timeout": 0})
        finally:
            other.close()

    def test_simultaneous_cross_daemon_publish_never_exceeds_global_cap(self):
        start = multiprocessing.Event()
        results = multiprocessing.Queue()
        children = [multiprocessing.Process(
            target=concurrent_publisher,
            args=(str(self.root), n, start, results),
        ) for n in range(1, 9)]
        try:
            for child in children:
                child.start()
            start.set()
            outcomes = [results.get(timeout=10)[0] for _ in children]
            self.assertEqual(outcomes.count("published"), 3, outcomes)
            self.assertEqual(outcomes.count("at-capacity"), 5, outcomes)
            self.assertEqual(len(self.finals()), 3)
            # Race losers cannot overwrite or mutate the winners.
            observed = {p.name: p.read_bytes() for p in self.finals()}
            self.store.rebuild_errors()
            self.store.rebuild()
            self.assertEqual(
                {p.name: p.read_bytes() for p in self.finals()}, observed)
        finally:
            start.set()
            for child in children:
                child.join(5)
                if child.is_alive():
                    child.terminate()
                    child.join(3)
        self.assertTrue(all(child.exitcode == 0 for child in children))

    def test_enospc_before_final_link_does_not_leave_report_or_temp(self):
        with patch("offline_store.os.link",
                   side_effect=OSError(errno.ENOSPC, "synthetic disk full")):
            with self.assertRaises(OSError) as caught:
                self.store.publish(crash(1))
            self.assertEqual(caught.exception.errno, errno.ENOSPC)
            with self.assertRaises(OSError):
                self.store.publish_error(burst(1))
        self.assertEqual(self.finals(), [])
        self.assertEqual(list(self.root.glob(".f15-s2-*")), [])
        # The disposable store is still able to accept a later event.
        self.assertTrue(self.store.publish(crash(1)))

    def test_eio_on_index_replace_preserves_final_crash_and_error(self):
        with patch("offline_store.os.replace",
                   side_effect=OSError(errno.EIO, "synthetic index failure")):
            with self.assertRaises(OSError):
                self.store.publish(crash(1))
            with self.assertRaises(OSError):
                self.store.publish_error(burst(1))
        saved = {p.name: p.read_bytes() for p in self.finals()}
        self.assertEqual(len(saved), 2)
        self.store.rebuild()
        self.store.rebuild_errors()
        self.assertIn("Total: 1", (self.root / "Crash-History.txt").read_text())
        self.assertIn("Total bursts: 1",
                      (self.root / "Error-History.txt").read_text())
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.finals()}, saved)
        self.assertFalse(self.store.publish(crash(1)))
        self.assertFalse(self.store.publish_error(burst(1)))

    def test_hostile_symlink_named_as_report_is_never_overwritten(self):
        external = Path(self.tmp.name) / "outside-sentinel"
        external.write_text("keep", encoding="utf-8")
        name = burst(1).filename()
        (self.root / name).symlink_to(external)
        with self.assertRaises(FileExistsError):
            self.store.publish_error(burst(1))
        self.assertEqual(external.read_text(encoding="utf-8"), "keep")
        self.assertTrue((self.root / name).is_symlink())
        self.assertEqual(self.finals(), [self.root / name])


if __name__ == "__main__":
    unittest.main()
