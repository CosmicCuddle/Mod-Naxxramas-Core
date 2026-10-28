#!/usr/bin/env python3
"""A03 P4: pinned-source facts behind the NT1 changed-build Alt Bot verdict.

Read-only. Checks the exact pinned AzerothCore, Playerbots and Individual
Progression sources, plus this module, for the facts that decide whether a
changed-build Alt Bot talent swap can be atomic AND keep gear and pets:

  F1  resetTalents dismisses the pet whenever any point is spent.
  F2  resetTalents clears Titan's Grip / dual wield and auto-unequips the offhand.
  F3  Those two capabilities are cleared ONLY by resetTalents and ActivateSpec,
      so a reset-free swap that drops such a talent would leave them stale.
  F4  The reset-free primitives are public on Player.
  F5  LearnTalent: hook veto first, then rule checks, then these post-steps
      a reset-free swap must reproduce: learnSpell / SendLearnPacket,
      additional talent spells, addTalent, SetFreeTalentPoints, OnPlayerLearnTalents.
  F6  addTalent fails only on static data or an already-present talent.
  F7  Talent hook inventory: Playerbots and IP implement none; this module's
      implementers are exactly the expected set.
  F8  The module Apply path still resets, and the Alt Bot offhand/pet guard
      that runs before it is still present.

Any mismatch exits 1: a changed pin or module needs fresh review of the
verdict, never a silent pass. This proves source facts only, not runtime.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PRIMITIVES = {
    "_removeTalent(PlayerTalentMap::iterator& itr, uint8 specMask)",
    "_removeTalent(uint32 spellId, uint8 specMask)",
    "_removeTalentAurasAndSpells(uint32 spellId)",
    "_addTalentAurasAndSpells(uint32 spellId)",
    "addTalent(uint32 spellId, uint8 addSpecMask, uint8 oldTalentRank)",
    "removeSpell(uint32 spellId, uint8 removeSpecMask, bool onlyTemporary, bool sendPacket = true)",
    "learnSpell(uint32 spellId, bool temporary = false, bool learnFromSkill = false)",
    "SetFreeTalentPoints(uint32 points)",
}

TALENT_HOOKS = ("OnPlayerCanLearnTalent", "OnPlayerTalentsReset",
                "OnPlayerLearnTalents", "OnPlayerFreeTalentPointsChanged")

EXPECTED_MODULE_HOOKS = {
    "OnPlayerCanLearnTalent": {"src/Systems/BotTalentCompletion.cpp",
                               "src/Systems/BotTalentExpansionLimits.cpp"},
    "OnPlayerTalentsReset": {"src/Class/Warlock/WarlockWrack.cpp",
                             "src/Systems/BotTalentCompletion.cpp"},
    "OnPlayerLearnTalents": {"src/Class/Shaman/ShamanRockbiter.cpp",
                             "src/Class/Warlock/WarlockWrack.cpp",
                             "src/Systems/BotTalentCompletion.cpp"},
    "OnPlayerFreeTalentPointsChanged": set(),
}


class FactError(Exception):
    pass


def span(source: str, signature: str) -> tuple[int, int]:
    """Brace-matched body span of the single definition starting with signature."""
    starts = [m.start() for m in re.finditer(r"(?m)^" + re.escape(signature), source)]
    if len(starts) != 1:
        raise FactError(f"expected one definition of {signature!r}, found {len(starts)}")
    open_at = source.index("{", starts[0])
    depth = 0
    for i in range(open_at, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return open_at + 1, i
    raise FactError(f"unterminated body for {signature!r}")


def body(source: str, signature: str) -> str:
    begin, end = span(source, signature)
    return source[begin:end]


def code_only(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def ordered(text: str, tokens: list[str], what: str) -> None:
    at = -1
    for token in tokens:
        found = text.find(token, at + 1)
        if found < 0:
            raise FactError(f"{what}: {token!r} missing or out of order")
        at = found


def check_reset(player_cpp: str) -> None:
    b = code_only(body(player_cpp, "bool Player::resetTalents(bool noResetCost)"))
    # F1: the pet is removed after the "nothing spent" and money returns and
    # before the talent loop, at statement level (not under a condition).
    ordered(b, ["if (m_usedTalentCount == 0)", "return false;",
                "RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);",
                "for (PlayerTalentMap::iterator iter = m_talents.begin();"], "F1 resetTalents")
    if b.count("RemovePet(") != 1:
        raise FactError("F1: expected exactly one RemovePet in resetTalents")
    line = next(l for l in b.splitlines() if "RemovePet(" in l)
    before = b[:b.index(line)].rstrip()
    if not before.endswith(("}", ";")):
        raise FactError("F1: RemovePet is no longer an unconditional statement")
    # F2
    ordered(b, ["SetCanTitanGrip(false);", "SetCanDualWield(false);",
                "AutoUnequipOffhandIfNeed();", "SetFreeTalentPoints(talentPointsForLevel);"],
            "F2 resetTalents")


def check_capability_sites(game_sources: dict[str, str]) -> None:
    calls = {"SetCanTitanGrip(false)": "tg", "SetCanDualWield(false)": "dw"}
    reset = spec = None
    seen = []
    for path, text in sorted(game_sources.items()):
        code = code_only(text)
        if path.endswith("Player/Player.cpp"):
            reset = span(code, "bool Player::resetTalents(bool noResetCost)")
            spec = span(code, "void Player::ActivateSpec(uint8 spec)")
        for call, kind in calls.items():
            for m in re.finditer(re.escape(call), code):
                if not path.endswith("Player/Player.cpp"):
                    raise FactError(f"F3: new capability reset site {call} in {path}")
                seen.append((m.start(), kind))
    if reset is None or spec is None:
        raise FactError("F3: Player.cpp missing from scan")
    where = []
    for at, kind in seen:
        if reset[0] <= at < reset[1]:
            where.append("reset-" + kind)
        elif spec[0] <= at < spec[1]:
            where.append("spec-" + kind)
        else:
            where.append("other-" + kind)
    if sorted(where) != ["reset-dw", "reset-tg", "spec-dw", "spec-tg"]:
        raise FactError(f"F3: capability reset sites changed: {sorted(where)}")


def check_public_primitives(player_h: str) -> None:
    start = player_h.index("class Player : public Unit")
    open_at = player_h.index("{", start)
    depth = 0
    access = "private"
    found: dict[str, str] = {}
    lines = player_h[open_at:].splitlines()
    for raw in lines:
        line = raw.split("//")[0]
        stripped = line.strip()
        if depth == 1 and stripped in ("public:", "protected:", "private:"):
            access = stripped[:-1]
        if depth == 1:
            for sig in PRIMITIVES:
                if sig in stripped:
                    found[sig] = access
        depth += line.count("{") - line.count("}")
        if depth == 0 and found is not None and raw is not lines[0]:
            break
    missing = PRIMITIVES - found.keys()
    if missing:
        raise FactError(f"F4: primitives not declared on Player: {sorted(missing)}")
    hidden = sorted(sig for sig, acc in found.items() if acc != "public")
    if hidden:
        raise FactError(f"F4: primitives no longer public: {hidden}")


def check_learn_talent(player_cpp: str) -> None:
    b = code_only(body(player_cpp,
                       "void Player::LearnTalent(uint32 talentId, uint32 talentRank, bool command /*= false*/)"))
    ordered(b, [
        "if (!sScriptMgr->OnPlayerCanLearnTalent(this, talentInfo, talentRank))",
        "if ((getClassMask() & talentTabInfo->ClassMask) == 0)",
        "if (currentTalentRank >= talentRank + 1)",
        "if (CurTalentPoints < talentPointsChange)",
        "if (talentInfo->DependsOn > 0)",
        "if (spentPoints < (talentInfo->Row * MAX_TALENT_RANK))",
        "learnSpell(spellId);",
        "SendLearnPacket(spellId, true);",
        "learnSpell(spellInfo->Effects[i].TriggerSpell);",
        "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
        "SetFreeTalentPoints(CurTalentPoints - talentPointsChange);",
        "sScriptMgr->OnPlayerLearnTalents(this, talentId, talentRank, spellId);",
    ], "F5 LearnTalent")
    if "return" in b[b.index("addTalent(spellId"):]:
        raise FactError("F5: LearnTalent gained an exit after addTalent")


def check_add_talent(player_cpp: str) -> None:
    b = code_only(body(player_cpp,
                       "bool Player::addTalent(uint32 spellId, uint8 addSpecMask, uint8 oldTalentRank)"))
    falses = [m.start() for m in re.finditer(r"return false;", b)]
    if len(falses) != 4:
        raise FactError(f"F6: addTalent has {len(falses)} 'return false' exits, expected 4")
    ordered(b, ["if (!SpellMgr::CheckSpellValid(spellInfo, spellId, true))", "return false;",
                "if (!talentPos)", "return false;", "if (!talentInfo)", "return false;",
                "_addTalentAurasAndSpells(spellId);"], "F6 addTalent")
    # The last false is the "already present in this spec mask" case.
    tail = b[b.rindex("else if (!(itr->second->specMask & addSpecMask))"):]
    if "return false;" not in tail:
        raise FactError("F6: duplicate-talent exit moved")
    if "sScriptMgr" in b:
        raise FactError("F6: addTalent gained a script hook")


def hook_implementers(root: Path, rel_to: Path) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {hook: set() for hook in TALENT_HOOKS}
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".cpp", ".h") or not path.is_file():
            continue
        text = code_only(path.read_text(errors="replace"))
        for hook in TALENT_HOOKS:
            if re.search(r"\b(?:void|bool)\s+" + hook + r"\s*\(", text):
                found[hook].add(path.relative_to(rel_to).as_posix())
    return found


def check_hooks(playerbots: Path, ip: Path, module: Path) -> None:
    for name, root in (("Playerbots", playerbots), ("Individual Progression", ip)):
        extra = {h: s for h, s in hook_implementers(root, root).items() if s}
        if extra:
            raise FactError(f"F7: {name} now implements talent hooks: {extra}")
    got = hook_implementers(module / "src", module)
    if got != EXPECTED_MODULE_HOOKS:
        raise FactError(f"F7: module talent hook set changed: {got}")


def check_module_apply(module: Path) -> None:
    text = code_only((module / "src/Systems/BotTalentImport.cpp").read_text())
    apply_body = body(text, "    bool ApplyValidated(Player* issuer, Player* bot, std::string const& code,")
    ordered(apply_body, ["CheckApplyReadiness(", "bot->resetTalents(true);",
                         "LearnValidated(bot, requested, error)", "bot->resetTalents(true);",
                         "LearnValidated(bot, snapshot, rollbackError)"], "F8 ApplyValidated")
    ordered(text, ["if (!randomBot)",
                   "INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND) != nullptr)",
                   "if (bot->GetPet() != nullptr)",
                   "bool ApplyValidated("], "F8 Alt Bot guard")


def run(core: Path, playerbots: Path, ip: Path, module: Path) -> list[str]:
    player_dir = core / "src/server/game/Entities/Player"
    player_cpp = (player_dir / "Player.cpp").read_text()
    player_h = (player_dir / "Player.h").read_text()
    game = {p.relative_to(core).as_posix(): p.read_text(errors="replace")
            for p in (core / "src/server/game").rglob("*.cpp")}
    check_reset(player_cpp)
    check_capability_sites(game)
    check_public_primitives(player_h)
    check_learn_talent(player_cpp)
    check_add_talent(player_cpp)
    check_hooks(playerbots / "src", ip / "src", module)
    check_module_apply(module)
    return [
        "F1-F8 hold at the given sources.",
        "reset_based_altbot_apply_preserves_pet=false",
        "reset_based_altbot_apply_preserves_offhand=false",
        "reset_based_rollback_is_transactional=false",
        "reset_free_swap_primitives_public=true",
        "reset_free_swap_needs_module_reimplementation_of=LearnTalent rules+post-steps, "
        "capability resets, OnPlayerLearnTalents callers",
        "changed_build_altbot_apply_safe=false (no such path is implemented)",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--playerbots", type=Path, required=True)
    parser.add_argument("--ip", type=Path, required=True)
    parser.add_argument("--module", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        lines = run(args.core, args.playerbots, args.ip, args.module)
    except (FactError, OSError, ValueError, StopIteration) as exc:
        print(f"FAIL: {exc}")
        print("The A03 verdict needs fresh review before anything relies on it.")
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
