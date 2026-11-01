"""P4 quest loot view guard: source contract and RED/GREEN on pinned bodies.

Requires A04_CORE (pinned Grimfeather 8daffda checkout) for the harness test;
it FAILS rather than skips when A04_CORE is missing.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "p4_view_guard"))
import build_guard  # noqa: E402

EXPECTED_CHECKS = 24
REQUIRED = [
    "BASE.T1_RED_view_marks_shared_looted_A_denied",
    "BASE.T2_RED_A_sees_no_row_and_is_denied",
    "GUARD.T1_B_view_marks_only_own_row_not_shared",
    "GUARD.T1_A_awarded_exactly_one",
    "GUARD.T1_corpse_settles",
    "GUARD.T1_rows_identical_to_pinned",
    "GUARD.T2_A_sees_allow_loot_row",
    "GUARD.T2_A_awarded_and_corpse_settles",
    "GUARD.T2_B_after_view_cannot_take",
    "GUARD.T3_rows_identical_to_pinned",
    "GUARD.T4a_first_taker_single_copy_unchanged",
    "GUARD.C1_ffa_both_copies",
    "GUARD.C3_master_rows_identical_to_pinned",
]

SCRIPT = (ROOT / "src" / "Systems" / "QuestLootViewGuard.cpp").read_text()
HEADER = (ROOT / "src" / "Systems" / "QuestLootViewGuard.h").read_text()
HEADER_CODE = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", HEADER, flags=re.S))
LOADER = (ROOT / "src" / "NaxxramasCore_loader.cpp").read_text()
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text()


class SourceContract(unittest.TestCase):
    def test_default_off_in_conf_and_code(self):
        self.assertEqual(CONF.count("NaxxramasCore.QuestLootViewGuard.Enabled"), 1)
        self.assertIn("\nNaxxramasCore.QuestLootViewGuard.Enabled = 0\n", CONF)
        self.assertIn('GetOption<bool>("NaxxramasCore.QuestLootViewGuard.Enabled", false)', SCRIPT)
        self.assertIn("std::atomic<bool> s_viewGuardEnabled{false};", SCRIPT)

    def test_config_read_only_on_world_thread_hook(self):
        # One ConfigMgr read, inside OnAfterConfigLoad; the loot hook reads the atomic only.
        self.assertEqual(SCRIPT.count("sConfigMgr"), 1)
        after = SCRIPT.index("void OnAfterConfigLoad(bool /*reload*/) override")
        loot = SCRIPT.index("void OnPlayerBeforeSendLoot(Player* player, ObjectGuid /*lootGuid*/, Loot* loot) override")
        self.assertLess(after, SCRIPT.index("sConfigMgr"))
        self.assertLess(SCRIPT.index("sConfigMgr"), loot)
        self.assertIn("{WORLDHOOK_ON_AFTER_CONFIG_LOAD}", SCRIPT)
        self.assertIn("{PLAYERHOOK_ON_BEFORE_SEND_LOOT}", SCRIPT)

    def test_hook_calls_the_shared_header_function(self):
        self.assertIn('#include "QuestLootViewGuard.h"', SCRIPT)
        self.assertEqual(SCRIPT.count("NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(player, *loot);"), 1)
        self.assertIn('#include "QuestLootViewGuard.h"', (ROOT / "tests" / "p4_view_guard" / "guard_harness.cpp").read_text())

    def test_header_writes_only_the_viewers_own_row(self):
        writes = re.findall(r"^\s*(\S+)\s*=\s*[^=].*;$", HEADER_CODE, re.M)
        assigned = [w for w in writes if not w.startswith(("bool", "QuestItemMap", "LootItem", "uint32"))]
        self.assertEqual(assigned, ["row.is_looted"])
        self.assertNotIn("unlootedCount", HEADER_CODE)
        self.assertNotIn("roundRobinPlayer", HEADER_CODE)

    def test_loader_registers_once(self):
        self.assertEqual(LOADER.count("void AddQuestLootViewGuardScripts();"), 1)
        self.assertEqual(LOADER.count("    AddQuestLootViewGuardScripts();"), 1)
        self.assertIn("    AddQuestLootProtectionScripts();\n    AddQuestLootViewGuardScripts();\n", LOADER)


class RedGreenOnPinnedBodies(unittest.TestCase):
    def test_pinned_red_then_guard_green(self):
        core = os.environ.get("A04_CORE")
        if not core:
            raise AssertionError("A04_CORE is not set")
        with tempfile.TemporaryDirectory(prefix="p4-guard-") as tmp:
            compiled, rc, output = build_guard.run(Path(core), Path(tmp))
        print(output)
        self.assertTrue(compiled, output[-4000:])
        checks = build_guard.parse_checks(output)
        if len(checks) != EXPECTED_CHECKS:
            self.fail(f"COUNT DRIFT: {len(checks)} checks, expected {EXPECTED_CHECKS}")
        self.assertEqual([c for v, c in checks if v == "FAIL"], [])
        self.assertEqual(rc, 0)
        for cid in REQUIRED:
            self.assertIn(("PASS", cid), checks)
        self.assertIn(f"CHECKS {EXPECTED_CHECKS} passed, 0 failed", output)


if __name__ == "__main__":
    unittest.main()
