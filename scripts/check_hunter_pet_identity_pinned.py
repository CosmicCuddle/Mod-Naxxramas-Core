#!/usr/bin/env python3
"""Pinned, source-only Hunter pet identity safety audit. No SQL or runtime."""
import argparse
from pathlib import Path
import re


def read(core, path):
    return (core / path).read_text(encoding="utf-8")


def section(data, start, end):
    assert data.count(start) == 1, "Upstream source changed: " + start
    return data.split(start, 1)[1].split(end, 1)[0]


def check(core):
    mgr = read(core, "src/server/game/Globals/ObjectMgr.cpp")
    load = section(mgr, "void ObjectMgr::LoadPetNumber()",
                   "std::string ObjectMgr::GeneratePetNameLocale(")
    next_id = section(mgr, "uint32 ObjectMgr::GeneratePetNumber()",
                      "void ObjectMgr::LoadReputationRewardRate()")
    assert "SELECT MAX(id) FROM character_pet" in load
    assert "_hiPetNumber = fields[0].Get<uint32>() + 1;" in load
    assert "return ++_hiPetNumber;" in next_id

    pet = read(core, "src/server/game/Entities/Pet/Pet.cpp")
    tame = section(pet, "bool Pet::CreateBaseAtTamed(",
                   "/// @todo: Move stat mods code to pet passive auras")
    assert "sObjectMgr->GeneratePetNumber()" in tame
    normal_save = section(pet, "void Pet::SavePetToDB(",
                          "void Pet::DeleteFromDB(")
    assert "CHAR_DEL_CHAR_PET_BY_ID" in normal_save
    assert "CHAR_REP_CHAR_PET" in normal_save
    retired = section(pet, "void Pet::DeleteFromDB(",
                      "void Pet::setDeathState(")
    assert "CHAR_DEL_CHAR_PET_BY_ID" in retired

    ddl = read(core, "data/sql/base/db_characters/character_pet.sql")
    match = re.search(r"CREATE TABLE \x60character_pet\x60 \((.*?)\) ENGINE=InnoDB",
                      ddl, re.DOTALL)
    assert match is not None
    columns = set(re.findall(r"^\s*\x60([A-Za-z]+)\x60", match.group(1),
                             re.MULTILINE))
    expected = {"id", "entry", "owner", "modelid", "CreatedBySpell", "PetType",
                "level", "exp", "Reactstate", "name", "renamed", "slot",
                "curhealth", "curmana", "curhappiness", "savetime", "abdata"}
    assert columns == expected, "Re-review identity: pet table schema changed"
    assert "PRIMARY KEY (\x60id\x60)" in match.group(1)

    stable = read(core, "src/server/game/Entities/Pet/PetDefines.h")
    info = section(stable, "    struct PetInfo",
                   "    Optional<PetInfo> CurrentPet;")
    for field in ("PetNumber", "CreatureId", "Name", "ActionBar",
                  "Experience", "LastSaveTime", "CreatedBySpellId"):
        assert re.search(r"\b" + field + r"\b", info)
    assert not re.search(r"\b(Incarnation|Generation|BirthGuid|BirthUUID)\b",
                         info)

    # This hook is a *pre-create attempt* for an existing stable PetInfo.
    # It is not emitted by Pet::CreateBaseAtTamed, and has no post-load
    # success contract. Its absence cannot prove that a pet was freshly tamed.
    native_load = section(pet, "bool Pet::LoadPetFromDB(",
                          "bool Pet::CreateBaseAtTamed(")
    assert "GetLoadPetInfo(*petStable, petEntry, petnumber, current)" in native_load
    assert "sScriptMgr->OnPlayerBeforeLoadPetFromDB(" in native_load
    assert "if (!Create(guid, map" in native_load
    assert (native_load.index("GetLoadPetInfo(") <
            native_load.index("sScriptMgr->OnPlayerBeforeLoadPetFromDB(") <
            native_load.index("if (!Create(guid, map"))
    player_hooks = read(core, "src/server/game/Scripting/ScriptDefines/PlayerScript.h")
    assert "PLAYERHOOK_ON_BEFORE_LOAD_PET_FROM_DB" in player_hooks
    assert "OnPlayerBeforeLoadPetFromDB(Player*" in player_hooks

    hooks = read(core, "src/server/game/Scripting/ScriptDefines/PetScript.h")
    assert "OnPetAddToWorld(Pet*" in hooks
    assert not re.search(r"OnPet(Abandon|Retire|Delete|Save|RemoveFromWorld)\s*\(",
                         hooks)
    print("PASS: pinned native PetNumber can be recycled after deletion/restart")
    print("PASS: native normal save deletes/replaces pet row")
    print("PASS: pinned pet table and stable metadata lack a proven birth token")
    print("PASS: existing-pet load hook is BEFORE Create and does not prove success")
    print("GATE BLOCKED: no durable preference store or autocast restore permitted")
    print("Source-only: does NOT inspect a running core or characters database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    check(parser.parse_args().core.resolve())
