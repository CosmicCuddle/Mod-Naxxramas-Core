"""Both-specialization out-of-era talent inspection remains read-only.

Source/static and synthetic checks only, NOT a C++ build or gameplay proof.
"""
from pathlib import Path
import re
import unittest

CPP = (Path(__file__).resolve().parents[1] / "src/Systems/BotTalentImport.cpp").read_text(encoding="utf-8")


def section(start, stop):
    begin = CPP.index(start)
    end = CPP.index(stop, begin + len(start))
    return CPP[begin:end]


GETTER = section(
    "    std::vector<OutOfEraTalent> GetOutOfEraTalents(",
    "    // Read-only volatile observation",
)
REPORT = section("    void PrintAltBotRepairPreview(", "    void PrintPreview(")
HANDLER = section("    static bool HandleRepairPreview(", "    static bool HandleApply(")
READINESS = section("    bool CheckApplyReadiness(", "    bool ApplyValidated(")


def synthetic_spec_invalid_ranks(talents_by_spec, allowed_ids):
    """Illustrative per-spec input; no specific live DBC data asserted."""
    return [
        sorted(set(talents) - set(allowed_ids))
        for talents in talents_by_spec
    ]


class InactiveSpecializationSafetyTests(unittest.TestCase):
    def test_getter_accepts_explicit_spec_number(self):
        self.assertIn(
            "Player const* bot, Era const& era, uint8 spec)", GETTER
        )
        self.assertIn(
            "bot->HasTalent(talent->RankID[j], spec)", GETTER
        )

    def test_spec_index_bounded_by_actual_bot_specs(self):
        self.assertIn("spec >= bot->GetSpecsCount()", GETTER)
        self.assertIn("spec >= MAX_TALENT_SPECS", GETTER)

    def test_active_spec_compatibility_wrapper_retained(self):
        self.assertIn("GetOutOfEraTalents(bot, era, bot->GetActiveSpec())", GETTER)
        self.assertIn("GetOutOfEraTalents(bot, proposed.Progression);", REPORT)

    def test_uses_exact_dbc_era_policy_for_both_specs(self):
        self.assertIn("AvailableInEra(", GETTER)
        self.assertIn("sTalentStore.LookupEntry(", GETTER)
        self.assertIn("TalentTabEntry const*", GETTER)
        self.assertIn("GetOutOfEraTalents(bot, proposed.Progression, spec)", REPORT)

    def test_other_specs_only_and_no_spec_switch(self):
        self.assertIn("if (spec == bot->GetActiveSpec())", REPORT)
        self.assertIn("spec < bot->GetSpecsCount()", REPORT)
        self.assertIn("spec < MAX_TALENT_SPECS", REPORT)
        self.assertIn("No specialization was switched", REPORT)

    def test_inactive_offera_records_show_id_rank_tree_and_position(self):
        self.assertIn("NT1 ALT INACTIVE SPEC {}", REPORT)
        self.assertIn("Inactive spec {} invalid Talent.dbc ID {}", REPORT)
        for field in ("t.Id", "t.Rank", "t.Tree", "t.Row", "t.Col"):
            self.assertIn(field, REPORT)

    def test_chat_output_bounded_for_damaged_offspec(self):
        self.assertIn("MAX_INACTIVE_DIAGNOSTIC_ENTRIES = 6", REPORT)
        self.assertIn("inactiveIllegal.size() - MAX_INACTIVE_DIAGNOSTIC_ENTRIES", REPORT)
        self.assertIn("further invalid talents omitted", REPORT)

    def test_no_mutation_in_era_getter_or_diagnostic_printer(self):
        bad_calls = re.compile(
            r"\b(?:resetTalents|ActivateSpec|SetActiveSpec|"
            r"LearnTalent|LearnValidated|RemovePet|SaveToDB|"
            r"DirectExecute|SetGlyph|AutoUnequipOffhandIfNeed|"
            r"RemoveItem|StoreItem)\s*\("
        )
        for code in (GETTER, REPORT):
            no_comments = re.sub(r"//[^\n]*", "", code)
            no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', no_comments)
            self.assertIsNone(bad_calls.search(no_strings))

    def test_altbot_owner_and_human_allowlist_enforced_before_new_report(self):
        self.assertIn("ValidateRequest(handler, args, bot, build)", HANDLER)
        self.assertIn("CanApplyToAltBot(issuer, error)", HANDLER)
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", HANDLER)
        self.assertLess(
            HANDLER.index("CanApplyToAltBot(issuer, error)"),
            HANDLER.index("PrintAltBotRepairPreview(handler, issuer, bot, build)"),
        )

    def test_no_new_destructive_command_or_relaxed_offhand(self):
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", READINESS)
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertNotIn('{"repairapply"', CPP)

    def test_synthetic_active_legal_inactive_invalid(self):
        invalid = synthetic_spec_invalid_ranks(
            [[100, 101], [101, 1768, 1202]], [100, 101]
        )
        self.assertEqual(invalid[0], [])
        self.assertEqual(invalid[1], [1202, 1768])

    def test_synthetic_no_inactive_talents(self):
        self.assertEqual(synthetic_spec_invalid_ranks([[101], []], [101]), [[], []])

    def test_synthetic_old_and_new_specs_remain_distinct(self):
        invalid = synthetic_spec_invalid_ranks(
            [[1202], [1768]], [101]
        )
        self.assertEqual(invalid, [[1202], [1768]])


if __name__ == "__main__":
    unittest.main()
