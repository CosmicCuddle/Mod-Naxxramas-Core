"""Read-only active NT1 talent equivalence: source and synthetic regression.

These tests model high-level cases and assert structural fail-closed gates.
They do NOT build C++, query a live server, or certify no-op Apply safety.
"""
from pathlib import Path
import re
import unittest

SOURCE = (
    Path(__file__).resolve().parents[1] /
    "src" / "Systems" / "BotTalentImport.cpp"
).read_text(encoding="utf-8")


def region(start, end):
    a = SOURCE.index(start)
    b = SOURCE.index(end, a + len(start))
    return SOURCE[a:b]


CHECK = region("    ActiveTalentMatch InspectActiveTalentMatch(",
               "    void PrintActiveTalentMatch(")
PRINT = region("    void PrintActiveTalentMatch(",
               "    // Diagnostic-only Alt Bot repair preview.")
REPAIR = region("    void PrintAltBotRepairPreview(", "    void PrintPreview(")
PREVIEW = region("    void PrintPreview(", "\n}\n\nclass NaxxramasBotTalentImportCommands")
APPLY = region("    bool ApplyValidated(", "    bool ReadArguments(")
READINESS = region("    bool CheckApplyReadiness(", "    bool ApplyValidated(")


def synthetic_compare(expected, records, free, budget, metadata_ok=True):
    """Model exact-rank expectation, including ambiguous/corrupt map records.

    records are tuples: (talent_id, rank, class_valid, dbc_valid, removed).
    Comparisons are active-spec only and cannot predict any reset effects.
    """
    if not metadata_ok or budget < 0 or free < 0 or free > budget:
        return "INDETERMINATE"
    observed = {}
    points = 0
    for record in records:
        if record is None:
            return "INDETERMINATE"
        talent, rank, class_valid, dbc_valid, removed = record[:5]
        state_valid = len(record) == 5 or record[5]
        if removed:
            continue
        if not state_valid or not class_valid or not dbc_valid or rank < 1 or rank > 5:
            return "INDETERMINATE"
        if talent in observed:
            return "INDETERMINATE"
        observed[talent] = rank
        points += rank
    if points > budget or points + free != budget:
        return "INDETERMINATE"
    return "EXACT" if observed == expected else "DIFFERENT"


class ActiveTalentMatchModelTests(unittest.TestCase):
    def test_exact_full_priest_allocation(self):
        self.assertEqual(synthetic_compare(
            {101: 5, 102: 5}, [(101, 5, True, True, False),
                                (102, 5, True, True, False)],
            0, 10
        ), "EXACT")

    def test_same_point_total_is_not_exact(self):
        self.assertEqual(synthetic_compare(
            {101: 5, 102: 5}, [(101, 5, True, True, False),
                                (103, 5, True, True, False)],
            0, 10
        ), "DIFFERENT")

    def test_wrong_rank_with_equal_points_is_not_exact(self):
        self.assertEqual(synthetic_compare(
            {101: 4, 102: 3}, [(101, 3, True, True, False),
                                (102, 4, True, True, False)],
            0, 7
        ), "DIFFERENT")

    def test_valid_partial_and_empty_builds(self):
        self.assertEqual(synthetic_compare({101: 3}, [
            (101, 3, True, True, False)], 7, 10), "EXACT")
        self.assertEqual(synthetic_compare({}, [], 10, 10), "EXACT")

    def test_extra_active_record_not_ignored(self):
        self.assertEqual(synthetic_compare(
            {101: 3}, [(101, 3, True, True, False),
                        (102, 2, True, True, False)],
            5, 10
        ), "DIFFERENT")

    def test_removed_rank_not_mistaken_as_live(self):
        self.assertEqual(synthetic_compare(
            {101: 3}, [(101, 2, True, True, True),
                        (101, 3, True, True, False)],
            7, 10
        ), "EXACT")

    def test_multiple_live_ranks_must_be_indeterminate(self):
        self.assertEqual(synthetic_compare(
            {101: 3}, [(101, 2, True, True, False),
                        (101, 3, True, True, False)],
            5, 10
        ), "INDETERMINATE")

    def test_unmatched_dbc_or_wrong_class_must_be_indeterminate(self):
        for klass, dbc in ((False, True), (True, False)):
            with self.subTest(klass=klass, dbc=dbc):
                self.assertEqual(synthetic_compare(
                    {101: 3}, [(101, 3, klass, dbc, False)],
                    7, 10
                ), "INDETERMINATE")

    def test_null_record_must_be_indeterminate(self):
        self.assertEqual(synthetic_compare(
            {}, [None], 10, 10
        ), "INDETERMINATE")

    def test_unexpected_live_record_state_is_indeterminate(self):
        self.assertEqual(synthetic_compare(
            {101: 3}, [(101, 3, True, True, False, False)],
            7, 10
        ), "INDETERMINATE")

    def test_duplicate_dbc_rank_mapping_is_indeterminate(self):
        # dbc_valid=False also models a spell ID present in two rank slots.
        self.assertEqual(synthetic_compare(
            {101: 3}, [(101, 3, True, False, False)],
            7, 10
        ), "INDETERMINATE")

    def test_stale_free_point_count_must_be_indeterminate(self):
        self.assertEqual(synthetic_compare(
            {101: 5}, [(101, 5, True, True, False)],
            6, 10
        ), "INDETERMINATE")
        self.assertEqual(synthetic_compare(
            {101: 5}, [(101, 5, True, True, False)],
            11, 10
        ), "INDETERMINATE")

    def test_stale_character_metadata_must_be_indeterminate(self):
        self.assertEqual(synthetic_compare(
            {}, [], 10, 10, metadata_ok=False
        ), "INDETERMINATE")


