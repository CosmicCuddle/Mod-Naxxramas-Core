#!/usr/bin/env python3
"""Pinned PUBLIC AzerothCore group-roll versus direct loot H1 evidence contract.

Only reads source from a separately pinned public checkout. No runtime hooks,
loot policy, owner IDs, item records, characters, SQL, logs or host access.
This lexical sentinel is NOT a C++ control-flow parser and cannot prove live
mail receipt, persisted inventory, offline winner awards or the owner's H1.
"""
import argparse
from pathlib import Path

GROUP = "src/server/game/Groups/Group.cpp"
PLAYER = "src/server/game/Entities/Player/Player.cpp"
BASE_H = "src/server/game/Scripting/ScriptDefines/PlayerScript.h"
BASE_CPP = "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp"
MANAGER_H = "src/server/game/Scripting/ScriptMgr.h"
HANDLER = "src/server/game/Handlers/LootHandler.cpp"
STORAGE = "src/server/game/Entities/Player/PlayerStorage.cpp"
PATHS = (GROUP, PLAYER, BASE_H, BASE_CPP, MANAGER_H, HANDLER, STORAGE)

DIRECT = "sScriptMgr->OnPlayerLootItem(this, newitem, item->count, this->GetLootGUID());"
ROLL_NEED = "sScriptMgr->OnPlayerGroupRollRewardItem(player, _item, item->count, NEED, roll);"
ROLL_GREED = "sScriptMgr->OnPlayerGroupRollRewardItem(player, _item, item->count, GREED, roll);"
STORE_ROLL = "Item* _item = player->StoreNewItem(dest, roll->itemid, true, item->randomPropertyId, looters);"
PRE_RECEIPT_NAMED_HOOK = "sScriptMgr->OnPlayerAfterCreatureLoot(player);"
NATIVE_STORE = "LootItem* lootItem = player->StoreLootItem(lootSlot, loot, msg);"
MASTER_STORE = "Item* newitem = target->StoreNewItem(dest, item.itemid, true, item.randomPropertyId, looters);"
MASTER_ALLOWED = "if (!item.AllowedForPlayer(target, loot->sourceWorldObjectGUID))"
STORE_NEW_HOOK = "sScriptMgr->OnPlayerStoreNewItem(this, pItem, count);"
MAIL = "SendRollWonItemViaMail(player, item, roll->itemid);"
MAIL_GUARD = ("if (msg == EQUIP_ERR_INVENTORY_FULL && "
              "(mailOnFull == MAIL_ITEM_ON_FULL_INVENTORY_EVERYWHERE || "
              "(mailOnFull == MAIL_ITEM_ON_FULL_INVENTORY_LFG_ONLY && isLFGGroup())))")


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def block(text, signature):
    """Pin one exact unique braced span; fail closed on unseen source changes."""
    require(text.count(signature) == 1, "SPAN_NOT_UNIQUE: " + signature)
    pos = text.index(signature)
    opening = text.find("{", pos + len(signature))
    require(opening >= 0, "SPAN_NO_BRACE: " + signature)
    depth = 0
    for i in range(opening, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1:i]
    raise ContractError("SPAN_UNBALANCED: " + signature)


def check_award_branch(part, name, call):
    require(part.count("if (msg == EQUIP_ERR_OK)") == 1,
            name + "_NATIVE_SUCCESS_GUARD_DRIFT")
    success = block(part, "if (msg == EQUIP_ERR_OK)")
    require(success.count(STORE_ROLL) == 1 and success.count(call) == 1,
            name + "_SUCCESS_RECEIPT_MISSING")
    require(success.count("if (_item)") == 1,
            name + "_NONNULL_ITEM_GUARD_MISSING")
    require(success.index(STORE_ROLL) < success.index("if (_item)") < success.index(call),
            name + "_SUCCESS_CALLBACK_ORDER_CHANGED")
    require(part.count(MAIL_GUARD) == 1 and part.count(MAIL) == 1,
            name + "_INVENTORY_FULL_MAIL_BRANCH_DRIFT")
    require(MAIL not in success and call not in part[part.index(MAIL_GUARD):],
            name + "_MAIL_INCORRECTLY_CLASSIFIED_AS_ROLL_CALLBACK")
    require(part.index(MAIL_GUARD) > part.index("if (msg == EQUIP_ERR_OK)"),
            name + "_MAIL_BRANCH_OUTSIDE_FAILURE")
    require(part.count("item->rollWinnerGUID = player->GetGUID();") == 1,
            name + "_NONFULL_RETRY_WINNER_CHANGED")
    require(part.index("item->rollWinnerGUID = player->GetGUID();") >
            part.index(MAIL), name + "_RETRY_BRANCH_ORDER_CHANGED")


