#!/usr/bin/env python3
"""Pin Golemagg offline-summary thresholds to the actual Playerbots MC policy.

READ-ONLY local C++ source check. No executable game call, action veto,
server startup, realm logs, or Playerbots/AzerothCore source edits.
"""
import argparse
from pathlib import Path
import re


def strip_comments(source):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)


def contains(source, needles, label):
    code = strip_comments(source)
    for needle in needles:
        if needle not in code:
            raise ValueError(f"{label}: pinned policy changed/missing {needle}")


def pinned_policy(helper, trigger, action, multiplier, strategy, observer, summary):
    """Fail closed when checked thresholds, classes or registration drift."""
    contains(helper, (
        "MAGMA_SPLASH_BACK_OFF_STACKS = 20",
        "MAGMA_SPLASH_BACK_OFF_DISTANCE = 12.0f",
    ), "MC constant")
    contains(trigger, (
        "bool McGolemaggMagmaSplashTrigger::IsActive()",
        "if (PlayerbotAI::IsTank(bot))",
        "if (!boss)",
        "if (boss->GetHealthPct() <= 10.0f)",
        "GetStackAmount() < MAGMA_SPLASH_BACK_OFF_STACKS",
        "return bot->GetDistance2d(boss) < MAGMA_SPLASH_BACK_OFF_DISTANCE",
    ), "MC retreat trigger")
    contains(action, (
        "bool McGolemaggBackOffAction::Execute(Event ",
        "float distToTravel = MAGMA_SPLASH_BACK_OFF_DISTANCE - bot->GetDistance2d(boss)",
        "if (distToTravel <= 0.0f)",
        "return MoveAway(boss, distToTravel)",
    ), "MC retreat action")
    contains(multiplier, (
        "float GolemaggMultiplier::GetValue(Action* action)",
        "bool burnPhase = golemagg->GetHealthPct() <= 10.0f",
        "GetStackAmount() >= MAGMA_SPLASH_BACK_OFF_STACKS",
        "dynamic_cast<AttackAction*>(action)",
        "dynamic_cast<MeleeAction*>(action)",
        "dynamic_cast<CastReachTargetSpellAction*>(action)",
        "!burnPhase && !PlayerbotAI::IsTank(bot) && backedOff && engagesBoss",
    ), "MC engagement multiplier")
    contains(strategy, (
        'new TriggerNode("mc golemagg magma splash"',
        'NextAction("mc golemagg back off", ACTION_RAID + 1)',
        "multipliers.push_back(new GolemaggMultiplier(botAI));",
    ), "MC strategy installation")
    contains(observer, (
        "MAGMA_SPLASH_RETREAT_STACKS = 20",
        "MAGMA_SPLASH_RETREAT_YARDS = 12.0f",
        "stacks >= MAGMA_SPLASH_RETREAT_STACKS",
        "bossDistanceYards < MAGMA_SPLASH_RETREAT_YARDS",
        "boss->GetHealthPct()",
    ), "Naxx Golemagg observer")
    contains(summary, (
        "sample.hp > 10.0",
        "sample.at_stacks",
        "sample.inside_distance is True",
        "sampled_retreat_condition_met",
    ), "offline counter contract")


def retreat_trigger(tank, boss_found, boss_hp, stacks, distance):
    """Disposable model of *one* pinned Playerbots back-off trigger."""
    return (not tank and boss_found and boss_hp > 10.0
            and stacks >= 20 and distance < 12.0)


def protected_engagement(tank, boss_found, boss_hp, stacks, action_type):
    """Do not generalize the pinned class filter to all movement actions."""
    return (not tank and boss_found and boss_hp > 10.0 and stacks >= 20
            and action_type in {
                "AttackAction", "MeleeAction", "CastReachTargetSpellAction"
            })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("helper", "trigger", "action", "multiplier", "strategy",
                 "observer", "summary"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        pinned_policy(*(getattr(args, key).read_text(encoding="utf-8")
                        for key in ("helper", "trigger", "action",
                                    "multiplier", "strategy", "observer",
                                    "summary")))
    except (OSError, ValueError) as error:
        print("FAIL: Golemagg threshold summary cannot be certified: " + str(error))
        return 1
    print("PASS: pinned normal MC Golemagg 20-stack / 12-yard / >10%-HP "
          "policy matches offline observer assumptions.")
    print("LIMIT: only named engagement classes blocked; no claim of "
          "movement causality, action execution, or live-game behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
