#!/usr/bin/env python3
"""Read-only NT1 source proof: direct LearnTalent is void and is NOT atomic.

The source contract checks both reviewed Grimfeather revisions and the Naxx
importer's sequential verification boundary. Passing means a partial mutation
risk remains. It does NOT establish an exploitable live failure, safety to
apply talents, a viable rollback, or a corrected talent importer.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from check_nt1_grimfeather_two_core_reset_boundary import (
    SourceContractError, function_body, must_contain,
)

LEARN_SIGNATURE = "void Player::LearnTalent(uint32 talentId, uint32 talentRank, bool command /*= false*/)"
IMPORT_SIGNATURE = (
    "bool LearnValidated(Player* bot, ValidatedBuild const& plan,\n"
    "        std::string& error)"
)


def check_direct_learn_risk(player_cpp: str, bot_cpp: str) -> dict[str, bool]:
    learn = function_body(player_cpp, LEARN_SIGNATURE)
    imported = function_body(bot_cpp, IMPORT_SIGNATURE)

    must_contain(learn, [
        "if (!sScriptMgr->OnPlayerCanLearnTalent(this, talentInfo, talentRank))",
        "if (CurTalentPoints < talentPointsChange)",
        "learnSpell(spellId);",
        "learned = true;",
        "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
        "SetFreeTalentPoints(CurTalentPoints - talentPointsChange);",
        "sScriptMgr->OnPlayerLearnTalents(this, talentId, talentRank, spellId);",
    ], "Player::LearnTalent")

    if not (
        learn.index("OnPlayerCanLearnTalent") <
        learn.index("learnSpell(spellId);") <
        learn.index("addTalent(spellId, GetActiveSpecMask(), currentTalentRank);") <
        learn.index("OnPlayerLearnTalents(")
    ):
        raise SourceContractError("LearnTalent validation/mutation ordering changed")

    # Hook vetoes and other precondition failures return VOID (not an error).
    hook_guard = learn.index("if (!sScriptMgr->OnPlayerCanLearnTalent")
    if "return;" not in learn[hook_guard:learn.index("TalentTabEntry", hook_guard)]:
        raise SourceContractError("LearnTalent hook veto return path changed")

    # In the pinned cores the one addTalent(...) call is a standalone
    # expression statement. Fail closed on ANY changed use, including:
    # assignment (typed/untyped), brace-init, return, macro/wrapper,
    # qualification, or another call. Do not guess whether a refactored
    # function is still unsafe; require another exact-source review.
    # This source-specific check is intentionally narrow, not a C++ parser.
    expected_call = "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"
    matches = list(re.finditer(r"\baddTalent\s*\(", learn))
    call_lines = [line.strip() for line in learn.splitlines()
                  if re.search(r"\baddTalent\s*\(", line)]
    if len(matches) != 1 or call_lines != [expected_call]:
        raise SourceContractError(
            "LearnTalent addTalent invocation is not exactly one standalone call: re-review")

    # A standalone line is insufficient: "return", assignment, a cast, or
    # an unbraced if may be on the PREVIOUS physical line. In the pinned
    # cores, the preceding completed statement ends with ';'. Accept only
    # an unambiguous statement/block boundary and require re-review for
    # any alternate multi-line expression or control-flow form.
    prefix = learn[:matches[0].start()].rstrip()
    if not prefix or prefix[-1] not in ";{}":
        raise SourceContractError(
            "LearnTalent addTalent call lacks a standalone statement boundary: re-review")

    must_contain(imported, [
        "for (TalentSelection const& selection : plan.Ordered)",
        "bot->LearnTalent(selection.Id, selection.Rank - 1);",
        "bot->HasTalent(spellId, bot->GetActiveSpec())",
        "return false;",
    ], "NT1 LearnValidated")
    if imported.index("bot->LearnTalent(") >= imported.index("bot->HasTalent("):
        raise SourceContractError("NT1 learn/postcheck order changed")
    if "resetTalents(" in imported:
        raise SourceContractError("NT1 LearnValidated now resets: inspect new semantics")

    return {
        "core_learn_talent_returns_void": True,
        "core_can_veto_each_selection": True,
        "nt1_mutates_before_checking_next_selection": True,
        "failure_after_prior_learns_can_leave_partial_build": True,
        "safe_gear_inert_changed_build_apply": False,
    }


def model_sequential_learn(selected: tuple[int, ...], reject_at: int | None) -> tuple[bool, tuple[int, ...]]:
    """Synthetic one-pass behaviour only; no AzerothCore/DB/gear operations."""
    learned: list[int] = []
    for index, spell in enumerate(selected):
        # In real core, a veto causes the void function to return unchanged;
        # the importer checks HasTalent after each attempted learn.
        if index == reject_at:
            return False, tuple(learned)
        learned.append(spell)
    return True, tuple(learned)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-cpp", required=True, type=Path)
    parser.add_argument("--module-cpp", required=True, type=Path)
    parser.add_argument("--reference-sha", required=True)
    args = parser.parse_args()
    risk = check_direct_learn_risk(
        args.player_cpp.read_text(encoding="utf-8"),
        args.module_cpp.read_text(encoding="utf-8"),
    )
    print("PINNED NT1 DIRECT LEARN PARTIAL-MUTATION RISK:", args.reference_sha)
    for k, v in risk.items():
        print(" ", k + "=" + str(v).lower())
    print("PASS: risk confirmed. Different-build Altbot Apply REMAINS BLOCKED.")
    print("NOT TESTED: worldserver, player, equipment, DB, actual veto or rollback.")


if __name__ == "__main__":
    main()
