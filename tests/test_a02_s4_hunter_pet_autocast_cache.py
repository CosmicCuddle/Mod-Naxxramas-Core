"""Policy tests for the A02 S4 hunter pet autocast cache.

The compiled program is tests/a02_s4_hunter_pet_autocast_cache_policy_tests.cpp
against src/Systems/HunterPetAutocastCache.h. A pass is not an in-game summon,
relog, or rank change, and it does not apply the characters SQL.
"""
from __future__ import annotations

import os
import re
import subprocess
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "src/Systems/HunterPetAutocastCache.h").read_text(encoding="utf-8")
SOURCE = (ROOT / "src/Systems/HunterPetAutocastCache.cpp").read_text(encoding="utf-8")
RESEARCH = (ROOT / "docs/research/a02-s4-hunter-pet-autocast-cache.md").read_text(encoding="utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/a02-s4-hunter-pet-autocast-cache.yml").read_text(encoding="utf-8")
SQL = (ROOT / "data/sql/db-characters/2026_10_20_00_hunter_pet_autocast_cache.sql").read_text(encoding="utf-8")
POLICY = ROOT / "tests/a02_s4_hunter_pet_autocast_cache_policy_tests.cpp"

IP_SHA = "4ff4b5fcc1480348f058c632573143e62d4e3a41"
CORE_OLD = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
CORE_NEW = "8daffdabe9202c228e45d833c9a1d399597a15cd"
IP_URL = (
    "https://raw.githubusercontent.com/Grimfeather/mod-individual-progression/"
    f"{IP_SHA}/src/IndividualProgressionSpells.cpp"
)

_POLICY: dict[str, object] = {}


def policy_program() -> dict[str, object]:
    if _POLICY:
        return _POLICY
    binary = Path("/tmp/a02_s4_hunter_pet_autocast_cache_policy_tests")
    compiled = subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "src/Systems"),
            str(POLICY),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
    )
    if compiled.returncode != 0:
        raise AssertionError(compiled.stderr or compiled.stdout)
    ran = subprocess.run([str(binary)], capture_output=True, text=True)
    if ran.returncode != 0:
        raise AssertionError(ran.stderr or ran.stdout)
    _POLICY.update({"stdout": ran.stdout, "stderr": ran.stderr, "code": ran.returncode})
    return _POLICY


def load_ip_source() -> str:
    override = os.environ.get("A02_IP")
    if override:
        path = Path(override)
        source = path / "src/IndividualProgressionSpells.cpp" if path.is_dir() else path
        return source.read_text(encoding="utf-8")
    with urllib.request.urlopen(IP_URL, timeout=60) as response:
        return response.read().decode("utf-8")


