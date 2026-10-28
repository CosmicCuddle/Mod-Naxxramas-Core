"""A04 H1 pinned public receipt callback; source mutations, no owner evidence."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_a04_positive_receipt_contract as contract  # noqa: E402

PIN = os.environ.get("A04_PIN_CORE")
if not PIN:
    raise RuntimeError("A04_PIN_CORE is required: no silent skipped source tests")


def replace_one(text, before, after, anchor=""):
    begin = text.find(anchor) if anchor else 0
    assert begin >= 0, "missing anchor " + anchor
    spot = text.find(before, begin)
    assert spot >= 0, "missing exact source fragment " + before
    return text[:spot] + after + text[spot + len(before):]


class PinnedReceiptContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = contract.load(PIN)

    def mutate(self, source, before, after, anchor=""):
        sources = dict(self.sources)
        sources[source] = replace_one(sources[source], before, after, anchor)
        return sources

    def fails(self, mutated, prefix):
        with self.assertRaises(contract.ContractError) as err:
            contract.check(mutated)
        self.assertTrue(str(err.exception).startswith(prefix), str(err.exception))

    def test_01_positive_pinned_core_receipt_boundary(self):
        self.assertEqual(
            contract.check(self.sources),
            "A04 POSITIVE DIRECT RECEIPT SOURCE CONTRACT: PASS (no runtime)")

    def test_02_absent_direct_receipt_callback_does_not_pass(self):
        self.fails(self.mutate(contract.PLAYER_CPP, contract.HOOK,
                               "/* no direct receipt callback */",
                               "LootItem* Player::StoreLootItem"), "P1")

    def test_03_receipt_callback_before_store_cannot_pass(self):
        s = self.sources[contract.PLAYER_CPP]
        anchor = "LootItem* Player::StoreLootItem"
        s = replace_one(s, contract.HOOK, "/* moved for negative test */", anchor)
        s = replace_one(s, contract.STORE, contract.HOOK + "\n        " + contract.STORE, anchor)
        src = dict(self.sources, **{contract.PLAYER_CPP: s})
        self.fails(src, "P6")

    def test_04_receipt_before_new_item_notification_cannot_pass(self):
        s = self.sources[contract.PLAYER_CPP]
        anchor = "LootItem* Player::StoreLootItem"
        s = replace_one(s, contract.HOOK, "/* moved for negative test */", anchor)
        s = replace_one(s, contract.NOTIFY, contract.HOOK + "\n        " + contract.NOTIFY, anchor)
        self.fails(dict(self.sources, **{contract.PLAYER_CPP: s}), "P6")

    def test_05_changed_success_branch_condition_cannot_pass(self):
        self.fails(self.mutate(
            contract.PLAYER_CPP, "if (msg == EQUIP_ERR_OK)", "if (msg != EQUIP_ERR_OK)",
            "LootItem* Player::StoreLootItem"), "P3")

    def test_06_missing_allowed_for_player_rejection_cannot_pass(self):
        self.fails(self.mutate(
            contract.PLAYER_CPP,
            "if (!item->AllowedForPlayer(this, loot->sourceWorldObjectGUID))",
            "if (false)", "LootItem* Player::StoreLootItem"), "P2")

    def test_07_missing_blocked_item_rejection_cannot_pass(self):
        self.fails(self.mutate(
            contract.PLAYER_CPP, "if (!qitem && item->is_blocked)",
            "if (false)", "LootItem* Player::StoreLootItem"), "P2")

    def test_08_missing_roll_winner_rejection_cannot_pass(self):
        self.fails(self.mutate(
            contract.PLAYER_CPP,
            "if (item->rollWinnerGUID && item->rollWinnerGUID != GetGUID())",
            "if (false)", "LootItem* Player::StoreLootItem"), "P2")

    def test_09_missing_inventory_capacity_check_cannot_pass(self):
        self.fails(self.mutate(
            contract.PLAYER_CPP,
            "msg = CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, item->itemid, item->count);",
            "msg = EQUIP_ERR_OK;", "LootItem* Player::StoreLootItem"), "P2")

    def test_10_false_packet_receipt_without_store_cannot_pass(self):
        self.fails(self.mutate(
            contract.HANDLER_CPP, "player->StoreLootItem(lootSlot, loot, msg);",
            "nullptr;", "void WorldSession::HandleAutostoreLootItemOpcode"), "H1")

    def test_11_mail_fallback_must_remain_item_only_not_corpse(self):
        self.fails(self.mutate(
            contract.HANDLER_CPP, contract.MAIL_GATE,
            "if (msg != EQUIP_ERR_OK)", "void WorldSession::HandleAutostoreLootItemOpcode"), "H3")

    def test_12_player_script_registration_surface_must_exist(self):
        self.fails(self.mutate(
            contract.PLAYER_SCRIPT_H,
            "virtual void OnPlayerLootItem(Player* /*player*/, Item* /*item*/, uint32 /*count*/, ObjectGuid /*lootguid*/)",
            "virtual void OnPlayerLootRenamed(Item*)"), "S1")

    def test_13_script_mgr_dispatch_must_remain_gated(self):
        self.fails(self.mutate(
            contract.PLAYER_SCRIPT_CPP,
            "CALL_ENABLED_HOOKS(PlayerScript, PLAYERHOOK_ON_LOOT_ITEM, script->OnPlayerLootItem(player, item, count, lootguid));",
            "/* removed for synthetic negative */",
            "void ScriptMgr::OnPlayerLootItem"), "S3")

    def test_14_no_missing_fixture_may_silently_pass(self):
        d = dict(self.sources)
        del d[contract.HANDLER_CPP]
        self.fails(d, "F1")


if __name__ == "__main__":
    unittest.main()
