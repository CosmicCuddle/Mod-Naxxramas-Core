#!/usr/bin/env python3
"""Read-only, pinned public C++ interface contract for an UNAPPLIED IP patch.

Checks the exact core signatures consumed by the review proposal, not the
correctness, buildability, or gameplay effects of any modified IP code.
"""
from pathlib import Path
import argparse


def require(text: str, marker: str, where: str) -> None:
    if marker not in text:
        raise AssertionError(f"{where}: absent or changed: {marker}")


def check(core: Path, proposal: Path) -> None:
    def read(relative: str) -> str:
        return (core / relative).read_text(encoding="utf-8")

    pet_h = read("src/server/game/Entities/Pet/Pet.h")
    pet_cpp = read("src/server/game/Entities/Pet/Pet.cpp")
    charm_h = read("src/server/game/Entities/Unit/CharmInfo.h")
    charm_cpp = read("src/server/game/Entities/Unit/CharmInfo.cpp")
    player_h = read("src/server/game/Entities/Player/Player.h")
    info_h = read("src/server/game/Spells/SpellInfo.h")
    patch = proposal.read_text(encoding="utf-8")

    public_pet = pet_h.split("public:", 1)[1].split("protected:", 1)[0]
    for marker in (
        "PetSpellMap     m_spells;",
        "bool learnSpell(uint32 spell_id);",
        "bool unlearnSpell(uint32 spell_id, bool learn_prev, bool clear_ab = true);",
        "void ToggleAutocast(SpellInfo const* spellInfo, bool apply);",
        "bool HasSpell(uint32 spell) const override;",
        "PetType getPetType() const",
        "bool isBeingLoaded() const override",
    ):
        require(public_pet, marker, "public Pet API")

    for marker in (
        "void SetSpellAutocast(SpellInfo const* spellInfo, bool state);",
        "UnitActionBarEntry const* GetActionBarEntry(uint8 index) const",
        "bool IsActionBarForSpell() const",
        "uint32 GetAction() const",
    ):
        require(charm_h, marker, "CharmInfo/actionbar API")
    require(charm_cpp, "void CharmInfo::SetSpellAutocast(", "actionbar implementation")
    require(charm_cpp, "PetActionBar[i].SetType(state ? ACT_ENABLED : ACT_DISABLED);",
            "actionbar state write")
    require(player_h, "void PetSpellInitialize();", "Player public pet refresh")
    require(info_h, "bool IsAutocastable() const;", "native spell legality")
    require(info_h, "bool IsDifferentRankOf(SpellInfo const* spellInfo) const;",
            "native spell-chain comparison")
    for marker in (
        "bool Pet::learnSpell(uint32 spell_id)",
        "bool Pet::HasSpell(uint32 spell) const",
        "void Pet::ToggleAutocast(SpellInfo const* spellInfo, bool apply)",
        "void Pet::CleanupActionBar()",
    ):
        require(pet_cpp, marker, "native Pet implementation")

    # Review diff must not directly patch any core/SQL/runtime-module files.
    assert patch.count("diff --git ") == 1
    require(patch, "diff --git a/src/IndividualProgressionSpells.cpp "
                   "b/src/IndividualProgressionSpells.cpp",
            "IP proposal scope")
    for marker in (
        "pet->m_spells.find(id)",
        "oldInfo->IsDifferentRankOf(keepInfo)",
        "pet->learnSpell(keepId)",
        "pet->ToggleAutocast(keepInfo, enabled)",
        "charm->SetSpellAutocast(keepInfo, enabled)",
        "player->PetSpellInitialize();",
        "pet->GetGUID() != _petGuid",
        "if (pet->isBeingLoaded())",
    ):
        require(patch, marker, "review diff API usage")

    print("PASS: proposed IP patch references verified public pinned core C++ APIs.")
    print("PASS: review diff targets only IndividualProgressionSpells.cpp.")
    print("NOT TESTED: actual patched C++ compiler, runtime events or player ON/OFF.")
    print("No source changed, no server/game/DB/Playerbots access.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    args = parser.parse_args()
    check(args.core.resolve(), args.proposal.resolve())
