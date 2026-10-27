"""Part29 narrow GFPP config access concurrency contract.

Protected #160 remains unchanged. The child changes only how the optional
GFPP enable switch is observed; it does not change item/aura behavior.
All tests are public-source/offline. None touches an owner server or SQL.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"
CONFIG = ROOT / "conf/mod_naxxramas_core.conf.dist"
KEY = "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled"


def text():
    return SOURCE.read_text(encoding="utf-8")


def section(a, b):
    data = text()
    return data.split(a, 1)[1].split(b, 1)[0]


class GfppConfigAtomicSnapshot(unittest.TestCase):
    def test_single_default_off_setting_and_single_worldthread_read(self):
        self.assertEqual(CONFIG.read_text(encoding="utf-8").count(KEY + " = 0"), 1)
        data = text()
        self.assertEqual(data.count('"' + KEY + '"'), 1)
        world = section(
            "void OnAfterConfigLoad(",
            "// World::Update calls this after MapMgr::Update"
        )
        self.assertIn('"' + KEY + '"', world)
        self.assertIn("GreaterFireProtectionOneShotEnabled.store(", world)
        self.assertIn("std::memory_order_relaxed", world)

    def test_default_off_atomic_and_release_safe_reader(self):
        data = text()
        self.assertIn(
            "std::atomic<bool> GreaterFireProtectionOneShotEnabled{ false };",
            data)
        get = section(
            "bool IsGreaterFireProtectionOneShotEnabled()",
            "}"
        )
        self.assertIn("GreaterFireProtectionOneShotEnabled.load(", get)
        self.assertIn("std::memory_order_relaxed", get)
        self.assertIn("#include <atomic>", data)

    def test_timer_and_schedule_do_not_access_mutable_configmgr(self):
        schedule = section(
            "void ApplyTimedGreaterFireProtection(",
            "// ========================================================="
        )
        timer = section(
            "void ProcessOneShotFireProtections(",
            "// ========================================================="
        )
        self.assertIn("!IsGreaterFireProtectionOneShotEnabled()", schedule)
        self.assertIn("!IsGreaterFireProtectionOneShotEnabled()", timer)
        self.assertNotIn("sConfigMgr->GetOption", schedule)
        self.assertNotIn("sConfigMgr->GetOption", timer)
        self.assertEqual(text().count("IsGreaterFireProtectionOneShotEnabled()"), 3)

    def test_reloaded_off_switch_cancels_already_consumed_once_attempt(self):
        data = text()
        timer = section(
            "void ProcessOneShotFireProtections(",
            "// ========================================================="
        )
        self.assertLess(timer.index("pending.Timer.ConsumeIfDue(diff)"),
                        timer.index("!IsGreaterFireProtectionOneShotEnabled()"))
        self.assertLess(timer.index("!IsGreaterFireProtectionOneShotEnabled()"),
                        timer.index("bot->AddAura(pending.SpellId, bot)"))
        self.assertIn("GreaterFireProtectionOneShotEnabled.store(", data)
        self.assertIn("WORLDHOOK_ON_AFTER_CONFIG_LOAD", data)
        # A reload changes the same atomic that both readers consult;
        # no silent restart-only change to historical feature semantics.

    def test_crossmap_atomic_and_other_p0_behavior_remain_separate(self):
        data = text()
        self.assertIn("std::atomic<bool> CrossMapAuraSafetyEnabled{ false };", data)
        self.assertIn("CrossMapAuraSafetyEnabled.store(", data)
        self.assertIn("CrossMapAuraSafetyEnabled.load(", data)
        self.assertIn("NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};", data)
        self.assertIn("pending.Timer.ConsumeIfDue(diff)", data)
        self.assertIn("pending.OriginallyRandomBot", data)
        self.assertIn("bot->GetMap() != master->GetMap()", data)
        self.assertIn("current->GetCasterGUID() != bot->GetGUID()", data)
        self.assertIn("if (!bot->AddAura(pending.SpellId, bot) &&", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
