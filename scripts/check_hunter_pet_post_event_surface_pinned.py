#!/usr/bin/env python3
"""Pinned public per-Pet post-event-loop hook / event visibility contract.

Read-only source assertions: no event queue introspection proves whether IP
has run or completed. The native callback can at most sample after one Pet
event-loop tick; it is not a post-IP callback.
"""
import argparse
from pathlib import Path


def between(code, begin, end):
    assert code.count(begin) == 1, "Source contract changed: " + begin
    tail = code.split(begin, 1)[1]
    assert end in tail, "Source boundary changed: " + end
    return tail.split(end, 1)[0]


def check(core, ip):
    obj = (core / "src/server/game/Entities/Object/Object.cpp").read_text("utf-8")
    pet = (core / "src/server/game/Entities/Pet/Pet.cpp").read_text("utf-8")
    ep = (core / "src/common/Utilities/EventProcessor.cpp").read_text("utf-8")
    eh = (core / "src/common/Utilities/EventProcessor.h").read_text("utf-8")
    hook = (core / "src/server/game/Scripting/ScriptDefines/WorldObjectScript.h").read_text("utf-8")
    ipp = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")

    world_tick = between(obj, "void WorldObject::Update(", "void WorldObject::setActive(")
    assert "m_Events.Update(diff);" in world_tick
    assert "sScriptMgr->OnWorldObjectUpdate(this, diff);" in world_tick
    assert world_tick.index("m_Events.Update(diff);") < world_tick.index(
        "sScriptMgr->OnWorldObjectUpdate(this, diff);")
    assert "WORLDOBJECTHOOK_ON_WORLD_OBJECT_UPDATE" in hook
    assert "OnWorldObjectUpdate(WorldObject*" in hook

    pet_tick = between(pet, "void Pet::Update(", "void Pet::CastPendingSpell(")
    assert "if (m_loading)" in pet_tick
    assert "Creature::Update(diff);" in pet_tick
    assert pet_tick.index("if (m_loading)") < pet_tick.index(
        "Creature::Update(diff);")

    queue_tick = between(ep, "void EventProcessor::Update(", "void EventProcessor::KillAllEvents(")
    assert "m_events.erase(i);" in queue_tick
    assert "event->Execute(m_time, p_time)" in queue_tick
    assert queue_tick.index("m_events.erase(i);") < queue_tick.index(
        "event->Execute(m_time, p_time)")
    assert "bool HasEvents() const { return !m_events.empty(); }" in eh
    assert "typedef std::multimap<uint64, BasicEvent*> EventList;" in eh

    started = "class DelayedPetSpellCheck : public BasicEvent"
    ended = "class IndividualPlayerProgression_UnitScript"
    ip_event = between(ipp, started, ended)
    assert "pet->isBeingLoaded() && _attempts < 10" in ip_event
    assert "sIndividualProgression->checkHunterPetSpells(player);" in ip_event
    assert "pet->CustomData.GetDefault<PendingPetSpellCheck>(PENDING_CHECK_KEY)->pending = false;" in ip_event

    print("PASS: WorldObject update callback is after its event queue tick.")
    print("PASS: ordinary loading-time Pet::Update returns before WorldObject update.")
    print("PASS: HasEvents means queue nonempty, not executing or IP completed.")
    print("BLOCKED: this public hook has no IP invocation ID or completion outcome.")
    print("Read-only pinned source check; no event scheduled, IP modified or spells changed.")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--core", type=Path, required=True)
    a.add_argument("--ip", type=Path, required=True)
    args = a.parse_args()
    check(args.core.resolve(), args.ip.resolve())
