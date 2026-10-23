"""Regression contract: raid consumables must not recreate permanent Shaman totems.

Source-only tests: no worldserver, character inventory, bank, DBC or SQL access.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"

ELEMENTAL_TOTEMS = {
    "EARTH": 5175,
    "FIRE": 5176,
    "WATER": 5177,
    "AIR": 5178,
}


def reagent_section(source: str) -> str:
    return source.split("void SupplyRaidReagents(", 1)[1].split(
        "void PrepareMoltenCoreCommon(", 1
    )[0]


def shaman_case(source: str) -> str:
    return reagent_section(source).split("case CLASS_SHAMAN:", 1)[1].split(
        "break;", 1
    )[0]


class ShamanTotemNoRegrant(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_permanent_totems_never_recreated_during_raid_preparation(self):
        # The four permanent, earned totems must not be in the generic grant
        # catalogue; using generic TopUpToCount would duplicate banked copies.
        for element, item_id in ELEMENTAL_TOTEMS.items():
            with self.subTest(totem=element):
                self.assertNotIn("ITEM_" + element + "_TOTEM", self.source)
                self.assertNotIn(f"topUp({item_id}", reagent_section(self.source))
                self.assertNotIn(f"AddItem({item_id}", self.source)

    def test_shaman_retains_consumable_reagents(self):
        section = shaman_case(self.source)
        self.assertIn("topUp(ITEM_ANKH, 5);", section)
        self.assertIn("topUp(ITEM_SHINY_FISH_SCALES, 20);", section)
        self.assertIn("topUp(ITEM_FISH_OIL, 20);", section)
        self.assertIn("quest-earned elemental totems", section)
        self.assertIn("may be banked", section)

    def test_no_bank_withdrawal_or_inventory_mutation_added(self):
        section = reagent_section(self.source)
        for forbidden in ("Withdraw", "RemoveItemFromBank", "MoveItemFromBank",
                          "StoreItemInInventory", "SetItemCount"):
            self.assertNotIn(forbidden, section)
        # Generic top-ups for actually consumable supplies are preserved.
        self.assertIn("TopUpToCount(", section)
        self.assertIn("bot,", section)

    def test_other_classes_and_mc_scope_remain_in_place(self):
        section = reagent_section(self.source)
        for other_class in ("DRUID", "MAGE", "PALADIN", "PRIEST",
                            "ROGUE", "WARLOCK"):
            self.assertIn("case CLASS_" + other_class + ":", section)
        self.assertEqual(self.source.count("SupplyRaidReagents(\n            bot,"), 1)
        self.assertIn("void PrepareMoltenCoreCommon(", self.source)


if __name__ == "__main__":
    unittest.main()
