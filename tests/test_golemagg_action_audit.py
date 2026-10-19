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
ALLOWLIST = (ROOT / "src/Systems/GolemaggActionAuditAllowlist.h").read_text()


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

    def test_single_exact_allowlisted_bot_is_required(self):
        self.assertIn(
            'NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName = ""',
            CONFIG,
        )
        self.assertIn(
            '"NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName", ""',
            SOURCE,
        )
        self.assertIn('#include "GolemaggActionAuditAllowlist.h"', SOURCE)
        self.assertIn("NaxxramasGolemaggActionAudit::IsAllowedBotName(", SOURCE)
        self.assertIn("player->GetName(), allowedBot", SOURCE)
        self.assertIn('if (first == std::string::npos)', ALLOWLIST)
        self.assertIn("expected.size() != actual.size()", ALLOWLIST)
        self.assertIn("std::equal(", ALLOWLIST)
        self.assertNotIn("find('*')", ALLOWLIST)

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
        self.assertIn("state->samples >= MAX_SAMPLES_PER_BOT", SOURCE)
        self.assertIn("state->lastTrace", SOURCE)
        self.assertIn("player->CustomData.Erase(AUDIT_STATE_KEY)", SOURCE)

    def test_transient_target_loss_does_not_rearm_logging_quota(self):
        # The boss lookup is allowed to flicker while the same bot remains
        # in combat. In that case the 24-line quota must NOT be cleared.
        self.assertIn("Unit* boss = found ? found->Get() : nullptr;", SOURCE)
        after_lookup = SOURCE.split(
            "Unit* boss = found ? found->Get() : nullptr;", 1
        )[1]
        self.assertIn("// This public branch returns", after_lookup)
        boss_block = after_lookup.split("// This public branch returns", 1)[0]
        # Only an actual dead/wrong-map boss clears state; a missing
        # threat-list lookup is covered using an earlier in-combat sighting.
        self.assertIn("if (boss && (!boss->IsAlive()", boss_block)
        self.assertIn("state->sawGolemaggInThisCombat = true;", boss_block)
        self.assertIn("if (!state->sawGolemaggInThisCombat)", boss_block)
        self.assertIn("bool const lookupPresent = boss != nullptr", boss_block)
        self.assertIn("return;", boss_block)

    def test_lost_threat_target_reports_status_only_after_prior_sighting(self):
        self.assertIn("bool sawGolemaggInThisCombat = false;", SOURCE)
        self.assertIn("bool lastLookupPresent = false;", SOURCE)
        self.assertIn("if (lookupPresent)", SOURCE)
        self.assertIn("state->sawGolemaggInThisCombat = true;", SOURCE)
        self.assertIn("if (!state->sawGolemaggInThisCombat)", SOURCE)
        self.assertIn("boss_lookup_present={}", SOURCE)
        self.assertIn("lookupPresent ? boss->GetHealthPct() : -1.0f", SOURCE)
        self.assertIn("lookupPresent ? player->GetDistance2d(boss) : -1.0f", SOURCE)
        self.assertIn("lookupPresent == state->lastLookupPresent", SOURCE)
        # Last looked-up boss is NEVER stored as a pointer across ticks.
        self.assertNotIn("Unit* lastBoss", SOURCE)
        self.assertNotIn("ObjectGuid lastBoss", SOURCE)

    def test_threshold_crossings_are_logged_even_if_action_tail_repeats(self):
        # Pin the exact Playerbots retreat thresholds; still observation only.
        self.assertIn("MAGMA_SPLASH_RETREAT_STACKS = 20", SOURCE)
        self.assertIn("MAGMA_SPLASH_RETREAT_YARDS = 12.0f", SOURCE)
        self.assertIn("Aura* splash = player->GetAura(MAGMA_SPLASH_SPELL);", SOURCE)
        self.assertIn("stacks >= MAGMA_SPLASH_RETREAT_STACKS", SOURCE)
        self.assertIn("bossDistanceYards < MAGMA_SPLASH_RETREAT_YARDS", SOURCE)
        self.assertIn("atRetreatStacks != state->lastAtRetreatStacks", SOURCE)
        self.assertIn("insideRetreatDistance != state->lastInsideRetreatDistance", SOURCE)
        self.assertIn("!thresholdChanged", SOURCE)
        self.assertIn("state->hasLastSample = true;", SOURCE)
        self.assertIn("state->lastAtRetreatStacks = atRetreatStacks;", SOURCE)
        self.assertIn("state->lastInsideRetreatDistance = insideRetreatDistance;", SOURCE)
        self.assertIn("retreat_stacks_20={}", SOURCE)
        self.assertIn("inside_retreat_12yd={}", SOURCE)
        # Evaluation of threshold crossings must be BEFORE duplicate filtering.
        self.assertLess(
            SOURCE.index("bool const thresholdChanged ="),
            SOURCE.index("trace == state->lastTrace"),
        )
        # The existing one-bot, 2.5-second and 24-sample quota remain.
        self.assertIn("state->samples >= MAX_SAMPLES_PER_BOT", SOURCE)
        self.assertIn("++state->samples;", SOURCE)
        self.assertIn("state->elapsedMs < SAMPLE_INTERVAL_MS", SOURCE)
        # No movement or spell mutation interface is introduced by the probe.
        for denied in ("MoveAway(", "MoveTo(", "DoSpecificAction(", "CastSpell("):
            self.assertNotIn(denied, SOURCE)

    def test_sample_state_is_per_player_not_global_across_maps(self):
        self.assertIn("struct SampleState final : DataMap::Base", SOURCE)
        self.assertIn(
            "player->CustomData.GetDefault<SampleState>(AUDIT_STATE_KEY)", SOURCE
        )
        self.assertIn('AUDIT_STATE_KEY = "NaxxramasCore.GolemaggActionAudit.BotState"', SOURCE)
        self.assertIn("player->CustomData.Erase(AUDIT_STATE_KEY)", SOURCE)
        self.assertNotIn("std::unordered_map<ObjectGuid::LowType", SOURCE)
        self.assertNotIn("_samples", SOURCE)

    def test_does_not_claim_action_is_causal(self):
        self.assertIn("RECENT action-log tail", SOURCE)
        self.assertIn("not one", SOURCE)
        self.assertIn("does not Execute an AI action", SOURCE)


if __name__ == "__main__":
    unittest.main()
