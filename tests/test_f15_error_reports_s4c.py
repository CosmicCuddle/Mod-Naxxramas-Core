"""F15 S4c OFFLINE durable redacted warning-burst reports; NEVER live logs."""
import multiprocessing
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_error_bursts import BurstAlert, OfflineBurstTracker, LogEvidence
from offline_error_reports import (
    ErrorBurstObservation, OfflineErrorReportStore, error_bytes
)
from offline_restart import RestartObservation
from offline_store import Incident


def sample(level="ERROR", code="DB_TIMEOUT", instance="world-boot1",
           uptime=3000, service="worldserver", time="2026-10-25T00:02:00Z",
           verified=True, stream="stderr"):
    return ErrorBurstObservation(
        BurstAlert(service, instance, stream, level, code, 3, 60000, uptime),
        time, verified)


def crash():
    return Incident(
        service="worldserver", host="fixture-host", boot="fixture-boot",
        invocation="fixture-run", pid=4321,
        start_utc="2026-10-25T00:00:00Z",
        end_utc="2026-10-25T00:01:00Z",
        verified_actual_death=True, unexpected_death=True, exit_code=1)


def worker(folder, obs, result):
    try:
        s = OfflineErrorReportStore(Path(folder))
        result.put(("ok", s.publish_error(obs)))
        s.close()
    except Exception as exc:
        result.put(("err", type(exc).__name__))


