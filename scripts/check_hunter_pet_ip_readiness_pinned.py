#!/usr/bin/env python3
"""Pinned, source-only IP Hunter pet reconciliation ordering audit.

This deliberately documents a BLOCKER rather than producing a readiness
signal. It never accesses a live database, executes an IP event, mutates
any pet, or touches core/IP/Playerbots source.
"""
import argparse
from pathlib import Path


def source(root, relative):
    return (root / relative).read_text(encoding="utf-8")


def section(text, start, end):
    assert text.count(start) == 1, "Pinned upstream source moved: " + start
    assert end in text.split(start, 1)[1], "Missing end of pinned source section"
    return text.split(start, 1)[1].split(end, 1)[0]


def check(core, ip):
    code = source(ip, "src/IndividualProgressionSpells.cpp")
    pet_script = section(code, "class IndividualPlayerProgression_PetScript : public PetScript",
                         "class IndividualPlayerProgression_UnitScript : public UnitScript")
    for expected in (
        'PENDING_CHECK_KEY = "ipp_PendingPetSpellCheck"',
        "pending->pending = true;",
        "if (pending->pending)",
        "void OnPetAddToWorld(Pet* pet) override",
        "void OnInitStatsForLevel(Guardian* guardian, uint8 /*petlevel*/) override",
        "new DelayedPetSpellCheck(owner->GetGUID())",
        "pet->m_Events.CalculateTime(200)",
        "if (pet->isBeingLoaded() && _attempts < 10)",
        "new DelayedPetSpellCheck(_ownerGuid, _attempts + 1)",
        "if (player->getClass() == CLASS_HUNTER)",
        "sIndividualProgression->checkHunterPetSpells(player);",
    ):
        assert expected in pet_script, "IP reconciliation contract changed: " + expected

    # This exact ordering forbids reading pending=false as IP finished.
    cleared = "pet->CustomData.GetDefault<PendingPetSpellCheck>(PENDING_CHECK_KEY)->pending = false;"
    call = "sIndividualProgression->checkHunterPetSpells(player);"
    assert pet_script.index(cleared) < pet_script.index(call), (
        "Re-review: IP pending-flag / reconciliation ordering changed")

    # Native pet loading and event-queue progression remain independent.
    pet_cpp = source(core, "src/server/game/Entities/Pet/Pet.cpp")
    pet_update = section(pet_cpp, "void Pet::Update(uint32 diff)",
                         "void Pet::CastPendingSpell()")
    assert "if (m_loading)" in pet_update
    assert "Creature::Update(diff);" in pet_update
    world_obj = source(core, "src/server/game/Entities/Object/Object.cpp")
    world_update = section(world_obj, "void WorldObject::Update(uint32 diff)",
                           "void WorldObject::setActive(bool on)")
    assert "m_Events.Update(diff);" in world_update
    pet_hooks = source(core, "src/server/game/Scripting/ScriptDefines/PetScript.h")
    assert "OnPetAddToWorld(Pet*" in pet_hooks

    print("PASS: IP delayed pet spell check is scheduled on pet event clock.")
    print("PASS: IP pending flag resets BEFORE Hunter spell reconciliation.")
    print("PASS: native m_loading flag is not an IP completion signal.")
    print("GATE BLOCKED: no validated module-only post-IP completion callback.")
    print("Source-only; no runtime IP execution or autocast restoration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--ip", type=Path, required=True)
    args = parser.parse_args()
    check(args.core.resolve(), args.ip.resolve())
