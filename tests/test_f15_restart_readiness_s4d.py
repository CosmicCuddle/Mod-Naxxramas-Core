"""F15 S4d synthetic restart readiness; actual OS and service signals NOT used."""
import sys
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_store import NAMESPACE
from offline_restart_readiness import (
    ChildRef, RestartStart, RestartSignal, OfflineRestartReadiness,
    SUPERVISOR, READY_PROBE, REAL_WAIT, MONOTONIC
)

OLD = ChildRef("worldserver", "demo-host", "host-boot1", "world-old",
               4321, "2026-10-25T00:00:00Z")
NEW = ChildRef("worldserver", "demo-host", "host-boot1", "world-new",
               4322, "2026-10-25T00:03:00Z")
INCIDENT = str(uuid.uuid5(NAMESPACE, "\x1f".join((
    OLD.host, OLD.boot, OLD.service, OLD.invocation, str(OLD.pid), OLD.start_utc
))))


def attempt(**modifiers):
    return replace(RestartStart(
        INCIDENT, "try1", OLD, NEW, "2026-10-25T00:02:00Z",
        5000, True, SUPERVISOR), **modifiers)


def event(kind="ready", elapsed=2000, **modifiers):
    expected = {"ready": READY_PROBE, "exited": REAL_WAIT, "timeout": MONOTONIC}[kind]
    return replace(RestartSignal(INCIDENT, "try1", NEW, kind, elapsed,
                                 True, expected), **modifiers)


