"""Static regressions for the read-only Alt Bot protected-state observation.

These are source checks, NOT compilation, full recovery, or equipment-proof.
"""
from pathlib import Path
import re
import unittest

CPP = (Path(__file__).resolve().parents[1] / "src/Systems/BotTalentImport.cpp").read_text(encoding="utf-8")


def source(start, stop):
    i = CPP.index(start)
    j = CPP.index(stop, i + len(start))
    return CPP[i:j]


SNAPSHOT = source("    // Read-only volatile observation", "    // Must run inside ImportScope.")
DIAGNOSTIC = source("    void PrintAltBotRepairPreview(", "    void PrintPreview(")
COMMAND = source("    static bool HandleRepairPreview(", "    static bool HandleApply(")
DANGEROUS = re.compile(
    r"\b(?:resetTalents|LearnTalent|SaveToDB|DirectExecute|"
    r"SetActiveSpec|SetGlyph|EquipNewItem|DestroyItem|StoreItem|"
    r"RemoveItem|AutoUnequipOffhandIfNeed|ImportScope)\s*\("
)


class AltBotProtectedStateSourceTests(unittest.TestCase):
    def test_snapshot_and_report_have_no_mutating_calls(self):
        for section in (SNAPSHOT, DIAGNOSTIC, COMMAND):
            uncommented = re.sub(r"//[^\n]*", "", section)
            self.assertIsNone(DANGEROUS.search(uncommented))

    def test_talent_map_covers_both_specs_and_removed_entries_are_skipped(self):
        self.assertIn("bot->GetTalentMap()", SNAPSHOT)
        self.assertIn("talent->State == PLAYERSPELL_REMOVED", SNAPSHOT)
        self.assertIn("MAX_TALENT_SPECS", SNAPSHOT)
        self.assertIn("talent->specMask & (1u << spec)", SNAPSHOT)

    def test_learned_spells_cover_both_specs(self):
        self.assertIn("bot->GetSpellMap()", SNAPSHOT)
        self.assertIn("spell->specMask & (1u << spec)", SNAPSHOT)
        self.assertIn("spell->State == PLAYERSPELL_REMOVED", SNAPSHOT)

    def test_talent_and_spell_records_sorted_for_determinism(self):
        self.assertIn("std::sort(snapshot.Talents[spec].begin()", SNAPSHOT)
        self.assertIn("std::sort(snapshot.Spells[spec].begin()", SNAPSHOT)

    def test_only_active_glyphs_read_without_switching_specs(self):
        self.assertIn("bot->GetGlyph(slot)", SNAPSHOT)
        self.assertIn("MAX_GLYPH_SLOT_INDEX", SNAPSHOT)
        self.assertIn("inactive glyphs require OFFLINE DB backup", SNAPSHOT)
        self.assertNotRegex(SNAPSHOT, r"\b(?:ActivateSpec|SetActiveSpec)\s*\(")

    def test_all_equipment_slots_are_observed_by_guid(self):
        self.assertIn("#include \"Item.h\"", CPP)
        self.assertIn("std::array<uint32, EQUIPMENT_SLOT_END> EquippedItemGuids", SNAPSHOT)
        self.assertIn("slot = EQUIPMENT_SLOT_START", SNAPSHOT)
        self.assertIn("slot < EQUIPMENT_SLOT_END", SNAPSHOT)
        self.assertIn("bot->GetItemByPos(INVENTORY_SLOT_BAG_0, slot)", SNAPSHOT)
        self.assertIn("item->GetGUID().GetCounter()", SNAPSHOT)

    def test_checksum_contains_spec_and_character_context(self):
        self.assertIn("snapshot.CharacterGuid", SNAPSHOT)
        self.assertIn("snapshot.Level", SNAPSHOT)
        self.assertIn("snapshot.SpecsCount", SNAPSHOT)
        self.assertIn("snapshot.ActiveSpec", SNAPSHOT)
        self.assertIn("for (uint32 spec = 0; spec < MAX_TALENT_SPECS; ++spec)", SNAPSHOT)

    def test_item_checksum_is_ordered_by_equipment_slot(self):
        start = SNAPSHOT.index("    uint64 FingerprintAltBotEquipment(")
        stop = SNAPSHOT.index("    uint64 FingerprintAltBotActiveGlyphs(", start)
        block = SNAPSHOT[start:stop]
        self.assertIn("MixStateFingerprint(hash, slot);", block)
        self.assertIn("snapshot.EquippedItemGuids[slot]", block)

    def test_active_glyph_checksum_records_slot_and_identity(self):
        start = SNAPSHOT.index("    uint64 FingerprintAltBotActiveGlyphs(")
        stop = SNAPSHOT.index("    std::string HexStateFingerprint(", start)
        block = SNAPSHOT[start:stop]
        self.assertIn("snapshot.ActiveSpec", block)
        self.assertIn("MixStateFingerprint(hash, slot);", block)
        self.assertIn("snapshot.ActiveGlyphs[slot]", block)

    def test_no_persistent_token_or_database_write(self):
        self.assertIn("NOT a security credential", SNAPSHOT)
        self.assertIn("NOT A BACKUP", SNAPSHOT)
        self.assertNotRegex(SNAPSHOT, r"\b(?:CharacterDatabase|WorldDatabase|AccountDatabase)\b")

    def test_all_bag_bank_mail_and_inactive_glyph_gaps_are_explicit(self):
        self.assertIn("no bag/bank/mail or inactive", SNAPSHOT)
        self.assertIn("glyph values captured", SNAPSHOT)
        self.assertIn("Checksums are not restore tokens", SNAPSHOT)

    def test_caller_already_checked_alt_allowlist_before_details(self):
        self.assertLess(
            COMMAND.index("CanApplyToAltBot(issuer, error)"),
            COMMAND.index("PrintAltBotRepairPreview(handler, issuer, bot, build)"),
        )
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", COMMAND)

    def test_same_report_still_shows_apply_denial(self):
        self.assertIn("CheckApplyReadiness(issuer, bot, proposed, reason, nullptr,", DIAGNOSTIC)
        self.assertIn("PrintAltBotProtectedState(handler, bot)", DIAGNOSTIC)
        self.assertLess(
            DIAGNOSTIC.index("NT1 ALT REPAIR DIAGNOSTIC BLOCKED"),
            DIAGNOSTIC.index("PrintAltBotProtectedState(handler, bot)"),
        )

    def test_no_destructive_repair_command(self):
        self.assertIn('{"repairpreview", HandleRepairPreview', CPP)
        self.assertNotIn('{"repairapply"', CPP)
        self.assertNotIn('{"repair",', CPP)

    def test_source_has_no_individual_progression_header_conflict(self):
        self.assertNotIn('#include "IndividualProgression.h"', CPP)


if __name__ == "__main__":
    unittest.main()
