"""F15 S4e: synthetic S3 completion lookup — NO OS monitoring or live host."""
import os
import sys
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_completed_lookup import OfflineCompletedRestartLookup
from offline_restart import RestartObservation, RestartSidecarStore, sidecar_bytes
from offline_restart_readiness import (
    ChildRef, OfflineRestartReadiness, RestartStart, RestartSignal,
    READY_PROBE, SUPERVISOR,
)
from offline_store import Incident


def crashed(service="worldserver", invocation="old-session", pid=4567):
    return Incident(service=service, host="fixture-host", boot="fixture-boot",
                    invocation=invocation, pid=pid,
                    start_utc="2026-10-25T00:00:00Z",
                    end_utc="2026-10-25T00:02:00Z",
                    verified_actual_death=True, unexpected_death=True,
                    exit_code=1)


def completed(incident, attempt="attempt-1", outcome="succeeded",
              time="2026-10-25T00:04:00Z"):
    return RestartObservation(incident.identity(), attempt, time, outcome, True)


def start_for(incident, attempt="attempt-1"):
    old = ChildRef(incident.service, incident.host, incident.boot,
                   incident.invocation, incident.pid, incident.start_utc)
    new = ChildRef(incident.service, incident.host, incident.boot,
                   "replacement-1", 4568, "2026-10-25T00:03:00Z")
    return RestartStart(incident.identity(), attempt, old, new,
                        incident.end_utc, 5000, True, SUPERVISOR)


