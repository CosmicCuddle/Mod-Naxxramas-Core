"""Disposable source and C++ timer tests for the optional MC GFPP one-shot.

The harness has no server process, character DB, items or Playerbot instances.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"
HEADER = ROOT / "src/Systems/GreaterFireProtectionOneShot.h"
CONFIG = ROOT / "conf/mod_naxxramas_core.conf.dist"
FLAG = "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled"


class GreaterFireProtectionOneShot(unittest.TestCase):
    def test_standalone_native_timer_exact_once_after_120s(self):
        compiler = shutil.which("g++")
        if compiler is None:
            self.fail("g++ is mandatory for a native one-shot timing regression test")
        code = r"""
#include "GreaterFireProtectionOneShot.h"
#include <cassert>
int main()
{
    NaxxramasOneShotTimer exact(120000);
    assert(!exact.ConsumeIfDue(0));
    assert(!exact.ConsumeIfDue(119999));
    assert(exact.RemainingMs == 1);
    assert(exact.ConsumeIfDue(1));
    assert(!exact.Pending);
    assert(exact.RemainingMs == 0);
    assert(!exact.ConsumeIfDue(120000));
    assert(!exact.ConsumeIfDue(1000000));

    NaxxramasOneShotTimer ticks(120000);
    for (int i = 0; i < 120; ++i)
        assert(!ticks.ConsumeIfDue(1000) || i == 119);
    assert(!ticks.Pending);
    assert(!ticks.ConsumeIfDue(120000));

    NaxxramasOneShotTimer bigDiff(120000);
    assert(bigDiff.ConsumeIfDue(200000));
    assert(!bigDiff.ConsumeIfDue(200000));

    NaxxramasOneShotTimer independent(120000);
    assert(!independent.ConsumeIfDue(30000));
    NaxxramasOneShotTimer nextCommand(120000);
    assert(nextCommand.ConsumeIfDue(120000));
    assert(!independent.ConsumeIfDue(89999));
    assert(independent.ConsumeIfDue(1));
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "test.cpp"
            executable = folder / "timer-test"
            source.write_text(code, encoding="utf-8")
            compiled = subprocess.run(
                [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                 "-I", str(HEADER.parent), str(source), "-o", str(executable)],
                capture_output=True, text=True, timeout=40,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(executable)], capture_output=True, text=True,
                timeout=12, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_schedules_exactly_one_120s_deadline(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(
            source.count("NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};"), 1
        )
        self.assertNotIn("NaxxramasOneShotTimer Timer{90 * IN_MILLISECONDS};", source)

    def test_config_is_default_off_and_matches_consumer(self):
        config = CONFIG.read_text(encoding="utf-8")
        source = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(config.count(FLAG + " = 0"), 1)
        self.assertIn('"' + FLAG + '"', source)
        self.assertIn("GetOption<bool>", source)
        self.assertIn("false) || !spellId", source)

    def test_only_molten_core_preparation_schedules_fire_protection(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(source.count("ApplyTimedGreaterFireProtection(bot, tracker, stats);"), 1)
        self.assertIn('tracker.Profile != "mc"', source)
        self.assertIn("pending.Timer.ConsumeIfDue(diff)", source)
        self.assertIn("OneShotFireProtection pending;", source)
        self.assertIn("tracker.FireProtectionOneShots.push_back(pending);", source)
        self.assertIn("if (!ApplyItemAura(", source)

    def test_juju_flurry_legacy_timer_is_unchanged(self):
        source = SOURCE.read_text(encoding="utf-8")
        segment = source.split("void ApplyTimedJujuFlurry(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("timed.ApplicationsUsed = 1;", segment)
        self.assertIn("timed.MaxApplications = 3;", segment)
        self.assertIn("60 * IN_MILLISECONDS", segment)
        # Existing JujuFlurry loop remains distinct from the new one-shot path.
        timed = source.split("void ProcessTimedAuras(", 1)[1].split(
            "void ProcessOneShotFireProtections(", 1)[0]
        self.assertIn("timed.ApplicationsUsed", timed)
        self.assertIn("5 * IN_MILLISECONDS", timed)
        self.assertIn("60 * IN_MILLISECONDS", timed)

    def test_scoped_original_bot_and_random_group_required(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ProcessOneShotFireProtections(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("ResolvePreparedBot(", section)
        self.assertIn("manager, pending.BotGuid", section)
        self.assertIn("!bot->IsInWorld()", section)
        self.assertIn("!bot->IsAlive()", section)
        self.assertIn("IsProfileLocationValid(", section)
        self.assertIn("pending.OriginallyRandomBot", section)
        self.assertIn("RandomBotIsInPreparationScope(master, bot)", section)
        self.assertIn("BotIsInPreparationScope(master, bot)", section)

    def test_dead_master_never_reapplies_due_protection(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ProcessOneShotFireProtections(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("!master->IsAlive()", section)
        self.assertLess(section.index("pending.Timer.ConsumeIfDue(diff)"),
                        section.index("!master->IsAlive()"))

    def test_same_worldserver_instance_required_not_only_map_id(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ProcessOneShotFireProtections(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("bot->GetMap() != master->GetMap()", section)
        self.assertLess(section.index("pending.Timer.ConsumeIfDue(diff)"),
                        section.index("bot->GetMap() != master->GetMap()"))

    def test_config_disable_reload_and_failure_report_are_once_only(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ProcessOneShotFireProtections(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn('"' + FLAG + '"', section)
        self.assertIn("!bot->AddAura(pending.SpellId, bot)", section)
        self.assertIn("one-time refresh failed", section)
        self.assertLess(section.index("pending.Timer.ConsumeIfDue(diff)"),
                        section.index("GetOption<bool>("))
        self.assertLess(section.index("pending.Timer.ConsumeIfDue(diff)"),
                        section.index("!bot->AddAura(pending.SpellId, bot)"))

    def test_cross_caster_aura_is_never_overwritten(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ProcessOneShotFireProtections(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("if (Aura* current = bot->GetAura(pending.SpellId))",
                      section)
        self.assertIn("current->GetCasterGUID() != bot->GetGUID()", section)
        self.assertNotIn("RemoveAurasDueToSpell(", section)
        self.assertIn("bot->AddAura(pending.SpellId, bot)", section)
        self.assertLess(section.index("current->GetCasterGUID()"),
                        section.index("bot->AddAura(pending.SpellId, bot)"))
        self.assertLess(section.index("pending.Timer.ConsumeIfDue(diff)"),
                        section.index("bot->AddAura(pending.SpellId, bot)"))

    def test_failed_one_shot_attempt_never_preemptively_removes_absorb(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ProcessOneShotFireProtections(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("if (!bot->AddAura(pending.SpellId, bot) &&", section)
        self.assertIn("one-time refresh failed", section)
        self.assertNotIn("bot->RemoveAura(", section)
        self.assertNotIn("bot->RemoveAurasDueToSpell(", section)
        self.assertNotIn("SetStackAmount(", section)

    def test_clear_reset_and_logout_cancel_future_actions(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("tracker.FireProtectionOneShots.clear();"), 2)
        self.assertIn("RaidConsumableTrackers.erase(", source)
        self.assertIn("OnPlayerLogout(", source)
        self.assertIn("ProcessOneShotFireProtections(player, tracker, diff);", source)

    def test_only_one_pending_record_for_same_guid(self):
        source = SOURCE.read_text(encoding="utf-8")
        section = source.split("void ApplyTimedGreaterFireProtection(", 1)[1].split(
            "// =========================================================", 1)[0]
        self.assertIn("if (existing.BotGuid == guid)", section)
        self.assertIn("return;", section)
        self.assertIn("sRandomPlayerbotMgr.GetPlayerBot(guid) == bot", section)
        self.assertIn("tracker.FireProtectionOneShots.push_back(pending)", section)


if __name__ == "__main__":
    unittest.main()
