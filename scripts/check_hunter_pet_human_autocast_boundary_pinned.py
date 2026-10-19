#!/usr/bin/env python3
"""Pinned source contract for HUMAN Hunter autocast loss, not a repair.

Only reads exact checkout files. Does not open a DB, set autocast, change bots
or claim that IP caused any particular real player's lost setting.
"""
import argparse
from pathlib import Path


def between(source: str, first: str, last: str) -> str:
    if source.count(first) != 1:
        raise AssertionError("Ambiguous/missing source boundary: " + first)
    tail = source.split(first, 1)[1]
    if last not in tail:
        raise AssertionError("Missing ending boundary: " + last)
    return tail.split(last, 1)[0]


def check(core: Path, ip: Path) -> None:
    pet = (core / "src/server/game/Entities/Pet/Pet.cpp").read_text("utf-8")
    db = (core / "src/server/database/Database/Implementation/CharacterDatabase.cpp").read_text("utf-8")
    hooks = (core / "src/server/game/Scripting/ScriptDefines/PetScript.h").read_text("utf-8")
    charm = (core / "src/server/game/Entities/Unit/CharmInfo.cpp").read_text("utf-8")
    charm_header = (core / "src/server/game/Entities/Unit/CharmInfo.h").read_text("utf-8")
    player_core = (core / "src/server/game/Entities/Player/Player.cpp").read_text("utf-8")
    ipp = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")

    loaded = between(pet, "void Pet::_LoadSpells(", "void Pet::_SaveSpells(")
    saved = between(pet, "void Pet::_SaveSpells(", "void Pet::_LoadAuras(")
    toggled = between(pet, "void Pet::ToggleAutocast(", "bool Pet::IsPermanentPetFor(")
    added = between(pet, "bool Pet::addSpell(", "bool Pet::learnSpell(")
    load_pet = between(pet, "bool Pet::LoadPetFromDB(", "void Pet::SavePetToDB(")
    reconcile = between(ipp, "void IndividualProgression::checkHunterPetSpells(",
                        "void IndividualProgression::checkWarlockPetSpells(")
    delayed = between(ipp, "class DelayedPetSpellCheck : public BasicEvent",
                      "class IndividualPlayerProgression_UnitScript")

    for marker in (
        "ActiveStates(fields[1].Get<uint8>())",
        "PETSPELL_UNCHANGED",
    ):
        assert marker in loaded, "Native spell reload changed: " + marker
    for marker in (
        "CHAR_DEL_PET_SPELLS",
        "CHAR_INS_PET_SPELL",
        "stmt->SetData(2, itr->second.active);",
    ):
        assert marker in saved, "Native active save changed: " + marker
    for stmt in (
        'SELECT spell, active FROM pet_spell WHERE guid = ?',
        'INSERT INTO pet_spell (guid, spell, active) VALUES (?, ?, ?)',
    ):
        assert stmt in db, "Character DB pet_spell schema changed: " + stmt
    for marker in (
        "itr->second.active = ACT_ENABLED;",
        "itr->second.active = ACT_DISABLED;",
    ):
        assert marker in toggled, "Native explicit ON/OFF changed: " + marker
    for marker in (
        "if (active == ACT_DECIDE)",
        "newspell.active = ACT_DISABLED;",
        "newspell.active = petSpell.active;",
    ):
        assert marker in added, "Default/rank inheritance changed: " + marker
    assert added.index("newspell.active = ACT_DISABLED;") < added.index(
        "newspell.active = petSpell.active;")
    for marker in (
        "if (sIndividualProgression->isBotAccount(player))",
        "pet->unlearnSpell(id, false, true);",
        "pet->learnSpell(keepId);",
    ):
        assert marker in reconcile, "IP human reconciliation changed: " + marker
    assert reconcile.index("pet->unlearnSpell(id, false, true);") < reconcile.index(
        "pet->learnSpell(keepId);")
    for marker in (
        "m_loading = false;",
        "_LoadSpells(holder.GetPreparedResult(PetLoadQueryHolder::SPELLS));",
        "map->AddToMap(ToCreature(), true);",
    ):
        assert marker in load_pet, "Async pet loading changed: " + marker
    assert load_pet.index("map->AddToMap(ToCreature(), true);") < load_pet.index(
        "_LoadSpells(holder.GetPreparedResult(PetLoadQueryHolder::SPELLS));")
    # Critical repeat-summon candidate: after native stored spell active values
    # are reloaded, the core explicitly runs level-family spell initialization
    # again. This may add a different spell rank (preserving ON only for some
    # native direct higher-rank paths) before IP's delayed keepId pruning.
    # A pet observed losing state every summon may therefore still encounter
    # IP remove/relearn even without a new player training action.
    assert (load_pet.index(
        "_LoadSpells(holder.GetPreparedResult(PetLoadQueryHolder::SPELLS));") <
        load_pet.index("InitLevelupSpellsForLevel();") <
        load_pet.rindex("m_loading = false;"))
    init_family = between(pet, "void Pet::InitLevelupSpellsForLevel()",
                          "bool Pet::unlearnSpell(")
    assert "sSpellMgr->GetPetLevelupSpellList(GetCreatureTemplate()->family)" in init_family
    assert "learnSpell(itr->second);" in init_family
    assert "sSpellMgr->GetPetDefaultSpellsEntry(petSpellsId)" in init_family
    assert "learnSpell(spellInfo->Id);" in init_family

    assert "pet->isBeingLoaded() && _attempts < 10" in delayed
    assert "sIndividualProgression->checkHunterPetSpells(player);" in delayed
    # Native autocast is represented twice: PetSpell.active + CharmInfo
    # actionbar slot type. A correction changing only PetSpell.active may be
    # undone by CleanupActionBar or appear wrong in SMSG_PET_SPELLS.
    cleanup = between(pet, "void Pet::CleanupActionBar()", "void Pet::InitPetCreateSpells()")
    setbar = between(charm, "void CharmInfo::SetSpellAutocast(",
                      "void CharmInfo::SetIsCommandAttack(")
    publish = between(player_core, "void Player::PetSpellInitialize()",
                      "void Player::PossessSpellInitialize()")
    for marker in (
        "ToggleAutocast(spellInfo, ab->GetType() == ACT_ENABLED);",
        "m_charmInfo->SetActionBar",
    ):
        # Cleanup specifically reads actionbar type into native autocast.
        # SetActionBar itself is used elsewhere and is not required inside
        # CleanupActionBar.
        if marker.startswith("ToggleAutocast"):
            assert marker in cleanup, "Pet actionbar cleanup no longer syncs active spell"
    assert "PetActionBar[i].SetType(state ? ACT_ENABLED : ACT_DISABLED);" in setbar
    assert "void SetSpellAutocast(SpellInfo const* spellInfo, bool state);" in charm_header
    assert "charmInfo->BuildActionBar(&data);" in publish
    assert "MAKE_UNIT_ACTION_BUTTON(itr->first, itr->second.active)" in publish
    assert "pet->m_spells.begin()" in publish

    for prohibited in ("OnPetBeforeUnlearnSpell", "OnPetAfterLearnSpell",
                       "OnPetSpellReconciled", "OnIPPetReconciled"):
        assert prohibited not in hooks, "Review newly available native hook: " + prohibited
    assert "virtual void OnPetAddToWorld(" in hooks
    print("PASS: human pet's spell ON/OFF already persists through native pet_spell.active.")
    print("PASS: native higher-rank replacement inherits old state; new spell defaults OFF.")
    print("PASS: IP's human-Hunter reconciliation may remove old rank before new rank.")
    print("PASS: AddToWorld precedes async spell load, and IP delayed check has no explicit completion hook.")
    print("PASS: native async load reinitializes level/default spells before delayed IP legal-rank pruning.")
    print("PASS: native PetSpell active and CharmInfo actionbar have separate synchronisation paths.")
    print("BLOCKED: root cause on real player and module-only atomic handoff NOT demonstrated.")
    print("No player data/character DB accessed; no Playerbot, IP, core or pet mutation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--ip", type=Path, required=True)
    args = parser.parse_args()
    check(args.core.resolve(), args.ip.resolve())
