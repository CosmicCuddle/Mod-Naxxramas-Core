"""Quest Loot Protection: source contract and conservative decision model.

Mocks are not actual Grimfeather/Playerbots runtime. Full pinned compilation
and owner-approved in-game tests are needed before activating the feature.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/QuestLootProtection.cpp").read_text("utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text("utf-8")
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text("utf-8")
DOC = (ROOT / "docs/QUEST-LOOT-PROTECTION.md").read_text("utf-8")


def modeled_pickup(
    enabled=True, packet=True, malformed=False, grouped=True,
    method="GROUP_LOOT", corpse=True, same_recipient=True,
    owner="owner", viewer="viewer", slot=4, normal_count=4,
    personal=None, quest_index=0, quest_count=1,
    needs_quest=True, looted=False, shared=False,
    follow_rules=False, blocked=False, roll_winner=False,
    item_template=True, owner_online=True, owner_in_group=True,
    owner_has_slot=True, owner_needs=True, owner_eligible=True,
    owner_personal=None
):
    """Model conditions in PermitPickup, not independent proof of source."""
    if not enabled or not packet or malformed or not grouped or not corpse:
        return True
    if method not in ("GROUP_LOOT", "ROUND_ROBIN", "NEED_BEFORE_GREED"):
        return True
    if not same_recipient or owner is None or owner == viewer:
        return True
    if slot < normal_count:
        return True
    if personal is None:
        personal = [quest_index]
    mapped_slot = slot - normal_count
    if mapped_slot < 0 or mapped_slot >= len(personal):
        return True
    # Translate client's viewer-specific SLOT to the underlying index.
    # This model considers one specified underlying quest item.
    mapped_index = personal[mapped_slot]
    if mapped_index < 0 or mapped_index >= quest_count:
        return True
    if mapped_index != quest_index:
        return True
    if not needs_quest or looted or shared or follow_rules or blocked or roll_winner:
        return True
    if not item_template or not owner_online or not owner_in_group or not owner_has_slot:
        return True
    if owner_personal is not None:
        # Match SAME quest_items index, with an unlooted owner view.
        if not any(item_index == mapped_index and not was_looted
                   for item_index, was_looted in owner_personal):
            return True
    if not owner_needs or not owner_eligible:
        return True
    return False


class QuestLootProtectionContract(unittest.TestCase):
    def test_disabled_default_and_no_database(self):
        self.assertEqual(CONFIG.count(
            "NaxxramasCore.QuestLootProtection.Enabled = 0"), 1)
        self.assertEqual(CONFIG.count(
            "NaxxramasCore.QuestLootProtection.Debug = 0"), 1)
        self.assertIn('GetOption<bool>', CPP)
        self.assertNotIn("CharacterDatabase", CPP)
        self.assertNotIn("WorldDatabase", CPP)

    def test_packet_hook_and_original_cursor(self):
        self.assertIn("ServerScript", CPP)
        self.assertIn("SERVERHOOK_CAN_PACKET_RECEIVE", CPP)
        self.assertIn("CMSG_AUTOSTORE_LOOT_ITEM", CPP)
        self.assertIn("packet.size() < 1", CPP)
        self.assertNotIn("packet.size() != 1", CPP)
        self.assertIn("WorldPacket copy(packet)", CPP)
        self.assertIn("copy.rpos(0)", CPP)
        self.assertIn("copy >> requestedSlot", CPP)
        self.assertNotIn("packet >> requestedSlot", CPP)
        self.assertIn("AddQuestLootProtectionScripts();", LOADER)
        self.assertIn("new NaxxramasQuestLootProtectionScript();", CPP)

    def test_quest_slot_indirection_and_bounds(self):
        for required in (
            "loot.items.size()", "requestedSlot - normalCount",
            "loot.GetPlayerQuestItems()", "personal.find(player->GetGUID())",
            "personalSlot >= found->second->size()",
            "view.index >= loot.quest_items.size()",
            "loot.quest_items[view.index]",
        ):
            with self.subTest(required=required):
                self.assertIn(required, CPP)

    def test_only_narrow_creature_corpse_and_group_loot(self):
        for required in (
            "sourceGuid.IsCreatureOrVehicle()",
            "creature->isDead()", "LOOT_CORPSE", "GROUP_LOOT",
            "ROUND_ROBIN", "NEED_BEFORE_GREED",
            "creature->GetLootRecipientGroup() != group",
            "item.count != 1", "!item.needs_quest",
            "item.freeforall", "ITEM_FLAG_MULTI_DROP",
            "item.follow_loot_rules", "item.is_blocked",
            "item.rollWinnerGUID",
        ):
            with self.subTest(required=required):
                self.assertIn(required, CPP)

    def test_no_round_robin_mutation_or_item_award(self):
        for forbidden in (
            "roundRobinPlayer.Clear(",
            "LootItemInSlot(", "StoreLootItem(", "StoreNewItem(",
            "NotifyQuestItemRemoved(", "SendNotifyLootItemRemoved(",
            "SetLootGUID(", "item.is_looted =",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CPP)
        self.assertNotRegex(CPP, r"roundRobinPlayer\\s*=(?!=)")
        self.assertIn("owner->HasQuestForItem(item.itemid)", CPP)
        self.assertIn("personal.find(owner->GetGUID())", CPP)
        self.assertIn("ownerItem.index == view.index && !ownerItem.is_looted", CPP)
        self.assertIn("item.AllowedForPlayer(owner", CPP)
        self.assertIn("player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", CPP)
        self.assertIn("QuestLootProtection.Enabled = 0", DOC)

    def test_non_owner_cannot_collect_single_copy(self):
        self.assertFalse(modeled_pickup())

    def test_owner_and_release(self):
        self.assertTrue(modeled_pickup(owner="viewer"))
        self.assertTrue(modeled_pickup(owner=None))
        self.assertFalse(modeled_pickup(owner="another"))

    def test_owner_no_longer_needs_or_is_ineligible(self):
        self.assertTrue(modeled_pickup(owner_needs=False))
        self.assertTrue(modeled_pickup(owner_eligible=False))
        self.assertTrue(modeled_pickup(owner_online=False))
        self.assertTrue(modeled_pickup(owner_in_group=False))
        self.assertTrue(modeled_pickup(owner_has_slot=False))

    def test_view_slot_must_map_to_the_exact_quest_item(self):
        self.assertTrue(modeled_pickup(personal=[1, 0], slot=4,
                                       quest_index=0, quest_count=2))
        self.assertFalse(modeled_pickup(personal=[1, 0], slot=5,
                                        quest_index=0, quest_count=2))
        self.assertTrue(modeled_pickup(personal=[-1],
                                       quest_index=0, quest_count=2))
        self.assertTrue(modeled_pickup(personal=[2],
                                       quest_index=0, quest_count=2))

    def test_owner_needs_same_underlying_unlooted_view(self):
        self.assertTrue(modeled_pickup(owner_personal=[(1, False)]))
        self.assertTrue(modeled_pickup(owner_personal=[(0, True)]))
        self.assertTrue(modeled_pickup(owner_personal=[]))
        self.assertFalse(modeled_pickup(owner_personal=[(1, False),
                                                       (0, False)]))
        self.assertTrue(modeled_pickup(owner_personal=[(1, False),
                                                      (0, True)]))

    def test_personal_view_and_owner_guards_present_in_real_cpp(self):
        for expression in (
            "QuestItem const& view = found->second->at(personalSlot);",
            "LootItem const& item = loot.quest_items[view.index];",
            "ownerItem.index == view.index && !ownerItem.is_looted",
            "owner->HasQuestForItem(item.itemid)",
            "item.AllowedForPlayer(owner, loot.sourceWorldObjectGUID)",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, CPP)

    def test_operator_acceptance_plan_identifies_real_gameplay_gates(self):
        for marker in ("QL-01", "QL-05", "QL-10", "QL-15",
                       "read-only", "restorable", "Random Bots"):
            with self.subTest(marker=marker):
                self.assertIn(marker, DOC)

    def test_native_loot_modes(self):
        for method in ("FREE_FOR_ALL", "MASTER_LOOT", "UNKNOWN"):
            with self.subTest(method=method):
                self.assertTrue(modeled_pickup(method=method))
        for method in ("ROUND_ROBIN", "GROUP_LOOT", "NEED_BEFORE_GREED"):
            with self.subTest(method=method):
                self.assertFalse(modeled_pickup(method=method))

    def test_shared_follow_rules_roll_and_nonquest(self):
        for param in (
            "shared", "follow_rules", "blocked", "roll_winner",
            "looted"
        ):
            with self.subTest(param=param):
                self.assertTrue(modeled_pickup(**{param: True}))
        self.assertTrue(modeled_pickup(needs_quest=False))
        self.assertTrue(modeled_pickup(item_template=False))

    def test_packet_and_corpse_scope(self):
        for keyword in ("enabled", "packet", "grouped", "corpse",
                        "same_recipient"):
            with self.subTest(keyword=keyword):
                self.assertTrue(modeled_pickup(**{keyword: False}))
        self.assertTrue(modeled_pickup(malformed=True))

    def test_normal_slot_and_bad_indices(self):
        self.assertTrue(modeled_pickup(slot=3, normal_count=4))
        self.assertTrue(modeled_pickup(slot=5, normal_count=4))
        self.assertTrue(modeled_pickup(personal=[], slot=4))
        self.assertTrue(modeled_pickup(personal=[6], quest_index=6,
                                       quest_count=2))
        self.assertFalse(modeled_pickup(personal=[1], quest_index=1,
                                        quest_count=2))


if __name__ == "__main__":
    unittest.main()
