"""Synthetic policy invariants; does NOT run Playerbots or a Worldserver."""
import importlib.util
from pathlib import Path
import sys
import unittest

checker = Path(__file__).resolve().parents[1] / "scripts/check_golemagg_retreat_policy_pinned.py"
spec = importlib.util.spec_from_file_location("golemagg_pinned_policy", checker)
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)


def fixture():
    helper = """constexpr uint32 MAGMA_SPLASH_BACK_OFF_STACKS = 20;
    constexpr float MAGMA_SPLASH_BACK_OFF_DISTANCE = 12.0f;"""
    trigger = """bool McGolemaggMagmaSplashTrigger::IsActive() {
      if (PlayerbotAI::IsTank(bot)) return false;
      if (!boss) return false;
      if (boss->GetHealthPct() <= 10.0f) return false;
      if (splash->GetStackAmount() < MAGMA_SPLASH_BACK_OFF_STACKS) return false;
      return bot->GetDistance2d(boss) < MAGMA_SPLASH_BACK_OFF_DISTANCE;
    }"""
    action = """bool McGolemaggBackOffAction::Execute(Event /*event*/) {
      float distToTravel = MAGMA_SPLASH_BACK_OFF_DISTANCE - bot->GetDistance2d(boss);
      if (distToTravel <= 0.0f) return true;
      return MoveAway(boss, distToTravel);
    }"""
    multiplier = """float GolemaggMultiplier::GetValue(Action* action) {
      bool burnPhase = golemagg->GetHealthPct() <= 10.0f;
      bool backedOff = splash && splash->GetStackAmount() >= MAGMA_SPLASH_BACK_OFF_STACKS;
      bool engagesBoss = (dynamic_cast<AttackAction*>(action) ||
                          dynamic_cast<MeleeAction*>(action) ||
                          dynamic_cast<CastReachTargetSpellAction*>(action));
      if (!burnPhase && !PlayerbotAI::IsTank(bot) && backedOff && engagesBoss)
          return 0.0f;
      return 1.0f;
    }"""
    strategy = """new TriggerNode("mc golemagg magma splash",
       { NextAction("mc golemagg back off", ACTION_RAID + 1) });
       multipliers.push_back(new GolemaggMultiplier(botAI));"""
    observer = """constexpr uint32 MAGMA_SPLASH_RETREAT_STACKS = 20;
       constexpr float MAGMA_SPLASH_RETREAT_YARDS = 12.0f;
       bool atRetreatStacks = stacks >= MAGMA_SPLASH_RETREAT_STACKS;
       bool inside = bossDistanceYards < MAGMA_SPLASH_RETREAT_YARDS;
       boss->GetHealthPct();"""
    summary = """sample.hp > 10.0 and sample.at_stacks and
       sample.inside_distance is True
       counters["sampled_retreat_condition_met"] += 1"""
    return [helper, trigger, action, multiplier, strategy, observer, summary]


class PinnedRetreatPolicyTests(unittest.TestCase):
    def test_exact_pinned_policy_shape(self):
        policy.pinned_policy(*fixture())

    def test_wrong_stack_and_distance_thresholds_fail(self):
        for index, old, new in (
            (0, "BACK_OFF_STACKS = 20", "BACK_OFF_STACKS = 15"),
            (0, "BACK_OFF_DISTANCE = 12.0f", "BACK_OFF_DISTANCE = 8.0f"),
            (5, "RETREAT_STACKS = 20", "RETREAT_STACKS = 10"),
            (5, "RETREAT_YARDS = 12.0f", "RETREAT_YARDS = 8.0f"),
        ):
            x = fixture()
            x[index] = x[index].replace(old, new)
            with self.subTest(index=index, old=old), self.assertRaises(ValueError):
                policy.pinned_policy(*x)

    def test_missing_actual_trigger_or_multiplier_fails(self):
        for index, needle in ((1, "GetStackAmount() < MAGMA_SPLASH_BACK_OFF_STACKS"),
                              (2, "return MoveAway(boss, distToTravel)"),
                              (3, "dynamic_cast<CastReachTargetSpellAction*>(action)"),
                              (4, "multipliers.push_back(new GolemaggMultiplier(botAI));")):
            x = fixture()
            x[index] = x[index].replace(needle, "// " + needle)
            with self.subTest(needle=needle), self.assertRaises(ValueError):
                policy.pinned_policy(*x)

    def test_offline_condition_requires_all_four_boundaries(self):
        check = policy.retreat_trigger
        self.assertFalse(check(False, True, 75.0, 19, 11.0))
        self.assertTrue(check(False, True, 75.0, 20, 11.99))
        self.assertFalse(check(False, True, 75.0, 20, 12.0))
        self.assertFalse(check(False, True, 10.0, 20, 9.0))
        self.assertFalse(check(True, True, 75.0, 25, 8.0))
        self.assertFalse(check(False, False, 75.0, 25, 8.0))

    def test_multiplier_blocks_only_verified_three_action_classes(self):
        check = policy.protected_engagement
        for action in ("AttackAction", "MeleeAction", "CastReachTargetSpellAction"):
            with self.subTest(action=action):
                self.assertTrue(check(False, True, 75.0, 21, action))
        for action in ("FollowAction", "MoveToAction", "McGolemaggBackOffAction"):
            with self.subTest(action=action):
                self.assertFalse(check(False, True, 75.0, 21, action))
        self.assertFalse(check(False, True, 75.0, 19, "AttackAction"))
        self.assertFalse(check(True, True, 75.0, 25, "AttackAction"))
        self.assertFalse(check(False, True, 10.0, 25, "AttackAction"))


if __name__ == "__main__":
    unittest.main()
