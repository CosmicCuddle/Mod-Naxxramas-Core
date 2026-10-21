#!/usr/bin/env python3
"""Read-only pinned-source check for the unproven Golemagg movement loop.

This proves ONLY the specified Playerbots action-class gate at one reviewed
commit. It does not identify the actual executed movement or implement a veto.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

PINNED_PLAYERBOTS = "037c01418b5d01506917a3db9b44fd56ac5f965c"
PINNED_BLOBS = {
    "multipliers": "99cda3cdcec54af0f3d95fc3a223593a5410515b",
    "triggers": "be44880217dbea3b6834463cde866cfd5a70b4a8",
    "actions": "3707c59f5f519561baea852d26d551a3d1e3ad77",
    "helpers": "0c90fcd95f10181dc375c386d03c7089e90bd6ef",
}


class PolicyEvidenceChanged(RuntimeError):
    pass


def git_blob_oid(text: str) -> str:
    binary = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(binary)).encode("ascii")
                        + b"\0" + binary).hexdigest()


def assert_exact_files(files: dict[str, str], playerbots_sha: str) -> None:
    if playerbots_sha != PINNED_PLAYERBOTS:
        raise PolicyEvidenceChanged("Unreviewed Playerbots commit: stop and re-review")
    for name, expected in PINNED_BLOBS.items():
        if name not in files or git_blob_oid(files[name]) != expected:
            raise PolicyEvidenceChanged(
                f"{name}: Playerbots source blob changed; source re-review required"
            )


def method_body(source: str, declaration: str) -> str:
    """Small balanced-body extractor; only used after whole-file source pin."""
    if source.count(declaration) != 1:
        raise PolicyEvidenceChanged(f"Expected exactly one {declaration!r}")
    start = source.index(declaration) + len(declaration)
    brace = source.find("{", start)
    if brace < 0:
        raise PolicyEvidenceChanged(f"No implementation of {declaration!r}")
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        if char == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise PolicyEvidenceChanged(f"Unbalanced body for {declaration!r}")


def require(text: str, token: str, where: str) -> None:
    if token not in text:
        raise PolicyEvidenceChanged(f"{where}: missing required source {token!r}")


def check_golemagg_contract(files: dict[str, str]) -> dict[str, bool]:
    helpers = files["helpers"]
    for token in (
        "SPELL_MAGMA_SPLASH = 13880",
        "MAGMA_SPLASH_BACK_OFF_STACKS = 20",
        "MAGMA_SPLASH_BACK_OFF_DISTANCE = 12.0f",
    ):
        require(helpers, token, "MCHelpers.h")
    trigger = method_body(files["triggers"],
                          "bool McGolemaggMagmaSplashTrigger::IsActive()")
    for token in (
        "PlayerbotAI::IsTank(bot)",
        "boss->GetHealthPct() <= 10.0f",
        "splash->GetStackAmount() < MAGMA_SPLASH_BACK_OFF_STACKS",
        "bot->GetDistance2d(boss) < MAGMA_SPLASH_BACK_OFF_DISTANCE",
    ):
        require(trigger, token, "MCTriggers.cpp")

    retreat = method_body(files["actions"],
                          "bool McGolemaggBackOffAction::Execute(Event /*event*/)")
    for token in (
        'AI_VALUE2(Unit*, "find target", "golemagg the incinerator")',
        "bot->CastStop();",
        "MAGMA_SPLASH_BACK_OFF_DISTANCE - bot->GetDistance2d(boss)",
        "return MoveAway(boss, distToTravel);",
    ):
        require(retreat, token, "MCActions.cpp")

    gate = method_body(files["multipliers"],
                       "float GolemaggMultiplier::GetValue(Action* action)")
    for token in (
        "bool burnPhase = golemagg->GetHealthPct() <= 10.0f;",
        "bool backedOff = splash && splash->GetStackAmount() >= MAGMA_SPLASH_BACK_OFF_STACKS;",
        "dynamic_cast<McGolemaggBackOffAction*>(action)",
        "dynamic_cast<AttackAction*>(action)",
        "dynamic_cast<MeleeAction*>(action)",
        "dynamic_cast<CastReachTargetSpellAction*>(action)",
        "!burnPhase && !PlayerbotAI::IsTank(bot) && backedOff && engagesBoss",
    ):
        require(gate, token, "MCMultipliers.cpp")
    # A broad MovementAction veto is present elsewhere (Baron Geddon)
    # but NOT in this exact Golemagg multiplier. Do not infer causal action
    # from category coverage. New movement gating changes require review.
    if "dynamic_cast<MovementAction*>(action)" in gate:
        raise PolicyEvidenceChanged(
            "Golemagg now mentions generic MovementAction: re-review policy"
        )
    require(files["multipliers"], "dynamic_cast<MovementAction*>(action)",
            "MCMultipliers.cpp Baron Geddon contrast")
    return {
        "retreat_trigger_threshold_20_12_verified": True,
        "selected_attack_action_suppression_verified": True,
        "general_movement_action_veto_proven": False,
        "actual_reengaging_action_observed": False,
        "safe_module_only_movement_fix_implemented": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--playerbots-sha", required=True)
    for name in PINNED_BLOBS:
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    files = {
        name: getattr(args, name).read_text(encoding="utf-8")
        for name in PINNED_BLOBS
    }
    assert_exact_files(files, args.playerbots_sha)
    for key, value in check_golemagg_contract(files).items():
        print(f"{key}={str(value).lower()}")
    print("A01_Golemagg_action_class_source_contract_PINNED_PASS")
    print("No module action veto, bot movement, Worldserver startup or in-game test.")


if __name__ == "__main__":
    main()
