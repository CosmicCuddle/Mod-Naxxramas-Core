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
import hashlib
import re

from check_nt1_grimfeather_two_core_reset_boundary import (
    SourceContractError, function_body, must_contain,
)

LEARN_SIGNATURE = "void Player::LearnTalent(uint32 talentId, uint32 talentRank, bool command /*= false*/)"
IMPORT_SIGNATURE = (
    "bool LearnValidated(Player* bot, ValidatedBuild const& plan,\n"
    "        std::string& error)"
)


# Source-only tripwire. The full Player.cpp Git blob is identical at both
# independently reviewed Grimfeather refs. Git SHA-1 here is a CONTENT
# fingerprint of a public source file, not a security/authentication check.
# This intentionally fails closed even on changes outside LearnTalent:
# any changed pinned core file requires fresh independent risk review.
PINNED_PLAYER_CPP_BLOBS = {
    "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7":
        "138e7eab4905ec366338a54cc18e6cfe749a3670",
    "8daffdabe9202c228e45d833c9a1d399597a15cd":
        "138e7eab4905ec366338a54cc18e6cfe749a3670",
}


def git_blob_oid(source: str) -> str:
    """Content identity only; the core pin is separately verified by CI."""
    payload = source.encode("utf-8")
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()


def verify_pinned_player_cpp_blob(source: str, reference_sha: str) -> str:
    """Reject edited, mixed-pin, or unreviewed Player.cpp content wholesale."""
    expected = PINNED_PLAYER_CPP_BLOBS.get(reference_sha)
    if expected is None:
        raise SourceContractError(
            "Unknown Grimfeather Player.cpp reference: require source review")
    observed = git_blob_oid(source)
    if observed != expected:
        raise SourceContractError(
            "Pinned Player.cpp blob changed: review all new LearnTalent "
            "control-flow paths before interpreting the read-only hazard "
            f"(expected {expected}, observed {observed})")
    return observed


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
    # Both pinned Player.cpp versions end the directly preceding statement
    # with ';' before the standalone addTalent call. A closing brace is NOT
    # an acceptable boundary: inserted fully balanced if/while/try blocks
    # can change the conditions under which the mutation is reached even
    # though the earlier nesting-depth check still returns zero.
    if not prefix or prefix[-1] != ";":
        raise SourceContractError(
            "LearnTalent addTalent call does not follow the pinned statement boundary: re-review")

    # function_body() returns the INTERIOR of LearnTalent, excluding its
    # enclosing braces. At the pinned direct call, every prior nested
    # conditional/loop scope is closed. Even if the preceding physical
    # character is '{', a newly inserted if/while/lambda block must require
    # a fresh source review. Deliberately fail closed on any unexpected
    # brace nesting; this is a narrow pinned-source contract, not a C++
    # parser (comments/strings containing braces may also require review).
    depth = prefix.count("{") - prefix.count("}")
    if depth != 0:
        raise SourceContractError(
            "LearnTalent addTalent call is nested in a new braced context: re-review")

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
    player_cpp = args.player_cpp.read_text(encoding="utf-8")
    observed_blob = verify_pinned_player_cpp_blob(player_cpp, args.reference_sha)
    risk = check_direct_learn_risk(
        player_cpp,
        args.module_cpp.read_text(encoding="utf-8"),
    )
    print("EXACT PINNED PLAYER.CPP GIT BLOB:", observed_blob)
    print("PINNED NT1 DIRECT LEARN PARTIAL-MUTATION RISK:", args.reference_sha)
    for k, v in risk.items():
        print(" ", k + "=" + str(v).lower())
    print("PASS: risk confirmed. Different-build Altbot Apply REMAINS BLOCKED.")
    print("NOT TESTED: worldserver, player, equipment, DB, actual veto or rollback.")


if __name__ == "__main__":
    main()
