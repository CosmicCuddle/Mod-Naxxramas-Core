"""No-write synthetic mutants of REAL PINNED Group.cpp roll/direct receipt facts."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_a04_roll_receipt_contract as c  # noqa: E402

PIN = os.environ.get("A04_PIN_CORE")
if not PIN:
    raise RuntimeError("A04_PIN_CORE required: never silently skip pinned source verification")


def substitute(s, before, after, anchor=""):
    start = s.index(anchor) if anchor else 0
    ix = s.find(before, start)
    if ix < 0:
        raise AssertionError("unavailable pinned source for mutant: " + before)
    return s[:ix] + after + s[ix + len(before):]


class RollDirectContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = c.load(PIN)

    def change(self, file, old, new, anchor=""):
        d = dict(self.src)
        d[file] = substitute(d[file], old, new, anchor)
        return d

    def denied(self, data, expected):
        with self.assertRaises(c.ContractError) as err:
            c.check(data)
        self.assertTrue(str(err.exception).startswith(expected),
                        f"expected {expected}, got {err.exception}")

    def test_01_real_pinned_source_need_greed_mail_offline_and_hook_contract(self):
        self.assertEqual(c.check(self.src),
                         "A04 GROUP ROLL vs DIRECT RECEIPT: PASS (pinned source only)")

    def test_02_remove_need_roll_callback_rejected(self):
        self.denied(self.change(c.GROUP, c.ROLL_NEED, "/* removed */",
                                "void Group::CountTheRoll"), "G1")

    def test_03_remove_greed_roll_callback_rejected(self):
        self.denied(self.change(c.GROUP, c.ROLL_GREED, "/* removed */",
                                "void Group::CountTheRoll"), "G1")

    def test_04_need_callback_before_store_rejected(self):
        d = dict(self.src)
        x = substitute(d[c.GROUP], c.ROLL_NEED, "/* moving callback */",
                       "void Group::CountTheRoll")
        x = substitute(x, c.STORE_ROLL,
                       c.ROLL_NEED + "\n                        " + c.STORE_ROLL,
                       "void Group::CountTheRoll")
        d[c.GROUP] = x
        self.denied(d, "NEED_SUCCESS_CALLBACK_ORDER_CHANGED")

    def test_05_greed_callback_before_store_rejected(self):
        d = dict(self.src)
        x = substitute(d[c.GROUP], c.ROLL_GREED, "/* moving callback */",
                       "void Group::CountTheRoll")
        x = substitute(x, c.STORE_ROLL,
                       c.ROLL_GREED + "\n                            " + c.STORE_ROLL,
                       "if (rollvote == GREED)")
        d[c.GROUP] = x
        self.denied(d, "GREED_SUCCESS_CALLBACK_ORDER_CHANGED")

    def test_06_need_nonnull_item_guard_cannot_be_removed(self):
        d = self.change(c.GROUP, "if (_item)", "if (true)",
                        "void Group::CountTheRoll")
        self.denied(d, "NEED_NONNULL_ITEM_GUARD_MISSING")

    def test_07_greed_nonnull_item_guard_cannot_be_removed(self):
        d = self.change(c.GROUP, "if (_item)", "if (true)",
                        "if (rollvote == GREED)")
        self.denied(d, "GREED_NONNULL_ITEM_GUARD_MISSING")

    def test_08_need_full_bag_mail_cannot_become_general_error_mail(self):
        d = self.change(c.GROUP, c.MAIL_GUARD,
                        "if (msg != EQUIP_ERR_OK)",
                        "void Group::CountTheRoll")
        self.denied(d, "NEED_INVENTORY_FULL_MAIL_BRANCH_DRIFT")

    def test_09_greed_full_bag_mail_cannot_become_general_error_mail(self):
        d = self.change(c.GROUP, c.MAIL_GUARD,
                        "if (msg != EQUIP_ERR_OK)",
                        "if (rollvote == GREED)")
        self.denied(d, "GREED_INVENTORY_FULL_MAIL_BRANCH_DRIFT")

    def test_10_mail_fallback_removed_must_fail_closed(self):
        self.denied(self.change(c.GROUP, c.MAIL, "/* no group-roll mail */",
                                "void Group::CountTheRoll"), "G2")

    def test_11_need_offline_candidate_skip_must_remain(self):
        d = self.change(c.GROUP, "--roll->totalNeed;", "++roll->totalNeed;",
                        "void Group::CountTheRoll")
        self.denied(d, "G4")

    def test_12_greed_offline_candidate_skip_must_remain(self):
        d = self.change(c.GROUP, "--roll->totalGreed;", "++roll->totalGreed;",
                        "void Group::CountTheRoll")
        self.denied(d, "G5")

    def test_13_need_winner_session_recheck_must_remain(self):
        d = self.change(c.GROUP, "player = ObjectAccessor::FindPlayer(maxguid);",
                        "player = nullptr;", "void Group::CountTheRoll")
        self.denied(d, "G6")

    def test_14_direct_inventory_receipt_must_not_disappear(self):
        d = self.change(c.PLAYER, c.DIRECT, "/* direct receipt removed */",
                        "LootItem* Player::StoreLootItem")
        self.denied(d, "P1")

    def test_15_group_roll_mailing_helper_must_remain_separate(self):
        d = self.change(c.GROUP, "player->SendItemRetrievalMail(mailItem);",
                        "/* no mail handoff */",
                        "static void SendRollWonItemViaMail")
        self.denied(d, "G7")

    def test_16_script_api_must_not_be_deleted(self):
        d = self.change(c.BASE_H,
                        "virtual void OnPlayerGroupRollRewardItem(Player* /*player*/, Item* /*item*/, uint32 /*count*/, RollVote /*voteType*/, Roll* /*roll*/)",
                        "virtual void OnPlayerGroupRollRewardItemDeleted();")
        self.denied(d, "S1")

    def test_17_roll_dispatch_feature_hook_guard_must_remain(self):
        d = self.change(c.BASE_CPP,
                        "CALL_ENABLED_HOOKS(PlayerScript, PLAYERHOOK_ON_GROUP_ROLL_REWARD_ITEM, script->OnPlayerGroupRollRewardItem(player, item, count, voteType, roll));",
                        "/* roll dispatch removed */",
                        "void ScriptMgr::OnPlayerGroupRollRewardItem")
        self.denied(d, "S3")

    def test_18_missing_public_source_fixture_must_fail(self):
        d = dict(self.src)
        d.pop(c.GROUP)
        self.denied(d, "F1")

    def test_19_misleading_after_creature_hook_missing_is_detected(self):
        d = self.change(c.HANDLER, c.PRE_RECEIPT_NAMED_HOOK,
                        "/* hook deliberately absent in synthetic mutant */",
                        "void WorldSession::HandleAutostoreLootItemOpcode")
        self.denied(d, "H1_PREAWARD_HOOK_MISSING_OR_DUPLICATED")

    def test_20_move_named_after_creature_hook_after_store_is_detected(self):
        d = dict(self.src)
        body = substitute(d[c.HANDLER], c.PRE_RECEIPT_NAMED_HOOK,
                          "/* original pre-store observation moved */",
                          "void WorldSession::HandleAutostoreLootItemOpcode")
        body = substitute(body, c.NATIVE_STORE,
                          c.NATIVE_STORE + "\n    " + c.PRE_RECEIPT_NAMED_HOOK,
                          "void WorldSession::HandleAutostoreLootItemOpcode")
        d[c.HANDLER] = body
        self.denied(d, "H1_PREAWARD_ORDER_CHANGED")


    def test_21_master_target_store_missing_is_detected(self):
        self.denied(
            self.change(c.HANDLER, c.MASTER_STORE,
                        "/* removed master recipient award */",
                        "void WorldSession::HandleLootMasterGiveOpcode"),
            "M1_MASTER_TARGET_STORE_CALL_DRIFT")

    def test_22_master_target_eligibility_gate_removed_is_detected(self):
        self.denied(
            self.change(c.HANDLER, c.MASTER_ALLOWED,
                        "/* removed target entitlement gate */",
                        "void WorldSession::HandleLootMasterGiveOpcode"),
            "M2_MASTER_ALLOWED_TARGET_CHECK_MISSING")

    def test_23_master_target_check_moved_after_award_is_detected(self):
        d = dict(self.src)
        body = substitute(d[c.HANDLER], c.MASTER_ALLOWED,
                          "/* old target entitlement gate moved */",
                          "void WorldSession::HandleLootMasterGiveOpcode")
        body = substitute(body, c.MASTER_STORE,
                          c.MASTER_STORE + "\n    " + c.MASTER_ALLOWED,
                          "void WorldSession::HandleLootMasterGiveOpcode")
        d[c.HANDLER] = body
        self.denied(d, "M3_MASTER_ALLOWED_CHECK_AFTER_STORE")

    def test_24_master_capacity_failure_guard_removed_is_detected(self):
        self.denied(
            self.change(c.HANDLER, "if (msg != EQUIP_ERR_OK)",
                        "if (false)",
                        "void WorldSession::HandleLootMasterGiveOpcode"),
            "M4_MASTER_INVENTORY_REJECT_CHECK_DRIFT")

    def test_25_shared_store_hook_removed_is_detected(self):
        self.denied(
            self.change(c.STORAGE, c.STORE_NEW_HOOK,
                        "/* removed post-store hook */",
                        "Item* Player::StoreNewItem(ItemPosCountVec const& dest, uint32 item, bool update, int32 randomPropertyId, AllowedLooterSet& allowedLooters, bool refund)"),
            "M6_POST_STORE_NEW_ITEM_HOOK_MISSING")

    def test_26_shared_store_hook_moved_before_inventory_storage_is_detected(self):
        d = dict(self.src)
        body = substitute(d[c.STORAGE], c.STORE_NEW_HOOK,
                          "/* moved hook from post-store location */",
                          "Item* Player::StoreNewItem(ItemPosCountVec const& dest, uint32 item, bool update, int32 randomPropertyId, AllowedLooterSet& allowedLooters, bool refund)")
        body = substitute(body, "pItem = StoreItem(dest, pItem, update);",
                          c.STORE_NEW_HOOK + "\n        pItem = StoreItem(dest, pItem, update);",
                          "Item* Player::StoreNewItem(ItemPosCountVec const& dest, uint32 item, bool update, int32 randomPropertyId, AllowedLooterSet& allowedLooters, bool refund)")
        d[c.STORAGE] = body
        self.denied(d, "M7_STORE_ITEM_AFTER_RECEIPT_CALLBACK")


if __name__ == "__main__":
    unittest.main()
