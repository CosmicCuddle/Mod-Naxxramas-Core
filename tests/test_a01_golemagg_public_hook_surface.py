"""Negative source mutation tests; no game server, character or movement changes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_a01_golemagg_public_hook_surface import (  # noqa: E402
    SourceSurfaceChanged, check_public_movement_surface,
)

FIXTURE = {
    "playerbot": """public:
    void ChangeStrategy(std::string const name, BotState type);
protected:
    Engine* currentEngine;
    Engine* engines[BOT_STATE_MAX];
""",
    "engine": "void AddActionExecutionListener(ActionExecutionListener* listener) { actionExecutionListeners.Add(listener); }",
    "context": """protected:
    NamedObjectContextList<Strategy> strategyContexts;
private:
    static SharedNamedObjectContextList<Strategy> sharedStrategyContexts;
public:
    static void BuildSharedStrategyContexts(SharedNamedObjectContextList<Strategy>& strategyContexts);""",
    "named": "std::unordered_map<std::string, ObjectCreator> const& creators;",
    "mc": """void RaidMcStrategy::InitMultipliers(std::vector<Multiplier*>& multipliers)
{
    multipliers.push_back(new GolemaggMultiplier(botAI));
}""",
    "movement": """MOVEMENTHOOK_ON_PLAYER_MOVE,
virtual void OnPlayerMove(Player* /*player*/, MovementInfo /*movementInfo*/, uint32 /*opcode*/) { }""",
    "movement_impl": """void ScriptMgr::OnPlayerMove(Player* player, MovementInfo movementInfo, uint32 opcode)
{
CALL_ENABLED_HOOKS(MovementHandlerScript, MOVEMENTHOOK_ON_PLAYER_MOVE, script->OnPlayerMove(player, movementInfo, opcode));
}""",
    "player": "virtual void OnPlayerUpdate(Player* /*player*/, uint32 /*p_time*/) { }",
    "unit": "virtual void OnUnitUpdate(Unit* /*unit*/, uint32 /*diff*/) { }",
}

class HookSurfaceEvidence(unittest.TestCase):
    def test_pinned_fixture_reports_limit_not_fix(self):
        proof = check_public_movement_surface(FIXTURE)
        self.assertTrue(proof["core_movement_hook_void_observation_only"])
        self.assertFalse(proof["safe_module_only_movement_fix_implemented"])
        self.assertFalse(proof["external_golemagg_action_veto_proven"])

    def test_public_engine_member_change_requires_new_review(self):
        changed = dict(FIXTURE)
        changed["playerbot"] = changed["playerbot"].replace(
            "protected:\n", "public:\n", 1)
        with self.assertRaises(SourceSurfaceChanged):
            check_public_movement_surface(changed)

    def test_factory_registry_visibility_change_requires_new_review(self):
        changed = dict(FIXTURE)
        changed["context"] = changed["context"].replace(
            "private:\n", "public:\n")
        with self.assertRaises(SourceSurfaceChanged):
            check_public_movement_surface(changed)

    def test_inserted_public_labels_between_guard_and_member_fail_closed(self):
        # CS02 review: rfind(protected:) missed a *closer* public: label.
        cases = (
            ("playerbot", "    Engine* currentEngine;",
             "public:\n    Engine* currentEngine;"),
            ("playerbot", "    Engine* engines[BOT_STATE_MAX];",
             "public:\n    Engine* engines[BOT_STATE_MAX];"),
            ("context", "    NamedObjectContextList<Strategy> strategyContexts;",
             "public:\n    NamedObjectContextList<Strategy> strategyContexts;"),
            ("context", "    static SharedNamedObjectContextList<Strategy> sharedStrategyContexts;",
             "public:\n    static SharedNamedObjectContextList<Strategy> sharedStrategyContexts;"),
        )
        for key, needle, replacement in cases:
            with self.subTest(member=needle):
                changed = dict(FIXTURE)
                changed[key] = changed[key].replace(needle, replacement)
                with self.assertRaises(SourceSurfaceChanged):
                    check_public_movement_surface(changed)

    def test_strategy_selector_changed_to_protected_fails_closed(self):
        changed = dict(FIXTURE)
        changed["playerbot"] = changed["playerbot"].replace(
            "    void ChangeStrategy", "protected:\n    void ChangeStrategy")
        with self.assertRaises(SourceSurfaceChanged):
            check_public_movement_surface(changed)

    def test_tab_indented_closer_public_labels_fail_closed(self):
        # A literal "\\\\t" in a raw regex meant 'backslash or t', not TAB;
        # verify actual TAB prefixes are visible to the access-label parser.
        cases = (
            ("playerbot", "    Engine* currentEngine;"),
            ("playerbot", "    Engine* engines[BOT_STATE_MAX];"),
            ("context", "    NamedObjectContextList<Strategy> strategyContexts;"),
            ("context", "    static SharedNamedObjectContextList<Strategy> sharedStrategyContexts;"),
        )
        for source_name, original in cases:
            with self.subTest(symbol=original):
                changed = dict(FIXTURE)
                changed[source_name] = changed[source_name].replace(
                    original, "\tpublic:\n" + original)
                with self.assertRaises(SourceSurfaceChanged):
                    check_public_movement_surface(changed)

    def test_movement_handler_veto_signature_change_requires_new_review(self):
        changed = dict(FIXTURE)
        changed["movement"] = changed["movement"].replace(
            "virtual void OnPlayerMove", "virtual bool OnPlayerMove")
        with self.assertRaises(SourceSurfaceChanged):
            check_public_movement_surface(changed)

    def test_movement_dispatch_modification_requires_new_review(self):
        changed = dict(FIXTURE)
        changed["movement_impl"] = changed["movement_impl"].replace(
            "CALL_ENABLED_HOOKS", "CALL_VETO_HOOKS")
        with self.assertRaises(SourceSurfaceChanged):
            check_public_movement_surface(changed)

    def test_golemagg_multiplier_is_not_proof_of_general_move_veto(self):
        changed = dict(FIXTURE)
        changed["mc"] = changed["mc"].replace(
            "multipliers.push_back(new GolemaggMultiplier(botAI));",
            "// no GolemaggMultiplier")
        with self.assertRaises(SourceSurfaceChanged):
            check_public_movement_surface(changed)

    def test_update_hooks_changed_require_new_review(self):
        for name in ("unit", "player"):
            with self.subTest(file=name):
                changed = dict(FIXTURE)
                changed[name] = changed[name].replace("virtual void", "virtual bool")
                with self.assertRaises(SourceSurfaceChanged):
                    check_public_movement_surface(changed)

    def test_missing_sources_require_new_review(self):
        for name in FIXTURE:
            with self.subTest(file=name):
                changed = dict(FIXTURE)
                changed[name] = ""
                with self.assertRaises(SourceSurfaceChanged):
                    check_public_movement_surface(changed)

if __name__ == "__main__":
    unittest.main()