class S4dReadinessTests(unittest.TestCase):
    def setUp(self):
        self.model = OfflineRestartReadiness()

    def begin(self, **overrides):
        return self.model.begin(attempt(**overrides))

    def obs(self, kind="ready", elapsed=2000, **overrides):
        return self.model.observe(event(kind, elapsed, **overrides))

    def test_child_launch_alone_never_means_restart_success(self):
        self.assertEqual(self.begin().status, "pending")
        self.assertEqual(self.model.counts(), (1, 0))

    def test_matching_ready_probe_completes_success_only_after_launch(self):
        self.begin()
        d = self.obs()
        self.assertEqual((d.status, d.outcome), ("completed", "succeeded"))

    def test_ready_for_unknown_attempt_refused(self):
        self.assertEqual(self.obs().status, "rejected")

    def test_gdb_transcript_cannot_make_restart_succeeded(self):
        self.begin()
        self.assertEqual(self.obs(source="gdb-transcript").status, "unverified")
        self.assertEqual(self.model.counts(), (1, 0))

    def test_process_exists_without_readiness_is_not_success(self):
        self.begin()
        self.assertEqual(self.obs(source="supervisor-fixture").status, "unverified")
        self.assertEqual(self.model.counts(), (1, 0))

    def test_wrong_child_or_recycled_pid_readiness_refused(self):
        self.begin()
        for ref in (OLD, replace(NEW, pid=4321),
                    replace(NEW, invocation="stale-old"),
                    replace(NEW, start_utc=OLD.start_utc)):
            with self.subTest(ref=ref):
                self.assertEqual(self.obs(child=ref).status, "rejected")
        self.assertEqual(self.model.counts(), (1, 0))

    def test_cross_service_probe_does_not_claim_world_restart(self):
        self.begin()
        foreign = replace(NEW, service="authserver")
        self.assertEqual(self.obs(child=foreign).status, "rejected")

    def test_ready_after_deadline_is_failed_not_success(self):
        self.begin()
        result = self.obs(elapsed=5001)
        self.assertEqual((result.status, result.outcome), ("completed", "failed"))

    def test_ready_exactly_at_deadline_is_candidate_success(self):
        self.begin()
        self.assertEqual(self.obs(elapsed=5000).outcome, "succeeded")

    def test_trusted_timeout_at_deadline_fails(self):
        self.begin()
        self.assertEqual(self.obs("timeout", 5000).outcome, "failed")

    def test_early_timeout_rejected_no_state_change(self):
        self.begin()
        self.assertEqual(self.obs("timeout", 4999).status, "rejected")
        self.assertEqual(self.obs().outcome, "succeeded")

    def test_child_exit_prior_to_readiness_fails(self):
        self.begin()
        self.assertEqual(self.obs("exited", 800).outcome, "failed")

    def test_stale_ready_after_child_exit_cannot_change_failed_outcome(self):
        self.begin()
        self.obs("exited", 700)
        d = self.obs(elapsed=2000)
        self.assertEqual((d.status, d.outcome), ("duplicate", "failed"))

    def test_stale_ready_after_timeout_cannot_reverse_failure(self):
        self.begin()
        self.obs("timeout", 5000)
        d = self.obs()
        self.assertEqual((d.status, d.outcome), ("duplicate", "failed"))

    def test_unverified_child_exit_or_timeout_does_not_mutate(self):
        self.begin()
        self.assertEqual(self.obs("exited", 500, verified=False).status, "unverified")
        self.assertEqual(self.obs("timeout", 6000, source="journal-text").status, "unverified")
        self.assertEqual(self.obs().outcome, "succeeded")

    def test_repeated_begin_is_idempotent_and_conflict_refused(self):
        self.assertEqual(self.begin().status, "pending")
        self.assertEqual(self.begin().status, "duplicate")
        self.assertEqual(self.begin(replacement=replace(NEW, pid=9999)).status, "rejected")

    def test_repeated_begin_after_completion_cannot_reopen(self):
        self.begin()
        self.obs()
        d = self.begin()
        self.assertEqual((d.status, d.outcome), ("duplicate", "succeeded"))

    def test_previous_child_equal_to_new_child_is_rejected(self):
        self.assertEqual(self.begin(replacement=OLD).status, "rejected")

    def test_replacement_before_reported_crash_death_is_rejected(self):
        self.assertEqual(self.begin(replacement=replace(
            NEW, start_utc="2026-10-25T00:01:00Z")).status, "rejected")

    def test_wrong_host_or_service_at_begin_refused(self):
        self.assertEqual(self.begin(replacement=replace(
            NEW, host="other-host")).status, "rejected")
        self.assertEqual(self.begin(replacement=replace(
            NEW, service="authserver")).status, "rejected")

    def test_untrusted_start_never_opens_attempt(self):
        for claim in ({"source": "gdb-transcript"},
                      {"verified_supervisor": False}):
            self.assertEqual(self.begin(**claim).status, "unverified")
        self.assertEqual(self.model.counts(), (0, 0))

    def test_malformed_identity_or_bounds_refused(self):
        for changed in ({"incident_id": "../secret"}, {"attempt": "../try"},
                        {"timeout_ms": 999}, {"timeout_ms": 600001},
                        {"verified_supervisor": 1},
                        {"death_utc": "2026-10-25T00:02:00+00:00"}):
            with self.subTest(changed=changed):
                self.assertEqual(self.begin(**changed).status, "rejected")

    def test_out_of_order_elapsed_does_not_rewrite_success(self):
        self.begin()
        # Wrong-kind/untrusted event doesn't advance the timeline.
        self.assertEqual(self.obs(elapsed=4000, verified=False).status, "unverified")
        self.assertEqual(self.obs(elapsed=3500).outcome, "succeeded")

    def test_invalid_probe_boolean_or_time_refused(self):
        self.begin()
        for changed in ({"verified": 1}, {"elapsed_ms": -1},
                        {"elapsed_ms": "now"}, {"child": None}):
            with self.subTest(changed=changed):
                self.assertEqual(self.obs(**changed).status, "rejected")
        self.assertEqual(self.model.counts(), (1, 0))

    def test_pending_capacity_is_bounded(self):
        t = OfflineRestartReadiness(max_pending=1)
        self.assertEqual(t.begin(attempt()).status, "pending")
        self.assertEqual(t.begin(attempt(attempt="try2")).status, "capacity")
        signal = event()
        self.assertEqual(t.observe(signal).outcome, "succeeded")
        self.assertEqual(t.begin(attempt(attempt="try2")).status, "pending")

    def test_finished_memory_bounded_over_200_attempts(self):
        persisted = {}
        t = OfflineRestartReadiness(
            max_finished=8, finished_lookup=lambda key: persisted.get(key))
        for i in range(200):
            key = "attempt-" + str(i)
            self.assertEqual(t.begin(attempt(attempt=key)).status, "pending")
            result = t.observe(event(attempt=key))
            self.assertEqual(result.outcome, "succeeded")
            persisted[(INCIDENT, key)] = result.outcome
        self.assertEqual(t.counts(), (0, 8))
        # Evicted old attempt still cannot be re-finalized.
        duplicate = t.begin(attempt(attempt="attempt-0"))
        self.assertEqual((duplicate.status, duplicate.outcome),
                         ("duplicate", "succeeded"))

    def test_evicted_history_without_durable_lookup_fails_closed(self):
        t = OfflineRestartReadiness(max_finished=1)
        t.begin(attempt(attempt="a0"))
        self.assertEqual(t.observe(event(attempt="a0")).outcome, "succeeded")
        t.begin(attempt(attempt="a1"))
        self.assertEqual(t.observe(event(attempt="a1")).outcome, "succeeded")
        self.assertEqual(t.begin(attempt(attempt="a0")).status, "unverified")
        self.assertEqual(t.begin(attempt(attempt="a2")).status, "unverified")
        self.assertEqual(t.counts(), (0, 1))

    def test_evicted_history_lookup_failure_fails_closed(self):
        def unavailable(key):
            raise OSError("synthetic storage unavailable")
        t = OfflineRestartReadiness(max_finished=1, finished_lookup=unavailable)
        for key in ("a0", "a1"):
            t.begin(attempt(attempt=key))
            t.observe(event(attempt=key))
        self.assertEqual(t.begin(attempt(attempt="a2")).status, "unverified")

    def test_lost_followup_expiry_reclaims_all_pending_slots(self):
        t = OfflineRestartReadiness(max_pending=64)
        for i in range(64):
            self.assertEqual(t.begin(attempt(attempt="lost-" + str(i))).status, "pending")
        self.assertEqual(t.begin(attempt(attempt="overflow")).status, "capacity")
        self.assertEqual(t.expire(4999), [])
        results = t.expire(5000)
        self.assertEqual(len(results), 64)
        self.assertTrue(all(result.outcome == "failed" for _, result in results))
        self.assertEqual(t.counts(), (0, 64))
        self.assertEqual(t.begin(attempt(attempt="fresh")).status, "pending")

    def test_expiry_uses_absolute_monotonic_start_time(self):
        self.assertEqual(self.begin(started_monotonic_ms=10_000).status, "pending")
        self.assertEqual(self.model.expire(14_999), [])
        done = self.model.expire(15_000)
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0][1].outcome, "failed")
        self.assertEqual(self.obs().outcome, "failed")

    def test_invalid_monotonic_expiry_and_start_are_rejected(self):
        for when in (-1, "now", True):
            with self.subTest(when=when), self.assertRaises(ValueError):
                self.model.expire(when)
            self.assertEqual(self.begin(started_monotonic_ms=when).status, "rejected")

    def test_canonical_but_unrelated_incident_uuid_rejected(self):
        forged = "11111111-1111-4111-8111-111111111111"
        self.assertNotEqual(forged, INCIDENT)
        self.assertEqual(self.begin(incident_id=forged).status, "rejected")

    def test_modified_crashed_child_identity_cannot_reuse_incident(self):
        self.assertEqual(self.begin(previous=replace(OLD, pid=9999)).status, "rejected")

    def test_wrong_signal_type_and_unknown_event_kind_refused(self):
        self.begin()
        self.assertEqual(self.model.observe({"fake": "ready"}).status, "rejected")
        self.assertEqual(self.model.observe(replace(
            event(), kind="wrapper-exit")).status, "rejected")

    def test_different_attempts_do_not_share_outcome(self):
        self.begin()
        self.begin(attempt="try2")
        self.assertEqual(self.obs("exited", 500).outcome, "failed")
        self.assertEqual(self.obs(attempt="try2").outcome, "succeeded")

    def test_no_auto_restart_or_sidecar_files_ever_written(self):
        self.assertFalse(hasattr(self.model, "publish_restart"))
        self.assertFalse(hasattr(self.model, "start_worldserver"))
        self.begin()
        self.assertEqual(self.model.counts(), (1, 0))


if __name__ == "__main__":
    unittest.main()
