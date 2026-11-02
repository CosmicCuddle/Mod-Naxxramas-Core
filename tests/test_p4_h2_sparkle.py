"""P4 H2 corpse sparkle guard: source contract, pinned seam facts, harness.

Requires A04_CORE (pinned Grimfeather 8daffda checkout); FAILS, not skips,
when it is missing.
"""
import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "p4_h2_sparkle"))
import build_sparkle  # noqa: E402

EXPECTED_CHECKS = 21
REQUIRED = [
    "STOCK.T3_core_sparkles_for_B", "SPARKLE.T3_cleared_for_B", "SPARKLE.T3_kept_for_A",
    "SPARKLE.T3_no_shared_side_effect", "SPARKLE.T3_A_still_awarded",
    "SPARKLE.T1_banked_B_core_yes_guard_no_view_guard_off", "SPARKLE.T1_banked_B_core_yes_guard_no_view_guard_on",
    "SPARKLE.both_need_kept", "SPARKLE.round_robin_owner_kept", "SPARKLE.gold_kept_when_core_sparkles",
    "SPARKLE.ffa_copies_kept", "SPARKLE.master_rows_kept", "SPARKLE.master_locked_normal_row_kept",
    "NOMUT.T1_passive_reads_change_nothing", "NOMUT.T3_passive_reads_change_nothing",
    "NOMUT.ffa_passive_reads_change_nothing", "NOMUT.B_needs_again_after_passive_read_gets_row_and_item",
]

SCRIPT = (ROOT / "src" / "Systems" / "QuestLootSparkleGuard.cpp").read_text()
HEADER = (ROOT / "src" / "Systems" / "QuestLootSparkleGuard.h").read_text()
LOADER = (ROOT / "src" / "NaxxramasCore_loader.cpp").read_text()
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text()

PINNED = {
    "src/server/game/Entities/Unit/Unit.cpp": ("ce188c543c00aa020a593641cb5491a48fb12ffa", [
        "                cacheValue.posPointers.UnitDynamicFlagsPos = int32(fieldBuffer.wpos());\n",
        "            if (!target->isAllowedToLoot(creature))\n                dynamicFlags &= ~UNIT_DYNFLAG_LOOTABLE;\n",
        "        valuesUpdateBuf.put(posPointers.UnitDynamicFlagsPos, dynamicFlags);\n",
        "    sScriptMgr->OnPatchValuesUpdate(this, valuesUpdateBuf, posPointers, target);\n",
    ]),
    "src/server/game/Entities/Player/PlayerStorage.cpp": ("c3117845d1b92b2e11f0362f6c8e2d6652857165", [
        "    if (loot->isLooted()) // nothing to loot or everything looted.\n        return false;\n",
        "    if (!loot->hasItemForAll() && !loot->hasItemFor(this)) // no loot in creature for this player\n        return false;\n",
        "            if (!loot->roundRobinPlayer || loot->roundRobinPlayer == GetGUID())\n                return true;\n\n"
        "            if (loot->hasOverThresholdItem())\n                return true;\n\n"
        "            return loot->hasItemFor(this);\n",
    ]),
    "src/server/game/Entities/Player/Player.cpp": ("138e7eab4905ec366338a54cc18e6cfe749a3670", [
        "    loot->loot_type = loot_type;\n",
    ]),
    "src/server/game/Entities/Unit/Unit.h": ("cdff5aa27534c58eeaa597c24ce9c2dba46e4cba", [
        "#include \"UnitUtils.h\"\n",
    ]),
}


class UnitUtilsHasNoGuard(unittest.TestCase):
    def test_pinned_header_is_unguarded(self):
        core = Path(os.environ.get("A04_CORE") or "")
        if not os.environ.get("A04_CORE"):
            raise AssertionError("A04_CORE is not set")
        path = core / "src/server/game/Entities/Unit/UnitUtils.h"
        data = path.read_bytes()
        self.assertEqual(hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(),
                         "3d9184bc20b9e305aa3a90b285d016342f033d57")
        text = data.decode()
        self.assertNotIn("#pragma once", text)
        self.assertNotRegex(text, r"#ifndef\s+\w+")


