#!/usr/bin/env python3
"""A04 research: fingerprint the core loot functions tests/research/a04_roll_model.py copies.

The Q6b witnesses transcribe a few native roll and pickup functions. This
script hashes each function, byte for byte, in an AzerothCore checkout so a
core pin change that touches any of them is caught before the model drifts.

Usage: check_a04_roll_fingerprint.py <core-checkout> [--print]
Exit 0 when every hash matches the reviewed pin, 1 otherwise.
"""
import hashlib
import sys
from pathlib import Path

REVIEWED_CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
GAME = "src/server/game/"

# (file, exact signature line); each is hashed from signature to matching brace.
FUNCTIONS = [
    ("Groups/Group.cpp",
     "static void SendRollWonItemViaMail(Player* player, LootItem const* lootItem, uint32 itemId)"),
    ("Groups/Group.cpp",
     "void Group::SendLootStartRoll(uint32 CountDown, uint32 mapid, Roll const& r)"),
    ("Groups/Group.cpp",
     "bool CanRollOnItem(LootItem const& item, Player const* player, Loot* loot)"),
    ("Groups/Group.cpp",
     "void Group::GroupLoot(Loot* loot, WorldObject* pLootedObject)"),
    ("Groups/Group.cpp",
     "bool Group::CountRollVote(ObjectGuid playerGUID, ObjectGuid Guid, uint8 Choice)"),
    ("Groups/Group.cpp",
     "void Group::CountTheRoll(Rolls::iterator rollI)"),
    ("Entities/Player/Player.cpp",
     "LootItem* Player::StoreLootItem(uint8 lootSlot, Loot* loot, InventoryResult& msg)"),
    ("Entities/Player/PlayerQuest.cpp",
     "void Player::AdjustQuestReqItemCount(Quest const* quest, QuestStatusData& questStatusData)"),
    ("Entities/Player/PlayerQuest.cpp",
     "void Player::ItemAddedQuestCheck(uint32 entry, uint32 count)"),
    ("Entities/Player/PlayerQuest.cpp",
     "void Player::ItemRemovedQuestCheck(uint32 entry, uint32 count)"),
    ("Entities/Player/PlayerQuest.cpp",
     "bool Player::HasQuestForItem(uint32 itemid, uint32 excludeQuestId /* 0 */, bool turnIn /* false */, bool* showInLoot /*= nullptr*/) const"),
    ("Loot/LootMgr.cpp",
     "bool LootItem::AllowedForPlayer(Player const* player, ObjectGuid source) const"),
    ("Loot/LootMgr.cpp",
     "LootItem* Loot::LootItemInSlot(uint32 lootSlot, Player* player, QuestItem * *qitem, QuestItem * *ffaitem, QuestItem * *conditem)"),
]

EXPECTED = {
    "SendRollWonItemViaMail":
        "4fe25d6d65f36d26b77b56c74f3b0ff6afa3e6210354ff7c17a7e8c1738a1593",
    "Group::SendLootStartRoll":
        "699864111392620e7136df250b3f0abedcc2628b7346e020262c69d7d06f1b3b",
    "CanRollOnItem":
        "6928d661407e57d5cb3068e354e2faf1404903aedd917e1b61580336a8ba9360",
    "Group::GroupLoot":
        "8bab2cd912b4d52045b2fa2a0a7fb2e36c278494c4e48f0c6dd0141f10fb22d4",
    "Group::CountRollVote":
        "514a4a2f1fbd0d0613e3f0e6dff3775fb0e286ab9aae127a0fbb6715be912ce5",
    "Group::CountTheRoll":
        "2ae206eb9c78a260ceee3a68e0e7b5891afccb851053bbfa456030df0bc56665",
    "Player::StoreLootItem":
        "eed5274682fc95174fea947e2bfc56c9375cbff9bad165e5c4375b16f04155dc",
    "Player::AdjustQuestReqItemCount":
        "afa1850b9dd106be371706bcdb4871db892e37d3dc76abd4d5606bcbb20c0bea",
    "Player::ItemAddedQuestCheck":
        "29589cfbd584414704b312db1f314b030d482b14101235c9b7f14e93cc0babf9",
    "Player::ItemRemovedQuestCheck":
        "53c2076d20dc77f89a01aa93138ead6275b21bd5e10658fdd0da4ad5d0586008",
    "Player::HasQuestForItem":
        "b8a183cec8a357dc8b1e30add82ad9b9921dd4cd4d1567ea6ce1f1b96554f1ad",
    "LootItem::AllowedForPlayer":
        "b3bd819cb45686c4d5d290eb4ed86dbf3a503bdf94e8945b6fd66e704360393f",
    "Loot::LootItemInSlot":
        "8d13186ea0d3721b3f54aa7e3d4783e480d383c99bee37cdc7b04b210286fc51",
}


def function_text(source, signature):
    """Signature through the matching closing brace, byte for byte."""
    if source.count(signature) != 1:
        raise ValueError("expected one definition of " + signature)
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError("unbalanced braces after " + signature)


def fingerprints(core_root):
    root = Path(core_root)
    out = {}
    for (rel, signature) in FUNCTIONS:
        text = (root / GAME / rel).read_text(encoding="utf-8")
        name = signature.split("(")[0].split()[-1].lstrip("*")
        out[name] = hashlib.sha256(function_text(text, signature).encode("utf-8")).hexdigest()
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    found = fingerprints(argv[1])
    if "--print" in argv[2:]:
        for name, digest in found.items():
            print("%-32s %s" % (name, digest))
    changed = [name for name, digest in found.items() if EXPECTED.get(name) != digest]
    for name in changed:
        print("%s changed since %s: %s" % (name, REVIEWED_CORE, found[name]))
    if not changed:
        print("OK: %d loot functions match core %s" % (len(found), REVIEWED_CORE))
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
