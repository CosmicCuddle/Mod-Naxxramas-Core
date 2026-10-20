#!/usr/bin/env python3
"""Read-only A02 pinned-core contract for accepted Hunter pet autocast paths.

PASS confirms a HAZARD, not a functional module-only solution. The two
validated client paths write pet spell/autocast state without a PetScript
post-acceptance callback, and RemovePet can save without OnPlayerSave.
No networking, database, spell, pet, item, or character writes are done.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


class SourceContractChanged(RuntimeError):
    """A pinned source shape changed; require a new human source audit."""


def body_of(source: str, signature: str) -> str:
    """Extract one reviewed C++ method's body by balanced braces."""
    if source.count(signature) != 1:
        raise SourceContractChanged(f"Expected exactly one {signature}")
    start = source.index(signature) + len(signature)
    brace = source.find("{", start)
    if brace < 0:
        raise SourceContractChanged(f"Missing method body for {signature}")
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise SourceContractChanged(f"Unclosed method body for {signature}")


PET_HOOKS = (
    "PETHOOK_ON_INIT_STATS_FOR_LEVEL",
    "PETHOOK_ON_CALCULATE_MAX_TALENT_POINTS_FOR_LEVEL",
    "PETHOOK_CAN_UNLEARN_SPELL_SET",
    "PETHOOK_CAN_UNLEARN_SPELL_DEFAULT",
    "PETHOOK_CAN_RESET_TALENTS",
    "PETHOOK_ON_PET_ADD_TO_WORLD",
    "PETHOOK_END",
)


def require(section: str, strings: tuple[str, ...], scope: str) -> None:
    for string in strings:
        if string not in section:
            raise SourceContractChanged(f"{scope} changed: expected {string!r}")


def check_accepted_autocast_paths(pet_handler: str, pet_script: str,
                                  player_cpp: str) -> dict[str, bool]:
    action = body_of(pet_handler, "void WorldSession::HandlePetSetAction(")
    autocast = body_of(
        pet_handler, "void WorldSession::HandlePetSpellAutocastOpcode(")
    removed = body_of(player_cpp, "void Player::RemovePet(")

    require(action, (
        "GetFirstControlled()",
        "ACT_ENABLED", "ACT_DISABLED",
        "pet->HasSpell(spell_id)",
        "((Pet*)pet)->ToggleAutocast(spellInfo, true);",
        "((Pet*)pet)->ToggleAutocast(spellInfo, false);",
        "charmInfo->SetActionBar(position[i], spell_id, ActiveStates(act_state));",
    ), "CMSG_PET_SET_ACTION")
    if not (action.index("ACT_ENABLED") <
            action.index("((Pet*)pet)->ToggleAutocast(spellInfo, true);") <
            action.index("((Pet*)pet)->ToggleAutocast(spellInfo, false);")):
        raise SourceContractChanged("CMSG_PET_SET_ACTION write order changed")

    require(autocast, (
        "GetCreatureOrPetOrVehicle", "GetGuardianPet()",
        "GetCharm()", "pet->HasSpell(packet.SpellID)",
        "spellInfo->IsAutocastable()",
        "summon->ToggleAutocast(spellInfo, packet.AutocastEnabled);",
        "charmInfo->SetSpellAutocast(spellInfo, packet.AutocastEnabled);",
    ), "CMSG_PET_SPELL_AUTOCAST")
    if not (autocast.index("pet->HasSpell(packet.SpellID)") <
            autocast.index("summon->ToggleAutocast(spellInfo, packet.AutocastEnabled);") <
            autocast.index("charmInfo->SetSpellAutocast(spellInfo, packet.AutocastEnabled);")):
        raise SourceContractChanged("CMSG_PET_SPELL_AUTOCAST validation order changed")

    hook_enum = re.search(r"\benum\s+PetHook\s*\{([^{}]*)\};", pet_script, re.S)
    if not hook_enum:
        raise SourceContractChanged("PetScript public hook enum changed")
    found_hooks = tuple(re.findall(r"\bPETHOOK_[A-Z_]+\b", hook_enum.group(1)))
    if found_hooks != PET_HOOKS:
        raise SourceContractChanged(
            "PetScript gained/changed hooks: inspect accepted-choice support")

    # This is a snapshot of the pinned source API, not a universal proof
    # that no unrelated script hooks or private fork customization exist.
    require(pet_script, ("virtual void OnPetAddToWorld(Pet*",),
            "public PetScript")
    require(removed, ("pet->SavePetToDB(mode);", "SetMinion(pet, false);"),
            "Player::RemovePet")
    if removed.index("pet->SavePetToDB(mode);") >= removed.index("SetMinion(pet, false);"):
        raise SourceContractChanged("RemovePet persistence order changed")

    return {
        "two_distinct_client_autocast_handlers_write_pet_state": True,
        "public_pet_script_has_no_accepted_autocast_hook": True,
        "remove_pet_directly_saves_before_detaching": True,
        "module_only_post_accepted_choice_and_dismiss_gate_proven": False,
        "safe_to_enable_hunter_pet_cache": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pet-handler", type=Path, required=True)
    parser.add_argument("--pet-script", type=Path, required=True)
    parser.add_argument("--player-cpp", type=Path, required=True)
    parser.add_argument("--core-sha", required=True)
    args = parser.parse_args()
    facts = check_accepted_autocast_paths(
        args.pet_handler.read_text(encoding="utf-8"),
        args.pet_script.read_text(encoding="utf-8"),
        args.player_cpp.read_text(encoding="utf-8"))
    print("PINNED A02 ACCEPTED-CHOICE HOOK HAZARD:", args.core_sha)
    for key, value in facts.items():
        print(" ", f"{key}={str(value).lower()}")
    print("PASS means A02 human Hunter autocast persistence remains BLOCKED.")
    print("NOT TESTED: compiled Worldserver, packet replay, SQL or player data.")


if __name__ == "__main__":
    main()