def check_group(source):
    roll = block(source, "void Group::CountTheRoll(Rolls::iterator rollI)")
    require(roll.count(ROLL_NEED) == 1 and roll.count(ROLL_GREED) == 1,
            "G1_NEED_GREED_RECEIPT_DISPATCH_DRIFT")
    require(roll.count(MAIL) == 2,
            "G2_MAIL_PATH_COUNT_CHANGED")
    require("OnPlayerLootItem(" not in roll,
            "G3_NORMAL_AUTOSTORE_HOOK_MISTAKEN_FOR_ROLL_RECEIPT")
    need = block(roll, "if (roll->totalNeed > 0)")
    greed = block(roll, "if (roll->totalNeed == 0 && roll->totalGreed > 0)")
    check_award_branch(need, "NEED", ROLL_NEED)
    greed_only = block(greed, "if (rollvote == GREED)")
    check_award_branch(greed_only, "GREED", ROLL_GREED)
    # An offline candidate does not receive via this online roll loop.
    # This does NOT establish every custom/offline/mail grant pathway.
    require(need.count("player = ObjectAccessor::FindPlayer(itr->first);") == 1 and
            need.count("if (!player)") == 1 and
            need.index("if (!player)") < need.index("SendLootRoll(") and
            "--roll->totalNeed;" in need and "continue;" in need,
            "G4_OFFLINE_NEED_SKIP_CHANGED")
    require(greed.count("player = ObjectAccessor::FindPlayer(itr->first);") == 1 and
            greed.count("if (!player)") == 1 and
            greed.index("if (!player)") < greed.index("SendLootRoll(") and
            "--roll->totalGreed;" in greed and "continue;" in greed,
            "G5_OFFLINE_GREED_SKIP_CHANGED")
    require(need.count("player = ObjectAccessor::FindPlayer(maxguid);") == 1 and
            greed.count("player = ObjectAccessor::FindPlayer(maxguid);") == 1,
            "G6_WINNER_AVAILABILITY_RECHECK_CHANGED")
    helper = block(source, "static void SendRollWonItemViaMail(Player* player, LootItem const* lootItem, uint32 itemId)")
    require("player->SendItemRetrievalMail(mailItem);" in helper and
            "Item::CreateItem(itemId, lootItem->count, player" in helper and
            "if (!mailItem)" in helper,
            "G7_MAIL_HELPER_BOUNDARY_CHANGED")
    require("OnPlayerGroupRollRewardItem(" not in helper,
            "G8_MAIL_HELPER_WRONG_RECEIPT_TYPE")


def check_player(source):
    fn = block(source, "LootItem* Player::StoreLootItem(uint8 lootSlot, Loot* loot, InventoryResult& msg)")
    require(fn.count(DIRECT) == 1 and "OnPlayerGroupRollRewardItem(" not in fn,
            "P1_DIRECT_AND_ROLL_PATHS_CONFLATED")


def check_api(h, impl, mgr):
    require("virtual void OnPlayerGroupRollRewardItem(Player* /*player*/, Item* /*item*/, uint32 /*count*/, RollVote /*voteType*/, Roll* /*roll*/)" in h,
            "S1_ROLL_PLAYER_SCRIPT_VIRTUAL_DRIFT")
    require("void OnPlayerGroupRollRewardItem(Player* player, Item* item, uint32 count, RollVote voteType, Roll* roll);" in mgr,
            "S2_ROLL_SCRIPT_MANAGER_API_DRIFT")
    target = block(impl, "void ScriptMgr::OnPlayerGroupRollRewardItem(Player* player, Item* item, uint32 count, RollVote voteType, Roll* roll)")
    require("CALL_ENABLED_HOOKS(PlayerScript, PLAYERHOOK_ON_GROUP_ROLL_REWARD_ITEM, script->OnPlayerGroupRollRewardItem(player, item, count, voteType, roll));" in target,
            "S3_ROLL_DISPATCH_GUARD_DRIFT")


