"""Build the A04 extracted-pinned-source harness inputs.

Usage: python3 -I tests/a04_native/prepare_pinned.py --core CORE --out OUT [--mutant NAME]

CORE is a checkout of Grimfeather/azerothcore-wotlk at PIN (only the files in
BLOBS are read). This script:

1. checks every source and SQL file against its pinned git blob SHA;
2. copies the original function bodies listed in FUNCTIONS byte for byte
   (each signature line must occur exactly once; the body ends at the first
   line that is exactly "}") into OUT/pinned_bodies.cpp, with #line markers
   pointing at the original file and line;
3. reads the fixture rows (items 5168 and 1931, quests 922 and 176, loot row
   2030/5168) from the pinned public SQL dumps into OUT/pinned_fixture.h;
4. writes OUT/manifest.json with blob SHAs and a SHA-256 for each body.

With --mutant NAME, one named change from MUTANTS is applied to the extracted
original text (used by mutants.py to show the tests depend on that text).
Nothing here touches a server, database or the module runtime.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"

LOOT_CPP = "src/server/game/Loot/LootMgr.cpp"
PLAYER_CPP = "src/server/game/Entities/Player/Player.cpp"
QUEST_CPP = "src/server/game/Entities/Player/PlayerQuest.cpp"
GUID_CPP = "src/server/game/Entities/Object/ObjectGuid.cpp"
BUFFER_CPP = "src/server/shared/Packets/ByteBuffer.cpp"
STORAGE_CPP = "src/server/game/Entities/Player/PlayerStorage.cpp"

BLOBS = {
    LOOT_CPP: "a103aab09b8f93aaef8ddd58239893ec9fb91184",
    "src/server/game/Loot/LootMgr.h": "62b2adc6055843810e310b3b43b3f571d76f42c5",
    PLAYER_CPP: "138e7eab4905ec366338a54cc18e6cfe749a3670",
    QUEST_CPP: "c36b8556b06880f7050baf587b21dac8e5ac4c14",
    GUID_CPP: "b6e12b6e2520c741b8dd91cce84f1de70f631bb5",
    BUFFER_CPP: "4f6273e08348ab72337ab4d7b98724523053c78f",
    STORAGE_CPP: "c3117845d1b92b2e11f0362f6c8e2d6652857165",
    "src/server/game/Quests/QuestDef.h": "9f08d6b918c293d4ce681af6b0fcafb62cee4783",
    "src/server/game/Globals/ObjectMgr.cpp": "61afa509148af2cf7e37e90afe0354e6447dc8d5",
    "src/server/game/Entities/Item/ItemTemplate.h": "709e3eb491220b12c932bfee1d5563920eb73f69",
    "src/server/game/Scripting/ScriptMgrMacros.h": "80895976796c2cc0219256b5b653d3e05c7c908c",
    "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp": "4ac4571a3d7d8c0f3f27e8477ff5d7f0734e6e05",
    "src/server/game/Scripting/ScriptDefines/GlobalScript.cpp": "9bcfd4634a410262f2f16522ec7bf8132f7e3c6c",
    "data/sql/base/db_world/item_template.sql": "a5f561ba1928c4b1d15a18effb73e348f64573ce",
    "data/sql/base/db_world/quest_template.sql": "9ebf71c00c7be4be350c614b05797e87effc1557",
    "data/sql/base/db_world/quest_template_addon.sql": "6438787baaf5664becd76afb87a5a61dcd659e84",
    "data/sql/base/db_world/creature_loot_template.sql": "1ae8dc3607c53ee882a9d4cddc55a3942d854030",
}

# (file, exact signature line). Order is the order in the generated file.
FUNCTIONS = [
    (LOOT_CPP, "LootItem::LootItem(LootStoreItem const& li)"),
    (LOOT_CPP, "bool LootItem::AllowedForPlayer(Player const* player, ObjectGuid source) const"),
    (LOOT_CPP, "void LootItem::AddAllowedLooter(Player const* player)"),
    (LOOT_CPP, "void Loot::AddItem(LootStoreItem const& item)"),
    (LOOT_CPP, "bool Loot::FillLoot(uint32 lootId, LootStore const& store, Player* lootOwner, bool personal, bool noEmptyError, uint16 lootMode /*= LOOT_MODE_DEFAULT*/, WorldObject* lootSource /*= nullptr*/)"),
    (LOOT_CPP, "void Loot::FillNotNormalLootFor(Player* player)"),
    (LOOT_CPP, "QuestItemList* Loot::FillFFALoot(Player* player)"),
    (LOOT_CPP, "QuestItemList* Loot::FillQuestLoot(Player* player)"),
    (LOOT_CPP, "QuestItemList* Loot::FillNonQuestNonFFAConditionalLoot(Player* player)"),
    (LOOT_CPP, "void Loot::NotifyItemRemoved(uint8 lootIndex)"),
    (LOOT_CPP, "void Loot::NotifyQuestItemRemoved(uint8 questIndex)"),
    (LOOT_CPP, "LootItem* Loot::LootItemInSlot(uint32 lootSlot, Player* player, QuestItem * *qitem, QuestItem * *ffaitem, QuestItem * *conditem)"),
    (LOOT_CPP, "uint32 Loot::GetMaxSlotInLootFor(Player* player) const"),
    (LOOT_CPP, "bool Loot::hasItemForAll() const"),
    (LOOT_CPP, "bool Loot::hasItemFor(Player* player) const"),
    (LOOT_CPP, "bool Loot::hasOverThresholdItem() const"),
    (LOOT_CPP, "ByteBuffer& operator<<(ByteBuffer& b, LootItem const& li)"),
    (LOOT_CPP, "ByteBuffer& operator<<(ByteBuffer& b, LootView const& lv)"),
    (PLAYER_CPP, "LootItem* Player::StoreLootItem(uint8 lootSlot, Loot* loot, InventoryResult& msg)"),
    (QUEST_CPP, "bool Player::HasQuestForItem(uint32 itemid, uint32 excludeQuestId /* 0 */, bool turnIn /* false */, bool* showInLoot /*= nullptr*/) const"),
    (QUEST_CPP, "void Player::ItemAddedQuestCheck(uint32 entry, uint32 count)"),
    (QUEST_CPP, "void Player::ItemRemovedQuestCheck(uint32 entry, uint32 count)"),
    # Support only (needed to link; not loot logic): GUID and packet buffer.
    (GUID_CPP, "ObjectGuid ObjectGuid::Global(HighGuid type, LowType counter)"),
    (GUID_CPP, "ObjectGuid ObjectGuid::MapSpecific(HighGuid type, uint32 entry, LowType counter)"),
    (BUFFER_CPP, "ByteBufferPositionException::ByteBufferPositionException(bool add, std::size_t pos, std::size_t size, std::size_t valueSize)"),
    (BUFFER_CPP, "void ByteBuffer::append(uint8 const* src, std::size_t cnt)"),
    (BUFFER_CPP, "void ByteBuffer::put(std::size_t pos, uint8 const* src, std::size_t cnt)"),
]

# Single-line original definitions copied as they are.
SINGLE_LINES = [
    (GUID_CPP, "ObjectGuid const ObjectGuid::Empty = ObjectGuid();"),
]

# Facts the stubs rely on; each line must appear exactly once in the pinned file.
PINNED_FACTS = [
    ("src/server/game/Quests/QuestDef.h", "#define MAX_QUEST_LOG_SIZE 25"),
    ("src/server/game/Quests/QuestDef.h", "#define QUEST_ITEM_OBJECTIVES_COUNT 6"),
    ("src/server/game/Quests/QuestDef.h", "#define QUEST_SOURCE_ITEM_IDS_COUNT 4"),
    ("src/server/game/Quests/QuestDef.h", "    QUEST_STATUS_NONE           = 0,"),
    ("src/server/game/Quests/QuestDef.h", "    QUEST_STATUS_COMPLETE       = 1,"),
    ("src/server/game/Quests/QuestDef.h", "    QUEST_STATUS_INCOMPLETE     = 3,"),
    ("src/server/game/Quests/QuestDef.h", "    QUEST_SPECIAL_FLAGS_DELIVER                 = 0x0200,   // Internal flag computed only"),
    # ObjectMgr::LoadQuests sets DELIVER on every quest with a required item (922 and 176 do).
    ("src/server/game/Globals/ObjectMgr.cpp", "                qinfo->SetSpecialFlag(QUEST_SPECIAL_FLAGS_DELIVER);"),
    # With no enabled scripts both boolean hooks return true (stock default).
    ("src/server/game/Scripting/ScriptMgrMacros.h", "#define CALL_ENABLED_BOOLEAN_HOOKS(scriptType, hookType, action) \\"),
    ("src/server/game/Scripting/ScriptDefines/PlayerScript.cpp",
     "    CALL_ENABLED_BOOLEAN_HOOKS(PlayerScript, PLAYERHOOK_CAN_SEND_ERROR_ALREADY_LOOTED, !script->OnPlayerCanSendErrorAlreadyLooted(player));"),
    ("src/server/game/Scripting/ScriptDefines/GlobalScript.cpp",
     "    CALL_ENABLED_BOOLEAN_HOOKS(GlobalScript, GLOBALHOOK_ON_ALLOWED_FOR_PLAYER_LOOT_CHECK, script->OnAllowedForPlayerLootCheck(player, source));"),
]

# Call orders the harness copies when it moves items (storage itself is not
# executed). Each snippet must occur exactly once in the pinned file.
ORDER_FACTS = [
    # Player::StoreNewItem: quest counter update, then StoreItem, for a new item.
    (STORAGE_CPP, "        ItemAddedQuestCheck(item, count);\n\n        if (!refund)\n"
                  "        { // Don't update counter criteria for refunded items (primarily currencies)\n"
                  "            UpdateAchievementCriteria(ACHIEVEMENT_CRITERIA_TYPE_RECEIVE_EPIC_ITEM, item, count);\n"
                  "            UpdateAchievementCriteria(ACHIEVEMENT_CRITERIA_TYPE_OWN_ITEM, item, count);\n"
                  "        }\n\n        pItem = StoreItem(dest, pItem, update);\n"),
    # Player::SwapItem, whole slot bag -> bank.
    (STORAGE_CPP, "            RemoveItem(srcbag, srcslot, true);\n            BankItem(dest, pSrcItem, true);\n"
                  "            UpdateTitansGrip();\n            ItemRemovedQuestCheck(pSrcItem->GetEntry(), pSrcItem->GetCount());\n"),
    # Player::SwapItem, whole slot bank -> bag.
    (STORAGE_CPP, "            RemoveItem(srcbag, srcslot, true);\n            StoreItem(dest, pSrcItem, true);\n"
                  "            UpdateTitansGrip();\n            if (IsBankPos(src))\n"
                  "                ItemAddedQuestCheck(pSrcItem->GetEntry(), pSrcItem->GetCount());\n"),
]

# Each mutant: (name, exact old text in the extracted bodies, new text).
MUTANTS = {
    "view-does-not-mark-shared-item-looted": (
        "                        if (!item.freeforall)\n                        {\n                            item.is_looted = true;\n                        }\n",
        ""),
    "showInLoot-ignores-bank": (
        "                        if (GetItemCount(itemid, true) < qinfo->RequiredItemCount[j])",
        "                        if (GetItemCount(itemid, false) < qinfo->RequiredItemCount[j])"),
    "allowed-skips-quest-check": (
        "        if (needs_quest && !player->HasQuestForItem(itemid))\n            return false;\n",
        ""),
    "store-skips-allowed-check": (
        "    if (!item->AllowedForPlayer(this, loot->sourceWorldObjectGUID))\n    {\n        SendLootRelease(GetLootGUID());\n        return nullptr;\n    }\n",
        ""),
    "store-ignores-shared-looted-flag": (
        "    if (!item || item->is_looted)\n", "    if (!item)\n"),
    "fill-quest-loot-skips-disallowed-check": (
        "        if (!allowed && !isMasterLooter)\n            continue;\n", ""),
    "ffa-quest-item-marked-looted-globally": (
        "        //if only one person is supposed to loot the item, then set it to looted\n        if (!item->freeforall)\n            item->is_looted = true;\n",
        "        item->is_looted = true;\n"),
    "added-check-does-not-count": (
        "                    q_status.ItemCount[j] = std::min<uint16>(q_status.ItemCount[j] + count, reqitemcount);\n",
        "                    (void)0;\n"),
    "removed-check-skips-bag-reread": (
        "                    curitemcount = GetItemCount(entry, false);\n", "                    (void)0;\n"),
    "bank-move-does-not-reopen-quest": (
        "                    m_QuestStatusSave[questid] = true;\n                    IncompleteQuest(questid);\n",
        "                    m_QuestStatusSave[questid] = true;\n"),
}


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def strip_literals(line: str) -> str:
    """Remove string and char literals and // comments, for brace counting."""
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if c in "\"'":
            q, i = c, i + 1
            while i < n and line[i] != q:
                i += 2 if line[i] == "\\" else 1
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def extract(text: str, signature: str):
    lines = text.split("\n")
    hits = [i for i, l in enumerate(lines) if l == signature]
    if len(hits) != 1:
        raise SystemExit(f"signature must occur exactly once ({len(hits)}): {signature}")
    start = hits[0]
    if lines[start + 1] != "{":
        raise SystemExit(f"expected '{{' after: {signature}")
    end = next(j for j in range(start + 1, len(lines)) if lines[j] == "}")
    body = lines[start:end + 1]
    depth = 0
    for l in body:
        s = strip_literals(l)
        depth += s.count("{") - s.count("}")
    if depth != 0:
        raise SystemExit(f"unbalanced braces in extracted body: {signature}")
    return start + 1, "\n".join(body) + "\n"


