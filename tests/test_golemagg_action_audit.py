"""Source-contract checks for the OFF-by-default Golemagg action audit.

These checks do not compile AzerothCore or prove in-game behaviour. They catch
accidental expansion of the research-only observer into a movement mutator.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/BotGolemaggActionAudit.cpp").read_text()
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()


class GolemaggActionAuditSourceContract(unittest.TestCase):
    def test_is_explicitly_disabled_by_default(self):
        self.assertIn(
            "NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0", CONFIG
        )
        self.assertRegex(
            SOURCE,
            r'sConfigMgr->GetOption<bool>\(\s*'
            r'"NaxxramasCore\.Playerbots\.GolemaggActionAudit\.Enabled", false\)',
        )

    def test_registration_is_isolated(self):
        self.assertEqual(LOADER.count("void AddBotGolemaggActionAuditScripts();"), 1)
        self.assertEqual(LOADER.count("    AddBotGolemaggActionAuditScripts();"), 1)
        self.assertIn("PLAYERHOOK_ON_UPDATE", SOURCE)
        self.assertIn("PLAYERHOOK_ON_LOGOUT", SOURCE)

    def test_only_altbots_non_tank_melee_in_mc(self):
        for required in [
            "MOLTEN_CORE_MAP = 409",
            "MAGMA_SPLASH_SPELL = 13880",
            "ai->IsAltBot()",
            "PlayerbotAI::IsTank(player)",
            "PlayerbotAI::IsMelee(player)",
            "PlayerbotAI::IsDps(player)",
            "player->IsInCombat()",
            "boss->IsAlive()",
        ]:
            with self.subTest(required=required):
                self.assertIn(required, SOURCE)

    def test_public_read_only_action_query_only(self):
        self.assertIn('ai->HandleRemoteCommand("action")', SOURCE)
        self.assertIn('ai->HandleRemoteCommand("target")', SOURCE)
        for forbidden in [
            "AddActionExecutionListener(",
            "removeActionExecutionListener(",
            "DoSpecificAction(",
            "ChangeStrategy(",
            "ToggleAutocast(",
            "LearnSpell(",
            "resetTalents(",
            "MoveTo(",
            "MoveAway(",
            "TeleportTo(",
            "CharacterDatabase.",
            "WorldDatabase.",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, SOURCE)

    def test_probe_is_bounded(self):
        self.assertRegex(SOURCE, r"SAMPLE_INTERVAL_MS\s*=\s*2500")
        self.assertRegex(SOURCE, r"MAX_SAMPLES_PER_BOT\s*=\s*24")
        self.assertRegex(SOURCE, r"MAX_ACTION_TEXT\s*=\s*320")
        self.assertIn("state.samples >= MAX_SAMPLES_PER_BOT", SOURCE)
        self.assertIn("state.lastTrace", SOURCE)
        self.assertIn("_samples.erase", SOURCE)

    def test_transient_target_loss_does_not_rearm_logging_quota(self):
        # The boss lookup is allowed to flicker while the same bot remains
        # in combat. In that case the 24-line quota must NOT be cleared.
        self.assertIn("Unit* boss = found ? found->Get() : nullptr;", SOURCE)
        after_lookup = SOURCE.split(
            "Unit* boss = found ? found->Get() : nullptr;", 1
        )[1]
        self.assertIn("// This public branch returns", after_lookup)
        boss_block = after_lookup.split("// This public branch returns", 1)[0]
        self.assertIn("if (!boss || !boss->IsAlive()", boss_block)
        self.assertNotIn("_samples.erase(guid)", boss_block)
        self.assertIn("return;", boss_block)

    def test_does_not_claim_action_is_causal(self):
        self.assertIn("RECENT action-log tail", SOURCE)
        self.assertIn("not one", SOURCE)
        self.assertIn("does not Execute an AI action", SOURCE)


if __name__ == "__main__":
    unittest.main()
