#!/usr/bin/env python3
"""Pinned client pet-toggle packet provenance and native acceptance boundary.

Read-only source verification, NOT a post-handler callback implementation,
not an actual client/Playerbot test, and never a permission to persist state.
"""
import argparse
from pathlib import Path


def section(source, begin, end):
    assert source.count(begin) == 1, "Unique pinned function moved: " + begin
    tail = source.split(begin, 1)[1]
    assert end in tail, "Pinned endpoint absent: " + end
    return tail.split(end, 1)[0]


def check(core):
    session = (core / "src/server/game/Server/WorldSession.cpp").read_text("utf-8")
    handler = (core / "src/server/game/Handlers/PetHandler.cpp").read_text("utf-8")
    pet = (core / "src/server/game/Entities/Pet/Pet.cpp").read_text("utf-8")
    interface = (core / "src/server/game/Scripting/ScriptDefines/ServerScript.h").read_text("utf-8")

    # Script hooks run before the native handlers, and there is no
    # public after-handler-accepted pet autocast hook in this surface.
    assert "SERVERHOOK_CAN_PACKET_RECEIVE" in interface
    assert "virtual bool CanPacketReceive(WorldSession*" in interface
    assert "SERVERHOOK_ON_PACKET_SENT" in interface
    assert "OnPetAutocastAccepted" not in interface
    assert "OnPacketHandled" not in interface
    assert "OnPacketReceivedAfterHandler" not in interface
    assert "sScriptMgr->CanPacketReceive(this, *packet)" in session
    assert "opHandle->Call(this, *packet);" in session
    for match in ("if (!sScriptMgr->CanPacketReceive(this, *packet))",
                  "opHandle->Call(this, *packet);"):
        assert session.count(match) >= 3, "Session packet gate changed"
    assert session.index("if (!sScriptMgr->CanPacketReceive(this, *packet))") < (
        session.index("opHandle->Call(this, *packet);"))

    autocast = section(handler, "void WorldSession::HandlePetSpellAutocastOpcode(",
                       "void WorldSession::HandlePetCastSpellOpcode(")
    for required in (
        "ObjectAccessor::GetCreatureOrPetOrVehicle(*_player, packet.PetGUID)",
        "if (!checkPet)", "GetSpellInfo(packet.SpellID)",
        "checkPet != _player->GetGuardianPet()",
        "checkPet != _player->GetCharm()",
        "!pet->HasSpell(packet.SpellID)",
        "!spellInfo->IsAutocastable()",
        "if (!charmInfo)",
        "summon->ToggleAutocast(spellInfo, packet.AutocastEnabled)",
        "charmInfo->SetSpellAutocast(spellInfo, packet.AutocastEnabled)"
    ):
        assert required in autocast, "Autocast handler guard changed: " + required
    assert autocast.index("if (!checkPet)") < autocast.index(
        "summon->ToggleAutocast(")

    action = section(handler, "void WorldSession::HandlePetSetAction(",
                     "void WorldSession::HandlePetRename(")
    for required in (
        "checkPet != _player->GetFirstControlled()",
        "count = (recvData.size() == 24) ? 2 : 1;",
        "if (position[i] >= MAX_UNIT_ACTION_BAR_INDEX)",
        "if (count == 1)",
        "if (move_command)",
        "pet->HasSpell(spell_id)",
        "((Pet*)pet)->ToggleAutocast(spellInfo, true)",
        "((Pet*)pet)->ToggleAutocast(spellInfo, false)",
        "charmInfo->SetActionBar(position[i], spell_id, ActiveStates(act_state))"
    ):
        assert required in action, "Actionbar handler guard changed: " + required
    assert action.index("checkPet != _player->GetFirstControlled()") < (
        action.index("ToggleAutocast(spellInfo, true)"))

    toggled = section(pet, "void Pet::ToggleAutocast(",
                      "bool Pet::IsPermanentPetFor(")
    assert "if (!spellInfo->IsAutocastable())" in toggled
    assert "if (itr == m_spells.end())" in toggled
    assert "if (autospellItr == m_autospells.end())" in toggled
    assert "if (autospellItr != m_autospells.end())" in toggled
    assert "itr->second.active = ACT_ENABLED;" in toggled
    assert "itr->second.active = ACT_DISABLED;" in toggled

    print("PASS: pre-handler packet hook runs before native pet-command checks.")
    print("PASS: native handlers can reject, skip or apply an autocast candidate.")
    print("PASS: native state can also change through direct ToggleAutocast calls.")
    print("BLOCKED: matching state alone proves neither handler acceptance nor human actor.")
    print("No native handler/IP/Playerbots code changed, and no persistent state saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    args = parser.parse_args()
    check(args.core.resolve())
