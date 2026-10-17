#!/usr/bin/env python3
"""Pin native Hunter pet remove/relearn observability limitations.

Only reads source at exact pinned AzerothCore/IP revisions. A PASS confirms
a missing public callback; it does not authorize a timer or restoration.
"""
import argparse
from pathlib import Path
import re


def segment(text, start, end):
    assert text.count(start) == 1, "Pinned source moved: " + start
    result = text.split(start, 1)[1]
    assert end in result, "Pinned source section missing: " + end
    return result.split(end, 1)[0]


def check(core, ip):
    native = (core / "src/server/game/Entities/Pet/Pet.cpp").read_text("utf-8")
    hooks = (core / "src/server/game/Scripting/ScriptDefines/PetScript.h").read_text("utf-8")
    sender = (core / "src/server/game/Server/WorldSession.cpp").read_text("utf-8")
    ipp = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")

    learn = segment(native, "bool Pet::learnSpell(", "void Pet::InitLevelupSpellsForLevel()")
    assert "if (!addSpell(spell_id))" in learn
    assert "if (!m_loading)" in learn
    assert "WorldPackets::Pet::PetLearnedSpell packet;" in learn
    assert "m_owner->SendDirectMessage(packet.Write());" in learn
    assert (learn.index("if (!m_loading)") <
            learn.index("WorldPackets::Pet::PetLearnedSpell packet;"))

    unlearn = segment(native, "bool Pet::unlearnSpell(", "bool Pet::removeSpell(")
    # The packet is literally commented out: verify it remains so.
    assert "WorldPackets::Pet::PetUnlearnedSpell packet;" in unlearn
    executable = re.sub(r"/\*.*?\*/", "", unlearn, flags=re.DOTALL)
    assert "PetUnlearnedSpell" not in executable
    assert "if (removeSpell(spell_id, learn_prev, clear_ab))" in executable
    assert "return true;" in executable

    removed = segment(native, "bool Pet::removeSpell(", "void Pet::CleanupActionBar()")
    assert "m_spells.erase(itr);" in removed
    assert "itr->second.state = PETSPELL_REMOVED;" in removed
    assert "OnPet" not in removed

    assert "PETHOOK_ON_PET_ADD_TO_WORLD" in hooks
    assert "PETHOOK_ON_INIT_STATS_FOR_LEVEL" in hooks
    assert "PETHOOK_ON_PET_LEARN_SPELL" not in hooks
    assert "PETHOOK_ON_PET_UNLEARN_SPELL" not in hooks
    assert "OnPetLearnSpell(" not in hooks
    assert "OnPetUnlearnSpell(" not in hooks

    send = segment(sender, "void WorldSession::SendPacket(", "void WorldSession::QueuePacket(")
    assert "sScriptMgr->OnPacketSent(this, *packet);" in send
    assert "if (!m_Socket)" in send
    assert send.index("sScriptMgr->OnPacketSent(") < send.index("if (!m_Socket)")

    ip_loop = segment(ipp, "class DelayedPetSpellCheck : public BasicEvent",
                      "class IndividualPlayerProgression_UnitScript")
    assert "if (pet->isBeingLoaded() && _attempts < 10)" in ip_loop
    assert "new DelayedPetSpellCheck(_ownerGuid, _attempts + 1)" in ip_loop
    assert "sIndividualProgression->checkHunterPetSpells(player);" in ip_loop
    assert (ip_loop.index("if (pet->isBeingLoaded() && _attempts < 10)") <
            ip_loop.index("sIndividualProgression->checkHunterPetSpells(player);"))

    print("PASS: native pet unlearn notification remains commented out.")
    print("PASS: native learn packet is emitted only when m_loading is false.")
    print("PASS: PetScript has no post-learn/unlearn or post-IP-completion hook.")
    print("PASS: IP may run its reconciler after loading retry cap.")
    print("BLOCKED: absence of packets or spellbook changes is not IP completion.")
    print("Read-only source check; nothing sent, trained, restored or saved.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--core", type=Path, required=True)
    p.add_argument("--ip", type=Path, required=True)
    args = p.parse_args()
    check(args.core.resolve(), args.ip.resolve())
