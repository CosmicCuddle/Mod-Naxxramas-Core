#!/usr/bin/env python3
"""Pinned Playerbots internal action listener: observational limits and ABI.

A source-only investigation; this script never imports/loads Playerbots or
registers a callback. Failure means the pinned assumptions require review.
"""
import argparse
from pathlib import Path


def between(text, start, end):
    assert text.count(start) == 1, "Pinned symbol moved: " + start
    rest = text.split(start, 1)[1]
    assert end in rest, "Pinned scope changed: " + end
    return rest.split(end, 1)[0]


def check(root):
    def read(path):
        return (root / path).read_text(encoding="utf-8")

    eng = read("src/Bot/Engine/Engine.cpp")
    eh = read("src/Bot/Engine/Engine.h")
    ai = read("src/Bot/PlayerbotAI.h")
    action = read("src/Ai/Base/Actions/PetsAction.cpp")
    event = read("src/Bot/Engine/WorldPacket/Event.h")
    trigger = read("src/Bot/Engine/Trigger/Trigger.cpp")

    dispatch = between(eng, "bool Engine::ListenAndExecute(",
                       "void Engine::LogAction(")
    for needle in (
        "actionExecutionListeners.Before(action, event)",
        "actionExecutionListeners.AllowExecution(action, event) ? action->Execute(event) : true;",
        "actionExecutionListeners.OverrideResult(action, actionExecuted, event)",
        "actionExecutionListeners.After(action, actionExecuted, event);",
    ):
        assert needle in dispatch, "Action dispatch changed: " + needle

    assert dispatch.index("actionExecutionListeners.Before(") < (
        dispatch.index("actionExecutionListeners.AllowExecution("))
    assert dispatch.index("actionExecutionListeners.AllowExecution(") < (
        dispatch.index("actionExecutionListeners.OverrideResult("))
    assert dispatch.index("actionExecutionListeners.OverrideResult(") < (
        dispatch.index("actionExecutionListeners.After("))

    assert "class ActionExecutionListener" in eh
    for needle in (
        "virtual bool Before(Action* action, Event event) = 0;",
        "virtual bool AllowExecution(Action* action, Event event) = 0;",
        "virtual void After(Action* action, bool executed, Event event) = 0;",
        "virtual bool OverrideResult(Action* action, bool executed, Event event) = 0;",
        "void AddActionExecutionListener(ActionExecutionListener* listener)",
        "void removeActionExecutionListener(ActionExecutionListener* listener)",
        "void Add(ActionExecutionListener* listener) { listeners.push_back(listener); }",
        "void Remove(ActionExecutionListener* listener) { listeners.remove(listener); }",
    ):
        assert needle in eh, "Listener signature or ownership changed: " + needle

    assert "ActionExecutionListeners::~ActionExecutionListeners()" in eng
    owner = between(eng, "ActionExecutionListeners::~ActionExecutionListeners()",
                    "Engine::~Engine(")
    assert "delete *i;" in owner
    assert "listeners.clear();" in owner

    # The engine contains registration API, but the existing bot's Engine*
    # is PROTECTED on PlayerbotAI and not exposed by a verified public
    # accessor. We must not cast, subclass a live bot, or reach into it.
    assert "protected:\n    Player* bot;" in ai
    assert "Engine* currentEngine;" in ai
    assert "Engine* engines[BOT_STATE_MAX];" in ai
    assert "Engine* GetCurrentEngine(" not in ai
    assert "Engine* GetEngine(" not in ai
    assert "Engine* GetEngines(" not in ai
    assert "void AddActionExecutionListener(" not in ai

    # The result belongs to an ACTION, NOT to a specific spell.
    pet_action = between(
        action, "bool TogglePetSpellAutoCastAction::Execute(",
        "bool PetAttackAction::Execute(")
    assert "bool toggled = false;" in pet_action
    assert "pet->ToggleAutocast(spellInfo, shouldApply);" in pet_action
    assert "toggled = true;" in pet_action
    assert "return toggled;" in pet_action
    assert "for (PetSpellMap::const_iterator itr = pet->m_spells.begin();" in pet_action

    # A generic AI-triggered action does not carry a real master identity.
    assert "Event(std::string const source) : source(source) {}" in event
    assert "Player* owner = nullptr;" in event
    assert "Event event(getName());" in trigger

    print("PASS: Playerbots action listeners run before/after the AI dispatch.")
    print("PASS: After(executed=true) may follow a blocked action or overridden result.")
    print("PASS: toggle pet spell action returns an aggregate boolean, not spell-by-spell changes.")
    print("PASS: engines are protected; no verified public registration path from Naxx.")
    print("PASS: engine destructor owns listener deletion; detach requires lifecycle proof.")
    print("BLOCKED: listener API alone is neither a master-intent nor native-spell-completion hook.")
    print("Source-only: no callback registered, no memory ownership, pet toggle or SQL.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--playerbots", type=Path, required=True)
    args = parser.parse_args()
    check(args.playerbots.resolve())
