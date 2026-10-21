"""Synthetic read-only Playerbots Golemagg action-class source contract.

Tests are designed to catch drift or overclaiming, not to move a bot.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_a01_golemagg_reengagement_gap import (  # noqa: E402
    PINNED_BLOBS, PINNED_PLAYERBOTS, PolicyEvidenceChanged,
    assert_exact_files, check_golemagg_contract, git_blob_oid,
)

FILES = {
    "helpers": """
SPELL_MAGMA_SPLASH = 13880,
constexpr uint32 MAGMA_SPLASH_BACK_OFF_STACKS = 20;
constexpr float MAGMA_SPLASH_BACK_OFF_DISTANCE = 12.0f;
""",
    "triggers": """
bool McGolemaggMagmaSplashTrigger::IsActive() {
    if (PlayerbotAI::IsTank(bot)) return false;
    if (boss->GetHealthPct() <= 10.0f) return false;
    if (splash->GetStackAmount() < MAGMA_SPLASH_BACK_OFF_STACKS) return false;
    return bot->GetDistance2d(boss) < MAGMA_SPLASH_BACK_OFF_DISTANCE;
}
""",
    "actions": """
bool McGolemaggBackOffAction::Execute(Event /*event*/) {
    Unit* boss = AI_VALUE2(Unit*, "find target", "golemagg the incinerator");
    bot->CastStop();
    float dist = MAGMA_SPLASH_BACK_OFF_DISTANCE - bot->GetDistance2d(boss);
    return MoveAway(boss, distToTravel);
}
""",
    "movement_h": """
class MovementAction : public Action
{
};
""",
    "reach_h": """
class ReachTargetAction : public MovementAction
{
};
class ReachMeleeAction : public ReachTargetAction
{
    ReachMeleeAction() : ReachTargetAction(botAI, "reach melee", 5.0f) {}
};
""",
    "reach_cpp": """
bool ReachTargetAction::Execute(Event /*event*/) { return ReachCombatTo(AI_VALUE(Unit*, GetTargetName()), distance); }
std::string const ReachTargetAction::GetTargetName() { return "current target"; }
""",
    "attack_h": """
class AttackAction : public MovementAction
{
};
class MeleeAction : public AttackAction
{
};
""",
    "multipliers": """
