"""F15 S4b: synthetic error-burst policy regression cases, never a live log tail."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_error_bursts import InstanceExit, LogEvidence, OfflineBurstTracker


def evidence(seq=1, ms=1000, **changes):
    return replace(LogEvidence(
        service="worldserver",
        instance="bootA-world-4111",
        stream="stderr",
        level="ERROR",
        code="DB_TIMEOUT",
        seq=seq,
        uptime_ms=ms,
        source="verified-stream-fixture",
        verified_stream=True,
    ), **changes)


class BurstModelTests(unittest.TestCase):
    def setUp(self):
        self.model = OfflineBurstTracker()

    def push(self, seq=1, ms=1000, **changes):
        return self.model.observe(evidence(seq, ms, **changes))

    def test_three_errors_in_one_window_emit_one_alert(self):
        self.assertEqual(self.push(1, 1000).status, "ignored")
        self.assertEqual(self.push(2, 2000).status, "ignored")
        a = self.push(3, 3000)
        self.assertEqual(a.status, "alert")
        self.assertEqual(a.alert.level, "ERROR")
        self.assertEqual(a.alert.code, "DB_TIMEOUT")

    def test_sustained_flood_does_not_repeat_alert(self):
        statuses = [self.push(n, n * 1000).status for n in range(1, 100)]
        self.assertEqual(statuses.count("alert"), 1)

    def test_quiet_interval_rearms_category(self):
        for n in range(1, 4):
            self.push(n, n * 1000)
        self.assertEqual(self.push(4, 66001).status, "ignored")
        self.assertEqual(self.push(5, 67001).status, "ignored")
        self.assertEqual(self.push(6, 68001).status, "alert")

    def test_same_window_boundary_inclusive(self):
        self.assertEqual(self.push(1, 0).status, "ignored")
        self.assertEqual(self.push(2, 20_000).status, "ignored")
        self.assertEqual(self.push(3, 60_000).status, "alert")

    def test_event_just_past_window_does_not_count_ancient_one(self):
        self.push(1, 0)
        self.push(2, 20_000)
        self.assertEqual(self.push(3, 60_001).status, "ignored")

    def test_less_than_threshold_never_emits(self):
        self.push(1, 100)
        self.assertIsNone(self.push(2, 200).alert)

    def test_warning_and_error_counters_isolated(self):
        self.push(1, 100, level="WARN")
        self.push(2, 200, level="WARN")
        self.assertEqual(self.push(3, 300, level="WARN").status, "alert")
        self.push(4, 400, level="ERROR")
        self.push(5, 500, level="ERROR")
        self.assertEqual(self.push(6, 600, level="ERROR").status, "alert")
        self.assertEqual(self.model.counts(), (1, 2))

    def test_different_codes_isolated(self):
        for i in range(1, 4):
            self.push(i, i * 100, code="SPELL")
        self.assertEqual(self.push(4, 400, code="LUA").status, "ignored")
        self.assertEqual(self.push(5, 500, code="LUA").status, "ignored")
        self.assertEqual(self.push(6, 600, code="LUA").status, "alert")

    def test_authserver_and_worldserver_are_separate(self):
        for i in range(1, 4):
            self.push(i, 100 * i)
        for i in range(1, 4):
            result = self.push(i, 100 * i, service="authserver")
        self.assertEqual(result.status, "alert")
        self.assertEqual(result.alert.service, "authserver")
        self.assertEqual(self.model.counts(), (2, 2))

    def test_new_instance_has_independent_sequence_and_burst(self):
        self.push(1, 100)
        self.push(2, 200)
        self.push(3, 300)
        for i in range(1, 4):
            result = self.push(i, 100 * i, instance="bootB-world-4111")
        self.assertEqual(result.status, "alert")
        self.assertEqual(self.model.counts(), (2, 2))

    def test_different_streams_are_isolated(self):
        for i in range(1, 4):
            self.push(i, 100 * i, stream="stderr")
        for i in range(1, 4):
            result = self.push(i, 100 * i, stream="stdout")
        self.assertEqual(result.status, "alert")

    def test_duplicate_sequence_cannot_increment_counter(self):
        self.push(1, 100)
        self.assertEqual(self.push(1, 100).status, "rejected")
        self.assertEqual(self.push(2, 200).status, "ignored")
        self.assertEqual(self.push(3, 300).status, "alert")

    def test_replayed_old_event_does_not_rearm_or_alert(self):
        for i in range(1, 4):
            self.push(i, 100 * i)
        self.assertEqual(self.push(2, 100).status, "rejected")
        self.assertEqual(self.push(4, 400).status, "ignored")

    def test_backward_uptime_is_rejected_without_advancing_seq(self):
        self.push(1, 500)
        self.assertEqual(self.push(2, 499).status, "rejected")
        self.assertEqual(self.push(2, 501).status, "ignored")
        self.assertEqual(self.push(3, 502).status, "alert")

    def test_unverified_fixture_cannot_alert(self):
        for i in range(1, 20):
            self.assertEqual(self.push(i, i * 10, verified_stream=False).status, "unverified")
        self.assertEqual(self.model.counts(), (0, 0))

    def test_source_text_cannot_authenticate_stream(self):
        for name in ("stderr-message", "gdb-transcript", "systemd-summary",
                     "journal-text", "worldserver-self-report", "unknown"):
            with self.subTest(name=name):
                self.assertEqual(self.push(1, 100, source=name).status, "unverified")
        self.assertEqual(self.model.counts(), (0, 0))

    def test_unverified_does_not_poison_later_verified_sequence(self):
        self.push(1, 100, verified_stream=False)
        self.assertEqual(self.push(1, 100).status, "ignored")

    def test_malformed_instance_rejected(self):
        self.assertEqual(self.push(1, 100, instance="../secret").status, "rejected")
        self.assertEqual(self.push(1, 100, instance="").status, "rejected")
        self.assertEqual(self.model.counts(), (0, 0))

    def test_malformed_code_and_level_rejected(self):
        self.assertEqual(self.push(1, 100, code="error\nprivate-token").status, "rejected")
        self.assertEqual(self.push(1, 100, level="FATAL").status, "rejected")
        self.assertEqual(self.push(1, 100, code="x" * 97).status, "rejected")

    def test_invalid_stream_and_service_rejected(self):
        self.assertEqual(self.push(1, 100, stream="/var/log").status, "rejected")
        self.assertEqual(self.push(1, 100, service="custom-app").status, "rejected")

    def test_unhashable_malformed_evidence_rejected_safely(self):
        self.assertEqual(self.push(1, 100, service=[]).status, "rejected")
        self.assertEqual(self.push(1, 100, stream=[]).status, "rejected")
        self.assertEqual(self.push(1, 100, level=[]).status, "rejected")
        self.assertEqual(self.model.counts(), (0, 0))

    def test_bad_sequence_timestamp_and_boolean_rejected(self):
        self.assertEqual(self.push(-1, 0).status, "rejected")
        self.assertEqual(self.push(1, -1).status, "rejected")
        self.assertEqual(self.push(1.2, 1).status, "rejected")
        self.assertEqual(self.push(1, 1, verified_stream=1).status, "rejected")

    def test_no_raw_log_text_accepted_or_in_report(self):
        self.assertNotIn("message", LogEvidence.__dataclass_fields__)
        self.assertNotIn("raw", LogEvidence.__dataclass_fields__)
        for i in range(1, 4):
            out = self.push(i, i * 100)
        self.assertNotIn("message", out.alert.__dict__)
        self.assertNotIn("text", out.alert.__dict__)

    def test_bounded_categories_refuse_new_group_without_state_change(self):
        t = OfflineBurstTracker(max_groups=1)
        self.assertEqual(t.observe(evidence(1, 100, code="A")).status, "ignored")
        self.assertEqual(t.observe(evidence(2, 200, code="B")).status, "capacity")
        self.assertEqual(t.counts(), (1, 1))
        self.assertEqual(t.observe(evidence(2, 200, code="A")).status, "ignored")
        self.assertEqual(t.observe(evidence(3, 300, code="A")).status, "alert")

    def test_bounded_streams_refuse_new_stream(self):
        t = OfflineBurstTracker(max_streams=1)
        t.observe(evidence(1, 100))
        out = t.observe(evidence(1, 100, stream="stdout"))
        self.assertEqual(out.status, "capacity")
        self.assertEqual(t.counts(), (1, 1))

    def test_threshold_and_window_can_be_configured(self):
        t = OfflineBurstTracker(threshold=2, window_ms=1000)
        self.assertEqual(t.observe(evidence(1, 100)).status, "ignored")
        self.assertEqual(t.observe(evidence(2, 1100)).status, "alert")


    def test_slow_trickle_rearms_before_subsequent_real_burst(self):
        # Peer-review negative: an isolated error every 50 seconds never
        # empties a 60-second window; it MUST NOT permanently suppress alerts.
        initial = [self.push(i, (i - 1) * 1000).status for i in range(1, 4)]
        self.assertEqual(initial, ["ignored", "ignored", "alert"])
        low_rate = [self.push(i + 3, i * 50_000).status
                    for i in range(1, 201)]
        self.assertNotIn("alert", low_rate)
        sudden = [self.push(i + 203, 10_000_000 + i * 100).status
                  for i in range(1, 4)]
        self.assertIn("alert", sudden)

    def test_authenticated_fixture_exit_reclaims_memory_over_200_restarts(self):
        tracker = OfflineBurstTracker(max_streams=3, max_groups=3)
        for i in range(200):
            instance = "boot-" + str(i)
            for stream in ("stdout", "stderr", "world-log"):
                decision = tracker.observe(
                    evidence(1, 100, instance=instance, stream=stream))
                self.assertEqual(decision.status, "ignored")
            cleanup = tracker.finish_instance(
                InstanceExit("worldserver", instance,
                             "verified-instance-exit-fixture", True))
            self.assertEqual(cleanup.status, "released")
            self.assertEqual((cleanup.streams_released,
                              cleanup.categories_released), (3, 3))
            self.assertEqual(tracker.counts(), (0, 0))
        self.assertEqual(tracker.observe(
            evidence(1, 100, instance="boot-new")).status, "ignored")

    def test_unverified_or_malformed_exit_cannot_free_capacity(self):
        tracker = OfflineBurstTracker(max_streams=1, max_groups=1)
        tracker.observe(evidence(1, 100, instance="A"))
        for fixture in (InstanceExit("worldserver", "A"),
                        InstanceExit("worldserver", "A",
                                     "verified-instance-exit-fixture", False),
                        InstanceExit("worldserver", "../A",
                                     "verified-instance-exit-fixture", True),
                        InstanceExit("worldserver", "A",
                                     "verified-instance-exit-fixture", 1)):
            self.assertNotEqual(tracker.finish_instance(fixture).status, "released")
        self.assertEqual(tracker.counts(), (1, 1))
        self.assertEqual(tracker.observe(
            evidence(1, 100, instance="B")).status, "capacity")
        self.assertEqual(tracker.finish_instance(
            InstanceExit("worldserver", "A",
                         "verified-instance-exit-fixture", True)).status, "released")
        self.assertEqual(tracker.observe(
            evidence(1, 100, instance="B")).status, "ignored")

    def test_retired_instance_replay_rejected_and_duplicate_cleanup_inert(self):
        tracker = OfflineBurstTracker()
        tracker.observe(evidence(1, 100, instance="A"))
        ended = InstanceExit("worldserver", "A",
                             "verified-instance-exit-fixture", True)
        self.assertEqual(tracker.finish_instance(ended).status, "released")
        self.assertEqual(tracker.finish_instance(ended).status, "duplicate")
        self.assertEqual(tracker.observe(
            evidence(2, 200, instance="A")).status, "rejected")
        self.assertEqual(tracker.counts(), (0, 0))

    def test_instance_cleanup_never_frees_another_service(self):
        tracker = OfflineBurstTracker()
        tracker.observe(evidence(1, 100, instance="same", service="worldserver"))
        tracker.observe(evidence(1, 100, instance="same", service="authserver"))
        ended = tracker.finish_instance(
            InstanceExit("worldserver", "same",
                         "verified-instance-exit-fixture", True))
        self.assertEqual((ended.streams_released, ended.categories_released), (1, 1))
        self.assertEqual(tracker.counts(), (1, 1))
        self.assertEqual(tracker.observe(
            evidence(2, 200, instance="same", service="authserver")).status,
            "ignored")

    def test_invalid_config_is_rejected(self):
        for kwargs in ({"threshold": 1}, {"window_ms": 0}, {"max_groups": 0},
                       {"max_streams": 0}, {"threshold": True}, {"window_ms": "1000"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                OfflineBurstTracker(**kwargs)

    def test_reject_unexpected_input_type(self):
        self.assertEqual(self.model.observe({"log": "spoof"}).status, "rejected")

    def test_no_incident_identity_or_restart_output(self):
        for i in range(1, 4):
            out = self.push(i, i * 100)
        self.assertNotIn("incident_id", out.alert.__dict__)
        self.assertNotIn("restart", out.alert.__dict__)
        self.assertEqual(self.model.counts(), (1, 1))


if __name__ == "__main__":
    unittest.main()