def columns(sql: str, table: str):
    m = re.search(r"CREATE TABLE `%s` \((.*?)\n\) ENGINE" % re.escape(table), sql, re.S)
    if not m:
        raise SystemExit(f"no CREATE TABLE for {table}")
    return re.findall(r"^  `([^`]+)`", m.group(1), re.M)


def parse_tuple(sql: str, pos: int):
    vals, cur, i = [], [], pos + 1
    while True:
        c = sql[i]
        if c == "'":
            i += 1
            s = []
            while sql[i] != "'":
                if sql[i] == "\\":
                    s.append(sql[i + 1])
                    i += 2
                    continue
                s.append(sql[i])
                i += 1
            cur.append("'" + "".join(s) + "'")
            i += 1
            continue
        if c in ",)":
            vals.append("".join(cur).strip())
            cur = []
            if c == ")":
                return vals
            i += 1
            continue
        cur.append(c)
        i += 1


def row(sql: str, table: str, key: str):
    cols = columns(sql, table)
    hits = [m.start() + len(m.group(1)) for m in re.finditer(r"(?m)(^|VALUES |\),)\(" + re.escape(key) + ",", sql)]
    if len(hits) != 1:
        raise SystemExit(f"{table} row {key} must occur exactly once ({len(hits)})")
    vals = parse_tuple(sql, hits[0])
    if len(vals) != len(cols):
        raise SystemExit(f"{table} row {key}: {len(vals)} values for {len(cols)} columns")
    return dict(zip(cols, vals))


