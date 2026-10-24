# A04 S1 — Per-viewer FFA slot and Playerbots packet evidence

**Status:** Research-only, pinned source review; not a code fix, not in-game reproduction, not confirmation of the human friend's reported incorrect quest pickup. **Owner contract:** retain normal WoW group-loot rules, ordinary one-copy shared drops, valid per-player multi-drop semantics, drop rates and native quest eligibility. Keep protected branches, owner's database, DBC, AzerothCore, Individual Progression, Playerbots and live server unchanged.

## Verified source pins and observations

AzerothCore **Grimfeather/azerothcore-wotlk `8daffdabe9202c228e45d833c9a1d399597a15cd`**, `src/server/game/Loot/LootMgr.cpp`:

1. **Template classification is decisive.** `LootItem::LootItem` initializes `freeforall = proto && proto->HasFlag(ITEM_FLAG_MULTI_DROP)` and `needs_quest = li.needs_quest`; `Loot::AddItem` chooses `quest_items` when `needs_quest`, and ordinary `items` otherwise. These flags are independent. `AllowedForPlayer` applies `HasQuestForItem(itemid)` only for `needs_quest`, unless `ITEM_FLAGS_CU_IGNORE_QUEST_STATUS` overrides. A `QuestRequired=0` ordinary item remains regular shared loot unless native conditions/restrictions apply.
2. **Personal FFA map preparation.** `Loot::FillFFALoot(Player*)` adds an ordinary `freeforall` item to `PlayerFFAItems[playerGuid]` only if `!item.is_looted` and `item.AllowedForPlayer(player, containerGUID)`. It increments `unlootedCount` per entry. `LootView` presents rows of `PlayerFFAItems` in a separate viewer-specific loop.
3. **Unexpected absence behavior worth separately investigating.** For `lootSlot < items.size()`, `Loot::LootItemInSlot` starts `item = &items[lootSlot]; is_looted = item->is_looted`. When `item->freeforall`, it looks for the requesting viewer's `PlayerFFAItems` entry. If the map entry **or the matching index is absent**, it does not obviously return `nullptr` or force `is_looted=true`: its baseline `item->is_looted` remains. Thus a *request for a slot the viewer's FFA view would not list* is a **possible** source-level visibility/slot-resolution discrepancy if all other native award checks pass. If a matching per-player entry exists but is marked looted, it returns `nullptr`.
4. **Final item award still has checks.** `Player::StoreLootItem` subsequently verifies `AllowedForPlayer`, item blocked state and winner before `StoreNewItem`. A `needs_quest=1` item with no quest need and no ignore-status flag remains rejected. This candidate is not evidence of an ordinary stock client actually sending a hidden FFA slot or being awarded an item from the owner's incident.
5. **Separate bucket, separate contract.** The CS01 review-only [#129](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/129) candidate deliberately excludes `item.freeforall` and does **not** fix or validate a personal-FFA membership gap. Never fold it into #129 silently without diagnosis and fresh independent tests; do not make personal copies, rewrite loot generation or change per-player counters.

Pinned public Playerbots **mod-playerbots/mod-playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091`**, `src/Ai/Base/Actions/LootAction.cpp`, `StoreLootAction`:

6. The **standard loot action** allocates `WorldPacket(CMSG_AUTOSTORE_LOOT_ITEM, 1)`, appends `itemindex` and calls `bot->GetSession()->QueuePacket(packet)`; the direct `HandleAutostoreLootItemOpcode(packet)` call is commented out. It also queues `CMSG_LOOT_RELEASE`. This is **evidence of the queued packet route for this action**, not proof every bot/inventory award on all paths uses it, nor that a specific owner bot/client packet traversed the module's `ServerScript::CanPacketReceive` hook. The owner's published Playerbots `e88cc409...` and two local edits are **not available to this synthetic research**.

## Stock-parity diagnostic categories (not redesign choices)

| Evidence at exact item/source | Native expectation | What a violation would mean |
| --- | --- | --- |
| `needs_quest=1`, viewer lacks quest, no ignore flag | `AllowedForPlayer` false before grant | If actual award happened, inspect item row/flags/alternate grant before changing stock loot |
| `needs_quest=0`, one shared ordinary item, legitimate holder | Regular group-loot rights; one copy remains shared | A friend receiving it can be stock behavior, not inherently an exploit |
| `ITEM_FLAG_MULTI_DROP`, viewer has FFA entry and has not looted | Personal copy is permitted | Friend taking their own copy should not consume another person's right |
| `ITEM_FLAG_MULTI_DROP`, viewer has no FFA entry but requests ordinary slot index | `LootView` does not list it for viewer; `LootItemInSlot` apparently does not enforce map membership by itself | Potential hidden-slot request gap requiring exact native/runtime proof before a fix |
| FFA entry already personally marked looted | `LootItemInSlot` returns nullptr | Repeated personal pickup should not award |
| `MASTER_LOOT`, rolls, conditions, GO, chest, currency, alternative award caller | Have different native routing | Do not assume a creature corpse packet guard covers them all |

**Limitations:** No owner item ID, quest ID, creature/GO GUID or row, `QuestRequired`, `ITEM_FLAG_MULTI_DROP` value, custom ignore flag, group-loot mode or turn holder has been established. No private SQL files were available in this specific conversation runtime. The code facts are *public pinned source*; whether this is the observed bug is **unknown**. No normal UI exploit demonstration, live packet capture, triggered inventory grant or deployed code is claimed.

## Safe follow-up acceptance gates

1. Cross-check the owner's actual source/item row **read-only** when the evidence is accessible, with no upload of private tables/character identifiers to GitHub. Preserve normal loot when two eligible players share a one-copy ordinary drop.
2. If an owner instance consistently lets a *noneligible* human receive a `needs_quest=1` drop despite stock `AllowedForPlayer`, investigate alternate award path or modified item flags; this FFA candidate is not an automatic explanation.
3. If an actual `freeforall` viewer-missing request is reproducible through the real stock client or queued bot path, propose a new **independently default-OFF**, minimal **packet membership guard**, and test genuine eligible FFA grants/repeats/retired players/currency/loot counter semantics. Do not change core/private data or implement it speculatively.
4. Require exact-head native regressions, pinned full Worldserver link, CS02 peer review, owner backup/permission and two-human staged inventory checks before declaring A04 complete or combining in the first test build.

The first test build still requires **functional** A04 human-human invalid loot access, A02 human Hunter pet autocast, F12 physical Scarlet Cathedral/Armory in/out, F13 Atiesh outdoor arrival and already verified #120 P0+B10. Research and synthetic cases alone do not meet that gate.
