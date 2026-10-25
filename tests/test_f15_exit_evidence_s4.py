"""F15 S4 offline exit-source admission tests (no real process or launcher)."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_exit_evidence import ExitEvidence, evaluate_exit_evidence


def fixture(**changed):
    return replace(ExitEvidence(
        source="direct-child-wait",
        service="worldserver",
        host="fixture-host",
        boot="fixture-boot",
        invocation="fixture-run",
        pid=4321,
        start_utc="2026-10-25T08:00:00Z",
        end_utc="2026-10-25T08:01:00Z",
        verified_actual_child=True,
        verified_unexpected=True,
        exit_code=1,
    ), **changed)


class ExitEvidenceContractTests(unittest.TestCase):
    def check(self, status, **changes):
        actual = evaluate_exit_evidence(fixture(**changes))
        self.assertEqual(actual.status, status, actual.reason)
        self.assertEqual(actual.candidate is not None, status == "candidate")
        return actual

    def test_worldserver_clean_zero_is_not_crash(self):
        self.check("ignored", exit_code=0)

    def test_worldserver_planned_code_two_is_not_crash(self):
        self.check("ignored", exit_code=2)

    def test_authserver_code_two_is_not_worldserver_restart(self):
        admitted = self.check("candidate", service="authserver", exit_code=2)
        self.assertEqual(admitted.candidate.metadata()["termination"], "exit 2")

    def test_worldserver_verified_code_one_is_candidate(self):
        self.check("candidate", exit_code=1)

    def test_actual_signal_segv_is_candidate(self):
        self.check("candidate", exit_code=None, signal="SIGSEGV")

    def test_actual_sigxfsz_is_not_lost_as_unsupported(self):
        self.check("candidate", exit_code=None, signal="SIGXFSZ")

    def test_planned_sigterm_is_not_crash(self):
        self.check("ignored", exit_code=None, signal="SIGTERM", planned_stop=True)

    def test_unplanned_verified_sigterm_can_be_incident(self):
        self.check("candidate", exit_code=None, signal="SIGTERM", planned_stop=False)

    def test_planned_sigkill_may_still_be_forced_failure(self):
        self.check("candidate", exit_code=None, signal="SIGKILL", planned_stop=True)

    def test_planned_stop_does_not_hide_verified_exit_one(self):
        self.check("candidate", exit_code=1, planned_stop=True)

    def test_planned_status_unknown_must_not_be_invented(self):
        self.check("ignored", exit_code=None, signal=None, planned_stop=True)

    def test_unexpected_verified_death_without_code_retains_unknown(self):
        result = self.check("candidate", exit_code=None, signal=None)
        self.assertIn("status unknown", result.candidate.metadata()["termination"])

    def test_wrapper_exit_139_is_not_actual_segv_proof(self):
        self.check("unverified", source="starter-wrapper", exit_code=139)

    def test_gdb_transcript_segv_is_not_authenticated_child_wait(self):
        self.check("unverified", source="gdb-transcript", signal="SIGSEGV", exit_code=None)

    def test_simple_restarter_zero_under_gdb_is_unverified(self):
        self.check("unverified", source="simple-restarter-text", exit_code=0)

    def test_journal_text_and_systemd_summary_cannot_admit(self):
        for source in ("journal-text", "systemd-summary", "unknown"):
            with self.subTest(source=source):
                self.check("unverified", source=source, signal="SIGSEGV", exit_code=None)

    def test_unverified_actual_child_identity_is_rejected(self):
        self.check("unverified", verified_actual_child=False)

    def test_not_proven_unexpected_is_not_candidate(self):
        self.check("ignored", verified_unexpected=False)

    def test_exit_139_is_still_exit_code_not_signal(self):
        incident = self.check("candidate", exit_code=139).candidate
        self.assertEqual(incident.metadata()["termination"], "exit 139")

    def test_conflicting_signal_and_exit_status_is_rejected(self):
        self.check("rejected", exit_code=139, signal="SIGSEGV")

    def test_missing_pid_or_start_is_rejected(self):
        self.check("rejected", pid=None)
        self.check("rejected", start_utc="")

    def test_invalid_service_and_injected_host_rejected(self):
        self.check("rejected", service="login-proxy")
        self.check("rejected", host="fixture\\nspoof")

    def test_malformed_booleans_rejected(self):
        self.check("rejected", verified_actual_child=1)
        self.check("rejected", verified_unexpected="yes")
        self.check("rejected", planned_stop=1)

    def test_reused_pid_with_new_process_start_changes_incident_identity(self):
        first = self.check("candidate").candidate
        second = self.check("candidate", start_utc="2026-10-25T08:00:01Z").candidate
        self.assertNotEqual(first.identity(), second.identity())

    def test_wrong_input_type_fails(self):
        with self.assertRaises(TypeError):
            evaluate_exit_evidence({"source": "direct-child-wait"})


if __name__ == "__main__":
    unittest.main()
