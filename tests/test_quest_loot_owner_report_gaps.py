"""Owner-reported quest loot cross-pickup: current source coverage contract.

The tests deliberately expose documented ALLOW paths in existing production
code. Passing here DOES NOT mean the owner-reported behaviour is fixed, nor
that the test exercised a Worldserver, player, drop or packet.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/QuestLootProtection.cpp").read_text("utf-8")
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text("utf-8")
NOTES = (ROOT / "docs/research/QUEST-LOOT-OWNER-FAILURE-20261023.md").read_text("utf-8")

class OwnerReportedQuestLootGapContract(unittest.TestCase):
    def test_owner_report_explicitly_blocks_functional_acceptance(self):
        for marker in ("Issue #109", "IN-GAME FAIL", "root cause unknown",
                       "NOT a gameplay fix"):
            self.assertIn(marker, NOTES)

    def test_packet_only_guard_cannot_validate_other_award_routes(self):
        self.assertIn("SERVERHOOK_CAN_PACKET_RECEIVE", CPP)
        self.assertIn("CMSG_AUTOSTORE_LOOT_ITEM", CPP)
        self.assertIn("packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM", CPP)
        self.assertNotIn("StoreNewItem(", CPP)
        self.assertNotIn("StoreLootItem(", CPP)
        self.assertIn("DIRECT STORE / SCRIPTED AWARD", NOTES)

    def test_normal_item_slots_are_explicitly_permitted(self):
        self.assertIn(
            "if (requestedSlot < normalCount)\n            return true;", CPP
        )
        self.assertIn("QuestRequired=0", NOTES)
        self.assertIn("NORMAL LOOT SLOT", NOTES)

    def test_quest_flag_is_not_all_quest_related_item_detection(self):
        self.assertIn("!item.needs_quest || item.count != 1", CPP)
        self.assertIn("QuestRequired", NOTES)
        self.assertIn("loot.items", NOTES)
        self.assertIn("loot.quest_items", NOTES)

    def test_multiple_item_counts_pass_through(self):
        self.assertIn("item.count != 1", CPP)
        self.assertIn("COUNT GREATER THAN ONE", NOTES)

    def test_inherently_personal_multi_drop_must_stay_native(self):
        self.assertIn("item.freeforall || item.follow_loot_rules", CPP)
        self.assertIn("proto->HasFlag(ITEM_FLAG_MULTI_DROP)", CPP)
        self.assertIn("MULTI_DROP", NOTES)
        self.assertIn("DO NOT blanket-ban", NOTES)

    def test_no_round_robin_owner_stays_permitted(self):
        self.assertIn("!loot.roundRobinPlayer ||", CPP)
        self.assertIn("loot.roundRobinPlayer == player->GetGUID()", CPP)
        self.assertIn("NO ROUND-ROBIN OWNER", NOTES)
        self.assertIn("RELEASED", NOTES)

    def test_ffa_and_master_loot_not_altered(self):
        for marker in ("case GROUP_LOOT:", "case ROUND_ROBIN:",
                       "case NEED_BEFORE_GREED:", "default:"):
            self.assertIn(marker, CPP)
        for mode in ("FREE_FOR_ALL", "MASTER_LOOT"):
            self.assertIn(mode, NOTES)

    def test_owner_presence_and_entitlement_requirement(self):
        self.assertIn("owner->IsInWorld()", CPP)
        self.assertIn("ownerMap != looterMap", CPP)
        self.assertIn("owner->GetInstanceId() != player->GetInstanceId()", CPP)
        self.assertIn("personal.find(owner->GetGUID())", CPP)
        self.assertIn("ownerItem.index == view.index && !ownerItem.is_looted", CPP)
        self.assertIn("owner->HasQuestForItem(item.itemid)", CPP)
        self.assertIn("OWNER INELIGIBLE / ABSENT", NOTES)

    def test_existing_deny_is_pre_inventory_and_does_not_mutate_owner(self):
        self.assertIn("player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", CPP)
        self.assertIn("return false;", CPP)
        self.assertNotIn("roundRobinPlayer.Clear(", CPP)
        self.assertNotIn("item.is_looted =", CPP)
        self.assertNotIn("CharacterDatabase", CPP)
        self.assertNotIn("WorldDatabase", CPP)

    def test_debug_only_logs_actual_denial_not_permit_reason(self):
        self.assertIn('QuestLootProtection: blocked player', CPP)
        self.assertNotIn('QuestLootProtection: permitted player', CPP)
        self.assertIn("DEBUG ALLOW-REASON DIAGNOSTICS", NOTES)

    def test_off_defaults_not_mistaken_for_active_owner_config(self):
        self.assertEqual(CONFIG.count(
            "NaxxramasCore.QuestLootProtection.Enabled = 0"), 1)
        self.assertEqual(CONFIG.count(
            "NaxxramasCore.QuestLootProtection.Debug = 0"), 1)
        self.assertIn("ACTIVE WORLDserver CONFIG: UNKNOWN", NOTES)

    def test_required_negative_controls_preserved(self):
        for marker in ("QLO-01", "QLO-02", "QLO-03", "QLO-04",
                       "QLO-05", "QLO-06", "QLO-07", "QLO-08",
                       "QLO-09", "QLO-10"):
            self.assertIn(marker, NOTES)

if __name__ == "__main__":
    unittest.main()
