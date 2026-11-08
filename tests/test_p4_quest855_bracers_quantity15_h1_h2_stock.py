"""READ-ONLY P4 reproduction model: quest 855 / item 5030 / 15 required.

The simulator uses actual Naxx H1+H2 headers and extracted pinned original
Core LootView/Player::StoreLootItem, but synthetic quest/item/drop rows.
It does NOT read or prove installed SQL, worldserver, configs or 3.3.5a client.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/a04_native"))
import build  # noqa: E402

HARNESS = ROOT / "tests/p4_quest855_barrens_bracers_h1_h2_stock.cpp"
TEST_PREFIX = "Q855."
REQUIRED = (
    "setup_A_14_B_14_and_one_in_bank",
    "corpse_has_normal_plus_required_quest_row",
    "normal_loot_awarded_A_without_using_quest_row",
    "only_required_quest_item_remains_unlooted",
    "B_incomplete_still_sparkles_for_rightful_quest_need",
    "B_incomplete_passive_view_does_not_consume_A_quest_item",
    "B_completes_15_after_corpse_but_A_still_needs_one",
    "B_old_cached_quest_row_remains_after_completion",
    "B_stock_view_may_still_show_LOCKED_quest_row",
    "B_H1_only_tests_slot_visibility",
    "B_H2_no_sparkle_when_normal_loot_gone",
    "B_H2_repeat_view_after_reentry_remains_no_sparkle",
    "B_passive_checks_leave_shared_and_owner_loot_unmodified",
    "B_stock_pickup_is_denied_despite_visible_locked_row",
    "B_denied_pickup_does_not_take_A_item",
    "A_still_sees_quest_item_after_B_denial",
    "A_H1_allows_and_H2_keeps_rightful_sparkle",
    "A_original_Core_awards_final_bracer",
    "A_reaches_15_and_B_keeps_independent_15",
    "nonparticipant_B_does_not_sparkle",
    "nonparticipant_A_still_sparkles",
    "gold_still_causes_ordinary_sparkle_for_B",
    "gold_removed_does_not_leave_false_quest_sparkle_B",
    "gold_read_checks_do_not_consume_shared_quest_item",
)


class ExactScopeAndFixture(unittest.TestCase):
    def test_quest855_item5030_quantity15_and_synthetic_drop(self):
        cpp = HARNESS.read_text()
        self.assertIn("constexpr uint32 BRACER_QUEST = 855;", cpp)
        self.assertIn("constexpr uint32 BRACER_ITEM = 5030;", cpp)
        self.assertIn("constexpr uint32 BRACER_NEED = 15;", cpp)
        self.assertIn("rowJunk(), RowCentaurBracer()", cpp)
        self.assertIn("return LootStoreItem(BRACER_ITEM, 0, 100.0f, true,", cpp)
        self.assertIn("SYNTHETIC loot-drop fixture", cpp)
        self.assertNotIn("WorldDatabase", cpp)
        self.assertNotIn("CharacterDatabase", cpp)
        self.assertNotIn("SaveToDB(", cpp)
        self.assertNotIn("ModifyMoney(", cpp)

    def test_real_h1_h2_header_calls_and_original_core_model(self):
        cpp = HARNESS.read_text()
        self.assertIn('#include "a04_native/harness.cpp"', cpp)
        self.assertNotIn('#include "p4_h1_pickup/pickup_harness.cpp"', cpp)
        self.assertIn('#include "QuestLootPickupAuthorization.h"', cpp)
        self.assertIn('#include "QuestLootSparkleGuard.h"', cpp)
        self.assertIn("PA::SlotVisibleInServerView", cpp)
        self.assertIn("SG::ViewOffersSomething", cpp)
        self.assertIn("s.take(s.A, 1)", cpp)
        self.assertIn("s.take(s.B, 1)", cpp)
        self.assertIn("p4_a04_baseline_main_unused", cpp)

    def test_named_regressions_exactly_no_hidden_omissions(self):
        cpp = HARNESS.read_text()
        self.assertEqual(cpp.count('check("Q855.'), len(REQUIRED))
        for testid in REQUIRED:
            self.assertEqual(cpp.count('check("Q855.' + testid + '"'), 1)
        self.assertIn("QUEST855 CHECKS %d passed, %d failed", cpp)

    def test_no_new_gameplay_settings_or_wrong_global_loot_policy(self):
        cpp = HARNESS.read_text()
        forbidden = (
            "SetDynamicFlag(", "sConfigMgr->Set", "FREE_FOR_ALL =",
            "QuestLootSparkleGuard.Enabled = 1", "QuestLootPickupAuthorization.Enabled = 1",
            "LOOT_SLOT_TYPE_LOCKED)\n                return false;",
        )
        for literal in forbidden:
            self.assertNotIn(literal, cpp)


class ActualPinnedCoreAndHeaders(unittest.TestCase):
    def test_quest855_24_behaviour_cases_in_pinned_native_fixture(self):
        raw = os.environ.get("A04_CORE")
        if not raw:
            raise AssertionError("A04_CORE must point to exact original Core 8daffdabe source")
        core = Path(raw)
        with tempfile.TemporaryDirectory(prefix="naxx-quest855-") as dirname:
            out = Path(dirname)
            build.prepare(core, out)
            compiler = os.environ.get("CXX", "g++")
            cmd = [
                compiler, "-std=c++20", "-O0", "-g", "-DFMT_HEADER_ONLY",
                "-I", str(ROOT / "src/Systems"),
                "-I", str(out),
                "-I", str(ROOT / "tests/a04_native"),
                "-I", str(ROOT / "tests/a04_native/stubs"),
            ]
            for inc in build.CORE_INCLUDES:
                cmd.extend(["-I", str(core / inc)])
            cmd.extend([
                str(out / "pinned_bodies.cpp"), str(HARNESS),
                "-o", str(out / "quest855"),
            ])
            compile_result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=140
            )
            self.assertEqual(compile_result.returncode, 0,
                             compile_result.stdout + compile_result.stderr)
            execution = subprocess.run(
                [str(out / "quest855")], capture_output=True,
                text=True, timeout=90
            )
        output = execution.stdout + execution.stderr
        print(output)
        self.assertEqual(execution.returncode, 0, output)
        checks = build.parse_checks(output)
        self.assertEqual(len(checks), len(REQUIRED), output)
        self.assertEqual(
            [name for verdict, name in checks if verdict != "PASS"], [], output
        )
        for name in REQUIRED:
            self.assertIn(("PASS", TEST_PREFIX + name), checks)
        self.assertIn(
            f"QUEST855 CHECKS {len(REQUIRED)} passed, 0 failed", output
        )


if __name__ == "__main__":
    unittest.main()
