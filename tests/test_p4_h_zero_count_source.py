"""Source-only regression: zero-quantity Master Loot items fail closed.

This does not claim that malformed rows are produced in real gameplay.
Pinned-core native harnesses separately test the actual helper.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = (ROOT / "src/Systems/MasterLootQuestGive.h").read_text()
GO = (ROOT / "tests/p4_h_interop/go_loot_harness.cpp").read_text()
CORPSE = (ROOT / "tests/p4_h_master_loot/master_loot_harness.cpp").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()

class SourceContract(unittest.TestCase):
    def test_zero_guard_before_inventory_or_mutations(self):
        start = HELPER.index("inline Outcome GiveQuestSlot(")
        body = HELPER[start:]
        guard = body.index("if (item.count == 0 || row.is_looted || item.is_looted)")
        store = body.index("target->CanStoreNewItem(")
        after = body.index("item.count = 0;")
        notify = body.index("loot.NotifyQuestItemRemoved(row.index)")
        self.assertLess(guard, store)
        self.assertLess(guard, after)
        self.assertLess(guard, notify)
        self.assertIn("return {Result::AlreadyLooted, LOOT_ERROR_DIDNT_KILL};", body[guard:store])
        self.assertIn("target->StoreNewItem(", body)
        self.assertIn("--loot.unlootedCount;", body)

    def test_zero_count_real_header_harnesses(self):
        for harness, name in (
            (GO, "GO.GIVE.zero_count_refused_without_side_effects"),
            (CORPSE, "GIVE.zero_count_unlooted_refused_no_effects"),
        ):
            self.assertIn("count = 0;", harness)
            self.assertIn(name, harness)
            self.assertIn("Result::AlreadyLooted", harness)
            self.assertIn("removedSlots.empty()", harness)
            self.assertIn("unlootedCount == before", harness)

    def test_master_loot_feature_still_off(self):
        self.assertIn("NaxxramasCore.MasterLootQuestGive.Enabled = 0", CONF)

if __name__ == "__main__":
    unittest.main()
