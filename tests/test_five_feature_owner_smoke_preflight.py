"""Source-only five-feature S5 preflight contract, NOT a Worldserver/DB test."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

CONF = read("conf/mod_naxxramas_core.conf.dist")
LOADER = read("src/NaxxramasCore_loader.cpp")
SHADE = read("src/Events/HallowsEndShadeOfTheHorseman.cpp")
SHADE_SQL = read("data/sql/db-world/2026_09_21_00_event_script_overrides.sql")
EP_INSTALL = read("docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql")
EP_ROLLBACK = read("docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql")
GFPP = read("src/Systems/BotRaidConsumables.cpp")
QUEST = read("src/Systems/QuestLootProtection.cpp")
DOC = read("docs/test/five-feature-integrated-owner-smoke-preflight-2026-10-20.md")

FLAGS = (
    "NaxxramasCore.BotConsumables.HunterAmmo.Enabled",
    "NaxxramasCore.QuestLootProtection.Enabled",
    "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled",
    "NaxxramasCore.HallowsEnd.SoloFire.Enabled",
)

class ReadOnlyFiveFeaturePreflight(unittest.TestCase):
    def test_exact_optional_flags_start_disabled_in_candidate_dist(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                matches = re.findall(
                    rf"(?m)^\s*{re.escape(flag)}\s*=\s*(\d+)\s*$", CONF
                )
                self.assertEqual(matches, ["0"])

    def test_multiplier_is_config_value_not_an_enable_flag(self):
        self.assertRegex(
            CONF, r"(?m)^NaxxramasCore\.HallowsEnd\.SoloFire\.PeriodMultiplier\s*=\s*3\s*$"
        )
        self.assertIn("one real player", DOC.lower())

    def test_loader_still_registers_all_required_module_hooks(self):
        for method in (
            "AddBotRaidConsumablesScripts();",
            "AddQuestLootProtectionScripts();",
            "AddNaxxramasEasternPlaguelandsTowerLockScripts();",
            "AddHallowsEndShadeOfTheHorsemanScripts();",
        ):
            with self.subTest(method=method):
                self.assertEqual(LOADER.count(method), 2)  # declaration + call

    def test_source_contract_includes_actual_quest_and_gfpp_hooks(self):
        self.assertIn("CMSG_AUTOSTORE_LOOT_ITEM", QUEST)
        self.assertIn("NaxxramasCore.QuestLootProtection.Enabled", QUEST)
        self.assertIn("NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled", GFPP)
        self.assertIn("OneShotFireProtection", GFPP)

    def test_shade_sql_maps_exact_npc_to_registered_script(self):
        self.assertIn("RegisterCreatureAI(", SHADE)
        self.assertIn("npc_naxxramas_hallows_end_soh", SHADE)
        self.assertRegex(
            SHADE_SQL,
            r"(?s)UPDATE `creature_template`\s+SET `ScriptName`\s*=\s*"
            r"'npc_naxxramas_hallows_end_soh'\s+WHERE `entry`\s*=\s*23543\s*;",
        )
        self.assertNotIn("23686", SHADE_SQL)

    def test_ep_bind_is_explicit_manual_and_rollback_is_scoped(self):
        self.assertIn("MANUAL, OWNER-APPROVED INSTALL ONLY", EP_INSTALL)
        self.assertIn("WHERE `TypeId` = 6", EP_INSTALL)
        self.assertIn("AND `ScriptName` = 'outdoorpvp_ep'", EP_INSTALL)
        self.assertIn("SET `ScriptName` = 'outdoorpvp_naxxramas_ep_lock'", EP_INSTALL)
        self.assertIn("SET `ScriptName` = 'outdoorpvp_ep'", EP_ROLLBACK)
        self.assertIn("AND `ScriptName` = 'outdoorpvp_naxxramas_ep_lock'", EP_ROLLBACK)

    def test_doc_has_read_only_queries_and_no_mutating_sql(self):
        self.assertIn("SELECT `entry`, `ScriptName`", DOC)
        self.assertIn("SELECT `TypeId`, `ScriptName`", DOC)
        for forbidden in ("DELETE FROM", "DROP TABLE", "TRUNCATE TABLE", "INSERT INTO", "UPDATE `"):
            self.assertNotIn(forbidden, DOC)

    def test_no_s4_or_s5_signoff_is_implied(self):
        for phrase in (
            "NOT STARTED", "NOT TESTED", "No deployment", "owner permission",
            "one comprehensive module upgrade", "One-bucket extinguish is NOT implemented",
            "A01 Golemagg", "A02 human Hunter", "A03 NT1",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DOC)

if __name__ == "__main__":
    unittest.main()
