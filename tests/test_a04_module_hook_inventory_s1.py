#!/usr/bin/env python3
"""A04 source-only inventory of this module's loot interception seams.

This scans ONLY this checkout's src/ C++/headers, not the worldserver,
other installed modules, addon code, external Playerbots/IP sources, or
anything actually loaded on the owner's private realm. No C++ executed.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
GUARD_PATH = Path("src/Systems/QuestLootProtection.cpp")
GUARD = ROOT / GUARD_PATH
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"
REPORT = ROOT / "docs/research/A04-MODULE-HOOK-INVENTORY-S1.md"

QUEST_CALLBACKS = (
    "OnPlayerBeforeFillQuestLootItem",
    "OnAllowedForPlayerLootCheck",
    "OnPlayerLootItem",
)


def source_files():
    return sorted(p for p in SRC.rglob("*") if p.suffix in {".cpp", ".h"} and p.is_file())


def matching_files(pattern):
    needle = re.compile(pattern)
    return [p.relative_to(ROOT).as_posix() for p in source_files()
            if needle.search(p.read_text(encoding="utf-8"))]


class ModuleHookInventory(unittest.TestCase):
    def test_inventory_has_real_module_source_files(self):
        files = source_files()
        self.assertGreaterEqual(len(files), 35)
        self.assertIn(GUARD, files)
        self.assertIn(ROOT / "src/NaxxramasCore_loader.cpp", files)

    def test_no_quest_eligibility_or_award_callback_implementation_in_module(self):
        for callback in QUEST_CALLBACKS:
            with self.subTest(callback=callback):
                self.assertEqual(matching_files(r"\b" + callback + r"\s*\("), [])

    def test_only_one_packet_receive_implementation(self):
        self.assertEqual(matching_files(r"\bCanPacketReceive\s*\("),
                         [GUARD_PATH.as_posix()])

    def test_only_one_packet_receive_hook_registration(self):
        self.assertEqual(matching_files(r"\bSERVERHOOK_CAN_PACKET_RECEIVE\b"),
                         [GUARD_PATH.as_posix()])

    def test_packet_guard_is_creature_corpse_autostore_only(self):
        code = GUARD.read_text("utf-8")
        for predicate in ("CMSG_AUTOSTORE_LOOT_ITEM",
                          "sourceGuid.IsCreatureOrVehicle()",
                          "loot.loot_type != LOOT_CORPSE",
                          "requestedSlot < normalCount",
                          "GROUP_LOOT", "ROUND_ROBIN", "NEED_BEFORE_GREED"):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, code)
        self.assertLess(code.index("CMSG_AUTOSTORE_LOOT_ITEM"),
                        code.index("session->GetPlayer(), requestedSlot"))

    def test_this_branch_still_default_off(self):
        conf = CONF.read_text("utf-8")
        self.assertEqual(len(re.findall(
            r"^NaxxramasCore\.QuestLootProtection\.Enabled\s*=\s*0\s*$",
            conf, re.MULTILINE)), 1)
        self.assertIn('"NaxxramasCore.QuestLootProtection.Enabled", false',
                      GUARD.read_text("utf-8"))

    def test_guard_contains_no_direct_item_award_or_turn_rewrite(self):
        code = GUARD.read_text("utf-8")
        self.assertNotRegex(code, r"\b(?:StoreNewItem|AddItem)\s*\(")
        self.assertNotRegex(code, r"\b(?:loot\.)?roundRobinPlayer\s*=(?!=)")
        self.assertIn("SendLootError", code)

    def test_known_legacy_finder_stays_an_explicit_open_safety_issue(self):
        # Deliberately assert the observed pre-#132 state of main-derived
        # #122 so nobody silently mistakes S1 research for hardened C++.
        self.assertIn("ObjectAccessor::FindPlayer(loot.roundRobinPlayer)",
                      GUARD.read_text("utf-8"))
        report = REPORT.read_text("utf-8")
        self.assertIn("#132", report)
        self.assertIn("not a fix", report.lower())

    def test_report_does_not_claim_full_server_or_other_modules_scanned(self):
        report = REPORT.read_text("utf-8").lower()
        for text in ("only this module", "other installed modules",
                     "not the entire server", "no owner gameplay",
                     "not a fix"):
            with self.subTest(text=text):
                self.assertIn(text, report)


if __name__ == "__main__":
    unittest.main()
