"""Source-contract checks for the default-OFF Golemagg melee reach guard.

These checks do not compile AzerothCore or prove in-game behaviour. They pin
the guard's narrow scope and its use of the Playerbots listener API, so a
later edit cannot quietly widen it into a general movement veto.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/BotGolemaggReachGuard.cpp").read_text()
POLICY = (ROOT / "src/Systems/GolemaggReachGuardPolicy.h").read_text()
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()


def code_only(text):
    """Strip // and /* */ comments so prose cannot satisfy a check."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


CODE = code_only(SOURCE)
POLICY_CODE = code_only(POLICY)


def method_body(code, signature):
    start = code.index(signature)
    brace = code.index("{", start)
    depth = 0
    for index in range(brace, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[brace:index + 1]
    raise AssertionError(f"unterminated body for {signature}")


class GolemaggReachGuardConfig(unittest.TestCase):
    def test_all_keys_default_off_or_empty(self):
        for line in (
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 0",
            'NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName = ""',
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug = 0",
        ):
            self.assertIn(line, CONFIG.splitlines())

    def test_code_defaults_match_config(self):
        self.assertRegex(
            CODE,
            r'GetOption<bool>\(\s*"NaxxramasCore\.Playerbots\.GolemaggMeleeGuard\.Enabled", false\)',
        )
        self.assertRegex(
            CODE,
            r'GetOption<bool>\(\s*"NaxxramasCore\.Playerbots\.GolemaggMeleeGuard\.Debug", false\)',
        )
        self.assertRegex(
            CODE,
            r'GetOption<std::string>\(\s*"NaxxramasCore\.Playerbots\.GolemaggMeleeGuard\.AllowedBotName", ""\)',
        )

    def test_each_key_appears_once(self):
        for key in ("Enabled", "AllowedBotName", "Debug"):
            pattern = rf"^NaxxramasCore\.Playerbots\.GolemaggMeleeGuard\.{key} ="
            self.assertEqual(len(re.findall(pattern, CONFIG, flags=re.M)), 1, key)

    def test_single_exact_name_gate_reused_from_observer(self):
        self.assertNotIn("AllowedBotNames", CONFIG + CODE)
        self.assertIn('#include "GolemaggActionAuditAllowlist.h"', CODE)
        self.assertIn(
            "NaxxramasGolemaggActionAudit::IsAllowedBotName(name, config.allowedBotName)", CODE
        )
        self.assertNotIn("NameFilter", CODE + POLICY_CODE)
        update = method_body(CODE, "void OnPlayerUpdate(Player* player")
        self.assertIn("IsGuardedBotName(config, player->GetName())", update)

    def test_existing_observer_keys_unchanged(self):
        self.assertIn("NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0", CONFIG)
        self.assertIn('NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName = ""', CONFIG)


class GolemaggReachGuardRegistration(unittest.TestCase):
    def test_loader_registers_once(self):
        self.assertEqual(LOADER.count("void AddBotGolemaggReachGuardScripts();"), 1)
        self.assertEqual(LOADER.count("    AddBotGolemaggReachGuardScripts();"), 1)
        self.assertEqual(LOADER.count("    AddBotGolemaggActionAuditScripts();"), 1)

    def test_only_player_update_hook(self):
        self.assertIn('PlayerScript("NaxxramasCoreGolemaggReachGuard", { PLAYERHOOK_ON_UPDATE })', CODE)
        self.assertNotIn("PLAYERHOOK_ON_LOGOUT", CODE)

    def test_registers_only_on_combat_engine_via_public_api(self):
        update = method_body(CODE, "void OnPlayerUpdate(Player* player")
        self.assertIn("ai->GetState() != BOT_STATE_COMBAT", update)
        self.assertIn("CurrentEngineOf(ai)", update)
        self.assertIn("NeedsRegistration(data->record, ai, engine)", update)
        self.assertIn("engine->AddActionExecutionListener(", update)
        self.assertIn("MOLTEN_CORE_MAP", update)
        self.assertIn("ai->IsAltBot()", update)
        self.assertIn("!config.enabled", update)

    def test_old_playerbots_fallback_is_compile_time_noop(self):
        self.assertIn("struct HasPublicCurrentEngine", CODE)
        self.assertIn("std::void_t<decltype(std::declval<T&>().GetCurrentEngine())>", CODE)
        self.assertIn("if constexpr (HasPublicCurrentEngine<T>::value)", CODE)
        self.assertIn("return nullptr;", method_body(CODE, "Engine* CurrentEngineOf(T* ai)"))

    def test_never_deletes_removes_or_reaches_into_engine(self):
        self.assertNotIn("removeActionExecutionListener", CODE)
        self.assertNotRegex(CODE, r"\bdelete\b")
        for forbidden in ("currentEngine", "engines[", "#define private", "#define protected"):
            self.assertNotIn(forbidden, CODE)

    def test_registration_record_is_never_erased(self):
        self.assertNotIn("CustomData.Erase", CODE)
        self.assertIn("CustomData.GetDefault<GuardRegistrationData>(GUARD_RECORD_KEY)", CODE)


class GolemaggReachGuardListener(unittest.TestCase):
    def test_before_is_the_only_deny_path(self):
        before = method_body(CODE, "bool Before(Action* action")
        self.assertIn("action->getName() != REACH_MELEE_ACTION", before)
        self.assertIn("ShouldDenyReachMelee(BuildContext(action))", before)
        self.assertEqual(before.count("return false;"), 1)

    def test_allow_execution_never_denies(self):
        allow = method_body(CODE, "bool AllowExecution(Action*")
        self.assertIn("return true;", allow)
        self.assertNotIn("false", allow)

    def test_after_and_override_are_pass_through(self):
        self.assertIn("return executed;", method_body(CODE, "bool OverrideResult(Action*"))
        after = method_body(CODE, "void After(Action*")
        self.assertEqual(after.strip("{} \n"), "")

    def test_destructor_only_clears_token(self):
        dtor = method_body(CODE, "~GolemaggReachGuardListener()")
        self.assertIn("_alive->store(false)", dtor)
        self.assertNotIn("_ai", dtor)

    def test_only_reach_melee_is_named(self):
        self.assertIn('REACH_MELEE_ACTION = "reach melee"', POLICY_CODE)
        for other in ('"reach spell"', '"set behind"', '"mc move from lava"', '"mc golemagg back off"'):
            self.assertNotIn(other, CODE + POLICY_CODE)
        self.assertNotIn("MovementAction", CODE)

    def test_context_uses_bot_and_current_target(self):
        build = method_body(CODE, "ReachMeleeContext BuildContext(Action* action) const")
        for required in (
            "_ai->IsAltBot()",
            "PlayerbotAI::IsTank(bot)",
            "PlayerbotAI::IsDps(bot)",
            "PlayerbotAI::IsMelee(bot)",
            "action->GetTarget()",
            "target->GetEntry()",
            "target->IsAlive()",
            "target->IsInCombat()",
            "target->GetHealthPct()",
            "bot->GetAura(MAGMA_SPLASH_SPELL)",
            "GetStackAmount()",
            "IsGuardedBotName(config, bot->GetName())",
        ):
            self.assertIn(required, build)

    def test_debug_logging_is_rate_limited(self):
        log = method_body(CODE, "void LogDeny()")
        self.assertIn("if (!GetGuardConfig().debug)", log)
        self.assertIn("DEBUG_LOG_INTERVAL_MS", log)


class GolemaggReachGuardPolicyConstants(unittest.TestCase):
    def test_thresholds_match_playerbots(self):
        for required in (
            "MOLTEN_CORE_MAP = 409",
            "GOLEMAGG_ENTRY = 11988",
            "MAGMA_SPLASH_SPELL = 13880",
            "MAGMA_SPLASH_BACK_OFF_STACKS = 20",
            "BURN_PHASE_HEALTH_PCT = 10.0f",
        ):
            self.assertIn(required, POLICY_CODE)

    def test_deny_requires_every_condition(self):
        body = method_body(POLICY_CODE, "inline bool ShouldDenyReachMelee(")
        for required in (
            "c.enabled", "c.botAlive", "c.mapId == MOLTEN_CORE_MAP", "c.isAltBot",
            "!c.isTank", "c.isDps", "c.isMelee", "c.nameAllowed", "c.targetPresent",
            "c.targetEntry == GOLEMAGG_ENTRY", "c.targetAlive", "c.targetInCombat",
            "c.targetHealthPct > BURN_PHASE_HEALTH_PCT",
            "c.magmaSplashStacks >= MAGMA_SPLASH_BACK_OFF_STACKS",
        ):
            self.assertIn(required, body)
        self.assertNotIn("||", body)

    def test_policy_header_is_dependency_free(self):
        includes = re.findall(r'#include [<"]([^>"]+)[>"]', POLICY)
        self.assertTrue(includes)
        for header in includes:
            self.assertNotIn(".h", header, header)


class GolemaggReachGuardIsolation(unittest.TestCase):
    def test_observer_source_untouched_by_guard(self):
        observer = (ROOT / "src/Systems/BotGolemaggActionAudit.cpp").read_text()
        self.assertNotIn("GolemaggReachGuard", observer)
        self.assertIn("Never access PlayerbotAI::currentEngine or register a listener.", observer)

    def test_no_sql_or_dbc_for_guard(self):
        for path in ROOT.glob("data/sql/**/*.sql"):
            self.assertNotIn("GolemaggMeleeGuard", path.read_text(errors="ignore"), path)


if __name__ == "__main__":
    unittest.main()
