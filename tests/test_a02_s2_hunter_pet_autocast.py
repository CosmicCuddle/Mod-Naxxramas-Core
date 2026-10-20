"""Policy tests for the A02 S2 hunter-pet autocast restore.

The compiled program is tests/a02_s2_hunter_pet_autocast_policy_tests.cpp
against src/Systems/HunterPetAutocastRestore.h. The Individual Progression
contract is read from the pinned commit. A pass is not an in-game summon,
relog, or rank change.
"""
from __future__ import annotations

import os
import re
import subprocess
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "src/Systems/HunterPetAutocastRestore.h").read_text(encoding="utf-8")
SOURCE = (ROOT / "src/Systems/HunterPetAutocastRestore.cpp").read_text(encoding="utf-8")
RESEARCH = (ROOT / "docs/research/a02-s2-hunter-pet-autocast-restore.md").read_text(encoding="utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/a02-s2-hunter-pet-autocast.yml").read_text(encoding="utf-8")
POLICY = ROOT / "tests/a02_s2_hunter_pet_autocast_policy_tests.cpp"

IP_SHA = "4ff4b5fcc1480348f058c632573143e62d4e3a41"
IP_URL = (
    "https://raw.githubusercontent.com/Grimfeather/mod-individual-progression/"
    f"{IP_SHA}/src/IndividualProgressionSpells.cpp"
)
CORE_OLD = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
CORE_NEW = "8daffdabe9202c228e45d833c9a1d399597a15cd"
PLAYERBOTS = "037c01418b5d01506917a3db9b44fd56ac5f965c"

_POLICY: dict[str, object] = {}


def policy_program() -> dict[str, object]:
    if _POLICY:
        return _POLICY
    binary = Path("/tmp/a02_s2_hunter_pet_autocast_policy_tests")
    compile_cmd = [
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
    ]
    compiled = subprocess.run(compile_cmd, capture_output=True, text=True)
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


def parse_ip_contract(source: str) -> dict[str, object]:
    """Fail unless DelayedPetSpellCheck still has one call site, 200ms, and cap 10."""
    if source.count("checkHunterPetSpells(") != 2:
        raise AssertionError("checkHunterPetSpells entry point count changed")
    call = "sIndividualProgression->checkHunterPetSpells(player);"
    if source.count(call) != 1:
        raise AssertionError("DelayedPetSpellCheck is no longer the only caller")

    start = source.find("class DelayedPetSpellCheck")
    end = source.find("class IndividualPlayerProgression_UnitScript")
    if start < 0 or end < start:
        raise AssertionError("DelayedPetSpellCheck class bounds changed")
    body = source[start:end]
    if call not in body:
        raise AssertionError("hunter pet check is outside DelayedPetSpellCheck::Execute")
    execute = body.find("bool Execute(")
    if execute < 0 or body.find(call) < execute:
        raise AssertionError("call is not inside Execute")

    delays = re.findall(r"CalculateTime\((\d+)\)", source)
    if delays != ["200", "200"]:
        raise AssertionError(f"200ms cadence changed: {delays}")
    caps = re.findall(r"_attempts < (\d+)", source)
    if caps != ["10"]:
        raise AssertionError(f"10-try cap changed: {caps}")
    if source.count("ScheduleDelayedSpellCheck(pet);") != 2:
        raise AssertionError("OnPetAddToWorld / OnInitStatsForLevel schedule count changed")
    if "void OnPetAddToWorld" not in source or "void OnInitStatsForLevel" not in source:
        raise AssertionError("pet hooks renamed")
    if source.count("pet->m_Events.AddEvent") != 2 or body.count("pet->m_Events.AddEvent") != 1:
        raise AssertionError("event is no longer queued on pet->m_Events")
    if "isBeingLoaded()" not in body:
        raise AssertionError("loading poll removed")
    return {"delay_ms": 200, "attempt_cap": 10, "caller": "DelayedPetSpellCheck::Execute"}


