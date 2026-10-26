#!/usr/bin/env python3
"""Read-only A02 pinned-core contract for accepted Hunter pet autocast paths.

PASS confirms a HAZARD, not a functional module-only solution. The two
validated client paths write pet spell/autocast state without a PetScript
post-acceptance callback, and RemovePet can save without OnPlayerSave.
No networking, database, spell, pet, item, or character writes are done.
"""
from __future__ import annotations

import argparse
import hashlib
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


# Independent CS02 review identified another pair of actual post-validation
# write sites. Both files are IDENTICAL across these two pinned Grimfeather
# source revisions; changing either file, even outside the method, requires
# a new human source audit. Git SHA-1 here is content provenance, not trust.
# Three additional externally observed acceptance/dismiss surfaces are also
# byte-identical at both reviewed Grimfeather source revisions. An extra
# unbraced early return, new script callback, or Player::RemovePet reordering
# must invalidate a pinned "hazard persists" interpretation even if the
# lexical source checker would still happen to find familiar substrings.
PINNED_ENTRY_BLOBS = {
    "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7": (
        "34f3070074e75cc6a83df3f0d7e74fe8a6fd6043",
        "f1455f20ca3a83e3fc38f0ba9c7dbff9d2faef46",
        "138e7eab4905ec366338a54cc18e6cfe749a3670",
    ),
    "8daffdabe9202c228e45d833c9a1d399597a15cd": (
        "34f3070074e75cc6a83df3f0d7e74fe8a6fd6043",
        "f1455f20ca3a83e3fc38f0ba9c7dbff9d2faef46",
        "138e7eab4905ec366338a54cc18e6cfe749a3670",
    ),
}


PINNED_LOW_LEVEL_BLOBS = {
    "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7": (
        "8f81cb2af39e885cd34cd39f04abe0a84053224b",
        "63b9b97fe8f31c0168edeeb47f8922676002527f",
    ),
    "8daffdabe9202c228e45d833c9a1d399597a15cd": (
        "8f81cb2af39e885cd34cd39f04abe0a84053224b",
        "63b9b97fe8f31c0168edeeb47f8922676002527f",
    ),
}


def git_blob_oid(text: str) -> str:
    data = text.encode("utf-8")
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("ascii") + data
    ).hexdigest()


def check_low_level_autocast_no_script_hook(
    pet_cpp: str, charm_cpp: str
) -> dict[str, bool]:
    """Confirm directly inspected Pet/Charm setters contain no script call.

    Only the TWO named setters are checked for a script callback. More
    layers may exist; do not claim a universal absence of all hooks.
    """
    toggle = body_of(pet_cpp, "void Pet::ToggleAutocast(")
    action_bar = body_of(charm_cpp, "void CharmInfo::SetSpellAutocast(")
    require(toggle, (
        "spellInfo->IsAutocastable()",
        "m_spells.find(spellInfo->Id)",
        "m_autospells.push_back(spellInfo->Id);",
        "m_autospells.erase(autospellItr);",
        "itr->second.active = ACT_ENABLED;",
        "itr->second.active = ACT_DISABLED;",
    ), "Pet::ToggleAutocast")
    require(action_bar, (
        "PetActionBar[i].GetAction()",
        "PetActionBar[i].IsActionBarForSpell()",
        "PetActionBar[i].SetType(state ? ACT_ENABLED : ACT_DISABLED);",
    ), "CharmInfo::SetSpellAutocast")
    for name, body in (
        ("Pet::ToggleAutocast", toggle),
        ("CharmInfo::SetSpellAutocast", action_bar),
    ):
        if re.search(r"\bsScriptMgr\b|\b(?:OnPet|OnPlayer)[A-Z][A-Za-z0-9_]*\s*\(", body):
            raise SourceContractChanged(
                f"{name} contains a possible post-write script callback; re-review")
    return {
        "pet_toggle_source_has_no_direct_script_callback": True,
        "charm_actionbar_setter_has_no_direct_script_callback": True,
        "universal_hook_absence_proven": False,
    }



def verify_pinned_entry_blobs(
    pet_handler: str, pet_script: str, player_cpp: str, core_sha: str
) -> tuple[str, str, str]:
    """Verify all three actual pinned handler/hook/dismiss source files.

    Must be run BEFORE narrower lexical interpretation in the production
    CLI. A caller using check_accepted_autocast_paths on its own does NOT
    receive this source-pin guarantee. These Git blob SHA-1 digests are
    *content identity* checks only, not file authenticity/trust.
    """
    expected = PINNED_ENTRY_BLOBS.get(core_sha)
    if expected is None:
        raise SourceContractChanged("Unreviewed core ref for accepted pet choices")
    observed = tuple(map(git_blob_oid, (pet_handler, pet_script, player_cpp)))
    if observed != expected:
        raise SourceContractChanged(
            "Pinned PetHandler.cpp/PetScript.h/Player.cpp source drift; "
            f"expected {expected}, got {observed}")
    return observed


def verify_pinned_low_level_blobs(
    pet_cpp: str, charm_cpp: str, core_sha: str
) -> tuple[str, str]:
    expected = PINNED_LOW_LEVEL_BLOBS.get(core_sha)
    if expected is None:
        raise SourceContractChanged("Unreviewed core ref for low-level pet writes")
    observed = (git_blob_oid(pet_cpp), git_blob_oid(charm_cpp))
    if observed != expected:
        raise SourceContractChanged(
            "Pinned Pet.cpp/CharmInfo.cpp source drift; "
            f"expected {expected}, got {observed}")
    return observed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pet-handler", type=Path, required=True)
    parser.add_argument("--pet-script", type=Path, required=True)
    parser.add_argument("--player-cpp", type=Path, required=True)
    parser.add_argument("--pet-cpp", type=Path, required=True)
    parser.add_argument("--charm-cpp", type=Path, required=True)
    parser.add_argument("--core-sha", required=True)
    args = parser.parse_args()
    pet_handler = args.pet_handler.read_text(encoding="utf-8")
    pet_script = args.pet_script.read_text(encoding="utf-8")
    player_cpp = args.player_cpp.read_text(encoding="utf-8")
    pet_cpp = args.pet_cpp.read_text(encoding="utf-8")
    charm_cpp = args.charm_cpp.read_text(encoding="utf-8")
    # All five full-file pinned blobs MUST match before we interpret methods.
    pinned_entries = verify_pinned_entry_blobs(
        pet_handler, pet_script, player_cpp, args.core_sha)
    pinned_low_level = verify_pinned_low_level_blobs(
        pet_cpp, charm_cpp, args.core_sha)
    facts = check_accepted_autocast_paths(
        pet_handler, pet_script, player_cpp)
    low_level_facts = check_low_level_autocast_no_script_hook(pet_cpp, charm_cpp)
    print("PINNED HANDLER / PETSCRIPT / PLAYER:", *pinned_entries)
    print("PINNED PET / CHARM SOURCES:", *pinned_low_level)
    for key, value in low_level_facts.items():
        print(" ", f"{key}={str(value).lower()}")
    print("PINNED A02 ACCEPTED-CHOICE HOOK HAZARD:", args.core_sha)
    for key, value in facts.items():
        print(" ", f"{key}={str(value).lower()}")
    print("PASS means A02 human Hunter autocast persistence remains BLOCKED.")
    print("NOT TESTED: compiled Worldserver, packet replay, SQL or player data.")


if __name__ == "__main__":
    main()
