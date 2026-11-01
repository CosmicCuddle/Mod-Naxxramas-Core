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

EXPECTED_CHECKS = 17
REQUIRED = [
    "STOCK.T3_core_sparkles_for_B", "SPARKLE.T3_cleared_for_B", "SPARKLE.T3_kept_for_A",
    "SPARKLE.T3_no_shared_side_effect", "SPARKLE.T3_A_still_awarded",
    "SPARKLE.T1_banked_B_core_yes_guard_no_view_guard_off", "SPARKLE.T1_banked_B_core_yes_guard_no_view_guard_on",
    "SPARKLE.both_need_kept", "SPARKLE.round_robin_owner_kept", "SPARKLE.gold_kept_when_core_sparkles",
    "SPARKLE.ffa_copies_kept", "SPARKLE.master_rows_kept", "SPARKLE.master_locked_normal_row_kept",
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
}


class SourceContract(unittest.TestCase):
    def test_default_off(self):
        self.assertEqual(CONF.count("NaxxramasCore.QuestLootSparkleGuard.Enabled"), 1)
        self.assertIn("\nNaxxramasCore.QuestLootSparkleGuard.Enabled = 0\n", CONF)
        self.assertIn('GetOption<bool>("NaxxramasCore.QuestLootSparkleGuard.Enabled", false)', SCRIPT)
        self.assertEqual(SCRIPT.count("sConfigMgr"), 1)
        self.assertIn("{UNITHOOK_ON_PATCH_VALUES_UPDATE}", SCRIPT)

    def test_only_clears_lootable_for_this_packet(self):
        # The only buffer write clears the LOOTABLE bit; nothing sets flags or the creature field.
        self.assertEqual(SCRIPT.count("buffer.put"), 1)
        self.assertIn("flags & ~uint32(UNIT_DYNFLAG_LOOTABLE)", SCRIPT)
        self.assertIn("if (!(flags & UNIT_DYNFLAG_LOOTABLE))", SCRIPT)
        self.assertNotRegex(SCRIPT, r"SetDynamicFlag|RemoveDynamicFlag|ForceValuesUpdateAtIndex")
        self.assertIn("if (loot.loot_type != LOOT_CORPSE && loot.loot_type != LOOT_NONE)", SCRIPT)
        self.assertIn("if (permission == NONE_PERMISSION)", SCRIPT)

    def test_header_reads_only(self):
        code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", HEADER, flags=re.S))
        self.assertIsNone(re.search(r"\b(is_looted|unlootedCount|roundRobinPlayer|is_blocked)\s*=[^=]", code))
        self.assertIn("NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);", code)

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