class ActiveTalentMatchSourceTests(unittest.TestCase):
    def test_expected_ranks_come_from_validated_build(self):
        self.assertIn("requested.Ordered", CHECK)
        self.assertIn("expected.emplace(choice.Id, choice.Rank)", CHECK)
        self.assertIn("!currentClass || requested.Class != currentClass", CHECK)
        self.assertIn("requested.Available != bot->CalculateTalentsPoints()", CHECK)

    def test_reads_only_active_spec_mask(self):
        self.assertIn("bot->GetTalentMap()", CHECK)
        self.assertIn("uint8 const spec = bot->GetActiveSpec()", CHECK)
        self.assertIn("record->specMask & (1u << spec)", CHECK)
        self.assertIn("record->State == PLAYERSPELL_REMOVED", CHECK)
        self.assertIn("bot->HasTalent(spellId, spec)", CHECK)

    def test_rejects_db_mismatch_and_multi_rank(self):
        for token in (
            "if (!record)", "record->talentID",
            "tab->tabpage >= 3", "tab->ClassMask & bot->getClassMask()",
            "talent->RankID[index] == spellId",
            "!sSpellMgr->GetSpellInfo(spellId)",
            "matchingDbcRanks != 1",
            "record->State != PLAYERSPELL_NEW",
            "!observed.emplace(record->talentID, rank).second",
            "observedPoints + bot->GetFreeTalentPoints() != requested.Available",
        ):
            self.assertIn(token, CHECK)

    def test_reports_exact_different_indeterminate_and_caveats(self):
        for token in (
            "EXACT active-spec talent ranks",
            "DIFFERENT active-spec build",
            "CANNOT VERIFY", "NOT Apply-ready",
        ):
            # The wording of 'NOT Apply-ready' is intentionally not a static
            # API requirement, but a broader no-reset/no-approval warning.
            if token == "NOT Apply-ready":
                self.assertIn("does NOT approve Apply", PRINT)
            else:
                self.assertIn(token, PRINT)
        self.assertIn("Inactive spec, glyphs, pets", PRINT)

    def test_read_only_diagnostics_never_mutate(self):
        diagnostics = CHECK + "\n" + PRINT
        diagnostics = re.sub(r"//[^\n]*", "", diagnostics)
        diagnostics = re.sub(r'"(?:\\.|[^"\\])*"', '""', diagnostics)
        self.assertIsNone(re.search(
            r"\b(?:resetTalents|LearnTalent|LearnValidated|SaveToDB|"
            r"DirectExecute|RemovePet|AutoUnequipOffhandIfNeed|"
            r"EquipNewItem|DestroyItem|StoreItem|ActivateSpec|"
            r"SetGlyph|SendMailTo)\s*\(",
            diagnostics,
        ))

    def test_preview_does_not_disclose_alt_match_before_allowlist(self):
        permission = PREVIEW.index("CanApplyToAltBot(matchIssuer, matchDenied)")
        display = PREVIEW.index("PrintActiveTalentMatch(handler, bot, build)")
        self.assertLess(permission, display)
        self.assertIn("!sRandomPlayerbotMgr.IsRandomBot(bot)", PREVIEW)

    def test_repair_uses_original_allowlisted_handler(self):
        handler = region("    static bool HandleRepairPreview(",
                         "    static bool HandleApply(")
        self.assertLess(
            handler.index("CanApplyToAltBot(issuer, error)"),
            handler.index("PrintAltBotRepairPreview(handler, issuer, bot, build)"),
        )
        self.assertIn("PrintActiveTalentMatch(handler, bot, proposed)", REPAIR)

    def test_guard_and_two_reset_recovery_untouched(self):
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", READINESS)
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertIn("if (IsReadOnlyAccessMode())", APPLY)
        self.assertEqual(APPLY.count("bot->resetTalents(true);"), 2)
        self.assertNotIn("InspectActiveTalentMatch(", APPLY)
        self.assertNotIn("PrintActiveTalentMatch(", APPLY)


if __name__ == "__main__":
    unittest.main()