class S4cErrorStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Crash Logs"
        self.root.mkdir(mode=0o700)
        self.store = OfflineErrorReportStore(self.root)
        self.addCleanup(self.store.close)

    def records(self):
        return sorted(self.root.glob("error-burst-*.txt"))

    def error_index(self):
        return (self.root / "Error-History.txt").read_text("utf-8")

    def test_first_error_report_is_immutable_private_and_redacted(self):
        self.assertTrue(self.store.publish_error(sample()))
        self.assertEqual(len(self.records()), 1)
        f = self.records()[0]
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        text = f.read_text("utf-8")
        self.assertIn("Finalized SHA-256", text)
        self.assertIn("Source verification: SYNTHETIC CLAIM ONLY", text)
        self.assertNotIn("SIGSEGV", text)
        self.assertNotIn("password=", text)
        self.assertIn("Errors: 1", self.error_index())
        self.assertIn("Warnings: 0", self.error_index())

    def test_warning_and_error_counts_separated_by_service(self):
        self.store.publish_error(sample())
        self.store.publish_error(sample(level="WARN", code="RETRY", uptime=5000))
        self.store.publish_error(sample(service="authserver", instance="auth-boot1"))
        history = self.error_index()
        for line in ("Worldserver: 2", "Authserver: 1",
                     "Warnings: 1", "Errors: 2", "Total bursts: 3"):
            self.assertIn(line, history)

    def test_unverified_source_does_not_create_report_or_history(self):
        self.assertFalse(self.store.publish_error(sample(verified=False)))
        self.assertEqual(self.records(), [])
        self.assertFalse((self.root / "Error-History.txt").exists())

    def test_duplicate_report_is_idempotent_across_reopens(self):
        event = sample()
        self.assertTrue(self.store.publish_error(event))
        self.assertFalse(self.store.publish_error(event))
        other = OfflineErrorReportStore(self.root)
        try:
            self.assertFalse(other.publish_error(event))
        finally:
            other.close()
        self.assertEqual(len(self.records()), 1)

    def test_distinct_bursts_on_one_process_remain_distinct(self):
        self.store.publish_error(sample(uptime=3000))
        self.store.publish_error(sample(uptime=71000, time="2026-10-25T00:03:00Z"))
        self.assertEqual(len(self.records()), 2)
        self.assertIn("Total bursts: 2", self.error_index())

    def test_same_identity_new_wall_timestamp_is_benign_replay(self):
        event = sample()
        self.store.publish_error(event)
        previous = self.records()[0].read_bytes()
        self.assertFalse(self.store.publish_error(
            replace(event, observed_utc="2026-10-25T00:04:00Z")))
        self.assertEqual(self.records()[0].read_bytes(), previous)
        self.assertEqual(len(self.records()), 1)

    def test_abandoned_temp_hardlink_is_recovered_before_rebuild(self):
        event = sample()
        self.store.publish_error(event)
        finalized = self.records()[0]
        abandoned = self.root / (".f15-s2-" + "a" * 32)
        os.link(finalized, abandoned)
        self.assertEqual(finalized.stat().st_nlink, 2)
        self.assertEqual(self.store.rebuild_errors(), (1, 0, 0, 1))
        self.assertFalse(abandoned.exists())
        self.assertEqual(finalized.stat().st_nlink, 1)
        self.assertIn("Total bursts: 1", self.error_index())
        self.assertFalse(self.store.publish_error(event))

    def test_abandoned_temp_link_recovered_on_duplicate_publish(self):
        event = sample()
        self.store.publish_error(event)
        first = self.records()[0].read_bytes()
        abandoned = self.root / (".f15-s2-" + "b" * 32)
        os.link(self.records()[0], abandoned)
        self.assertFalse(self.store.publish_error(
            replace(event, observed_utc="2026-10-25T00:08:00Z")))
        self.assertFalse(abandoned.exists())
        self.assertEqual(self.records()[0].read_bytes(), first)

    def test_temp_symlink_never_followed_or_removed(self):
        sentinel = Path(self.tmp.name) / "outside"
        sentinel.write_text("do not touch", encoding="utf-8")
        hostile = self.root / (".f15-s2-" + "c" * 32)
        hostile.symlink_to(sentinel)
        self.store.publish_error(sample())
        self.assertTrue(hostile.is_symlink())
        self.assertEqual(sentinel.read_text("utf-8"), "do not touch")
        self.assertEqual(self.store.rebuild_errors(), (1, 0, 0, 1))

    def test_future_stamp_rejected_before_persisting(self):
        with self.assertRaisesRegex(ValueError, "future"):
            self.store.publish_error(sample(time="2099-01-01T00:00:00Z"))
        self.assertEqual(self.records(), [])

    def test_correctly_hashed_future_sidecar_excluded_during_rebuild(self):
        event = sample(time="2099-01-01T00:00:00Z")
        (self.root / event.filename()).write_bytes(error_bytes(event.info()))
        self.assertEqual(self.store.rebuild_errors(), (0, 0, 0, 0))
        self.assertIn("Invalid / modified warning reports: 1", self.error_index())

    def test_corruption_does_not_count_and_warning_survives(self):
        self.store.publish_error(sample())
        f = self.records()[0]
        f.write_bytes(f.read_bytes() + b"MUTATION")
        self.assertEqual(self.store.rebuild_errors(), (0, 0, 0, 0))
        self.assertIn("Invalid / modified warning reports: 1", self.error_index())
        self.assertIn("Unverified error report:", self.error_index())

    def test_symlink_attack_does_not_touch_outside_file(self):
        sentinel = Path(self.tmp.name) / "sentinel"
        sentinel.write_text("untouched", "utf-8")
        (self.root / sample().filename()).symlink_to(sentinel)
        with self.assertRaises(FileExistsError):
            self.store.publish_error(sample())
        self.assertEqual(sentinel.read_text("utf-8"), "untouched")
        self.assertIn("Invalid / modified warning reports: 1", self.error_index())

    def test_hardlink_and_public_mode_are_invalid(self):
        event = sample()
        self.store.publish_error(event)
        f = self.records()[0]
        link = Path(self.tmp.name) / "second-link"
        os.link(f, link)
        self.assertEqual(self.store.rebuild_errors(), (0, 0, 0, 0))
        link.unlink()
        os.chmod(f, 0o644)
        self.assertEqual(self.store.rebuild_errors(), (0, 0, 0, 0))

    def test_unsafe_filename_not_echoed_in_history(self):
        name = "error-burst-" + "oops\nSPOOFED-COUNT" + ".txt"
        (self.root / name).write_text("bad", "utf-8")
        self.assertEqual(self.store.rebuild_errors(), (0, 0, 0, 0))
        index = self.error_index()
        self.assertIn("Invalid / modified warning reports: 1", index)
        self.assertNotIn("SPOOFED-COUNT", index)

    def test_deleted_error_history_rebuilt_from_durable_files(self):
        self.store.publish_error(sample())
        (self.root / "Error-History.txt").unlink()
        other = OfflineErrorReportStore(self.root)
        try:
            self.assertEqual(other.rebuild_errors(), (1, 0, 0, 1))
        finally:
            other.close()
        self.assertIn("Total bursts: 1", self.error_index())

    def test_error_index_failure_preserves_immutable_record(self):
        with patch.object(self.store, "_rebuild_errors_locked",
                          side_effect=OSError("fault injected")):
            with self.assertRaisesRegex(OSError, "fault injected"):
                self.store.publish_error(sample())
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(self.store.rebuild_errors(), (1, 0, 0, 1))

    def test_original_crash_history_and_restart_projection_unchanged(self):
        incident = crash()
        self.store.publish(incident)
        restart = RestartObservation(incident.identity(), "retry1",
                                     "2026-10-25T00:05:00Z", "succeeded", True)
        self.store.publish_restart(restart)
        old = (self.root / "Crash-History.txt").read_bytes()
        self.store.publish_error(sample())
        self.assertEqual((self.root / "Crash-History.txt").read_bytes(), old)
        self.assertIn("restart: succeeded (attempt retry1)", old.decode("utf-8"))
        self.assertIn("Total: 1", old.decode("utf-8"))
        self.assertIn("Total bursts: 1", self.error_index())
        self.assertEqual(len(list(self.root.glob("*-crash-*.txt"))), 1)

    def test_crash_rebuild_and_new_crash_preserve_error_index(self):
        self.store.publish_error(sample())
        original = (self.root / "Error-History.txt").read_bytes()
        self.store.publish(crash())
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertEqual((self.root / "Error-History.txt").read_bytes(), original)

    def test_malformed_samples_fail_before_file_mutation(self):
        x = sample()
        variants = [
            replace(x, observed_utc="2026-10-25T13:59:00+00:00"),
            replace(x, verified=1),
            replace(x, alert=replace(x.alert, code="../secret")),
            replace(x, alert=replace(x.alert, level=[])),
            replace(x, alert=replace(x.alert, window_ms=0)),
            replace(x, alert=replace(x.alert, observed_uptime_ms=-1)),
            replace(x, alert=replace(x.alert, service="proxy")),
            replace(x, alert=replace(x.alert, instance="evil\nhost")),
        ]
        for bad in variants:
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                self.store.publish_error(bad)
        self.assertEqual(self.records(), [])

    def test_wrong_type_is_rejected(self):
        with self.assertRaises(TypeError):
            self.store.publish_error(sample().alert)

    def test_report_has_no_raw_message_or_crash_identity(self):
        event = sample()
        self.assertNotIn("message", event.info())
        self.assertNotIn("raw", event.info())
        self.assertNotIn("incident_id", event.info())
        self.assertNotIn("restart", event.info())
        self.store.publish_error(event)
        text = self.records()[0].read_text("utf-8")
        self.assertNotIn("Crash cause:", text)
        self.assertNotIn("Automatic restart: ", text)

    def test_two_publishers_same_event_dedup_under_existing_lock(self):
        event = sample()
        ctx = multiprocessing.get_context("fork")
        result = ctx.Queue()
        ps = [ctx.Process(target=worker, args=(str(self.root), event, result))
              for _ in range(2)]
        for p in ps:
            p.start()
        for p in ps:
            p.join(timeout=10)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(sorted(result.get(timeout=5) for _ in ps),
                         [("ok", False), ("ok", True)])
        self.assertEqual(len(self.records()), 1)
        self.assertIn("Total bursts: 1", self.error_index())

    def test_burst_alert_from_s4b_tracker_can_be_stored(self):
        tracker = OfflineBurstTracker()
        last = None
        for seq in range(1, 4):
            e = LogEvidence("worldserver", "world-boot1", "stderr",
                            "ERROR", "DB_TIMEOUT", seq, seq * 1000,
                            source="verified-stream-fixture", verified_stream=True)
            last = tracker.observe(e)
        self.assertEqual(last.status, "alert")
        self.assertTrue(self.store.publish_error(
            ErrorBurstObservation(last.alert, "2026-10-25T00:02:00Z", True)))
        self.assertIn("Total bursts: 1", self.error_index())


if __name__ == "__main__":
    unittest.main()
