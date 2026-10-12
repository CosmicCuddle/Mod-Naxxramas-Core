"""Alt Bot talent-map anomaly report: source and synthetic contracts ONLY.

This cannot prove installed AzerothCore compatibility, actual character
database integrity, or safety of talent reset/spec switching.
"""
from collections import Counter
from pathlib import Path
import re
import unittest

CPP = (Path(__file__).resolve().parents[1] /
       "src/Systems/BotTalentImport.cpp").read_text(encoding="utf-8")


def section(start, end):
    i = CPP.index(start)
    j = CPP.index(end, i + len(start))
    return CPP[i:j]


AUDIT = section("    void PrintAltBotTalentMapIntegrity(",
                "    // Read-only volatile observation")
SAFE = section("    static bool HandleSafetyPreview(",
               "    static bool HandleRepairPreview(")
REPAIR_HANDLER = section("    static bool HandleRepairPreview(",
                         "    static bool HandleApply(")
REPAIR_REPORT = section("    void PrintAltBotRepairPreview(",
                        "    void PrintPreview(")
APPLY_READY = section("    bool CheckApplyReadiness(",
                      "    bool ApplyValidated(")


def synthetic_rank_issues(records, dbc_allowed):
    """Example model; does not execute AzerothCore or inspect real DBCs.

    records=(spell_id,talent_id,spec_bitmask,is_removed), dbc_allowed is
    a dictionary of valid talent ID -> set of valid rank-spell IDs.
    """
    output = []
    for spec in range(2):
        seen = Counter()
        unmatched = []
        for spell, talent, mask, removed in records:
            if removed or not mask & (1 << spec):
                continue
            if spell not in dbc_allowed.get(talent, set()):
                unmatched.append(spell)
            else:
                seen[talent] += 1
        output.append((sorted(unmatched),
                       sum(count >= 2 for count in seen.values())))
    return output


class AltBotTalentMapIntegrityTests(unittest.TestCase):
    def test_reader_uses_only_in_memory_player_talent_map(self):
        self.assertIn("bot->GetTalentMap()", AUDIT)
        self.assertIn("record->talentID", AUDIT)
        self.assertIn("record->specMask & (1u << spec)", AUDIT)
        self.assertIn("record->State == PLAYERSPELL_REMOVED", AUDIT)
        self.assertNotIn("CharacterDatabase.", AUDIT)
        self.assertNotIn("WorldDatabase.", AUDIT)

    def test_checks_loaded_dbc_rank_and_player_class(self):
        self.assertIn("sTalentStore.LookupEntry(record->talentID)", AUDIT)
        self.assertIn("sTalentTabStore.LookupEntry(talent->TalentTab)", AUDIT)
        self.assertIn("tab->ClassMask & bot->getClassMask()", AUDIT)
        self.assertIn("talent->RankID[i] == spellId", AUDIT)
        self.assertIn("tab->tabpage < 3", AUDIT)

    def test_bounds_owned_specs_and_reports_metadata_mismatch(self):
        self.assertIn("spec < specCount && spec < MAX_TALENT_SPECS", AUDIT)
        self.assertIn("specCount > MAX_TALENT_SPECS", AUDIT)
        self.assertIn("bot->GetActiveSpec() >= specCount", AUDIT)
        self.assertIn("unusual spec metadata", AUDIT)

    def test_reports_multiple_ranks_once_per_talent(self):
        self.assertIn("++rankCounts[record->talentID] == 2", AUDIT)
        self.assertIn("++multiRankTalents", AUDIT)

    def test_deterministic_and_chat_bounded_examples(self):
        self.assertIn("std::sort(unmatchedSpellIds.begin()", AUDIT)
        self.assertIn("MAX_UNMATCHED_EXAMPLES = 3", AUDIT)
        self.assertIn("i < MAX_UNMATCHED_EXAMPLES", AUDIT)
        self.assertIn("unmatchedSpellIds.size(), multiRankTalents", AUDIT)

    def test_report_explicitly_disclaims_completeness_and_repairs(self):
        self.assertIn("DBC differences can cause warnings", AUDIT)
        self.assertIn("Zero warnings do NOT prove", AUDIT)
        self.assertIn("no mutation", AUDIT)

    def test_new_reporter_contains_no_mutating_methods(self):
        code = re.sub(r"//[^\n]*", "", AUDIT)
        code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
        self.assertIsNone(re.search(
            r"\b(?:resetTalents|ActivateSpec|SetActiveSpec|LearnTalent|"
            r"RemovePet|SetGlyph|AutoUnequipOffhandIfNeed|SaveToDB|"
            r"RemoveItem|StoreItem|DirectExecute|EquipNewItem)\s*\(", code))

    def test_safety_report_runs_after_allowlist_and_random_bot_refusal(self):
        for check in ("sRandomPlayerbotMgr.IsRandomBot(bot)",
                      "CanApplyToAltBot(issuer, error)"):
            self.assertLess(SAFE.index(check),
                            SAFE.index("PrintAltBotTalentMapIntegrity(handler, bot)"))

    def test_repair_report_runs_only_through_protected_handler(self):
        self.assertLess(
            REPAIR_HANDLER.index("CanApplyToAltBot(issuer, error)"),
            REPAIR_HANDLER.index(
                "PrintAltBotRepairPreview(handler, issuer, bot, build)"))
        self.assertIn("PrintAltBotTalentMapIntegrity(handler, bot)", REPAIR_REPORT)

    def test_original_altbot_equipment_and_pet_guards_preserved(self):
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", APPLY_READY)
        self.assertIn("Alt Bot NT1 Apply blocked: the bot has an active", APPLY_READY)
        self.assertNotIn('{"repairapply"', CPP)

    def test_repair_active_spec_number_is_human_readable(self):
        self.assertIn("static_cast<uint32>(bot->GetActiveSpec() + 1)", REPAIR_REPORT)

    def test_synthetic_conflicting_ranks_active_spec_only(self):
        records = [(100, 10, 1, False), (101, 10, 1, False)]
        self.assertEqual(synthetic_rank_issues(records, {10: {100, 101}}),
                         [([], 1), ([], 0)])

    def test_synthetic_unmatched_in_inactive_spec(self):
        records = [(100, 10, 1, False), (999, 10, 2, False)]
        self.assertEqual(synthetic_rank_issues(records, {10: {100, 101}}),
                         [([], 0), ([999], 0)])

    def test_synthetic_removed_ranks_ignored_and_shared_rank_allowed(self):
        records = [(100, 10, 3, False), (999, 10, 1, True)]
        self.assertEqual(synthetic_rank_issues(records, {10: {100}}),
                         [([], 0), ([], 0)])

    def test_synthetic_bad_class_or_unknown_dbc_is_warning_not_repair(self):
        records = [(5678, 1000, 1, False), (1234, 10, 1, False)]
        self.assertEqual(synthetic_rank_issues(records, {10: {1234}}),
                         [([5678], 0), ([], 0)])


if __name__ == "__main__":
    unittest.main()
