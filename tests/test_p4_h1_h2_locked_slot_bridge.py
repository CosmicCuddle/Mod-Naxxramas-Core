"""P4 quest855-style locked-slot cross-check: original stock + real H1 + H2.

Requires exact pinned public Grimfeather Core 8daffdabe9 source in A04_CORE.
Compiles a C++ executable with original extracted LootView/StoreLootItem bodies.
No server binary, actual game client, database or production operations.
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

HARNESS = ROOT / "tests/p4_h_locked_slot_bridge.cpp"
H1 = ROOT / "src/Systems/QuestLootPickupAuthorization.h"
H2 = ROOT / "src/Systems/QuestLootSparkleGuard.h"
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"

NEEDED = [
    "BRIDGE.quest_B_core_window_locked",
    "BRIDGE.quest_B_H1_can_pass_visible_locked_slot",
    "BRIDGE.quest_B_H2_does_not_sparkle_locked_only",
    "BRIDGE.quest_B_observation_does_not_consume_shared_item",
    "BRIDGE.quest_B_stock_award_denied_in_spite_of_H1_visible",
    "BRIDGE.quest_A_unlocked_visible",
    "BRIDGE.quest_A_H1_passes",
    "BRIDGE.quest_A_H2_keeps_sparkle",
    "BRIDGE.quest_A_original_award_preserved",
    "BRIDGE.master_normal_B_locked_visible",
    "BRIDGE.master_normal_H1_respects_visible_locked",
    "BRIDGE.master_normal_H2_keeps_stock_sparkle",
    "BRIDGE.master_normal_shared_state_preserved",
    "BRIDGE.normal_A_actionable",
    "BRIDGE.normal_A_H1_passes",
    "BRIDGE.normal_A_H2_sparkles",
    "BRIDGE.gold_B_sparkle_available",
    "BRIDGE.normal_A_original_award",
]

def extract_braced(source, signature):
    if source.count(signature) != 1:
        raise AssertionError(f"Expected one exact function: {signature}")
    at = source.index(signature)
    opening = source.index("{", at)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[at:i + 1]
    raise AssertionError(f"Unbalanced source function: {signature}")


class HeaderAndPinSafety(unittest.TestCase):
    def test_two_actual_headers_not_duplicated(self):
        cpp = HARNESS.read_text()
        # Include only the original A04 base harness: the existing H1
        # *executable* fixture declares its own main and must not be nested.
        self.assertIn('#include "a04_native/harness.cpp"', cpp)
        self.assertNotIn('#include "p4_h1_pickup/pickup_harness.cpp"', cpp)
        self.assertIn('#include "QuestLootPickupAuthorization.h"', cpp)
        self.assertIn('#include "QuestLootSparkleGuard.h"', cpp)
        self.assertIn('namespace PA = NaxxramasQuestLootPickupAuthorization;', cpp)
        h1 = H1.read_text()
        h2 = H2.read_text()
        self.assertIn("inline bool SlotVisibleInServerView(", h1)
        self.assertIn("if (shownSlot == slot)", h1)
        self.assertIn("inline bool ViewOffersSomething(", h2)
        self.assertIn("slotType != LOOT_SLOT_TYPE_LOCKED", h2)
        self.assertIn("if (slot < normalRows)", h2)
        self.assertEqual(cpp.count('check("BRIDGE.'), len(NEEDED))

    def test_original_pinned_award_and_serializer_bodies_match_owner_core2(self):
        pinned = os.environ.get("A04_CORE")
        current = os.environ.get("OWNER_CORE2")
        if not pinned or not current:
            raise AssertionError("A04_CORE and OWNER_CORE2 must be exact pinned checkouts")
        roots = [Path(pinned), Path(current)]
        for path, signature in (
            ("src/server/game/Entities/Player/Player.cpp",
             "LootItem* Player::StoreLootItem("),
            ("src/server/game/Loot/LootMgr.cpp",
             "ByteBuffer& operator<<(ByteBuffer& b, LootView const& lv)"),
            ("src/server/game/Loot/LootMgr.cpp",
             "ByteBuffer& operator<<(ByteBuffer& b, LootItem const& li)"),
        ):
            with self.subTest(path=path, signature=signature):
                old = extract_braced((roots[0] / path).read_text(), signature)
                live_fork_source = extract_braced((roots[1] / path).read_text(),
                                                  signature)
                self.assertEqual(old, live_fork_source,
                                 "Core owner fork loot semantics changed; re-review before porting the historical harness")

    def test_all_p4_helpers_remain_default_off(self):
        data = CONF.read_text()
        for key in (
            "NaxxramasCore.QuestLootProtection.Enabled = 0",
            "NaxxramasCore.QuestLootViewGuard.Enabled = 0",
            "NaxxramasCore.QuestLootPickupAuthorization.Enabled = 0",
            "NaxxramasCore.QuestLootSparkleGuard.Enabled = 0",
        ):
            self.assertIn("\n" + key + "\n", data)

    def test_no_new_runtime_or_write_semantics(self):
        s = HARNESS.read_text()
        for bad in ("CharacterDatabase", "WorldDatabase", "ModifyMoney(", "SaveToDB(",
                    "ForceUpdateProgressionState(", "SetDynamicFlag(",
                    "sConfigMgr->Set", "QuestLootProtection.Enabled = 1"):
            self.assertNotIn(bad, s)
        self.assertIn("stock_award_denied", s)
        self.assertIn("master_normal_H2_keeps_stock_sparkle", s)


class PinnedExecutableBridge(unittest.TestCase):
    def test_locked_quest_stock_and_two_guards(self):
        raw = os.environ.get("A04_CORE")
        if not raw:
            raise AssertionError("A04_CORE must point to pinned Core 8daffda source; do not skip")
        core = Path(raw)
        with tempfile.TemporaryDirectory(prefix="naxx-p4-slot-") as tmp:
            out = Path(tmp)
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
                "-o", str(out / "bridge"),
            ])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=140)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            execution = subprocess.run(
                [str(out / "bridge")], capture_output=True, text=True, timeout=90
            )
        output = execution.stdout + execution.stderr
        print(output)
        self.assertEqual(execution.returncode, 0, output)
        checks = build.parse_checks(output)
        self.assertEqual(len(checks), len(NEEDED), output)
        self.assertEqual([name for verdict, name in checks if verdict != "PASS"], [], output)
        for cid in NEEDED:
            self.assertIn(("PASS", cid), checks)
        self.assertIn(f"BRIDGE CHECKS {len(NEEDED)} passed, 0 failed", output)


if __name__ == "__main__":
    unittest.main()