class HunterPetAutocastRestoreTests(unittest.TestCase):
    def test_compiled_policy(self):
        ran = policy_program()
        self.assertEqual(ran["code"], 0)
        self.assertIn("A02_S2_POLICY_OK", ran["stdout"])
        self.assertNotIn("A02_S2_POLICY_FAIL", ran["stderr"])

    def test_config_defaults_off_and_loader_registers_it(self):
        self.assertIn("NaxxramasCore.HunterPetAutocastRestore.Enabled = 0\n", CONF)
        self.assertNotIn("NaxxramasCore.HunterPetAutocastRestore.Enabled = 1", CONF)
        self.assertIn('GetOption<bool>(EnabledConfigKey, false)', SOURCE)
        self.assertIn("void AddHunterPetAutocastRestoreScripts();", LOADER)
        self.assertEqual(LOADER.count("AddHunterPetAutocastRestoreScripts();"), 2)

    def test_module_uses_the_pinned_hooks_and_pet_writes(self):
        for needle in (
            "OnPetAddToWorld",
            "OnInitStatsForLevel",
            "ToggleAutocast(current, true)",
            "SetSpellAutocast(current, true)",
            "PetSpellInitialize",
            "PETSPELL_REMOVED",
            "DecideRestore",
            "ClassifyAccount",
            "CheckLiveIdentity",
            "ScheduleCycle",
            "IsDuringRemoveFromWorld",
            "IsLoggingOut",
            "GetRawValue",
            "FirstPollDelayMs",
            "BotAccountsRegexKey",
            "HUNTER_PET",
            "CLASS_HUNTER",
            "AccountVerdict::ConfirmedHuman",
            "RestoreOutcome::ApplyOn",
        ):
            self.assertIn(needle, SOURCE, needle)
        apply_at = SOURCE.index("RestoreOutcome::ApplyOn")
        toggle_at = SOURCE.index("ToggleAutocast(current, true)")
        self.assertLess(apply_at, toggle_at)
        self.assertNotIn("ToggleAutocast(previous, false)", SOURCE)
        self.assertNotIn("ToggleAutocast(current, false)", SOURCE)
        self.assertNotIn("ToggleAutocast(current, plan.desiredOn)", SOURCE)
        self.assertNotIn("CanPacketReceive", SOURCE)
        self.assertNotIn("CMSG_PET_SPELL_AUTOCAST", SOURCE)
        self.assertNotIn("PlanRestores", SOURCE)
        self.assertNotIn("AccountIsBot", SOURCE)
        self.assertNotIn("PetNumberMatches", SOURCE)
        self.assertIn('BotAccountsRegexKey = "IndividualProgression.BotAccountsRegex"', HEADER)
        self.assertIn("enum class AccountVerdict", HEADER)
        self.assertIn("UnvalidatedPacketDrivesToggle", HEADER)
        self.assertIn("CounterexampleDelayedLoadThenSave", HEADER)
        self.assertIn("RuntimeFaithfulIpSaveThenPoll", HEADER)
        self.assertIn("CommitSnapshotRuntime", HEADER)
        self.assertIn("ClearPendingAllowed", HEADER)
        self.assertIn("PetLifetimeStore", HEADER)
        self.assertIn("BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE", HEADER)
        self.assertIn("GetOption<std::string>(BotAccountsRegexKey, DefaultBotAccountsRegex)", SOURCE)
        self.assertIn("std::atomic<bool> FeatureEnabled", SOURCE)
        self.assertIn("CustomData.GetDefault<PetAutocastCycle>", SOURCE)
        self.assertIn("ClearPendingIfBound", SOURCE)
        self.assertIn("GuidRaw(pet->GetGUID()) != bound.petGuid", SOURCE)
        self.assertIn("BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE", SOURCE)
        self.assertIn("literal false", SOURCE)
        self.assertNotIn("PetMemories", SOURCE)
        self.assertNotIn("unordered_map", SOURCE)
        self.assertNotIn("ForgetOwner", SOURCE)
        self.assertNotIn("uint64_t PreferenceSequence", SOURCE)
        self.assertNotIn("ClearPending(pet)", SOURCE)
        self.assertNotIn('AccountIsBot(found, accountName.c_str(), "^RNDBOT.*")', SOURCE)
        self.assertNotIn("GET_PLAYERBOT_AI", SOURCE)
        self.assertNotIn("IndividualProgression.h", SOURCE)
        self.assertNotIn("CharacterDatabase", SOURCE)
        self.assertNotIn(".sql", SOURCE)
        self.assertNotIn("Playerbots.h", SOURCE)
        self.assertNotIn("ServerScript.h", SOURCE)
        self.assertNotIn("PetPackets.h", SOURCE)

    def test_no_new_sql_under_the_module(self):
        sql_root = ROOT / "data" / "sql"
        self.assertTrue(sql_root.is_dir())
        # The hunter pet autocast cache table is manual SQL under docs/install.
        # Nothing that names it may sit under data/sql, at any depth.
        for path in sql_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix == ".sql" and "autocast" in path.name.lower():
                self.fail(path.name)
            if path.suffix == ".sql" and "mod_naxxramas_hunter_pet_autocast" in path.read_text(
                encoding="utf-8", errors="replace"
            ).lower():
                self.fail(str(path))

    def test_workflow_reads_contents_and_does_not_upload(self):
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotIn("upload-artifact", WORKFLOW)
        self.assertNotIn("actions/upload", WORKFLOW)
        self.assertIn(CORE_OLD, WORKFLOW)
        self.assertIn(CORE_NEW, WORKFLOW)
        self.assertIn(IP_SHA, WORKFLOW)
        self.assertIn(PLAYERBOTS, WORKFLOW)
        self.assertIn("HunterPetAutocastRestore.cpp", WORKFLOW)
        self.assertIn("NaxxramasCore.HunterPetAutocastRestore.Enabled = 0", WORKFLOW)

    def test_header_constants_match_the_pinned_cadence(self):
        self.assertIn("IpEventDelayMs = 200", HEADER)
        self.assertIn("IpLoadingAttemptCap = 10", HEADER)
        self.assertIn("RestoreLagMs = 150", HEADER)
        self.assertIn("SnapshotPollMs = 50", HEADER)

    def test_pinned_ip_contract(self):
        contract = parse_ip_contract(load_ip_source())
        self.assertEqual(contract["delay_ms"], 200)
        self.assertEqual(contract["attempt_cap"], 10)
        self.assertEqual(contract["caller"], "DelayedPetSpellCheck::Execute")
        self.assertIn("constexpr uint32_t IpEventDelayMs = 200", HEADER)
        self.assertIn("constexpr uint8_t IpLoadingAttemptCap = 10", HEADER)

    def test_research_records_counterexample_and_hook_search(self):
        self.assertIn("EXPERIMENTAL", RESEARCH)
        self.assertIn("not functional S2 completion", RESEARCH)
        self.assertIn("not CS01 acceptance", RESEARCH)
        self.assertIn("CounterexampleDelayedLoadThenSave", RESEARCH)
        self.assertIn("explicit ON", RESEARCH)
        self.assertIn("explicit OFF", RESEARCH)
        self.assertIn("PendingPetSpellCheck is not a public hook", RESEARCH)
        self.assertIn("No synchronous before/after IP rank-reconciliation hook exists", RESEARCH)
        self.assertIn("void OnPetAddToWorld(Pet* pet)", RESEARCH)
        self.assertIn("PetScript.h:58", RESEARCH)
        self.assertIn("void checkHunterPetSpells(Player* player)", RESEARCH)
        self.assertIn("IndividualProgression.h:430", RESEARCH)
        self.assertIn("IndividualProgressionSpells.cpp:1252", RESEARCH)
        self.assertIn("TogglePetSpellAutoCastAction::Execute", RESEARCH)
        self.assertIn("PetsAction.cpp:342", RESEARCH)
        self.assertIn("POTENTIAL ISSUE", RESEARCH)
        self.assertIn("m_autospells", RESEARCH)
        self.assertIn("NOT TESTED", RESEARCH)
        self.assertIn("BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE", RESEARCH)
        self.assertIn("RuntimeFaithfulIpSaveThenPoll", RESEARCH)
        self.assertIn("literal false", RESEARCH)
        self.assertIn("Pet::CustomData", RESEARCH)
        self.assertIn("std::atomic<bool>", RESEARCH)
        self.assertIn("ClearPendingAllowed", RESEARCH)

    def test_contract_fails_when_the_cap_or_cadence_or_caller_changes(self):
        source = load_ip_source()
        parse_ip_contract(source)
        with self.assertRaises(AssertionError):
            parse_ip_contract(source.replace("_attempts < 10", "_attempts < 11", 1))
        with self.assertRaises(AssertionError):
            parse_ip_contract(source.replace("CalculateTime(200)", "CalculateTime(250)", 1))
        with self.assertRaises(AssertionError):
            parse_ip_contract(source.replace(
                "sIndividualProgression->checkHunterPetSpells(player);",
                "sIndividualProgression->checkWarlockPetSpells(player);",
                1,
            ))


if __name__ == "__main__":
    unittest.main()