def num(v: str) -> int:
    return int(float(v))


def fixture_header(core: Path) -> str:
    read = lambda p: (core / p).read_text(encoding="utf-8", errors="strict")
    items_sql = read("data/sql/base/db_world/item_template.sql")
    quest_sql = read("data/sql/base/db_world/quest_template.sql")
    addon_sql = read("data/sql/base/db_world/quest_template_addon.sql")
    loot_sql = read("data/sql/base/db_world/creature_loot_template.sql")

    out = ["// Generated by prepare_pinned.py from the pinned public SQL dumps. Do not edit.",
           "#pragma once", "#include <cstdint>", "namespace pinned {",
           "struct ItemRow { uint32_t entry, cls, quality, flags, flagsExtra, flagsCustom, bonding, startquest, requiredSkill, displayid, bagFamily; int32_t maxcount, stackable; const char* name; };",
           "struct QuestRow { uint32_t id, questType, prevQuestId, requiredItemId[6], requiredItemCount[6], itemDrop[4], itemDropQuantity[4], specialFlags; const char* title; };",
           "struct LootRow { uint32_t entry, item, questRequired, lootMode, groupId, minCount, maxCount; int32_t reference; float chance; };"]
    for entry in ("5168", "1931"):
        r = row(items_sql, "item_template", entry)
        out.append(
            "constexpr ItemRow ITEM_%s{%d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, \"%s\"};" % (
                entry, num(r["entry"]), num(r["class"]), num(r["Quality"]), num(r["Flags"]), num(r["FlagsExtra"]),
                num(r["flagsCustom"]), num(r["bonding"]), num(r["startquest"]), num(r["RequiredSkill"]),
                num(r["displayid"]), num(r["BagFamily"]), num(r["maxcount"]), num(r["stackable"]),
                r["name"].strip("'").replace('"', "")))
    for qid in ("922", "176"):
        q = row(quest_sql, "quest_template", qid)
        a = row(addon_sql, "quest_template_addon", qid)
        req = [num(q[f"RequiredItemId{i}"]) for i in range(1, 7)]
        cnt = [num(q[f"RequiredItemCount{i}"]) for i in range(1, 7)]
        drop = [num(q[f"ItemDrop{i}"]) for i in range(1, 5)]
        dq = [num(q[f"ItemDropQuantity{i}"]) for i in range(1, 5)]
        out.append(
            "constexpr QuestRow QUEST_%s{%d, %d, %d, {%s}, {%s}, {%s}, {%s}, %d, \"%s\"};" % (
                qid, num(q["ID"]), num(q["QuestType"]), num(a["PrevQuestID"]),
                ", ".join(map(str, req)), ", ".join(map(str, cnt)), ", ".join(map(str, drop)),
                ", ".join(map(str, dq)), num(a["SpecialFlags"]), q["LogTitle"].strip("'").replace('"', "")))
    l = row(loot_sql, "creature_loot_template", "2030,5168")
    out.append("constexpr LootRow LOOT_2030_5168{%d, %d, %d, %d, %d, %d, %d, %d, %rf};" % (
        num(l["Entry"]), num(l["Item"]), num(l["QuestRequired"]), num(l["LootMode"]), num(l["GroupId"]),
        num(l["MinCount"]), num(l["MaxCount"]), num(l["Reference"]), float(l["Chance"])))
    out.append("}  // namespace pinned")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--mutant")
    args = ap.parse_args(argv)

    manifest = {"pin": PIN, "blobs": {}, "bodies": [], "mutant": args.mutant}
    for path, want in BLOBS.items():
        got = blob_sha((args.core / path).read_bytes())
        if got != want:
            raise SystemExit(f"BLOB MISMATCH {path}: {got} != {want}")
        manifest["blobs"][path] = got

    for path, line in PINNED_FACTS:
        n = (args.core / path).read_text().split("\n").count(line)
        if n != 1:
            raise SystemExit(f"pinned fact must occur once ({n}) in {path}: {line}")

    for path, snippet in ORDER_FACTS:
        n = (args.core / path).read_text().count(snippet)
        if n != 1:
            raise SystemExit(f"pinned call order must occur once ({n}) in {path}: {snippet!r}")

    texts = {}
    parts = ['// Generated by prepare_pinned.py: original pinned function bodies, byte for byte. Do not edit.',
             '#include "harness_env.h"', '']
    for path, sig in FUNCTIONS:
        text = texts.setdefault(path, (args.core / path).read_text())
        lineno, body = extract(text, sig)
        manifest["bodies"].append({"file": path, "line": lineno, "signature": sig,
                                   "sha256": hashlib.sha256(body.encode()).hexdigest()})
        parts.append(f'#line {lineno} "{path}"')
        parts.append(body)
    for path, line in SINGLE_LINES:
        lines = (args.core / path).read_text().split("\n")
        hits = [i for i, l in enumerate(lines) if l == line]
        if len(hits) != 1:
            raise SystemExit(f"single line must occur exactly once ({len(hits)}): {line}")
        manifest["bodies"].append({"file": path, "line": hits[0] + 1, "signature": line,
                                   "sha256": hashlib.sha256((line + "\n").encode()).hexdigest()})
        parts.append(f'#line {hits[0] + 1} "{path}"')
        parts.append(line + "\n")
    generated = "\n".join(parts)

    if args.mutant:
        old, new = MUTANTS[args.mutant]
        if generated.count(old) != 1:
            raise SystemExit(f"MUTANT ANCHOR NOT UNIQUE: {args.mutant}")
        generated = generated.replace(old, new)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "pinned_bodies.cpp").write_text(generated)
    (args.out / "pinned_fixture.h").write_text(fixture_header(args.core))
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS: {len(BLOBS)} pinned blobs verified, {len(PINNED_FACTS)} pinned facts, {len(ORDER_FACTS)} call orders, "
          f"{len(FUNCTIONS) + len(SINGLE_LINES)} original definitions extracted" + (f", mutant={args.mutant}" if args.mutant else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
