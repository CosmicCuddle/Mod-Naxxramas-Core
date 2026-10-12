"""Code-free Alt Bot cross-class safety inspection: source-level contracts.

Not an AzerothCore C++ compilation or in-game validation.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src" / "Systems" / "BotTalentImport.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    a = CPP.index(start)
    b = CPP.index(end, a + len(start))
    return CPP[a:b]


HANDLER = section("    static bool HandleSafetyPreview(", "    static bool HandleRepairPreview(")
GET_COMMANDS = section("    ChatCommandTable GetCommands()", "    // AzerothCore treats false")
CROSSCLASS = section("    void PrintAltBotCrossClassSafetyAudit(", "    // Must run inside ImportScope.")


class CrossClassNoCodeCommandTests(unittest.TestCase):
    def test_command_registered_at_player_level(self):
        self.assertIn(
            '{"safetypreview", HandleSafetyPreview, SEC_PLAYER, Console::No}',
            GET_COMMANDS,
        )

    def test_accepts_only_bot_name_without_nt1_code(self):
        self.assertIn("std::istringstream input(args ? args", HANDLER)
        self.assertIn("if (!(input >> name) || (input >> extra))", HANDLER)
        self.assertIn("safetypreview <online-altbotname>", HANDLER)
        self.assertNotIn("ParseCode(", HANDLER)
        self.assertNotIn("ProjectPriorityCode(", HANDLER)

    def test_module_must_be_enabled(self):
        self.assertIn("if (!handler || !Enabled())", HANDLER)
        self.assertIn("player inspection disabled", HANDLER)

    def test_non_gm_requires_existing_access_mode_2_or_4(self):
        self.assertIn("if (!gm && !AllowNonGMPlayers())", HANDLER)
        self.assertIn("return AccessMode() == 2 || AccessMode() == 4;", CPP)
        self.assertIn("return mode <= 4 ? mode : 0;", CPP)

    def test_only_real_online_human_can_inspect(self):
        self.assertIn("issuer->IsInWorld()", HANDLER)
        self.assertIn("GetPlayerbotAI(issuer)", HANDLER)
        self.assertIn("GetSession()", HANDLER)

    def test_online_playerbot_identity_checked(self):
        self.assertIn("ObjectAccessor::FindPlayerByName(name)", HANDLER)
        self.assertIn("bot->IsInWorld()", HANDLER)
        self.assertIn("GetPlayerbotAI(bot)", HANDLER)
        self.assertIn("bot == issuer", HANDLER)

    def test_non_gm_control_check_before_report(self):
        self.assertIn("if (!gm && !CanControlBot(issuer, bot, ai))", HANDLER)
        self.assertLess(
            HANDLER.index("CanControlBot(issuer, bot, ai)"),
            HANDLER.index("PrintAltBotCrossClassSafetyAudit(handler, bot)"),
        )

    def test_random_bot_disallowed(self):
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", HANDLER)
        self.assertLess(
            HANDLER.index("sRandomPlayerbotMgr.IsRandomBot(bot)"),
            HANDLER.index("PrintAltBotCrossClassSafetyAudit(handler, bot)"),
        )

    def test_human_character_allowlist_mandatory_even_for_gms(self):
        self.assertIn("CanApplyToAltBot(issuer, error)", HANDLER)
        self.assertLess(
            HANDLER.index("CanApplyToAltBot(issuer, error)"),
            HANDLER.index("PrintAltBotProtectedState(handler, bot)"),
        )

    def test_only_two_read_only_reporters_invoked(self):
        self.assertIn("PrintAltBotProtectedState(handler, bot);", HANDLER)
        self.assertIn("PrintAltBotCrossClassSafetyAudit(handler, bot);", HANDLER)

    def test_no_mutating_calls_in_handler_or_classifier(self):
        mutating = re.compile(
            r"\b(?:resetTalents|ActivateSpec|SetActiveSpec|LearnTalent|"
            r"LearnValidated|SaveToDB|DirectExecute|RemovePet|"
            r"AutoUnequipOffhandIfNeed|SetGlyph|EquipNewItem|"
            r"RemoveItem|StoreItem|MailDraft)\s*\("
        )
        for src in (HANDLER, CROSSCLASS):
            code = re.sub(r"//[^\n]*", "", src)
            code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
            self.assertIsNone(mutating.search(code))

    def test_no_relaxed_offhand_guard_or_new_repair_apply(self):
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", CPP)
        self.assertNotIn('{"repairapply"', CPP)
        self.assertIn("NaxxramasCore.BotTalentImport.AccessMode = 0", CONF)

    def test_read_only_handler_does_not_change_regular_repair_preview(self):
        self.assertIn(
            '{"repairpreview", HandleRepairPreview, SEC_PLAYER, Console::No}',
            GET_COMMANDS,
        )
        self.assertIn("GetOutOfEraTalents(bot, proposed.Progression, spec)", CPP)


if __name__ == "__main__":
    unittest.main()
