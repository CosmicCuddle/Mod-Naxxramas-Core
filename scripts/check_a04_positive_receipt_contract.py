#!/usr/bin/env python3
"""A04 H1 PUBLIC pinned-source receipt boundary. Read-only, not an observer.

Checks the native direct StoreLootItem path at immutable public Grimfeather
8daffdabe... . A registered OnPlayerLootItem callback on this path follows
an in-memory StoreNewItem. A packet/window/returned LootItem is NOT a receipt.

This source assertion cannot prove: a durable DB commit, mail or roll award,
genuine friend eligibility, the installed fork, or the owner's H1/H2 incident.
No character values, player IDs, SQL, server, network, or files are written.
"""
import argparse
from pathlib import Path

PLAYER_CPP = "src/server/game/Entities/Player/Player.cpp"
HANDLER_CPP = "src/server/game/Handlers/LootHandler.cpp"
PLAYER_SCRIPT_H = "src/server/game/Scripting/ScriptDefines/PlayerScript.h"
PLAYER_SCRIPT_CPP = "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp"
SCRIPT_MGR_H = "src/server/game/Scripting/ScriptMgr.h"
PATHS = (PLAYER_CPP, HANDLER_CPP, PLAYER_SCRIPT_H, PLAYER_SCRIPT_CPP, SCRIPT_MGR_H)

HOOK = "sScriptMgr->OnPlayerLootItem(this, newitem, item->count, this->GetLootGUID());"
STORE = "Item* newitem = StoreNewItem(dest, item->itemid, true, item->randomPropertyId, looters);"
NOTIFY = "SendNewItem(newitem, uint32(item->count), false, false, true);"
MAIL_GATE = "if (msg != EQUIP_ERR_OK && lguid.IsItem() && loot->loot_type != LOOT_CORPSE)"


class ContractError(ValueError):
    """Pinned C++ control flow was changed or source fixture was incomplete."""


def demand(ok, code):
    if not ok:
        raise ContractError(code)


def body(source, signature):
    """Extract a unique C++ braced span. Purposefully fail on source drift.

    This lexical sentinel is NOT a C++ parser. It checks a specific immutable
    source revision and must be re-reviewed before changing dependency pins.
    """
    demand(source.count(signature) == 1, "SIGNATURE_MISSING_OR_DUPLICATED: " + signature)
    start = source.index(signature)
    opening = source.find("{", start + len(signature))
    demand(opening >= 0, "BODY_MISSING: " + signature)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:i]
    raise ContractError("UNBALANCED_SOURCE: " + signature)


def check_player(source):
    fn = body(source, "LootItem* Player::StoreLootItem(uint8 lootSlot, Loot* loot, InventoryResult& msg)")
    demand(fn.count(HOOK) == 1, "P1_RECEIPT_CALLBACK_MISSING_OR_DUPLICATED")
    # Check early rejection branches remain before inventory acceptance.
    checks = (
        "if (!item || item->is_looted)",
        "if (!item->AllowedForPlayer(this, loot->sourceWorldObjectGUID))",
        "if (!qitem && item->is_blocked)",
        "if (item->rollWinnerGUID && item->rollWinnerGUID != GetGUID())",
        "msg = CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, item->itemid, item->count);",
    )
    positions = [fn.find(s) for s in checks]
    demand(all(i >= 0 for i in positions) and positions == sorted(positions),
           "P2_NATIVE_GUARDS_OR_STORE_CHECK_CHANGED")
    demand(fn.count("if (msg == EQUIP_ERR_OK)") == 1,
           "P3_SUCCESS_GUARD_CHANGED")
    success = body(fn, "if (msg == EQUIP_ERR_OK)")
    demand(fn.index("if (msg == EQUIP_ERR_OK)") > positions[-1],
           "P4_SUCCESS_BRANCH_PRECEDES_INVENTORY_CHECK")
    demand(all(x in success for x in (STORE, NOTIFY, HOOK)),
           "P5_RECEIPT_NOT_CONFINED_TO_SUCCESS_BRANCH")
    demand(success.index(STORE) < success.index(NOTIFY) < success.index(HOOK),
           "P6_RECEIPT_NOT_AFTER_IN_MEMORY_STORE_AND_NOTICE")
    demand("return item;" in fn[fn.index("if (msg == EQUIP_ERR_OK)"):],
           "P7_RETURN_SEMANTICS_CHANGED")
    # Returned LootItem* is possible even when CanStoreNewItem failed. Never
    # turn the return value into proof of successful in-memory item storage.
    demand("SendEquipError(msg, nullptr, nullptr, item->itemid);" in fn and
           "else" in fn[fn.index("if (msg == EQUIP_ERR_OK)"):],
           "P8_FAILURE_PATH_OR_RETURN_SEMANTICS_CHANGED")


def check_packet(source):
    fn = body(source, "void WorldSession::HandleAutostoreLootItemOpcode(WorldPacket& recvData)")
    demand(fn.count("player->StoreLootItem(lootSlot, loot, msg);") == 1,
           "H1_NATIVE_STORE_CALL_MISSING")
    demand(fn.index("InventoryResult msg;") < fn.index("player->StoreLootItem("),
           "H2_PACKET_RESULT_FLOW_CHANGED")
    demand(MAIL_GATE in fn, "H3_ITEM_ONLY_MAIL_FALLBACK_CHANGED")
    demand("loot = &creature->loot;" in fn,
           "H4_CREATURE_ROUTE_CHANGED")
    demand("OnPlayerLootItem(" not in fn, "H5_PACKET_INCORRECTLY_TREATED_AS_RECEIPT")


def check_hooks(header, implementation, manager):
    demand("virtual void OnPlayerLootItem(Player* /*player*/, Item* /*item*/, uint32 /*count*/, ObjectGuid /*lootguid*/)" in header,
           "S1_PLAYER_SCRIPT_CALLBACK_CHANGED")
    demand("void OnPlayerLootItem(Player* player, Item* item, uint32 count, ObjectGuid lootguid);" in manager,
           "S2_SCRIPT_MGR_API_CHANGED")
    fn = body(implementation, "void ScriptMgr::OnPlayerLootItem(Player* player, Item* item, uint32 count, ObjectGuid lootguid)")
    demand("CALL_ENABLED_HOOKS(PlayerScript, PLAYERHOOK_ON_LOOT_ITEM, script->OnPlayerLootItem(player, item, count, lootguid));" in fn,
           "S3_DISPATCH_OR_HOOK_FILTER_CHANGED")


def check(sources):
    demand(set(sources) == set(PATHS), "F1_MISSING_OR_EXTRA_SOURCE_FIXTURE")
    check_player(sources[PLAYER_CPP])
    check_packet(sources[HANDLER_CPP])
    check_hooks(sources[PLAYER_SCRIPT_H], sources[PLAYER_SCRIPT_CPP], sources[SCRIPT_MGR_H])
    return "A04 POSITIVE DIRECT RECEIPT SOURCE CONTRACT: PASS (no runtime)"


def load(root):
    root = Path(root)
    return {p: (root / p).read_text(encoding="utf-8") for p in PATHS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(check(load(args.core)))
    except (OSError, ContractError) as exc:
        parser.exit(1, f"A04 pinned source changed; no receipt inference: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