def check_native_handler(source):
    """The misleadingly named AfterCreatureLoot callback is PRE-store.

    Do not use this void hook as positive H1 item-receipt evidence. The
    separately checked Player::OnPlayerLootItem and Group roll callbacks
    are the successful online reward witnesses, not a universal veto.
    """
    fn = block(source, "void WorldSession::HandleAutostoreLootItemOpcode(WorldPacket& recvData)")
    require(fn.count(PRE_RECEIPT_NAMED_HOOK) == 1,
            "H1_PREAWARD_HOOK_MISSING_OR_DUPLICATED")
    require(fn.count(NATIVE_STORE) == 1,
            "H1_NATIVE_ITEM_STORE_CALL_DRIFT")
    require(fn.index(PRE_RECEIPT_NAMED_HOOK) < fn.index(NATIVE_STORE),
            "H1_PREAWARD_ORDER_CHANGED")


def check_master_award(handler, storage):
    """Master Loot stores directly into the TARGET's inventory.

    This bypasses ordinary Player::StoreLootItem and its OnPlayerLootItem
    receipt hook. The common StoreNewItem hook is post-store but shared
    with many other item awards: it is not Master-Loot-only telemetry.
    """
    master = block(handler, "void WorldSession::HandleLootMasterGiveOpcode(WorldPacket& recvData)")
    require(master.count(MASTER_STORE) == 1,
            "M1_MASTER_TARGET_STORE_CALL_DRIFT")
    require(master.count(MASTER_ALLOWED) == 1,
            "M2_MASTER_ALLOWED_TARGET_CHECK_MISSING")
    require(master.index(MASTER_ALLOWED) < master.index(MASTER_STORE),
            "M3_MASTER_ALLOWED_CHECK_AFTER_STORE")
    require("if (msg != EQUIP_ERR_OK)" in master and
            master.index("if (msg != EQUIP_ERR_OK)") < master.index(MASTER_STORE),
            "M4_MASTER_INVENTORY_REJECT_CHECK_DRIFT")
    require("OnPlayerLootItem(" not in master and
            "OnPlayerGroupRollRewardItem(" not in master,
            "M5_MASTER_AWARD_CONFLATED_WITH_DIRECT_OR_ROLL_HOOK")

    fn = block(storage,
        "Item* Player::StoreNewItem(ItemPosCountVec const& dest, uint32 item, bool update, int32 randomPropertyId, AllowedLooterSet& allowedLooters, bool refund)")
    require(fn.count(STORE_NEW_HOOK) == 1,
            "M6_POST_STORE_NEW_ITEM_HOOK_MISSING")
    require("pItem = StoreItem(dest, pItem, update);" in fn and
            fn.index("pItem = StoreItem(dest, pItem, update);") < fn.index(STORE_NEW_HOOK),
            "M7_STORE_ITEM_AFTER_RECEIPT_CALLBACK")
    require("if (pItem)" in fn and
            fn.index("if (pItem)") < fn.index(STORE_NEW_HOOK),
            "M8_STORE_NEW_HOOK_NOT_GUARDED_BY_CREATED_ITEM")


def check(sources):
    require(set(sources) == set(PATHS), "F1_SOURCE_FIXTURE_MISSING_OR_EXTRA")
    check_group(sources[GROUP])
    check_player(sources[PLAYER])
    check_native_handler(sources[HANDLER])
    check_master_award(sources[HANDLER], sources[STORAGE])
    check_api(sources[BASE_H], sources[BASE_CPP], sources[MANAGER_H])
    return "A04 GROUP ROLL vs DIRECT RECEIPT: PASS (pinned source only)"


def load(root):
    return {p: (Path(root) / p).read_text(encoding="utf-8") for p in PATHS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    options = parser.parse_args(argv)
    try:
        print(check(load(options.core)))
    except (OSError, ContractError) as exc:
        parser.exit(1, "A04 roll/direct receipt source must be re-reviewed: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
