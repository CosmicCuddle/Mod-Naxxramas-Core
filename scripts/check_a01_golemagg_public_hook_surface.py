#!/usr/bin/env python3
"""Pin the inspected external movement-hook surface; read-only source checks.

This checker does NOT assert that no usable hook exists anywhere. It verifies
exact findings in the selected public headers at fixed dependency revisions.
Any material API change fails closed and requires a fresh developer review.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re

class SourceSurfaceChanged(RuntimeError):
    pass

def needs(source: str, needle: str, path: str) -> int:
    count = source.count(needle)
    if count != 1:
        raise SourceSurfaceChanged(f"{path}: expected one {needle!r}, found {count}")
    return source.index(needle)

def require_nearest_access(source: str, declaration: str, expected: str, path: str) -> None:
    """Check the nearest preceding C++ access label at a pinned declaration.

    The previous 'rfind(protected:)' check could be bypassed by inserting a
    newer 'public:' label between the original protected label and member.
    These checks are source guards, not general C++ scope parsers.
    """
    position = needs(source, declaration, path)
    labels = list(re.finditer(r"(?m)^[ \\t]*(public|private|protected)[ \\t]*:", source[:position]))
    if not labels or labels[-1].group(1) != expected:
        raise SourceSurfaceChanged(
            f"{path}: nearest access for {declaration!r} is not {expected}: re-review")


def check_public_movement_surface(files: dict[str, str]) -> dict[str, bool]:
    p = files["playerbot"]
    engine = files["engine"]
    context = files["context"]
    named = files["named"]
    mc = files["mc"]
    movement = files["movement"]
    movement_impl = files["movement_impl"]
    player = files["player"]
    unit = files["unit"]

    selection = "void ChangeStrategy(std::string const name, BotState type);"
    needs(p, selection, "PlayerbotAI.h")
    require_nearest_access(p, selection, "public", "PlayerbotAI.h")
    require_nearest_access(p, "Engine* currentEngine;", "protected", "PlayerbotAI.h")
    require_nearest_access(p, "Engine* engines[BOT_STATE_MAX];", "protected", "PlayerbotAI.h")
    needs(engine, "void AddActionExecutionListener(ActionExecutionListener* listener)", "Engine.h")

    require_nearest_access(
        context, "NamedObjectContextList<Strategy> strategyContexts;",
        "protected", "AiObjectContext.h")
    require_nearest_access(
        context, "static SharedNamedObjectContextList<Strategy> sharedStrategyContexts;",
        "private", "AiObjectContext.h")
    needs(context, "static void BuildSharedStrategyContexts(SharedNamedObjectContextList<Strategy>& strategyContexts);", "AiObjectContext.h")
    needs(named, "std::unordered_map<std::string, ObjectCreator> const& creators;", "NamedObjectContext.h")
    needs(mc, "void RaidMcStrategy::InitMultipliers(std::vector<Multiplier*>& multipliers)", "MCStrategy.cpp")
    needs(mc, "multipliers.push_back(new GolemaggMultiplier(botAI));", "MCStrategy.cpp")

    needs(movement, "MOVEMENTHOOK_ON_PLAYER_MOVE,", "MovementHandlerScript.h")
    needs(movement, "virtual void OnPlayerMove(Player* /*player*/, MovementInfo /*movementInfo*/, uint32 /*opcode*/) { }", "MovementHandlerScript.h")
    needs(movement_impl, "void ScriptMgr::OnPlayerMove(Player* player, MovementInfo movementInfo, uint32 opcode)", "MovementHandlerScript.cpp")
    needs(movement_impl, "CALL_ENABLED_HOOKS(MovementHandlerScript, MOVEMENTHOOK_ON_PLAYER_MOVE, script->OnPlayerMove(player, movementInfo, opcode));", "MovementHandlerScript.cpp")

    needs(player, "virtual void OnPlayerUpdate(Player* /*player*/, uint32 /*p_time*/) { }", "PlayerScript.h")
    needs(unit, "virtual void OnUnitUpdate(Unit* /*unit*/, uint32 /*diff*/) { }", "UnitScript.h")

    return {
        "public_selector_without_external_strategy_registration_proven": True,
        "engine_listener_inaccessible_via_inspected_public_bot_member": True,
        "core_movement_hook_void_observation_only": True,
        "core_player_unit_update_hooks_void": True,
        "external_golemagg_action_veto_proven": False,
        "safe_module_only_movement_fix_implemented": False,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("playerbot", "engine", "context", "named", "mc",
                "movement", "movement_impl", "player", "unit"):
        parser.add_argument("--" + arg.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    keys = ("playerbot", "engine", "context", "named", "mc",
            "movement", "movement_impl", "player", "unit")
    files = {name: getattr(args, name).read_text(encoding="utf-8") for name in keys}
    proof = check_public_movement_surface(files)
    for label, value in proof.items():
        print(f"{label}={str(value).lower()}")
    print("A01_PUBLIC_HOOK_SURFACE_PIN_OK")
    print("NO Playerbots action veto, Golemagg fix, Worldserver run, or live test.")

if __name__ == "__main__":
    main()