class S4eLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Crash Logs"
        self.root.mkdir(mode=0o700)
        self.store = RestartSidecarStore(self.root)
        self.addCleanup(self.store.close)
        self.item = crashed()
        self.assertTrue(self.store.publish(self.item))
        self.lookup = OfflineCompletedRestartLookup(self.store)

    def sidecar(self, attempt="attempt-1", outcome="succeeded"):
        record = completed(self.item, attempt=attempt, outcome=outcome)
        return record, self.root / record.filename()

    def test_absent_sidecar_is_new_attempt_only_when_original_exists(self):
        self.assertIsNone(self.lookup((self.item.identity(), "fresh")))
        model = OfflineRestartReadiness(finished_lookup=self.lookup)
        self.assertEqual(model.begin(start_for(self.item, "fresh")).status, "pending")

    def test_verified_success_can_be_replayed_across_new_collector(self):
        obs, _ = self.sidecar()
        self.assertTrue(self.store.publish_restart(obs))
        self.assertEqual(self.lookup((obs.incident_id, obs.attempt)), "succeeded")
        model = OfflineRestartReadiness(finished_lookup=self.lookup)
        result = model.begin(start_for(self.item))
        self.assertEqual((result.status, result.outcome), ("duplicate", "succeeded"))
        self.assertEqual(model.counts(), (0, 0))

    def test_verified_failure_is_replay_protected(self):
        obs, _ = self.sidecar(outcome="failed")
        self.assertTrue(self.store.publish_restart(obs))
        model = OfflineRestartReadiness(finished_lookup=self.lookup)
        result = model.begin(start_for(self.item))
        self.assertEqual((result.status, result.outcome), ("duplicate", "failed"))

    def test_reopened_s3_ledger_retains_final_outcome(self):
        obs, _ = self.sidecar()
        self.store.publish_restart(obs)
        reopened = RestartSidecarStore(self.root)
        try:
            lookup = OfflineCompletedRestartLookup(reopened)
            self.assertEqual(lookup((obs.incident_id, obs.attempt)), "succeeded")
            model = OfflineRestartReadiness(finished_lookup=lookup)
            self.assertEqual(model.begin(start_for(self.item)).status, "duplicate")
        finally:
            reopened.close()

    def test_missing_original_is_unverified_not_absent_sidecar(self):
        other = crashed("authserver", "auth-only")
        with self.assertRaisesRegex(ValueError, "original"):
            self.lookup((other.identity(), "attempt-1"))
        model = OfflineRestartReadiness(finished_lookup=self.lookup)
        result = model.begin(start_for(other))
        self.assertEqual(result.status, "unverified")
        self.assertEqual(model.counts(), (0, 0))

    def test_modified_original_blocks_prior_completion(self):
        obs, _ = self.sidecar()
        self.store.publish_restart(obs)
        original = list(self.root.glob("*-crash-*.txt"))[0]
        original.write_bytes(original.read_bytes() + b"corrupt")
        with self.assertRaisesRegex(ValueError, "original"):
            self.lookup((obs.incident_id, obs.attempt))

    def test_public_original_file_blocks_completion(self):
        obs, _ = self.sidecar()
        self.store.publish_restart(obs)
        original = list(self.root.glob("*-crash-*.txt"))[0]
        original.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mode"):
            self.lookup((obs.incident_id, obs.attempt))

    def test_corrupted_sidecar_never_confirms_success(self):
        obs, path = self.sidecar()
        self.store.publish_restart(obs)
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.lookup((obs.incident_id, obs.attempt))
        model = OfflineRestartReadiness(finished_lookup=self.lookup)
        self.assertEqual(model.begin(start_for(self.item)).status, "unverified")

    def test_public_sidecar_never_confirms_success(self):
        obs, path = self.sidecar()
        self.store.publish_restart(obs)
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mode"):
            self.lookup((obs.incident_id, obs.attempt))

    def test_hardlinked_sidecar_never_confirms_success(self):
        obs, path = self.sidecar()
        self.store.publish_restart(obs)
        sibling = self.root / "unrelated-hardlink"
        os.link(path, sibling)
        with self.assertRaisesRegex(ValueError, "link"):
            self.lookup((obs.incident_id, obs.attempt))

    def test_symlinked_sidecar_does_not_follow_external_file(self):
        obs, path = self.sidecar()
        sentinel = Path(self.temp.name) / "outside"
        sentinel.write_text("secret", encoding="utf-8")
        path.symlink_to(sentinel)
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.lookup((obs.incident_id, obs.attempt))
        self.assertEqual(sentinel.read_text("utf-8"), "secret")

    def test_future_sidecar_even_with_hash_never_confirms(self):
        obs, path = self.sidecar()
        future = replace(obs, observed_utc="2099-01-01T00:00:00Z")
        path.write_bytes(sidecar_bytes(future.info()))
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.lookup((future.incident_id, future.attempt))

    def test_predeath_sidecar_even_with_hash_never_confirms(self):
        obs, path = self.sidecar()
        early = replace(obs, observed_utc="2026-10-25T00:01:00Z")
        path.write_bytes(sidecar_bytes(early.info()))
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.lookup((early.incident_id, early.attempt))

    def test_distinct_attempts_still_independent(self):
        first, _ = self.sidecar(attempt="failed-1", outcome="failed")
        second, _ = self.sidecar(attempt="succeeded-2", outcome="succeeded")
        self.store.publish_restart(first)
        self.store.publish_restart(second)
        self.assertEqual(self.lookup((self.item.identity(), "failed-1")), "failed")
        self.assertEqual(self.lookup((self.item.identity(), "succeeded-2")), "succeeded")
        self.assertIsNone(self.lookup((self.item.identity(), "fresh-3")))

    def test_world_auth_isolation(self):
        auth = crashed("authserver", "auth-instance", pid=9001)
        self.assertTrue(self.store.publish(auth))
        auth_observation = completed(auth, "auth-try", "failed")
        self.store.publish_restart(auth_observation)
        self.assertEqual(self.lookup((auth.identity(), "auth-try")), "failed")
        self.assertIsNone(self.lookup((self.item.identity(), "auth-try")))

    def test_malformed_names_and_keys_fail_closed(self):
        for key in (None, "string", ("only",), ("not-uuid", "try"),
                    (self.item.identity(), "../path"),
                    (self.item.identity().upper(), "try"),
                    (self.item.identity(), 5),
                    (self.item.identity(), [])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.lookup(key)

    def test_refuses_legacy_base_incident_store(self):
        from offline_store import IncidentStore
        old = IncidentStore(self.root)
        try:
            with self.assertRaises(TypeError):
                OfflineCompletedRestartLookup(old)
        finally:
            old.close()

    def test_no_report_writer_methods_in_lookup(self):
        self.assertFalse(hasattr(self.lookup, "publish_restart"))
        self.assertFalse(hasattr(self.lookup, "start_worldserver"))
        self.assertEqual(list(self.root.glob("restart-*.txt")), [])


if __name__ == "__main__":
    unittest.main()