class SourceContract(unittest.TestCase):
    def test_default_off(self):
        self.assertEqual(CONF.count("NaxxramasCore.QuestLootSparkleGuard.Enabled"), 1)
        self.assertIn("\nNaxxramasCore.QuestLootSparkleGuard.Enabled = 0\n", CONF)
        self.assertIn('GetOption<bool>("NaxxramasCore.QuestLootSparkleGuard.Enabled", false)', SCRIPT)
        self.assertEqual(SCRIPT.count("sConfigMgr"), 2)
        self.assertIn('GetOption<bool>("NaxxramasCore.QuestLootProtection.Enabled", false)', SCRIPT)
        self.assertIn("{UNITHOOK_ON_PATCH_VALUES_UPDATE}", SCRIPT)

    def test_only_clears_lootable_for_this_packet(self):
        # The only buffer write clears the LOOTABLE bit; nothing sets flags or the creature field.
        self.assertEqual(SCRIPT.count("buffer.put"), 1)
        self.assertIn("flags & ~uint32(UNIT_DYNFLAG_LOOTABLE)", SCRIPT)
        self.assertIn("if (!(flags & UNIT_DYNFLAG_LOOTABLE))", SCRIPT)
        self.assertNotRegex(SCRIPT, r"SetDynamicFlag|RemoveDynamicFlag|ForceValuesUpdateAtIndex")
        self.assertIn("if (loot.loot_type != LOOT_CORPSE && loot.loot_type != LOOT_NONE)", SCRIPT)
        self.assertIn("if (permission == NONE_PERMISSION)", SCRIPT)

    def test_header_restores_what_the_helper_marks(self):
        # The helper it calls marks the viewer's own rows; the only write in this
        # header is the scoped restore of those same rows. Behaviour is proven by
        # the NOMUT snapshot checks in the harness, not by this text check.
        code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", HEADER, flags=re.S))
        writes = re.findall(r"\b(\S+)\s*=\s*[^=;]+;", code)
        self.assertEqual([w for w in writes if "is_looted" in w], ["saved.first->is_looted"])
        self.assertIsNone(re.search(r"\b(unlootedCount|roundRobinPlayer|is_blocked)\s*=[^=]", code))
        save = code.index("savedRows.emplace_back(&row, row.is_looted);")
        helper = code.index("NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);")
        self.assertLess(save, helper)
        self.assertLess(code.index("} restore{savedRows};"), helper)

    def test_h2_skips_only_quest_rows_the_enabled_h1_turn_would_deny(self):
        # Non-mutating bridge: leave ordinary, FFA, rolls and all other
        # visible rows untouched. Config reload is read on world thread.
        h1 = (ROOT / "src/Systems/QuestLootProtection.cpp").read_text()
        shared = (ROOT / "src/Systems/QuestLootTurnGuard.h").read_text()
        self.assertIn('bool WouldDenyQuestSlotForViewer(Player* player, Creature* creature, uint8 requestedSlot)', h1)
        self.assertIn("WouldDenyQuestSlotForViewer(Player* player, Creature* creature, std::uint8_t requestedSlot)", shared)
        self.assertIn("if (!WouldDenyQuestSlotForViewer(player, creature, requestedSlot))", h1)
        self.assertIn("SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", h1)
        self.assertIn("if (slot < normalRows)", HEADER)
        self.assertIn("slotType != LOOT_SLOT_TYPE_LOCKED", HEADER)
        self.assertIn("(!deniedPickup || !deniedPickup(slot))", HEADER)
        self.assertIn("s_pickupTurnEnabled.load(std::memory_order_relaxed) &&", SCRIPT)
        self.assertIn("NaxxramasQuestLootProtection::WouldDenyQuestSlotForViewer(", SCRIPT)
        self.assertIn("deniedByTurn))", SCRIPT)
        # Never infer denial from race, quest eligibility alone or from
        # the viewer's current loot GUID (not set during create updates).
        body = h1.split("bool WouldDenyQuestSlotForViewer(", 1)[1].split("    bool PermitPickup(", 1)[0]
        self.assertNotIn("GetLootGUID()", body)
        self.assertNotIn("SendLootError(", body)
        self.assertNotIn("LOOT_ERROR_LOCKED", body)
        self.assertIn("GetLootRecipientGroup()", body)
        self.assertIn("ownerHasUnlootedSlot", body)
        self.assertIn("AllowedForPlayer(owner, loot.sourceWorldObjectGUID)", body)
        self.assertIn("return true;", body)
        self.assertEqual(body.count("return true;"), 1)

    def test_no_direct_unitutils_include(self):
        # Pinned UnitUtils.h has no include guard and already arrives through
        # Creature.h -> Unit.h; including it again redefines its classes
        # (the first hosted full build of this file failed exactly so).
        self.assertNotIn('#include "UnitUtils.h"', SCRIPT)
        self.assertIn('#include "Creature.h"', SCRIPT)

    def test_loader(self):
        self.assertEqual(LOADER.count("void AddQuestLootSparkleGuardScripts();"), 1)
        self.assertIn("    AddQuestLootPickupAuthorizationScripts();\n    AddQuestLootSparkleGuardScripts();\n", LOADER)


class PinnedSeamFacts(unittest.TestCase):
    def test_pinned_blobs_and_text(self):
        core = Path(os.environ.get("A04_CORE") or "")
        if not os.environ.get("A04_CORE"):
            raise AssertionError("A04_CORE is not set")
        for path, (sha, snippets) in PINNED.items():
            data = (core / path).read_bytes()
            self.assertEqual(hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(), sha, path)
            text = data.decode()
            for snippet in snippets:
                self.assertEqual(text.count(snippet), 1, (path, snippet[:80]))


class HarnessOnPinnedBodies(unittest.TestCase):
    def test_sparkle_cleared_only_when_nothing_to_take(self):
        core = os.environ.get("A04_CORE")
        if not core:
            raise AssertionError("A04_CORE is not set")
        with tempfile.TemporaryDirectory(prefix="p4-h2-") as tmp:
            compiled, rc, output = build_sparkle.run(Path(core), Path(tmp))
        print(output)
        self.assertTrue(compiled, output[-4000:])
        checks = build_sparkle.parse_checks(output)
        if len(checks) != EXPECTED_CHECKS:
            self.fail(f"COUNT DRIFT: {len(checks)} checks, expected {EXPECTED_CHECKS}")
        self.assertEqual([c for v, c in checks if v == "FAIL"], [])
        self.assertEqual(rc, 0)
        for cid in REQUIRED:
            self.assertIn(("PASS", cid), checks)


if __name__ == "__main__":
    unittest.main()
