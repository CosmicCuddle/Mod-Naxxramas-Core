#!/usr/bin/env python3
"""Pin Hunter autocast native producer blockers against exact IP/Playerbots source.

Read-only SOURCE contract, not a runtime event emitter. If upstream evolves,
fail and re-review its changed native evidence instead of assuming persistence
is now safe. No data, bot, pet, SQL or configuration mutations.
"""
import argparse
from pathlib import Path


def require(condition, message):
    if not condition:
        raise AssertionError("Pinned upstream boundary changed: " + message)


def unique_scope(text, first, last):
    require(text.count(first) == 1, first)
    tail = text.split(first, 1)[1]
    require(last in tail, last)
    return tail.split(last, 1)[0]


def check(ip, playerbots):
    spells = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")
    progression = (ip / "src/IndividualProgression.cpp").read_text("utf-8")
    pets = (playerbots / "src/Ai/Base/Actions/PetsAction.cpp").read_text("utf-8")
    bot_ai = (playerbots / "src/Bot/PlayerbotAI.cpp").read_text("utf-8")

    event = unique_scope(
        spells, "class DelayedPetSpellCheck : public BasicEvent",
        "class IndividualPlayerProgression_UnitScript"
    )
    require("new DelayedPetSpellCheck(owner->GetGUID())" in spells,
            "IP queues with owner GUID")
    for marker in (
        "explicit DelayedPetSpellCheck(ObjectGuid ownerGuid, uint8 attempts = 0)",
        "Player* player = ObjectAccessor::FindPlayer(_ownerGuid);",
        "Pet* pet = player->GetPet();",
        "if (pet->isBeingLoaded() && _attempts < 10)",
        "new DelayedPetSpellCheck(_ownerGuid, _attempts + 1)",
        "uint8      _attempts;",
        "ObjectGuid _ownerGuid;",
    ):
        require(marker in event, "IP delayed event: " + marker)
    require("_petGuid" not in event and "_petEventGeneration" not in event,
            "IP event has no original Pet identity/generation")
    pending = (
        "pet->CustomData.GetDefault<PendingPetSpellCheck>"
        "(PENDING_CHECK_KEY)->pending = false;"
    )
    reconcile = "sIndividualProgression->checkHunterPetSpells(player);"
    require(pending in event and reconcile in event, "IP pending/call markers")
    require(event.index(pending) < event.index(reconcile),
            "IP clears pending before void reconcile")

    hunter = unique_scope(
        spells, "void IndividualProgression::checkHunterPetSpells(Player* player)",
        "void IndividualProgression::checkWarlockPetSpells("
    )
    for marker in (
        "!player || !player->IsInWorld() || !VanillaHunterPets",
        "sIndividualProgression->isBotAccount(player)",
        "player->getClass() != CLASS_HUNTER",
        "PROGRESSION_TBC_TIER_5",
        "Pet* pet = player->GetPet();",
        "if (!pet)",
        "if (!familyEntry)",
        "return;",
    ):
        require(marker in hunter, "IP early return: " + marker)

    account = unique_scope(
        progression, "bool IndividualProgression::isBotAccount(Player* player)",
        "bool IndividualProgression::isNormalAccount("
    )
    require("AccountMgr::GetName(" in account,
            "IP bot account derives actual account name")
    require("std::regex_match(accountName, botAccountsRegex)" in account,
            "IP bot account regex matching")
    require(
        'sConfigMgr->GetOption<std::string>("IndividualProgression.BotAccountsRegex", "^RNDBOT.*")'
        in progression, "pinned default IP bot regex"
    )

    action = unique_scope(
        pets, "bool TogglePetSpellAutoCastAction::Execute(",
        "bool PetAttackAction::Execute("
    )
    require("for (PetSpellMap::const_iterator itr = pet->m_spells.begin();" in action,
            "Playerbots per-spell policy loop")
    require("pet->ToggleAutocast(spellInfo, shouldApply);" in action,
            "Playerbots AI default toggle")
    require("return toggled;" in action, "aggregate policy action outcome")
    require(bot_ai.count("pet->ToggleAutocast(spellInfo, !autocast);") >= 2,
            "at least two direct CastSpell native toggle paths")

    handle = unique_scope(
        bot_ai, "void PlayerbotAI::HandleCommand(uint32 type,",
        "void PlayerbotAI::HandleTeleportAck("
    )
    require("chatCommands.push_back(ChatCommandHolder(filtered, &fromPlayer, type));"
            in handle, "deferred master commands")
    require("helper.ParseChatCommand(command, owner)" in bot_ai,
            "deferred trigger dispatch")
    require("OnHunterPetSpellsReconciled" not in spells,
            "no established signed after-IP notification in pinned file")

    print("PASS: IP event still captures owner/retry only and resolves current Pet.")
    print("PASS: IP void early returns and effective account-name bot regex are pinned.")
    print("PASS: Playerbots has bot-default and two additional CastSpell native toggles.")
    print("PASS: Playerbots chat processing can be deferred after security filtering.")
    print("BLOCKED: no trusted native per-spell master/applied + IP ready producer proved.")
    print("This guard is a SOURCE audit, not a pet preference cache or restoration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=Path, required=True)
    parser.add_argument("--playerbots", type=Path, required=True)
    args = parser.parse_args()
    check(args.ip.resolve(), args.playerbots.resolve())
