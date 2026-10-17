#!/usr/bin/env python3
"""Source-pinned, read-only audit of direct Playerbot pet autocast policy.

No Playerbot invocation or game server launched; no actor attribution from
packet hooks is inferred. Changing upstream sources fails this contract.
"""
import argparse
from pathlib import Path


def read(root, relative):
    return (root / relative).read_text("utf-8")


def between(source, start, end):
    assert source.count(start) == 1, "Pinned bot action changed: " + start
    block = source.split(start, 1)[1]
    assert end in block
    return block.split(end, 1)[0]


def check(root):
    pets = read(root, "src/Ai/Base/Actions/PetsAction.cpp")
    pet_header = read(root, "src/Ai/Base/Actions/PetsAction.h")
    botai = read(root, "src/Bot/PlayerbotAI.cpp")
    tame = read(root, "src/Ai/Base/Actions/TameAction.cpp")
    factory = read(root, "src/Bot/Factory/PlayerbotFactory.cpp")

    action = between(pets, "bool TogglePetSpellAutoCastAction::Execute(",
                     "bool PetAttackAction::Execute(")
    for required in (
        "Pet* pet = bot->GetPet();",
        "for (PetSpellMap::const_iterator itr = pet->m_spells.begin();",
        "itr->second.state == PETSPELL_REMOVED",
        "!spellInfo || !spellInfo->IsAutocastable()",
        "for (uint32 disabledSpell : disabledPetSpells)",
        "bool shouldApply = true;",
        "if (shouldApply != isAutoCast)",
        "pet->ToggleAutocast(spellInfo, shouldApply);",
    ):
        assert required in action, "Bot direct-policy source changed: " + required
    assert action.index("if (shouldApply != isAutoCast)") < (
        action.index("pet->ToggleAutocast(spellInfo, shouldApply);"))
    assert "static std::vector<uint32> disabledPetSpells" in pets
    for marker in ("PET_PROWL_1", "PET_PROWL_2", "PET_PROWL_3",
                   "PET_COWER", "PET_LEAP", "PET_SPELL_LOCK_1",
                   "PET_DEVOUR_MAGIC_1"):
        assert marker in pets, "Bot disabled list changed: " + marker
    assert 'Action(ai, "toggle pet spell")' in pet_header

    assert botai.count("pet->ToggleAutocast(spellInfo, !autocast);") >= 2
    assert "TellMaster(out);" in botai
    assert "pet->ToggleAutocast(spellInfo, true);" in tame
    assert "pet->ToggleAutocast(spellInfo, true);" in factory

    print("PASS: pinned bot action reasserts ON except its disabledPetSpells.")
    print("PASS: bot command, tame and factory paths call native ToggleAutocast directly.")
    print("BLOCKED: native/packet state cannot attribute AI versus human master intent.")
    print("Bot preference policy must be separate, with no automatic override of bot AI.")
    print("No Playerbots source edits, pet changes, config enable or SQL.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--playerbots", type=Path, required=True)
    args = parser.parse_args()
    check(args.playerbots.resolve())
