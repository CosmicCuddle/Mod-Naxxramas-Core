#!/usr/bin/env python3
"""Fail-closed source contract for exact pinned IP per-character Hunter stage.

This inspects only checked-out source; no imports or runtime calls into IP,
account database access, writes, spell changes or readiness claim.
"""
import argparse
from pathlib import Path
import re


def between(code, first, next_one):
    assert code.count(first) == 1, "Pinned source changed: " + first
    section = code.split(first, 1)[1]
    assert next_one in section, "Missing expected end: " + next_one
    return section.split(next_one, 1)[0]


def check(ip_root):
    core = (ip_root / "src/IndividualProgression.cpp").read_text("utf-8")
    hdr = (ip_root / "src/IndividualProgression.h").read_text("utf-8")
    pet = (ip_root / "src/IndividualProgressionSpells.cpp").read_text("utf-8")

    from_quests = between(core,
                          "uint8 IndividualProgression::GetPlayerProgressionFromQuests(",
                          "bool IndividualProgression::hasPassedProgression(")
    assert "if (!player || !player->IsInWorld())" in from_quests
    assert "for (uint8 i = PROGRESSION_MOLTEN_CORE; i <= PROGRESSION_WOTLK_TIER_5; ++i)" in from_quests
    assert "uint32 PROGRESSION_QUEST = 66000 + i;" in from_quests
    assert "player->GetQuestStatus(PROGRESSION_QUEST) == QUEST_STATUS_REWARDED" in from_quests
    assert "progressionLevel = i;" in from_quests
    assert "return progressionLevel;" in from_quests

    passed = between(core, "bool IndividualProgression::hasPassedProgression(",
                     "bool IndividualProgression::isBeforeProgression(")
    assert "if (!enabled || !state || !player || !player->IsInWorld())" in passed
    assert "if (progressionLimit && (state > progressionLimit))" in passed
    assert "GetPlayerProgressionFromQuests(player) >= state" in passed
    assert "GetAccountProgression(" not in passed

    bot = between(core, "bool IndividualProgression::isBotAccount(",
                  "bool IndividualProgression::isNormalAccount(")
    assert "AccountMgr::GetName(player->GetSession()->GetAccountId(), accountName)" in bot
    assert "std::regex_match(accountName, botAccountsRegex)" in bot
    assert "botAccountsRegex" in bot

    progression = between(hdr, "enum ProgressionState : uint8",
                          "enum RandomDungeonIds")
    for constant, value in (("PROGRESSION_MOLTEN_CORE", 1),
                            ("PROGRESSION_BLACKWING_LAIR", 3),
                            ("PROGRESSION_PRE_TBC", 8),
                            ("PROGRESSION_TBC_TIER_5", 13),
                            ("PROGRESSION_WOTLK_TIER_5", 18)):
        assert re.search(r"\b" + constant + r"\s*=\s*" + str(value) + r"\b",
                         progression), "Pinned IP stage enum changed: " + constant

    check_hunter = between(pet, "void IndividualProgression::checkHunterPetSpells(",
                           "void IndividualProgression::checkWarlockPetSpells(")
    assert "if (!player || !player->IsInWorld() || !VanillaHunterPets)" in check_hunter
    assert "if (sIndividualProgression->isBotAccount(player))" in check_hunter
    assert "if (player->getClass() != CLASS_HUNTER)" in check_hunter
    assert "hasPassedProgression(player, PROGRESSION_TBC_TIER_5)" in check_hunter
    assert "hasPassedProgression(player, PROGRESSION_PRE_TBC)" in check_hunter
    assert "if (player->HasSpell(*it))" in check_hunter
    assert "keepId = *it - 600000;" in check_hunter

    conf = core
    assert 'GetOption<bool>("IndividualProgression.VanillaHunterPets", true)' in conf
    assert 'GetOption<uint8>("IndividualProgression.ProgressionLimit", 0)' in conf

    print("PASS: owner character rewarded hidden quests (66000 + tier) select stage.")
    print("PASS: milestone guard includes IP enabled / progressionLimit / in-world.")
    print("PASS: account progression is NOT used for Hunter spell eligibility.")
    print("PASS: IP skips configured bot accounts and uses Hunter dummy knowledge.")
    print("BLOCKED: source stage evidence is NOT runtime stage, native DBC, or IP readiness.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=Path, required=True)
    args = parser.parse_args()
    check(args.ip.resolve())
