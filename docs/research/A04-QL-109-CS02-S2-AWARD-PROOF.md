# A04 / #109 S2 — human award-path proof (review only)

**Status:** isolated source proof and negative tests. This is not a production loot-entitlement rule. No `src/` change, no SQL, no config, no personal copies, no new ownership, no altered allocation. Do not merge.

**Author:** CosmicScript02. **Assignment:** [#48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48) comments [6382451976](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6382451976) and [6382497699](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6382497699). **Issue:** [#109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109). S1 stays on draft PR #110 at `f9022be` and draft PR #111. This note does not redo those tests.

**Executable model:** `tests/test_ql109_cs02_s2_award_proof.py`. The model is synthetic. It does not link Grimfeather, Playerbots, or Individual Progression, and it does not move an item.

## Finding

The friend's pickup is permitted, and a one-copy non-`freeforall` line is then stored, when `CanPacketReceive` returns true and `Player::StoreLootItem` (`Player.cpp:13861`) runs. On this pin that commit sets `item->is_looted` (`Player.cpp:13941-13943`) and decrements `unlootedCount`. There is no `roundRobinPlayer` comparison anywhere in `StoreLootItem`.

That permit-then-store sequence is the current source for:

- **H09.** The friend holds `roundRobinPlayer`. The module returns true at `QuestLootProtection.cpp:75`. The quest row was already `LOOT_SLOT_TYPE_ALLOW_LOOT`.
- **H10.** The holder no longer needs the item (`!owner->HasQuestForItem`, `QuestLootProtection.cpp:177-179`). The friend's own `AllowedForPlayer` still passes, and the single copy is stored.
- **A released or cleared turn.** `WorldSession::DoLootRelease` clears `roundRobinPlayer` at `LootHandler.cpp:459-461` (gameobject release at `LootHandler.cpp:390-391`). The module returns true at `QuestLootProtection.cpp:74`.
- **Normal quest-relevant `loot.items`.** `QuestRequired = 0` is stored in `items`, not `quest_items` (`LootMgr.cpp:166` and `LootMgr.cpp:490`). The module returns true at `QuestLootProtection.cpp:82` for every slot below `loot.items.size()`, including conditional drops. `StoreLootItem` then consumes a non-`freeforall` line. The loot window can omit an under-threshold unconditional row from a non-holder (`LootMgr.cpp:1047-1049`) and still the server awards the slot if the packet arrives.
- **Human A/B quest eligibility.** A friend with no quest has no personal quest view, no quest row, and `StoreLootItem` returns no slot (`LootMgr.cpp:826-838`, `Player.cpp:13870`). A friend who has the quest is shown `ALLOW_LOOT` even while someone else holds the turn (`LootMgr.cpp:1154-1155`). The guard denies that click only while every narrow predicate at `QuestLootProtection.cpp:193-194` is true.
- **Manual loot and autoloot.** Both are `CMSG_AUTOSTORE_LOOT_ITEM` (`Opcodes.h:294`, value `0x108`; `Opcodes.cpp:395` → `HandleAutostoreLootItemOpcode`). The server path is the same. `HandleAutostoreLootItemOpcode` calls `StoreLootItem` at `LootHandler.cpp:107`.
- **MULTI_DROP / `freeforall` versus one shared copy.** `LootItem::LootItem` sets `freeforall` from `ITEM_FLAG_MULTI_DROP` (`LootMgr.cpp:400`). A `freeforall` store marks only the personal view and leaves `item->is_looted` false (`Player.cpp:13915-13943`). A group loot method of `FREE_FOR_ALL` is a different fact: the module permits it at `QuestLootProtection.cpp:59`, and a one-copy quest line is still consumed by the first successful store.

**No exact module-only pre-storage hook** on Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd` can reject one wrong-human award and leave valid loot visible. The negative matrix is below. `ServerScript::CanPacketReceive` is a socket pre-handler, not a call inside `StoreLootItem`. Widening it would be a new entitlement policy, which this proof does not write. `OnAllowedForPlayerLootCheck` can return a deny before `StoreNewItem` and also removes the same items from the loot window. `CanPacketSend` can only drop a whole `SMSG_LOOT_RESPONSE`.

## Labels

| Label | Meaning |
| --- | --- |
| VERIFIED | Read at the SHA in the pins table. File:line refers to that tree. |
| NOT TESTED | Not run in game and not run on a linked worldserver. A green Python run stays NOT TESTED for gameplay. |
| UNKNOWN | The owner's item, quest, creature, loot method, group mix, loaded binary, and loaded config. Whether a unique copy moved on that corpse is UNKNOWN. |

Both owner reports stay open. Report (a) matches the deny cell: sparkle and `ALLOW_LOOT`, then `CanPacketReceive` returns false and `StoreLootItem` is not reached. Report (b) matches every permit cell whose award is `stored_shared_consumed`. Neither report is identified with one cell.

## Pins

| Tree | SHA | What was read |
| --- | --- | --- |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` | Detached checkout. `git rev-parse HEAD` returned that SHA. Loot, session, group, and script hooks cited below. |
| Mod-Naxxramas-Core `main` | `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` | `QuestLootProtection.cpp` blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f`. This branch does not edit it. |

Workflows in this repo check out Grimfeather `azerothcore-wotlk`, not another fork, at this same pin.

## Four stages

Stage 1 is `Unit::PatchValuesUpdate` (`Unit.cpp:16594-16610`) calling `Player::isAllowedToLoot` (`PlayerStorage.cpp:5746-5796`). Stage 2 is `operator<<(ByteBuffer&, LootView const&)` (`LootMgr.cpp:974-1230`) inside `Player::SendLoot` (`Player.cpp:8385-8388`). Stage 3 is `NaxxramasQuestLootProtectionScript::CanPacketReceive` (`QuestLootProtection.cpp:205-226`), reached from `WorldSession::Update` only while `m_Socket` is set (`WorldSession.cpp:461-464`). Stage 4 is `Player::StoreLootItem` (`Player.cpp:13861-13961`).

`LOOT_SLOT_TYPE_ALLOW_LOOT` is 0 (`LootMgr.h:114`). Quest rows for a viewer with `HasQuestForItem` (`PlayerQuest.cpp:2338`) and a non-`follow_loot_rules`, non-`freeforall` line send `partySlotType` (`LootMgr.cpp:1094-1097` and `LootMgr.cpp:1154-1155`). For group, round robin, need-before-greed, and non-master master-loot permissions, that value is `ALLOW_LOOT`. The quest loop does not read `roundRobinPlayer`.

| Case | 1 Sparkle | 2 Row | 3 Guard | 4 Award |
| --- | --- | --- | --- | --- |
| H09 friend holds the turn, both need the one-copy quest line, group loot, manual or autoloot | Yes | `ALLOW_LOOT` | Permit `QuestLootProtection.cpp:75` | `stored_shared_consumed` |
| H09 owner clicks while the friend still holds the turn and still needs it | Yes | `ALLOW_LOOT` | Deny `QuestLootProtection.cpp:194` | `not_reached` |
| H10 holder no longer needs it, friend still does | Yes | `ALLOW_LOOT` | Permit `QuestLootProtection.cpp:177` | `stored_shared_consumed` |
| H10 friend also has no quest | No | omitted | Permit `QuestLootProtection.cpp:86` | `no_slot` |
| Released turn (`roundRobinPlayer` cleared), friend has the quest | Yes | `ALLOW_LOOT` | Permit `QuestLootProtection.cpp:74` | `stored_shared_consumed` |
| `QuestRequired = 0` unconditional under-threshold line, friend is not the holder | No | omitted | Permit `QuestLootProtection.cpp:82` | `stored_shared_consumed` if that slot packet arrives |
| Conditional `loot.items` line the friend meets, friend is not the holder | Yes | `ALLOW_LOOT` (`LootMgr.cpp:1218-1219`, no turn check) | Permit `QuestLootProtection.cpp:82` | `stored_shared_consumed` |
| Friend has the quest, holder still needs it, guard on | Yes | `ALLOW_LOOT` | Deny | `not_reached`. The same slot would store if the guard were absent (`Player.cpp:13888` then `13941`) |
| `ITEM_FLAG_MULTI_DROP` on a quest line | Yes | `ALLOW_LOOT` | Permit `QuestLootProtection.cpp:102` | `stored_personal_copy` |
| `ITEM_FLAG_MULTI_DROP` on `loot.items` | Yes | `ALLOW_LOOT` (`LootMgr.cpp:1178`) | Permit `QuestLootProtection.cpp:82` (slot is still a normal index) | `stored_personal_copy` |
| Loot method `FREE_FOR_ALL`, one-copy quest line, friend has the quest | Yes | `ALLOW_LOOT` | Permit `QuestLootProtection.cpp:59` | `stored_shared_consumed` |
| Loot method `MASTER_LOOT`, non-master friend has the quest | Yes | `ALLOW_LOOT` under `RESTRICTED_PERMISSION` | Permit `QuestLootProtection.cpp:59` | `stored_shared_consumed` (`qitem` skips `Player.cpp:13881-13886`) |
| `follow_loot_rules` quest line with `is_blocked` (roll in progress) | Yes | `ROLL_ONGOING` | Permit `QuestLootProtection.cpp:102` | `stored_shared_consumed` because `!qitem` is false at `Player.cpp:13895` |
| Normal `is_blocked` line | Yes for group / need-before-greed | `ROLL_ONGOING` | Permit `QuestLootProtection.cpp:82` | `rejected_blocked` |
| Second human after the shared copy was stored | No | omitted | Permit, view already looted | `already_looted` (`Player.cpp:13870-13876`) |
| Inventory full on an otherwise permitted quest click | Yes | `ALLOW_LOOT` | Permit | `rejected_inventory`. `is_looted` stays false (`Player.cpp:13956-13959`) |

Need-before-greed uses the same `GROUP_PERMISSION` arm as group loot (`Player.cpp:8333-8340`) and the same guard methods (`QuestLootProtection.cpp:53-56`). Round robin does not use `hasOverThresholdItem` (`PlayerStorage.cpp:5775-5781` versus `5782-5793`). An over-threshold normal line therefore sparkles for a group non-holder and does not sparkle for a round-robin non-holder. The window hides that round-robin row (`LootMgr.cpp:1064-1066`) and `StoreLootItem` still awards a packet for it.

Manual and autoloot are not two server awards. The client chooses which shown slots generate `CMSG_AUTOSTORE_LOOT_ITEM`. A stock client is not shown here sending a slot the window omitted. If that packet is on the socket, stage 3 and stage 4 treat it like a click. NOT TESTED on a client.

## Where stage 4 is reached without stage 3

These are VERIFIED call sites. They are not the human autostore click. They show why a packet guard is not a pre-storage hook.

| Path | Call | Guard |
| --- | --- | --- |
| Human manual or client autoloot | `LootHandler.cpp:107` `StoreLootItem` | Runs first, socket only |
| FFA currency token during fill | `LootMgr.cpp:623-628` `StoreLootItem` | Not called |
| Group roll winner | `Group.cpp:1658-1662` `StoreNewItem` | Not called. Quest lines are rolled only when `follow_loot_rules` (`Group.cpp:1222-1224`, `Group.cpp:1375-1378`) |
| Master loot give | `LootHandler.cpp:541-563` `StoreNewItem`. The index is `quest_items[slot - items.size()]`, not the personal quest view | Not called. `AllowedForPlayer` still applies at `LootHandler.cpp:545` |
| Spell, skin, disenchant `Player::AutoStoreLoot` | `Player.cpp:13834` builds a fresh personal `Loot` and calls `StoreNewItem` | Not the corpse window |

`OnPlayerLootItem` runs only after a successful `StoreLootItem` commit (`Player.cpp:13954`). `OnPlayerStoreNewItem` runs from `Player::StoreNewItem` after `StoreItem` (`PlayerStorage.cpp:2685`).

## Negative matrix — module-only hooks

A hook is sufficient only when all of these hold: it can return a deny; it receives the resolved item; `StoreLootItem` calls it before `StoreNewItem`; loot display and fill do not use the same deny; it does not take a mutable shared `LootItem`; it cannot blank an entire `SMSG_LOOT_RESPONSE`; it is not limited to the socket autostore opcode. None of the hooks below pass.

| Hook | Signature | Why it is not that hook |
| --- | --- | --- |
| `ServerScript::CanPacketReceive` | `bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)` | `ServerScript.h:75`, called at `WorldSession.cpp:461` before `opHandle->Call`. The packet is a slot byte, not a `LootItem`. `Player.cpp:13861` does not call it. Currency fill, rolls, and master give never enter it. Returning false does not rewrite `SMSG_LOOT_RESPONSE`. The current module already uses it and still permits the award rows above. |
| `ServerScript::CanPacketSend` | `bool CanPacketSend(WorldSession* session, WorldPacket const& packet)` | `ServerScript.h:65`, `WorldSession.cpp:351-356`. A false return drops the whole const packet. Vetoeing `SMSG_LOOT_RESPONSE` hides gold and legitimate FFA rows with the quest row. |
| `GlobalScript::OnAllowedForPlayerLootCheck` | `bool OnAllowedForPlayerLootCheck(Player const* player, ObjectGuid source)` | `GlobalScript.h:98`. `CALL_ENABLED_BOOLEAN_HOOKS` (`ScriptMgrMacros.h:76-80`) turns a true hook return into a false `ScriptMgr` result, and `LootItem::AllowedForPlayer` then returns false (`LootMgr.cpp:465-466`). The arguments are player and source, not the item. The same check builds quest views (`LootMgr.cpp:671`), FFA and conditional views, the loot window (`LootMgr.cpp:1004`), and `StoreLootItem` (`Player.cpp:13888`). A deny hides those valid item rows. Gold can remain (`LootMgr.cpp:894-897`). |
| `GlobalScript::OnAllowedToLootContainerCheck` | `bool OnAllowedToLootContainerCheck(Player const* player, ObjectGuid source)` | `GlobalScript.h:101`, `Player.cpp:8373-8377`. A true hook return makes `SendLoot` send `LOOT_ERROR_DIDNT_KILL` and skip the loot response. The whole window, including valid loot, stays closed. It does not run inside `StoreLootItem`. |
| `PlayerScript::OnPlayerBeforeSendLoot` | `void OnPlayerBeforeSendLoot(Player* player, ObjectGuid lootGuid, Loot* loot)` | `PlayerScript.h:311`, `Player.cpp:8383`. No deny return. `Loot*` is the shared corpse loot. |
| `PlayerScript::OnPlayerBeforeFillQuestLootItem` | `void OnPlayerBeforeFillQuestLootItem(Player* player, LootItem& item)` | `PlayerScript.h:461`, `LootMgr.cpp:667-669`. `item` is `quest_items[i]`, shared by every viewer. No deny return. A write is a shared mutation. This proof does not do that. |
| `MiscScript::OnAfterLootTemplateProcess` | `void OnAfterLootTemplateProcess(Loot* loot, LootTemplate const* tab, LootStore const& store, Player* lootOwner, bool personal, bool noEmptyError, uint16 lootMode)` | `MiscScript.h:84`, `LootMgr.cpp:563`. Generation time, before `roundRobinPlayer` (`LootMgr.cpp:569`). No deny return. `loot_type` is still `LOOT_NONE` until `Player::SendLoot` (`Player.cpp:8371`). Not an award reject. |
| `PlayerScript::OnPlayerAfterCreatureLoot` | `void OnPlayerAfterCreatureLoot(Player* player)` | `PlayerScript.h:817`, `LootHandler.cpp:104`, immediately before `StoreLootItem`. Void, no item, no slot. Cannot reject one award. |
| `PlayerScript::OnPlayerCanSendErrorAlreadyLooted` | `bool OnPlayerCanSendErrorAlreadyLooted(Player* player)` | `PlayerScript.h:809`, `Player.cpp:13872`. Reached only when the slot is already empty. It chooses whether to send an error. It does not stop a live item. |
| `PlayerScript::OnPlayerLootItem` | `void OnPlayerLootItem(Player* player, Item* item, uint32 count, ObjectGuid lootguid)` | `PlayerScript.h:458`, `Player.cpp:13954`. The personal view and, for a one-copy line, `item->is_looted` are already set. |
| `PlayerScript::OnPlayerStoreNewItem` | `void OnPlayerStoreNewItem(Player* player, Item* item, uint32 count)` | `PlayerScript.h:464`, `PlayerStorage.cpp:2685`. The item is already in the inventory. |
| `PlayerScript::OnPlayerBeforeStoreOrEquipNewItem` | `void OnPlayerBeforeStoreOrEquipNewItem(Player* player, uint32 vendorslot, uint32& item, uint8 count, uint8 bag, uint8 slot, ItemTemplate const* pProto, Creature* pVendor, VendorItem const* crItem, bool bStore)` | `PlayerScript.h:494`, `Player.cpp:10863` inside `Player::_StoreOrEquipNewItem`. Vendor purchase, not corpse loot. |
| `PlayerScript::OnPlayerGroupRollRewardItem` | `void OnPlayerGroupRollRewardItem(Player* player, Item* item, uint32 count, RollVote voteType, Roll* roll)` | `PlayerScript.h:476`, `Group.cpp:1664`, after `StoreNewItem`. |
| `LootScript::OnLootMoney` | `void OnLootMoney(Player* player, uint32 gold)` | `LootScript.h:44`. Money only. |

`OnPlayerBeforeLootMoney(Player*, Loot*)` (`PlayerScript.h:308`, `LootHandler.cpp:199`) is the same kind of gap for coins. It is not an item award hook.

## What this proof refuses to do

- Mutate the shared `LootItem` (`freeforall`, `is_looted`, `needs_quest`, counts, or allowed looters) in `OnPlayerBeforeFillQuestLootItem` or `OnAfterLootTemplateProcess`.
- Return false from `CanPacketSend` for `SMSG_LOOT_RESPONSE`.
- Add a second packet script, a player script, or a global loot check to `src/`.
- Treat `FREE_FOR_ALL` loot method as `ITEM_FLAG_MULTI_DROP`.
- Treat a personal MULTI_DROP store as the friend consuming the owner's only copy.
- Choose personal copies, a named owner, or a different turn rule. Those remain owner decisions recorded on #109 and #111.

## Evidence labels for this branch

| Claim | Label |
| --- | --- |
| File:line citations in this note, read at Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd` | VERIFIED |
| Module blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f` unchanged on this branch | VERIFIED |
| Synthetic four-stage model and hook matrix | VERIFIED as a model of those lines, by the Python tests on this branch |
| Owner's reported corpse, exact item, and whether a copy moved | UNKNOWN |
| In-game manual click, client autoloot, sparkle, and inventory | NOT TESTED |
| Linked worldserver, Playerbots, Individual Progression | NOT TESTED |
| A module-only hook that rejects one wrong human inside `StoreLootItem` without hiding valid loot | VERIFIED absent on this pin, by the matrix |

The Python tests re-read the module and this note. They do not re-clone Grimfeather. Re-reading the cited lines is the source check for a reviewer.