class HunterPetAutocastCacheTests(unittest.TestCase):
    def test_compiled_policy(self):
        ran = policy_program()
        self.assertEqual(ran["code"], 0)
        self.assertIn("A02_S4_POLICY_OK", ran["stdout"])
        self.assertNotIn("A02_S4_POLICY_FAIL", ran["stderr"])

    def test_config_defaults_off_and_loader_registers_it(self):
        self.assertIn("NaxxramasCore.HunterPet.AutocastCache.Enabled = 0\n", CONF)
        self.assertNotIn("NaxxramasCore.HunterPet.AutocastCache.Enabled = 1", CONF)
        self.assertIn("NaxxramasCore.HunterPet.AutocastCache.OptionalSpellIds = \"\"", CONF)
        self.assertIn('GetOption<bool>(EnabledConfigKey, false)', SOURCE)
        self.assertIn("void AddHunterPetAutocastCacheScripts();", LOADER)
        self.assertEqual(LOADER.count("AddHunterPetAutocastCacheScripts();"), 2)

    def test_module_hooks_and_pet_writes(self):
        for needle in (
            "OnPetAddToWorld",
            "OnInitStatsForLevel",
            "isBeingLoaded",
            "ToggleAutocast(info, action.desiredOn)",
            "SetSpellAutocast(info, action.desiredOn)",
            "PetSpellInitialize",
            "PLAYERHOOK_ON_SAVE",
            "ChooseLoadSnapshot",
            "PlanApply",
            "VerifiedCacheRows",
            "AllowCacheWrite",
            "HUNTER_PET",
            "CLASS_HUNTER",
            "AccountVerdict::ConfirmedHuman",
            "CustomData.GetDefault<PetAutocastCacheCycle>",
            "std::atomic<bool> FeatureEnabled",
            "pet_spell",
            "CacheTableName",
        ):
            self.assertIn(needle, SOURCE, needle)
        toggle_at = SOURCE.index("ToggleAutocast(info, action.desiredOn)")
        bar_at = SOURCE.index("SetSpellAutocast(info, action.desiredOn)")
        init_at = SOURCE.index("PetSpellInitialize")
        self.assertLess(toggle_at, bar_at)
        self.assertLess(bar_at, init_at)
        self.assertIn("UsesProcessGlobalPetMap", HEADER)
        self.assertNotIn("unordered_map", SOURCE)
        self.assertNotIn("GET_PLAYERBOT_AI", SOURCE)
        self.assertNotIn("IndividualProgression.h", SOURCE)
        self.assertNotIn("Playerbots.h", SOURCE)
        self.assertNotIn("CanPacketReceive", SOURCE)

    def test_sql_is_present_and_not_applied(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS `mod_naxxramas_hunter_pet_autocast`", SQL)
        self.assertIn("`pet_number`", SQL)
        self.assertIn("`spell_first`", SQL)
        self.assertIn("`active`", SQL)
        self.assertIn("DO NOT APPLY", SQL)
        self.assertIn("back up", SQL.lower())
        self.assertNotIn("INSERT INTO `pet_spell`", SQL)
        self.assertNotIn("UPDATE `pet_spell`", SQL)
        for path in (ROOT / "scripts").rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "mod_naxxramas_hunter_pet_autocast" in text:
                self.fail(path.name)

    def test_workflow_reads_contents_and_pins_both_cores(self):
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotIn("upload-artifact", WORKFLOW)
        self.assertNotIn("actions/upload", WORKFLOW)
        self.assertIn(CORE_OLD, WORKFLOW)
        self.assertIn(CORE_NEW, WORKFLOW)
        self.assertIn(IP_SHA, WORKFLOW)
        self.assertIn("HunterPetAutocastCache.cpp", WORKFLOW)
        self.assertIn("NaxxramasCore.HunterPet.AutocastCache.Enabled = 0", WORKFLOW)

    def test_research_labels_and_boundaries(self):
        for label in ("VERIFIED", "POTENTIAL ISSUE", "UNKNOWN", "NOT TESTED"):
            self.assertIn(label, RESEARCH)
        self.assertIn("default off", RESEARCH.lower())
        self.assertIn("DO NOT APPLY", RESEARCH)
        self.assertIn("no one-time migration", RESEARCH.lower())
        self.assertIn("Bad Manner", RESEARCH)
        self.assertIn("26090", RESEARCH)
        self.assertIn("26094", RESEARCH)
        self.assertIn("Pet.cpp:1810", RESEARCH)
        self.assertIn("PetHandler.cpp:1002", RESEARCH)

    def test_pinned_ip_still_resets_with_learn_default(self):
        source = load_ip_source()
        self.assertIn("if (sIndividualProgression->isBotAccount(player))", source)
        self.assertIn("pet->learnSpell(keepId);", source)
        self.assertIn("pet->unlearnSpell(id, false, true);", source)
        delays = re.findall(r"CalculateTime\((\d+)\)", source)
        self.assertEqual(delays, ["200", "200"])
        self.assertIn("_attempts < 10", source)
        self.assertEqual(source.count("sScriptMgr"), 0)

    def test_header_ids_match_the_documented_split(self):
        self.assertIn("26090  /* Pummel */", HEADER)
        self.assertIn("26094, /* Thunderstomp */", HEADER)
        self.assertIn("24423, /* Demoralizing Screech (Screech chain) */", HEADER)
        self.assertIn("BadAttitudeFirstRank = 50433", HEADER)
        self.assertIn("Bad Manner has no 3.3.5a spell", HEADER)
        self.assertNotIn("93433", HEADER)


if __name__ == "__main__":
    unittest.main()
