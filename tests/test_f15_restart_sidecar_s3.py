"""F15 S3: synthetic immutable restart evidence, no actual server/supervisor."""
import multiprocessing
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_store import Incident, IncidentStore
from offline_restart import RestartObservation, RestartSidecarStore


def crash(service="worldserver", invocation="boot-a"):
    return Incident(service=service, host="fake-host", boot="boot-a",
                    invocation=invocation, pid=344,
                    start_utc="2026-10-25T00:01:00Z",
                    end_utc="2026-10-25T00:02:00Z",
                    verified_actual_death=True, unexpected_death=True,
                    exit_code=1)


def restart(item, attempt="try-1", outcome="succeeded", time="2026-10-25T00:03:00Z",
            verified=True):
    return RestartObservation(item.identity(), attempt, time, outcome, verified)


def concurrent_worker(folder, result, queue):
    try:
        state = RestartSidecarStore(Path(folder))
        queue.put(("ok", state.publish_restart(result)))
        state.close()
    except Exception as exc:
        queue.put(("err", type(exc).__name__))


class S3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Crash Logs"
        self.root.mkdir(mode=0o700)
        self.store = RestartSidecarStore(self.root)
        self.addCleanup(self.store.close)
        self.item = crash()
        self.assertTrue(self.store.publish(self.item))

    def history(self):
        return (self.root / "Crash-History.txt").read_text("utf-8")

    def sidecars(self):
        return list(self.root.glob("restart-*.txt"))

    def test_verified_restart_success_updates_only_history(self):
        self.assertTrue(self.store.publish_restart(restart(self.item)))
        self.assertIn("restart: succeeded (attempt try-1)", self.history())
        self.assertIn("Total: 1", self.history())
        self.assertEqual(len(list(self.root.glob("*-crash-*.txt"))), 1)
        self.assertEqual(len(self.sidecars()), 1)

    def test_legacy_s2_rebuild_cannot_erase_s3_restart_projection(self):
        self.store.publish_restart(restart(self.item))
        previous = self.history()
        old_writer = IncidentStore(self.root)
        try:
            with self.assertRaisesRegex(RuntimeError, "legacy S2 index"):
                old_writer.rebuild()
        finally:
            old_writer.close()
        self.assertEqual(self.history(), previous)
        self.assertIn("restart: succeeded (attempt try-1)", self.history())

    def test_legacy_s2_publish_rejected_before_mutating_s3_directory(self):
        self.store.publish_restart(restart(self.item))
        old_writer = IncidentStore(self.root)
        try:
            with self.assertRaisesRegex(RuntimeError, "legacy S2 index"):
                old_writer.publish(crash("authserver", "unexpected-auth"))
        finally:
            old_writer.close()
        self.assertIn("Worldserver: 1", self.history())
        self.assertIn("Authserver: 0", self.history())
        self.assertEqual(len(list(self.root.glob("*-crash-*.txt"))), 1)
        self.assertIn("restart: succeeded", self.history())

    def test_future_dated_restart_is_refused_without_sidecar(self):
        with self.assertRaisesRegex(ValueError, "future"):
            self.store.publish_restart(
                restart(self.item, attempt="bad-clock",
                        time="2099-01-01T00:00:00Z"))
        self.assertEqual(len(self.sidecars()), 0)
        self.assertIn("restart: Not verified", self.history())

    def test_correctly_hashed_future_sidecar_cannot_hide_later_failure(self):
        from offline_restart import sidecar_bytes
        self.store.publish_restart(restart(
            self.item, attempt="real", outcome="failed",
            time="2026-10-25T00:05:00Z"))
        forged = restart(self.item, attempt="bad-clock", outcome="succeeded",
                         time="2099-01-01T00:00:00Z")
        (self.root / forged.filename()).write_bytes(sidecar_bytes(forged.info()))
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertIn("Unverified or orphan restart sidecars: 1", self.history())
        self.assertIn("restart: failed (attempt real)", self.history())
        self.assertNotIn("restart: succeeded (attempt bad-clock)", self.history())

    def test_world_and_auth_remain_separate_and_correct(self):
        auth = crash("authserver", "auth-run")
        self.store.publish(auth)
        self.store.publish_restart(restart(self.item, outcome="failed"))
        self.store.publish_restart(restart(auth, attempt="auth-try", outcome="succeeded"))
        self.assertIn("Worldserver: 1", self.history())
        self.assertIn("Authserver: 1", self.history())
        self.assertIn("Total: 2", self.history())
        self.assertIn("restart: failed (attempt try-1)", self.history())
        self.assertIn("restart: succeeded (attempt auth-try)", self.history())

    def test_repeated_same_observation_is_idempotent_after_restart(self):
        obs = restart(self.item)
        self.assertTrue(self.store.publish_restart(obs))
        self.assertFalse(self.store.publish_restart(obs))
        next_instance = RestartSidecarStore(self.root)
        try:
            self.assertFalse(next_instance.publish_restart(obs))
        finally:
            next_instance.close()
        self.assertEqual(len(self.sidecars()), 1)

    def test_conflicting_outcome_in_same_attempt_refuses_overwrite(self):
        original = restart(self.item)
        self.store.publish_restart(original)
        data = self.sidecars()[0].read_bytes()
        with self.assertRaises(FileExistsError):
            self.store.publish_restart(replace(original, outcome="failed"))
        self.assertEqual(data, self.sidecars()[0].read_bytes())
        self.assertIn("restart: succeeded", self.history())

    def test_second_attempt_may_recover_from_failed_first(self):
        self.store.publish_restart(restart(self.item, "try-1", "failed"))
        self.store.publish_restart(restart(self.item, "try-2", "succeeded",
                                           "2026-10-25T00:04:00Z"))
        self.assertEqual(len(self.sidecars()), 2)
        self.assertIn("restart: succeeded (attempt try-2)", self.history())
        self.assertIn("Total: 1", self.history())

    def test_out_of_order_observation_uses_utc_evidence_not_writer_order(self):
        self.store.publish_restart(restart(self.item, "later", "succeeded",
                                           "2026-10-25T00:10:00Z"))
        self.store.publish_restart(restart(self.item, "earlier", "failed",
                                           "2026-10-25T00:05:00Z"))
        self.assertIn("restart: succeeded (attempt later)", self.history())

    def test_same_second_conflicting_attempts_are_ambiguous_not_success(self):
        self.store.publish_restart(restart(self.item, attempt="first", outcome="succeeded",
                                           time="2026-10-25T00:05:00Z"))
        self.store.publish_restart(restart(self.item, attempt="second", outcome="failed",
                                           time="2026-10-25T00:05:00Z"))
        self.assertEqual(len(self.sidecars()), 2)
        history = self.history()
        self.assertIn("restart: Ambiguous (2 attempts observed at 2026-10-25T00:05:00Z", history)
        self.assertNotIn("restart: succeeded (attempt", history)
        self.assertNotIn("restart: failed (attempt", history)
        self.assertIn("Total: 1", history)

    def test_later_unique_observation_resolves_same_second_ambiguity(self):
        self.store.publish_restart(restart(self.item, attempt="a", outcome="succeeded",
                                           time="2026-10-25T00:04:00Z"))
        self.store.publish_restart(restart(self.item, attempt="b", outcome="failed",
                                           time="2026-10-25T00:04:00Z"))
        self.assertIn("restart: Ambiguous", self.history())
        self.store.publish_restart(restart(self.item, attempt="c", outcome="succeeded",
                                           time="2026-10-25T00:05:00Z"))
        self.assertIn("restart: succeeded (attempt c)", self.history())
        self.assertIn("Total: 1", self.history())

    def test_restart_evidence_before_incident_death_rejected(self):
        obs = restart(self.item, attempt="before-death",
                      time="2026-10-25T00:01:59Z")
        with self.assertRaisesRegex(ValueError, "predates"):
            self.store.publish_restart(obs)
        self.assertEqual(len(self.sidecars()), 0)
        self.assertIn("restart: Not verified", self.history())

    def test_pre_crash_but_correctly_hashed_sidecar_is_unverified(self):
        # This simulates a separate producer bypassing publish_restart,
        # proving rebuild independently enforces the chronology.
        from offline_restart import sidecar_bytes
        obs = restart(self.item, attempt="forged-order",
                      time="2026-10-25T00:01:59Z")
        (self.root / obs.filename()).write_bytes(sidecar_bytes(obs.info()))
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertIn("Unverified or orphan restart sidecars: 1", self.history())
        self.assertIn("restart: Not verified", self.history())
        self.assertEqual(len(self.sidecars()), 1)  # never auto-destroy evidence

    def test_equal_timestamp_and_matching_outcomes_still_ambiguous_sequence(self):
        self.store.publish_restart(restart(self.item, attempt="a", outcome="succeeded",
                                           time="2026-10-25T00:06:00Z"))
        self.store.publish_restart(restart(self.item, attempt="b", outcome="succeeded",
                                           time="2026-10-25T00:06:00Z"))
        self.assertIn("restart: Ambiguous (2 attempts", self.history())

    def test_unverified_restart_cannot_claim_success(self):
        self.assertFalse(self.store.publish_restart(restart(self.item, verified=False)))
        self.assertEqual(len(self.sidecars()), 0)
        self.assertIn("restart: Not verified", self.history())

    def test_missing_crash_report_does_not_get_restart_sidecar(self):
        fake = replace(restart(self.item), incident_id="11111111-1111-4111-8111-111111111111")
        with self.assertRaisesRegex(ValueError, "original"):
            self.store.publish_restart(fake)
        self.assertEqual(len(self.sidecars()), 0)

    def test_corrupted_original_prevents_verified_sidecar(self):
        item_report = list(self.root.glob("*-crash-*.txt"))[0]
        item_report.write_bytes(item_report.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "original"):
            self.store.publish_restart(restart(self.item))
        self.assertEqual(len(self.sidecars()), 0)

    def test_sidecar_tampering_visible_but_original_crash_still_counted(self):
        self.store.publish_restart(restart(self.item))
        sidecar = self.sidecars()[0]
        sidecar.write_bytes(sidecar.read_bytes() + b"changed")
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertIn("Unverified or orphan restart sidecars: 1", self.history())
        self.assertIn("restart: Not verified", self.history())
        self.assertIn("Total: 1", self.history())

    def test_symlink_sidecar_does_not_modify_external_target(self):
        sentinel = Path(self.tmp.name) / "sentinel"
        sentinel.write_text("do not write", encoding="utf-8")
        name = restart(self.item).filename()
        (self.root / name).symlink_to(sentinel)
        with self.assertRaises(FileExistsError):
            self.store.publish_restart(restart(self.item))
        self.assertEqual(sentinel.read_text(), "do not write")
        self.assertIn("Unverified or orphan restart sidecars: 1", self.history())

    def test_a_valid_restart_sidecar_is_private_and_finalized(self):
        self.store.publish_restart(restart(self.item))
        sidecar = self.sidecars()[0]
        self.assertEqual(sidecar.stat().st_mode & 0o777, 0o600)
        self.assertIn("Finalized SHA-256:", sidecar.read_text("utf-8"))

    def test_rebuild_uses_immutable_reports_and_sidecars_after_history_loss(self):
        self.store.publish_restart(restart(self.item))
        (self.root / "Crash-History.txt").unlink()
        newer = RestartSidecarStore(self.root)
        try:
            self.assertEqual(newer.rebuild(), (1, 0))
        finally:
            newer.close()
        self.assertIn("restart: succeeded", self.history())

    def test_crash_publish_after_restart_uses_s3_index(self):
        self.store.publish_restart(restart(self.item))
        new_item = crash("authserver", "new-auth")
        self.store.publish(new_item)
        self.assertIn("restart: succeeded", self.history())
        self.assertIn("Total: 2", self.history())

    def test_invalid_attempt_and_unknown_outcome_rejected(self):
        for attempt in ("", "../escape", "new\nline"):
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                self.store.publish_restart(restart(self.item, attempt=attempt))
        for status in ("unknown", "restarting", "succeeded\nbad", ""):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.store.publish_restart(restart(self.item, outcome=status))
        self.assertEqual(len(self.sidecars()), 0)

    def test_noncanonical_or_invalid_incident_id_rejected(self):
        for value in ("bad", self.item.identity().upper(), "../" + self.item.identity()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.publish_restart(replace(restart(self.item), incident_id=value))

    def test_same_attempt_with_different_timestamp_is_conflict(self):
        original = restart(self.item)
        self.store.publish_restart(original)
        with self.assertRaises(FileExistsError):
            self.store.publish_restart(replace(original, observed_utc="2026-10-25T00:04:00Z"))
        self.assertEqual(len(self.sidecars()), 1)

    def test_sidecar_after_index_fault_remains_durable_and_rebuildable(self):
        with patch.object(self.store, "_rebuild_locked",
                          side_effect=OSError("injected history failure")):
            with self.assertRaisesRegex(OSError, "injected"):
                self.store.publish_restart(restart(self.item))
        self.assertEqual(len(self.sidecars()), 1)
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertIn("restart: succeeded", self.history())

    def test_orphan_sidecar_excluded_when_original_report_modified(self):
        self.store.publish_restart(restart(self.item))
        file = list(self.root.glob("*-crash-*.txt"))[0]
        file.write_bytes(file.read_bytes() + b"modified")
        self.assertEqual(self.store.rebuild(), (0, 0))
        self.assertIn("Unverified or orphan restart sidecars: 1", self.history())
        self.assertIn("Unverified or modified report files: 1", self.history())

    def test_two_processes_publish_identical_restart_once(self):
        obs = restart(self.item)
        ctx = multiprocessing.get_context("fork")
        queue = ctx.Queue()
        p = [ctx.Process(target=concurrent_worker,
                         args=(str(self.root), obs, queue)) for _ in range(2)]
        for x in p:
            x.start()
        for x in p:
            x.join(timeout=10)
            self.assertEqual(x.exitcode, 0)
        self.assertEqual(sorted(queue.get(timeout=5) for _ in p),
                         [("ok", False), ("ok", True)])
        self.assertEqual(len(self.sidecars()), 1)
        self.assertIn("Total: 1", self.history())

    def test_two_distinct_attempts_in_same_second_not_collapsed(self):
        for attempt in ("attempt-1", "attempt-2"):
            self.assertTrue(self.store.publish_restart(restart(self.item, attempt)))
        self.assertEqual(len(self.sidecars()), 2)
        self.assertIn("Total: 1", self.history())


if __name__ == "__main__":
    unittest.main()
