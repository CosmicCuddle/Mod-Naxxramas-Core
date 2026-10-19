"""Offline tests for exact-scope and owner-approval release blocking."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/check_naxx_release_feature_gates.py"
MANIFEST = ROOT / "docs/release-gates/1.0.6.8.5.json"
spec = importlib.util.spec_from_file_location("release_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseFeatureGates(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(MANIFEST.read_text(encoding="utf-8"))
        gate.validate(self.d)

    def test_actual_manifest_is_release_blocked_by_default(self):
        reasons = gate.release_blockers(self.d)
        self.assertTrue(reasons)
        self.assertTrue(any("No explicitly selected" in reason for reason in reasons))
        self.assertFalse(self.d["release_approved"])
        self.assertTrue(all(not r["include_in_release"] for r in self.d["components"]))

    def test_all_ten_named_project_tracks_are_present(self):
        self.assertEqual({r["id"] for r in self.d["components"]}, gate.REQUIRED_COMPONENTS)
        self.assertEqual({r["id"] for r in self.d["components"] if r["in_combined_candidate"]},
                         gate.COMBINED_THREE)

    def test_green_ci_cannot_authorize_unapproved_feature(self):
        row = next(x for x in self.d["components"] if x["id"] == "hunter_ammunition")
        row["include_in_release"] = True
        self.assertTrue(any("owner feature-inclusion" in reason
                            for reason in gate.release_blockers(self.d)))
        self.assertTrue(any("no independently accepted in-game" in reason
                            for reason in gate.release_blockers(self.d)))

    def test_pet_audit_cannot_be_misreported_as_autocast_fix(self):
        a = next(x for x in self.d["components"] if x["id"] == "hunter_pet_autocast_observer")
        b = next(x for x in self.d["components"] if x["id"] == "hunter_pet_autocast_fix")
        self.assertTrue(a["full_build_verified"])
        self.assertFalse(b["full_build_verified"])
        self.assertEqual(b["source_state"], "not_implemented")

    def test_fail_if_workstream_missing_or_repeated(self):
        self.d["components"].pop()
        with self.assertRaises(ValueError):
            gate.validate(self.d)
        self.d["components"].append(copy.deepcopy(self.d["components"][0]))
        with self.assertRaises(ValueError):
            gate.validate(self.d)

    def test_fail_if_combined_features_mislabeled(self):
        row = next(x for x in self.d["components"] if x["id"] == "quest_loot_turn_guard")
        row["in_combined_candidate"] = True
        with self.assertRaises(ValueError):
            gate.validate(self.d)

    def test_live_acceptance_requires_restorable_backups(self):
        row = self.d["components"][0]
        row["live_accepted"] = True
        with self.assertRaises(ValueError):
            gate.validate(self.d)

    def test_cannot_claim_built_unimplemented_function(self):
        row = next(x for x in self.d["components"] if x["id"] == "golemagg_movement_fix")
        row["full_build_verified"] = True
        with self.assertRaises(ValueError):
            gate.validate(self.d)

    def test_unimplemented_function_cannot_claim_release_or_advanced_stage(self):
        row = next(x for x in self.d["components"] if x["id"] == "golemagg_movement_fix")
        row["stage"] = "S4"
        with self.assertRaisesRegex(ValueError, "unimplemented"):
            gate.validate(self.d)

    def test_draft_cannot_claim_released_stage(self):
        row = next(x for x in self.d["components"] if x["id"] == "hunter_ammunition")
        row.update(stage="S7", backup_restore_verified=True, live_accepted=True)
        with self.assertRaisesRegex(ValueError, "unmerged draft"):
            gate.validate(self.d)

    def test_s4_requires_full_worldserver_evidence(self):
        row = next(x for x in self.d["components"] if x["id"] == "ep_tower_lock")
        row["stage"] = "S4"
        with self.assertRaisesRegex(ValueError, "S4\\+"):
            gate.validate(self.d)

    def test_s5_requires_restorable_backup_evidence(self):
        row = next(x for x in self.d["components"] if x["id"] == "hunter_ammunition")
        # Isolate S5 missing backup proof; S4 proof is synthetic in this fixture.
        row.update(stage="S5", full_build_verified=True)
        with self.assertRaisesRegex(ValueError, "S5\\+"):
            gate.validate(self.d)

    def test_s6_requires_accepted_gameplay_evidence(self):
        row = next(x for x in self.d["components"] if x["id"] == "hunter_ammunition")
        # Isolate S6 missing gameplay proof; previous stages are synthetic.
        row.update(stage="S6", full_build_verified=True, backup_restore_verified=True)
        with self.assertRaisesRegex(ValueError, "S6\\+"):
            gate.validate(self.d)

    def test_s4_cannot_already_claim_accepted_gameplay(self):
        row = next(x for x in self.d["components"] if x["id"] == "hunter_ammunition")
        row.update(backup_restore_verified=True, live_accepted=True)
        with self.assertRaisesRegex(ValueError, "classified at S6"):
            gate.validate(self.d)

    def test_early_stage_cannot_claim_full_build(self):
        row = next(x for x in self.d["components"] if x["id"] == "golemagg_movement_fix")
        row["full_build_verified"] = True
        with self.assertRaises(ValueError):
            gate.validate(self.d)

    def test_approved_fixture_can_pass_only_all_independent_gates(self):
        row = next(x for x in self.d["components"] if x["id"] == "quest_loot_turn_guard")
        row.update(stage="S6", source_state="merged_main",
                   draft_pr=None, exact_head=None,
                   full_build_verified=True, live_accepted=True,
                   backup_restore_verified=True, owner_approved=True,
                   default_behavior="off", include_in_release=True)
        self.d.update(release_approved=True, installed_shas_verified=True,
                      release_backup_restore_verified=True)
        gate.validate(self.d)
        self.assertEqual(gate.release_blockers(self.d), [])

    def test_combined_requires_separate_overall_candidate_approval(self):
        row = next(x for x in self.d["components"] if x["id"] == "hunter_ammunition")
        row.update(stage="S6", source_state="merged_main",
                   draft_pr=None, exact_head=None,
                   full_build_verified=True, live_accepted=True,
                   backup_restore_verified=True, owner_approved=True,
                   include_in_release=True)
        self.d.update(release_approved=True, installed_shas_verified=True,
                      release_backup_restore_verified=True)
        self.assertIn("combined candidate PR #33 has not been approved",
                      "\n".join(gate.release_blockers(self.d)))
        self.d["combined_candidate"]["owner_approved"] = True
        self.assertEqual(gate.release_blockers(self.d), [])

    def test_report_does_not_make_a_status_mutation(self):
        before = copy.deepcopy(self.d)
        message = gate.report(self.d)
        self.assertIn("RELEASE GATE: BLOCKED", message)
        self.assertIn("Golemagg", message)
        self.assertEqual(before, self.d)


if __name__ == "__main__":
    unittest.main()
