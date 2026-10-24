# A04 — Source-backed ordinary quest-loot path divergence (S1; stock-parity investigation)

**Status:** review-only technical investigation as CS01 covers Claude's break. Not a source fix, not a runtime reproduction, not a request to change normal loot allocation. **Owner requirement:** preserve stock WoW/AzerothCore group-loot behavior and fix *only an actual incorrect quest-item visibility/access/award path*. The user has observed a human friend actually collecting unexpected quest-related drops. What exact item/quest/source, loot bucket and eligibility applied is still **not established**. This note does not claim the observed case is explained by the code paths below.

**Inspected exact pins:** module `main` `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` `src/Systems/QuestLootProtection.cpp`; Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`:

- `src/server/game/Loot/LootMgr.cpp` around `LootItem::AllowedForPlayer` (lines 415+), `Loot::AddItem` (around 477–530), `Loot::FillLoot` (540–600), `Loot::FillQuestLoot` (650–700), `Loot::LootItemInSlot` (840–910), `LootView::operator<<` (990–1220).
- `src/server/game/Entities/Player/Player.cpp` `Player::StoreLootItem` (13860–13960).
- `src/server/game/Entities/Player/PlayerStorage.cpp` `Player::isAllowedToLoot` (5750–5810).
- `src/server/game/Handlers/LootHandler.cpp` `WorldSession::HandleAutostoreLootItemOpcode` (near 25–130).

## 1. What is explicitly protected by stock AzerothCore

1. **Eligibility before grant.** `Player::StoreLootItem` resolves the requested slot via `Loot::LootItemInSlot`, then explicitly tests `item->AllowedForPlayer(this, loot->sourceWorldObjectGUID)` *before* `CanStoreNewItem` / `StoreNewItem`. An `AllowedForPlayer=false` result releases the window and returns without the item being added. A visible line alone does not bypass this check.
2. **Quest-only bucket.** In `Loot::AddItem`, `needs_quest` routes generated items to `quest_items`; otherwise they are normal `items`. `Loot::FillQuestLoot` constructs a player's quest-slot list using `AllowedForPlayer`. `LootItem::AllowedForPlayer` rejects a `needs_quest` item when `!player->HasQuestForItem(itemid)`, **except** when the item's `ITEM_FLAGS_CU_IGNORE_QUEST_STATUS` custom flag explicitly skips quest-status restrictions. It also checks conditions, disable list, faction, recipes and `OnAllowedForPlayerLootCheck`. The existence/value of this custom flag for the owner's affected item has not been inspected.
3. **Personal flags.** `ITEM_FLAG_MULTI_DROP` sets `LootItem::freeforall`, with viewer-specific accounting. Do not treat another eligible player's copy as an unauthorised award. Do not confuse the `FREE_FOR_ALL` **group loot method** with this item-template flag.
4. **Normal item that is also a quest objective.** If the source's loot template says `QuestRequired=0`, it enters regular `loot.items`, and `AllowedForPlayer` does not apply the `needs_quest` test. Such an item can be valid shared loot under stock rules even if a party member needs it for a quest. **Do not convert it to personal loot merely because it is quest-related.**

## 2. Exact path divergence worth a safe follow-up

**Fact A — visibility:** `LootView::operator<<` for `ROUND_ROBIN_PERMISSION` hides an ordinary, non-FFA, condition-free `loot.items` row from a player if `loot.roundRobinPlayer` is set to someone else's GUID; the grouped/restricted path also decides when a normal row is displayed or marked locked according to threshold, blocks and the current looter. `Player::isAllowedToLoot` additionally considers group/round-robin but permits openings that have player-specific quest/FFA items.

**Fact B — item-award guard:** `Player::StoreLootItem` checks current item eligibility, `is_blocked`, roll winner, and a particular **MASTER_LOOT** ownership case. It does **not** generally repeat the same `roundRobinPlayer` vs clicking GUID check that the normal `LootView` display path uses for ordinary under-threshold rows. The handler forwards `CMSG_AUTOSTORE_LOOT_ITEM` to `StoreLootItem` once source/range are resolved.

**Fact C — module gap:** `QuestLootProtection::PermitPickup` currently returns `true` immediately when `requestedSlot < loot.items.size()`. Therefore it does not close a potential discrepancy between a client-visible normal-item slot and native award eligibility. Its narrow quest-slot owner-turn denial does not address this regular bucket.

**Bounded conclusion:** The pinned source permits a **possible** normal-item *hidden-slot request versus store-time turn check* divergence. This is a **candidate security/integrity seam**, not proof that a stock client sent a hidden-slot packet, that an ordinary item counted as the user's personal quest-only drop, or that this caused the observed friend pickup. Group rounds/rolls and the item's real template classification still matter. A server-only guard for a hidden normal row could alter stock behavior unless tested against the exact native permission cases; do **not** implement a universal “no one else may collect my quest item” rule.

## 3. Explicit unresolved scenarios and safe falsifiers

| Scene | Source prediction at pinned core | Evidence needed to identify the real cause |
| --- | --- | --- |
| Human friend lacks quest, `QuestRequired=1`, no custom ignore flag | `AllowedForPlayer=false`, so native `StoreLootItem` must reject inventory award | An actual award here would falsify the assumed item row/flags, show a bypass/alternate path, or require more source/runtime tracing |
| Friend needs same quest, real shared one-copy quest item | Valid under stock rules when its slot is available; friend taking it is not inherently a bug | Real holder and item allocation method; don't force personal copies or a designated owner |
| `QuestRequired=0` ordinary item needed by quest | Stock ordinary-item eligibility and loot turn apply, not `needs_quest` exclusivity | Item ID, exact creature/GO loot-template record, group method, holder, slot type |
| `ITEM_FLAG_MULTI_DROP` | Independent personal item rights are possible | Item template flags and whether the same shared copy actually diminished |
| Round-robin normal row hidden from the friend, but autostore request occurs anyway | Display and award paths do not have the same explicit holder check | Controlled packet/slot trace on an owner-backed-up staging clone; do not infer from a client sparkle alone |
| Chest/GO or skinning/pickpocket source | Module's creature-corpse-specific guard returns early; stock source checks still apply | Actual source GUID type and loot kind; never claim this is protected by current module |
| Master/roll winner | Separate award and recipient paths, not identical to human autostore | The group's actual loot mode and final server award path |

## 4. Next safe work (no owner action now)

1. Continue pinpointing all *module and native* hook subscribers on `OnPlayerBeforeFillQuestLootItem`, `OnAllowedForPlayerLootCheck`, and `OnPlayerLootItem` that could affect quest eligibility or award handling at owner pins. Avoid asserting the source module is the only subscriber without an exhaustive code search.
2. Build an exact-native **visibility-vs-award decision matrix** for `GROUP_LOOT`, `ROUND_ROBIN`, `NEED_BEFORE_GREED` and `MASTER_LOOT` before considering any C++ denial; normal legitimate shared one-copy drops must continue working.
3. Identify the affected item/quest/source and loaded flags **read-only when evidence is already available or owner separately authorises access**. Never upload private world SQL or character identifiers to GitHub. It is not necessary to ask the owner to change the server or consume quest items right now.
4. Only if a concrete *invalid* pickup is established: propose the smallest default-OFF, module-owned patch with native negatives for hidden slots, valid turn holders, quest-only/per-player views, `MULTI_DROP`, released turns, chest/GO, out-of-range, group/roll/master methods, bots and map-thread concurrency. Verify full pinned Worldserver link, separate Grok peer review and owner-backed-up staged play.

**No change or reproduction claimed:** this note and the source facts do not fix the user's game, authorise game testing, alter group rights, or choose a new loot economy. The first combined test build still requires actual A04 + A02 + F12 normal Scarlet portals + F13 Atiesh, as well as #120 P0+B10.
