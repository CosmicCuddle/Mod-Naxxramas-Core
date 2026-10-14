"""Static source-contract regressions for the Alt Bot read-only repair diagnostic.

The tests examine *source structure only*, NOT a compiled AzerothCore server.
They cannot assert in-game behaviour, correct DBC loading, or data rollback.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src" / "Systems" / "BotTalentImport.cpp").read_text(
    encoding="utf-8"
)


def section(begin, end):
    first = CPP.index(begin)
    last = CPP.index(end, first + len(begin))
    return CPP[first:last]


def strip_comments(code):
    return re.sub(r"//[^\n]*", "", code)


DANGEROUS_CALLS = re.compile(
    r"\b(?:resetTalents|LearnTalent|LearnValidated|SaveToDB|"
    r"DirectExecute|EquipNewItem|DestroyItem|ApplyValidated|"
    r"RemovePet|AutoUnequipOffhandIfNeed)\s*\("
)


class RepairPreviewSourceSafetyTests(unittest.TestCase):
    def test_command_is_explicitly_preview_only(self):
        self.assertIn(
            '{"repairpreview", HandleRepairPreview, SEC_PLAYER, Console::No}', CPP
        )
        self.assertNotIn('{"repairapply"', CPP)
        self.assertNotIn('{"repair"', CPP)

    def test_existing_commands_retained(self):
        self.assertIn('{"preview", HandlePreview, SEC_PLAYER, Console::No}', CPP)
        self.assertIn('{"apply", HandleApply, SEC_PLAYER, Console::No}', CPP)

    def test_diagnostic_is_read_only(self):
        for source in (
            section(
                "    std::vector<OutOfEraTalent> GetOutOfEraTalents(",
                "    // Must run inside ImportScope.",
            ),
            section(
                "    void PrintAltBotRepairPreview(",
                "    void PrintPreview(",
            ),
            section(
                "    static bool HandleRepairPreview(",
                "    static bool HandleApply(",
            ),
        ):
            self.assertIsNone(DANGEROUS_CALLS.search(strip_comments(source)))

    def test_no_individual_progression_header_conflict(self):
        self.assertNotIn('#include "IndividualProgression.h"', CPP)
        self.assertIn("CheckPlayerProgressionEra(", CPP)

    def test_random_bot_refused_before_diagnostic(self):
        h = section(
            "    static bool HandleRepairPreview(",
            "    static bool HandleApply(",
        )
        self.assertLess(
            h.index("sRandomPlayerbotMgr.IsRandomBot(bot)"),
            h.index("PrintAltBotRepairPreview(handler, issuer, bot, build)"),
        )

    def test_human_identity_and_allowlist_checked_first(self):
        h = section(
            "    static bool HandleRepairPreview(",
            "    static bool HandleApply(",
        )
        self.assertLess(
            h.index("ValidateRequest(handler, args, bot, build)"),
            h.index("CanApplyToAltBot(issuer, error)"),
        )
        self.assertLess(
            h.index("CanApplyToAltBot(issuer, error)"),
            h.index("PrintAltBotRepairPreview(handler, issuer, bot, build)"),
        )
        self.assertIn("PlayerbotsMgr::instance().GetPlayerbotAI(issuer)", h)

    def test_uses_selected_active_spec(self):
        d = section(
            "    std::vector<OutOfEraTalent> GetOutOfEraTalents(",
            "    // Must run inside ImportScope.",
        )
        self.assertIn("bot->GetActiveSpec()", d)
        self.assertIn("bot->HasTalent(", d)
        self.assertIn("tab->tabpage >= 3", d)

    def test_uses_original_era_policy(self):
        d = section(
            "    std::vector<OutOfEraTalent> GetOutOfEraTalents(",
            "    // Must run inside ImportScope.",
        )
        self.assertIn("AvailableInEra(", d)
        self.assertIn("proposed.Progression", section(
            "    void PrintAltBotRepairPreview(", "    void PrintPreview("
        ))

    def test_preflight_is_read_only_and_not_replaced(self):
        d = section("    void PrintAltBotRepairPreview(", "    void PrintPreview(")
        self.assertIn("CheckApplyReadiness(issuer, bot, proposed, reason, nullptr,", d)
        self.assertIn("NT1 ALT REPAIR DIAGNOSTIC BLOCKED", d)
        self.assertIn("NT1 ALT REPAIR DISABLED", d)
        self.assertIn("READ ONLY:", d)

    def test_diagnostic_is_not_an_authorization_token(self):
        h = section(
            "    static bool HandleRepairPreview(", "    static bool HandleApply("
        )
        self.assertNotIn("ImportScope", strip_comments(h))
        self.assertNotIn("SaveToDB", strip_comments(h))

    def test_exposes_multiple_old_talent_errors_in_one_pass(self):
        d = section(
            "    std::vector<OutOfEraTalent> GetOutOfEraTalents(",
            "    // Must run inside ImportScope.",
        )
        self.assertIn("result.push_back(", d)
        self.assertIn("return result;", d)

    def test_does_not_introduce_equipment_generator(self):
        h = section(
            "    static bool HandleRepairPreview(", "    static bool HandleApply("
        )
        self.assertNotRegex(h, r"\b(?:AutoGear|InitEquipment|EquipNewItem)\s*\(")


if __name__ == "__main__":
    unittest.main()