bool IsAllowedGeddonMovementAction(Action* action) {
    return !dynamic_cast<MovementAction*>(action);
}
float GolemaggMultiplier::GetValue(Action* action) {
    bool burnPhase = golemagg->GetHealthPct() <= 10.0f;
    bool backedOff = splash && splash->GetStackAmount() >= MAGMA_SPLASH_BACK_OFF_STACKS;
    bool engagesBoss = !dynamic_cast<McGolemaggBackOffAction*>(action) &&
        (dynamic_cast<AttackAction*>(action) || dynamic_cast<MeleeAction*>(action) ||
         dynamic_cast<CastReachTargetSpellAction*>(action));
    if (!burnPhase && !PlayerbotAI::IsTank(bot) && backedOff && engagesBoss)
        return 0.0f;
    return 1.0f;
}
""",
}


class GolemaggMovementGapContract(unittest.TestCase):
    def test_fixture_proves_only_scoped_gate_not_actual_movement_fix(self):
        facts = check_golemagg_contract(FILES)
        self.assertTrue(facts["retreat_trigger_threshold_20_12_verified"])
        self.assertTrue(facts["selected_attack_action_suppression_verified"])
        self.assertFalse(facts["general_movement_action_veto_proven"])
        self.assertTrue(facts["reach_melee_is_unfiltered_movement_class_candidate"])
        self.assertFalse(facts["actual_reengaging_action_observed"])
        self.assertFalse(facts["safe_module_only_movement_fix_implemented"])

    def test_new_generic_movement_interception_requires_new_review(self):
        changed = dict(FILES)
        changed["multipliers"] = changed["multipliers"].replace(
            "bool engagesBoss =", "bool allMovement = "
            "dynamic_cast<MovementAction*>(action);\n"
            "    bool engagesBoss =")
        with self.assertRaises(PolicyEvidenceChanged):
            check_golemagg_contract(changed)

    def test_reach_melee_sibling_movement_class_evidence(self):
        # This is SOURCE TYPE hierarchy, not an in-game action trace.
        facts = check_golemagg_contract(FILES)
        self.assertTrue(facts["reach_melee_is_unfiltered_movement_class_candidate"])
        self.assertFalse(facts["actual_reengaging_action_observed"])
        self.assertIn("class ReachTargetAction : public MovementAction",
                      FILES["reach_h"])
        self.assertIn("class AttackAction : public MovementAction",
                      FILES["attack_h"])
        self.assertNotIn("class ReachMeleeAction : public AttackAction",
                         FILES["reach_h"])

    def test_changed_reach_melee_parents_or_movement_execution_fail_closed(self):
        cases = (
            ("reach_h",
             "class ReachTargetAction : public MovementAction",
             "class ReachTargetAction : public AttackAction"),
            ("reach_h",
             "class ReachMeleeAction : public ReachTargetAction",
             "class ReachMeleeAction : public AttackAction"),
            ("reach_h",
             'ReachTargetAction(botAI, "reach melee",',
             'ReachTargetAction(botAI, "other action",'),
            ("reach_cpp",
             "return ReachCombatTo(AI_VALUE(Unit*, GetTargetName()), distance);",
             "return true;"),
            ("reach_cpp", 'return "current target";',
             'return "another target";'),
            ("movement_h", "class MovementAction : public Action",
             "class MovementAction : public NewBase"),
            ("attack_h", "class AttackAction : public MovementAction",
             "class AttackAction : public Action"),
        )
        for key, before, after in cases:
            with self.subTest(key=key, before=before):
                changed = dict(FILES)
                changed[key] = changed[key].replace(before, after)
                self.assertNotEqual(changed[key], FILES[key])
                with self.assertRaises(PolicyEvidenceChanged):
                    check_golemagg_contract(changed)

    def test_changed_retreat_thresholds_or_burn_override_require_new_review(self):
        cases = (
            ("helpers", "MAGMA_SPLASH_BACK_OFF_STACKS = 20",
             "MAGMA_SPLASH_BACK_OFF_STACKS = 15"),
            ("helpers", "MAGMA_SPLASH_BACK_OFF_DISTANCE = 12.0f",
             "MAGMA_SPLASH_BACK_OFF_DISTANCE = 9.0f"),
            ("triggers", "boss->GetHealthPct() <= 10.0f",
             "boss->GetHealthPct() <= 20.0f"),
            ("triggers", "PlayerbotAI::IsTank(bot)",
             "PlayerbotAI::IsDps(bot)"),
        )
        for name, old, new in cases:
            with self.subTest(name=name, old=old):
                changed = dict(FILES)
                changed[name] = changed[name].replace(old, new)
                with self.assertRaises(PolicyEvidenceChanged):
                    check_golemagg_contract(changed)

    def test_removed_attack_reach_gate_or_moveaway_requires_review(self):
        cases = (
            ("multipliers", "dynamic_cast<AttackAction*>(action)"),
            ("multipliers", "dynamic_cast<MeleeAction*>(action)"),
            ("multipliers", "dynamic_cast<CastReachTargetSpellAction*>(action)"),
            ("actions", "return MoveAway(boss, distToTravel);"),
        )
        for name, item in cases:
            with self.subTest(item=item):
                changed = dict(FILES)
                changed[name] = changed[name].replace(item, "/* changed */")
                with self.assertRaises(PolicyEvidenceChanged):
                    check_golemagg_contract(changed)

    def test_pinned_file_identity_must_be_checked_before_parsing(self):
        self.assertEqual(len(PINNED_BLOBS), 8)
        self.assertEqual(
            PINNED_PLAYERBOTS,
            "037c01418b5d01506917a3db9b44fd56ac5f965c")
        self.assertEqual(
            git_blob_oid("hello\n"),
            "ce013625030ba8dba906f756967f9e9ca394464a")
        for ref in (PINNED_PLAYERBOTS, "unreviewed-new-source"):
            with self.subTest(ref=ref):
                with self.assertRaises(PolicyEvidenceChanged):
                    assert_exact_files(FILES, ref)

    def test_missing_or_duplicate_implementation_fails_closed(self):
        for name, signature in (
            ("multipliers", "float GolemaggMultiplier::GetValue(Action* action)"),
            ("triggers", "bool McGolemaggMagmaSplashTrigger::IsActive()"),
            ("actions", "bool McGolemaggBackOffAction::Execute(Event /*event*/)"),
        ):
            changed = dict(FILES)
            changed[name] += "\n" + signature + " { return false; }\n"
            with self.subTest(method=signature):
                with self.assertRaises(PolicyEvidenceChanged):
                    check_golemagg_contract(changed)

    def test_production_cli_runs_sha_gate_before_interpretation(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "check_a01_golemagg_reengagement_gap.py").read_text()
        main = source.split("def main() -> None:", 1)[1]
        self.assertLess(main.index("assert_exact_files(files, args.playerbots_sha)"),
                        main.index("check_golemagg_contract(files)"))
        self.assertNotIn("MovementAction::Execute(", source)
        self.assertNotIn("DoSpecificAction(", source)


if __name__ == "__main__":
    unittest.main()
