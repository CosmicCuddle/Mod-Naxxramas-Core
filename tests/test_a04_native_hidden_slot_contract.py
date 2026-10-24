"""A04 native hidden ordinary-slot prototype source contract; no worldserver."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/QuestLootProtection.cpp").read_text(encoding="utf-8")
POLICY = (ROOT / "src/Systems/QuestLootNormalSlotPolicy.h").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")


class GuardContract(unittest.TestCase):
    def test_both_flags_off_in_dist(self):
        for key in ("Enabled", "RestrictHiddenOrdinarySlots"):
            self.assertRegex(CONF, rf"(?m)^NaxxramasCore\.QuestLootProtection\.{key} = 0$")

    def test_separate_missing_option_defaults_off(self):
        self.assertIn(
            '"NaxxramasCore.QuestLootProtection.RestrictHiddenOrdinarySlots", false',
            CPP,
        )

    def test_header_is_dependency_free(self):
        self.assertIn("QuestLootNormalSlotPolicy.h", CPP)
        self.assertNotIn("#include", POLICY.split("#define NAXXRAMAS_CORE_QUEST_LOOT_NORMAL_SLOT_POLICY_H")[1])

    def test_guard_is_only_for_normal_bucket(self):
        start = CPP.index("if (requestedSlot < normalCount)")
        end = CPP.index("auto const& personal = loot.GetPlayerQuestItems();", start)
        body = CPP[start:end]
        self.assertIn("!RestrictHiddenOrdinarySlots()", body)
        self.assertIn("loot.items[requestedSlot]", body)
        self.assertIn("RejectHiddenOrdinarySlot(facts)", body)
        self.assertIn("return true;", body)
        self.assertIn("SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", body)
        self.assertIn("return false;", body)
        self.assertNotIn("StoreNewItem", body)
        self.assertNotIn("roundRobinPlayer.Clear()", body)

    def test_existing_quest_bucket_owner_guard_retained(self):
        for needle in (
            "auto const& personal = loot.GetPlayerQuestItems();",
            "QuestItem const& view = found->second->at(personalSlot);",
            "QuestItem const& ownerItem", # checked below via approximate source contract
            "owner->HasQuestForItem(item.itemid)",
        ):
            if needle == "QuestItem const& ownerItem":
                self.assertIn("for (QuestItem const& ownerItem :", CPP)
            else:
                self.assertIn(needle, CPP)

    def test_master_ffa_still_native(self):
        self.assertIn("case GROUP_LOOT:", CPP)
        self.assertIn("case ROUND_ROBIN:", CPP)
        self.assertIn("case NEED_BEFORE_GREED:", CPP)
        self.assertIn("default:\n                return true;", CPP)
        self.assertIn("GroupMethod::Other", CPP)

    def test_same_live_group_and_map_fails_open_when_missing(self):
        for needle in (
            "ObjectAccessor::FindPlayer(loot.roundRobinPlayer)",
            "turnOwner->GetGroup() == group",
            "ownerMap == requesterMap",
            "ownerMap == sourceMap",
            "turnOwner->GetInstanceId() == creature->GetInstanceId()",
            "facts.OwnerPresentInSameGroupAndMap = ownerLiveHere;",
        ):
            self.assertIn(needle, CPP)

    def test_per_player_and_roll_paths_fail_open(self):
        for needle in (
            "f.IsFreeForAllItem",
            "f.HasConditions",
            "f.IsBlocked",
            "f.HasRollWinner",
            "f.FollowsSpecialLootRules",
            "f.RequesterHoldsTurn",
        ):
            self.assertIn(needle, POLICY)

    def test_group_and_nbg_only_under_threshold(self):
        self.assertIn("f.Method == GroupMethod::RoundRobin", POLICY)
        self.assertIn("return f.IsUnderThreshold;", POLICY)

    def test_debug_only_logging_and_no_loot_state_mutation(self):
        self.assertIn("if (Debug())\n                LOG_INFO", CPP)
        for forbidden in ("StoreNewItem(", "item.is_looted = true",
                          "loot.unlootedCount--", "loot.roundRobinPlayer.Clear()"):
            self.assertNotIn(forbidden, CPP)

    def test_declared_candidate_not_claimed_as_user_fix(self):
        self.assertIn("not a proven explanation", CONF.lower())
        self.assertIn("REVIEW-ONLY candidate", CPP)


if __name__ == "__main__":
    unittest.main()
