#!/usr/bin/env python3
"""Fail-closed NT1 Altbot gear-inert respec API source evidence.

This does NOT modify talents or prove all code paths. It checks known hazards in
two exact published Grimfeather AzerothCore revisions. A successful run means
the dangerous reset/offhand path STILL EXISTS, not that changing talents is safe.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re


class SourceContractError(AssertionError):
    """Published source does not match the known and reviewed risk boundary."""


def function_body(text: str, signature: str) -> str:
    """Extract the uniquely named C++ function body via balanced braces.

    This is only intended for the pinned functions; it is not a generic C++
    parser. Ambiguous or missing signatures are denied rather than guessed.
    """
    match = text.count(signature)
    if match != 1:
        raise SourceContractError(
            f"expected one exact {signature!r}, found {match}")
    pos = text.index(signature) + len(signature)
    brace = text.find("{", pos)
    if brace < 0:
        raise SourceContractError(f"no body for {signature!r}")
    # Don't confuse a declaration ending in ';' with a function definition.
    if ";" in text[pos:brace]:
        raise SourceContractError(f"declaration, not definition: {signature!r}")
    depth = 0
    for end in range(brace, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:end]
    raise SourceContractError(f"unterminated body for {signature!r}")


def must_contain(section: str, needles: list[str], description: str) -> None:
    missing = [name for name in needles if name not in section]
    if missing:
        raise SourceContractError(
            f"{description}: missing expected source markers {missing!r}")


def verify_source(player_cpp: str, player_h: str) -> dict[str, bool]:
    """Return explicit risks; never return an 'apply safe' result."""
    reset = function_body(
        player_cpp, "bool Player::resetTalents(bool noResetCost)")
    offhand = function_body(
        player_cpp, "void Player::AutoUnequipOffhandIfNeed(bool force /*= false*/)")
    partial_remove = function_body(
        player_cpp, "void Player::_removeTalent(PlayerTalentMap::iterator& itr, uint8 specMask)")
    add = function_body(
        player_cpp, "bool Player::addTalent(uint32 spellId, uint8 addSpecMask, uint8 oldTalentRank)")

    must_contain(reset, [
        "sScriptMgr->OnPlayerTalentsReset(this, noResetCost);",
        "if (m_usedTalentCount == 0)",
        "m_usedTalentCount = 0;",
        "RemovePet(",
        "_removeTalentAurasAndSpells(",
        "AutoUnequipOffhandIfNeed();",
    ], "resetTalents")
    if not (reset.index("OnPlayerTalentsReset") <
            reset.index("m_usedTalentCount = 0;") <
            reset.index("AutoUnequipOffhandIfNeed();")):
        raise SourceContractError("resetTalents: unexpected hook/count/offhand ordering")

    must_contain(offhand, [
        "GetItemByPos(", "CanStoreItem(", "RemoveItem(",
        "StoreItem(", "MoveItemFromInventory(", "MailDraft(",
        "SendMailTo(", "CharacterDatabase.CommitTransaction(",
    ], "AutoUnequipOffhandIfNeed")
    if ("OnPlayerCanUnequipItem" in offhand or
            "OnPlayerUnequip" in offhand):
        raise SourceContractError("offhand path changed: re-review hooks and veto semantics")
    # Match full function identifiers; "StoreItem(" is a suffix of
    # "CanStoreItem(", so str.index would return a false call ordering.
    def call_position(name: str) -> int:
        match = re.search(r"\b" + re.escape(name) + r"\s*\(", offhand)
        if not match:
            raise SourceContractError(f"offhand: missing call {name}")
        return match.start()

    if not (call_position("CanStoreItem") <
            call_position("RemoveItem") <
            call_position("StoreItem")):
        raise SourceContractError("offhand inventory branch changed")

    must_contain(add, [
        "_removeTalent(", "m_usedTalentCount",
    ], "addTalent")
    must_contain(partial_remove, ["m_talents"], "_removeTalent")
    if "m_usedTalentCount" in partial_remove:
        raise SourceContractError(
            "_removeTalent counter semantics changed: requires renewed feasibility review")
    must_contain(player_h, [
        "bool resetTalents(bool noResetCost = false);",
        "bool addTalent(uint32 spellId, uint8 addSpecMask, uint8 oldTalentRank);",
        "void _removeTalent(PlayerTalentMap::iterator& itr, uint8 specMask);",
        "uint32 m_usedTalentCount;",
    ], "Player.h")

    # These mean UNSAFE RESET STILL EXISTS. No claim about whether any
    # other module-only mechanism can work, nor installed core compatibility.
    return {
        "reset_invokes_hook": True,
        "reset_can_remove_pet": True,
        "reset_invokes_offhand_relocation": True,
        "offhand_can_move_or_mail_item": True,
        "partial_remove_not_accounting_complete": True,
        "different_build_altbot_apply_safe": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-cpp", required=True, type=Path)
    parser.add_argument("--player-h", required=True, type=Path)
    parser.add_argument("--reference-sha", required=True)
    args = parser.parse_args()
    risks = verify_source(
        args.player_cpp.read_text(encoding="utf-8"),
        args.player_h.read_text(encoding="utf-8"))
    print(f"PINNED NT1 RESET HAZARD: {args.reference_sha}")
    for key, value in risks.items():
        print(f"  {key}={str(value).lower()}")
    print("PASS: risk exists; CHANGED-BUILD ALT BOT APPLY must remain denied")
    print("NOT TESTED: actual installed build, game runtime, safe respec, DB or gear")


if __name__ == "__main__":
    main()
