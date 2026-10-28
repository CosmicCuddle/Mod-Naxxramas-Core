"""A04 P29 offline triage negative controls: no actual owner evidence included."""
import importlib.util
import itertools
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/a04/incident_triage.py"
spec = importlib.util.spec_from_file_location("a04_incident_triage", SCRIPT)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

Incident = module.Incident
assess = module.assess


class SafetyAndSeparation(unittest.TestCase):
    def test_all_unknown_h1_does_not_claim_invalid_award(self):
        r = assess(Incident("H1"))
        self.assertIn("H1_AWARD_NOT_VERIFIED", r.hypothesis_codes)
        self.assertIn("verified friend inventory/mail award (not merely click/window)",
                      r.needed_categories)
        self.assertFalse(r.accepted)
        self.assertFalse(r.bug_proven)

    def test_all_unknown_h2_does_not_claim_source_trigger(self):
        r = assess(Incident("H2"))
        self.assertEqual(r.hypothesis_codes, ("H2_SOURCE_PATH_UNDETERMINED",))
        self.assertFalse(r.accepted)

    def test_friend_click_without_award_is_not_a_positive_receipt(self):
        for award in ("no", "unknown"):
            with self.subTest(award=award):
                r = assess(Incident("H1", award_to_friend=award,
                                    friend_eligible="no"))
                self.assertIn("H1_AWARD_NOT_VERIFIED", r.hypothesis_codes)
                self.assertNotIn(
                    "H1_UNEXPECTED_AWARD_REQUIRES_PRIVATE_NATIVE_AUDIT",
                    r.hypothesis_codes)

    def test_genuine_ineligible_award_flags_private_audit_not_proven_bug(self):
        r = assess(Incident("H1", award_to_friend="yes",
                            friend_eligible="no", bucket="quest"))
        self.assertIn("H1_UNEXPECTED_AWARD_REQUIRES_PRIVATE_NATIVE_AUDIT",
                      r.hypothesis_codes)
        self.assertFalse(r.bug_proven)

    def test_ordinary_loot_without_quest_requirement_is_not_wrong_award_proof(self):
        # Ordinary loot can be related to someone's quest yet legitimately
        # acquired by another group member lacking that quest.
        r = assess(Incident("H1", source="creature", bucket="ordinary",
                            method="group", turn="friend",
                            award_to_friend="yes", friend_eligible="no",
                            shared_one_copy="yes", hidden_ordinary_guard="off"))
        self.assertIn("H1_ORDINARY_ENTITLEMENT_UNDETERMINED", r.hypothesis_codes)
        self.assertIn("H1_ORDINARY_ITEM_IS_NOT_AUTOMATICALLY_PERSONAL",
                      r.hypothesis_codes)
        self.assertNotIn("H1_UNEXPECTED_AWARD_REQUIRES_PRIVATE_NATIVE_AUDIT",
                         r.hypothesis_codes)
        self.assertIn("friend's native ordinary-loot entitlement, not quest status alone",
                      r.needed_categories)
        self.assertFalse(r.bug_proven)
        self.assertFalse(r.can_change_shared_loot)

    def test_unknown_bucket_ineligible_friend_requires_bucket_before_judgment(self):
        r = assess(Incident("H1", award_to_friend="yes",
                            friend_eligible="no", bucket="unknown"))
        self.assertIn("H1_BUCKET_REQUIRED_BEFORE_ELIGIBILITY_JUDGMENT",
                      r.hypothesis_codes)
        self.assertNotIn("H1_UNEXPECTED_AWARD_REQUIRES_PRIVATE_NATIVE_AUDIT",
                         r.hypothesis_codes)
        self.assertFalse(r.bug_proven)

    def test_quest_bucket_ineligible_friend_still_flags_private_audit(self):
        # Never call a quest-bucket award 'proved bug': conditions and the
        # actual server-side receipt path still require private evidence.
        r = assess(Incident("H1", award_to_friend="yes", friend_eligible="no",
                            bucket="quest", legacy_quest_guard="off"))
        self.assertIn("H1_UNEXPECTED_AWARD_REQUIRES_PRIVATE_NATIVE_AUDIT",
                      r.hypothesis_codes)
        self.assertFalse(r.bug_proven)
        self.assertFalse(r.can_enable_a04)

    def test_eligible_friend_shared_award_is_not_classified_as_bug(self):
        for turn in ("friend", "reporter", "released", "unknown"):
            with self.subTest(turn=turn):
                r = assess(Incident("H1", award_to_friend="yes",
                                    friend_eligible="yes", shared_one_copy="yes",
                                    bucket="quest", turn=turn))
                self.assertIn("H1_POSSIBLE_LEGITIMATE_SHARED_AWARD",
                              r.hypothesis_codes)
                self.assertFalse(r.bug_proven)

    def test_not_every_possible_shared_award_is_turn_proven(self):
        r = assess(Incident("H1", award_to_friend="yes",
                            friend_eligible="yes", shared_one_copy="yes",
                            turn="reporter"))
        self.assertNotIn("H1_TURN_RELEASE_STOCK_CONSISTENT_CANDIDATE",
                         r.hypothesis_codes)

    def test_ordinary_quest_related_item_not_assumed_personal(self):
        r = assess(Incident("H1", bucket="ordinary"))
        self.assertIn("H1_ORDINARY_ITEM_IS_NOT_AUTOMATICALLY_PERSONAL",
                      r.hypothesis_codes)

    def test_h2_cached_sparkle_locked_is_possible_stock_not_bug(self):
        r = assess(Incident("H2", sparkle="yes", slot="locked", denied="yes"))
        self.assertIn("H2_CACHED_SPARKLE_LOCKED_ROW_STOCK_POSSIBLE",
                      r.hypothesis_codes)
        self.assertFalse(r.bug_proven)

    def test_exact_source_mismatch_requires_all_four_gates(self):
        r = assess(Incident("H2", bucket="quest", shared_one_copy="yes",
                            objective="short", inventory="met"))
        self.assertIn("H2_SHARED_WINDOW_COUNTER_DRIFT_SOURCE_CANDIDATE",
                      r.hypothesis_codes)
        self.assertTrue(any("BEFORE first loot window" in q
                            for q in r.needed_categories))
        self.assertFalse(r.can_enable_a04)

    def test_normal_counter_in_step_cannot_trip_mismatch(self):
        for objective, inventory in (("met", "met"), ("short", "short"),
                                     ("met", "short"), ("unknown", "met"),
                                     ("short", "unknown")):
            with self.subTest(objective=objective, inventory=inventory):
                r = assess(Incident("H2", bucket="quest",
                                    shared_one_copy="yes",
                                    objective=objective, inventory=inventory))
                self.assertNotIn(
                    "H2_SHARED_WINDOW_COUNTER_DRIFT_SOURCE_CANDIDATE",
                    r.hypothesis_codes)

    def test_nonshared_or_ordinary_cannot_trip_specific_mismatch(self):
        for bucket, shared in (("ordinary", "yes"), ("quest", "no"),
                               ("quest", "unknown"), ("unknown", "yes")):
            with self.subTest(bucket=bucket, shared=shared):
                r = assess(Incident("H2", bucket=bucket,
                                    shared_one_copy=shared,
                                    objective="short", inventory="met"))
                self.assertNotIn(
                    "H2_SHARED_WINDOW_COUNTER_DRIFT_SOURCE_CANDIDATE",
                    r.hypothesis_codes)

    def test_legacy_quest_guard_does_not_masquerade_as_ordinary_guard(self):
        r = assess(Incident("H2", bucket="quest", legacy_quest_guard="on",
                            hidden_ordinary_guard="off"))
        self.assertIn("H2_LEGACY_QUEST_TURN_GUARD_CANDIDATE",
                      r.hypothesis_codes)
        self.assertNotIn("H2_HIDDEN_ORDINARY_SLOT_GUARD_CANDIDATE",
                         r.hypothesis_codes)
        self.assertFalse(r.can_enable_a04)

    def test_hidden_ordinary_guard_does_not_masquerade_as_quest_guard(self):
        r = assess(Incident("H2", bucket="ordinary",
                            legacy_quest_guard="off",
                            hidden_ordinary_guard="on"))
        self.assertIn("H2_HIDDEN_ORDINARY_SLOT_GUARD_CANDIDATE",
                      r.hypothesis_codes)
        self.assertNotIn("H2_LEGACY_QUEST_TURN_GUARD_CANDIDATE",
                         r.hypothesis_codes)
        self.assertFalse(r.can_enable_a04)

    def test_guard_for_other_bucket_cannot_make_a_false_h2_cause(self):
        for bucket, quest_flag, ordinary_flag in (
            ("quest", "off", "on"),
            ("ordinary", "on", "off"),
        ):
            with self.subTest(bucket=bucket):
                r = assess(Incident("H2", bucket=bucket,
                                    legacy_quest_guard=quest_flag,
                                    hidden_ordinary_guard=ordinary_flag))
                self.assertNotIn("H2_LEGACY_QUEST_TURN_GUARD_CANDIDATE",
                                 r.hypothesis_codes)
                self.assertNotIn("H2_HIDDEN_ORDINARY_SLOT_GUARD_CANDIDATE",
                                 r.hypothesis_codes)

    def test_schema_refuses_arbitrary_id_password_or_sql_as_fields(self):
        for keyword in ("item_id", "character_guid", "quest_id", "host",
                        "password", "raw_log", "sql", "npc_entry"):
            with self.subTest(keyword=keyword):
                with self.assertRaises(TypeError):
                    Incident("H2", **{keyword: "12345"})

    def test_schema_refuses_any_unknown_values_except_literal_unknown(self):
        for value in (1, False, "1234", "manual", "accepted", "enabled", "",
                      "PASS", "fix", "H1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Incident("H2", objective=value)

    def test_bad_case_name_cannot_fall_through_to_h2(self):
        with self.assertRaises(ValueError):
            Incident("OTHER")

    def test_assessment_rejects_unapproved_success_claims(self):
        for kw in ({"accepted": True}, {"bug_proven": True},
                   {"can_enable_a04": True}, {"can_change_shared_loot": True},
                   {"write_policy": "ON"}):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    module.Assessment("H1", (), (), **kw)

    def test_all_generic_synthetic_pairings_remain_no_write(self):
        for kind, eligible, award, objective, inventory, shared in itertools.product(
            ("H1", "H2"), ("yes", "no", "unknown"),
            ("yes", "no", "unknown"), ("short", "met", "unknown"),
            ("short", "met", "unknown"), ("yes", "no", "unknown"),
        ):
            r = assess(Incident(kind=kind, friend_eligible=eligible,
                                award_to_friend=award, objective=objective,
                                inventory=inventory, shared_one_copy=shared))
            self.assertEqual(r.write_policy, "NO_WRITE")
            self.assertFalse(r.accepted)
            self.assertFalse(r.bug_proven)
            self.assertFalse(r.can_enable_a04)
            self.assertFalse(r.can_change_shared_loot)

    def test_printable_blank_worksheet_contains_no_real_identifiers(self):
        text = module.blank_checklist()
        self.assertIn("H1", text)
        self.assertIn("H2", text)
        self.assertIn("PUBLIC", text)
        self.assertNotIn("password=", text)
        self.assertNotIn("127.0.0.1", text)

    def test_import_is_pure_and_does_not_contain_io_call_sinks(self):
        # Review tripwire, not a formal security sandbox.
        src = SCRIPT.read_text(encoding="utf-8")
        for token in ("requests", "urllib", "socket", "subprocess",
                      "open(", "write(", "Path(", "logging.", "print(",
                      "input(", "exec(", "eval("):
            with self.subTest(token=token):
                self.assertNotIn(token, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
