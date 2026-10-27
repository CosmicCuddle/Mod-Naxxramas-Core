# A04 Part29 — Corpse sparkle vs viewer quest-slot visibility vs native award

**Status: PUBLIC pinned-source research + synthetic controls only. DRAFT, NOT A FIX.** Independent CS01 child stacked on untouched [#153](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/153) `eab1da443b84b34ed41e8582ca10a91a1d50b8d8`. All original stock loot policies and previously staged A04 candidate flags remain unchanged and default OFF. No owner data, SQL/DB, module runtime, configuration, installed Playerbots/IP or Worldserver access.

## Specific new causal distinction for H2

At the immutable **public** Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`:

1. `Player::isAllowedToLoot` in `PlayerStorage.cpp:5746–5797` checks corpse and reward status and uses `Loot::hasItemFor(this)` when a non-turn-owner may access Free-for-All/conditional/personal quest items. The same check participates in whether the client receives a **lootable corpse indicator**. It does **not** assert an individual quest item's current final eligibility.
2. `Loot::hasItemFor` in `LootMgr.cpp:906–949` consults the **already assembled** viewer-specific `PlayerQuestItems` entries and their `is_looted` flags without freshly calling `Player::HasQuestForItem` or rechecking inventory. This is a cached-row existence test, not a proof that the row will be lootable when the window is serialized.
3. `LootView::operator<<` in `LootMgr.cpp:1099–1164` independently calls `HasQuestForItem(itemid, 0, false, &showInLoot)` per viewer. An existing cached quest row for which the objective no longer needs that item can be sent as **`LOOT_SLOT_TYPE_LOCKED`** while the corpse-level check just found a cached row. This can explain a *possible* sparkle followed by an uncollectable displayed row without establishing any invalid server refusal or module involvement.
4. In `PlayerQuest.cpp:2338–2387` the **quest objective counter** (`q_status.ItemCount`) and **inventory count** (`GetItemCount(itemid, true)`) have different roles. If the stored objective counter is still short but the inventory already holds enough, `HasQuestForItem(...,&showInLoot)` can set `showInLoot=false`. Then `LootView` sets the **viewer-specific** `QuestItem::is_looted` flag, and if `!item.freeforall` also sets the **shared** underlying `LootItem::is_looted` flag. This is a source-backed side effect *during loot-window serialization* worth future scrutiny, not proof of actual player loss or a valid fix. It does not say the owner’s reported friend had mismatched counter/inventory.
5. `Player::StoreLootItem` in `Player.cpp:13861–13962` re-resolves packet `uint8` slot via the **viewer-specific** quest list and does fresh `AllowedForPlayer`, blocked/roll-owner, and bag-space checks. The `qitem` branch has distinct blocked semantics; `LootHandler.cpp:33–120` has different source checks and error paths. A lootable sparkle, a LOCKED slot, a native RELEASE, `EQUIP_ERR_ALREADY_LOOTED`, inventory failure, or actual `StoreNewItem`/`OnPlayerLootItem` are **different events**. The screenshot alone cannot identify which occurred.

## Synthetic H2 witness matrix (held-favorable corpse/group state only)

| Previously cached unlooted quest slot | Current objective still short | Inventory still short | FFA | Source-shaped window result |
| --- | --- | --- | --- | --- |
| Yes | Yes | Yes | Either | Quest item displayed as allowed (subject to other permission/roll gates) |
| Yes | No | Either | Either | LOCKED row may be displayed; initial quest-slot sparkle contribution can remain |
| Yes | Yes | No | No | HIDDEN row; local and shared `is_looted` may be set by window serialization |
| Yes | Yes | No | Yes | HIDDEN row; only local row `is_looted` set by this branch |
| No (or already looted) | Either | Either | Either | No quest-slot-specific contribution to corpse sparkle |

These are **reference-state reductions**, not a server emulator. They hold eligible corpse/range/party/method and ignore conditional, rolling and custom script changes. They must not be used as a live failure diagnosis or a reason to enable the legacy guard.

## Keep H1 entirely separate

**H1 (friend apparently obtaining the other human's quest loot)** is an *award* report, not an indicator problem. The key source decision is whether the award was a legitimate one-copy group turn, a still-needed viewer-specific `quest_items` slot, an ordinary `items` slot, roll/mail result, or an actual entitlement bypass. Stock `LootItem::AllowedForPlayer` checks `needs_quest` via `HasQuestForItem` unless custom ignore-quest-status rules apply, and `StoreLootItem` rechecks this at pickup; the existing model [#153](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/153) enumerates legitimate and negative paths. Do NOT make quest loot automatically personal or block legitimate group turns.

**Evidence required privately, with separate owner approval before observing installed systems:** for H1 and H2 separately record active installed Worldserver/module core versions and effective A04 switches, loot source kind, native group method/turn and corpse release, both players' objective counters and quest stages, whether the friend was independently eligible, visible slot type/error, and **actual** item delivery to bag/mail. Public docs intentionally omit server item IDs, NPC IDs, quest entries, SQL rows, character identifiers, logs and host information. No assumption actual installed core equals public pin.

## Regression intent and proof limits

New `tests/research/test_cs01_a04_sparkle_slot_contract.py` contains **seven source-anchored tests** and **six disposable synthetic witnesses**. It checks the cached corpse-level quest entry, viewer quest row allocation, independent objective/inventory recheck, LOCKED/HIDDEN serialization branches, the shared `is_looted` side effect, and separate actual award gates. It uses exactly the seven public core source files already checked out by #153's fingerprint CI. Its workflow runs the inherited 33 tests and exact core fingerprint unchanged, then these new tests; no runtime files or definitions are modified. All A04 flags remain OFF.

**OPEN:** owner H1/H2 facts and runtime reproduction, possible consequences of the inventory/counter mismatch in the owner-custom build, review of concurrent map/logout and any external hook changes, actual eligibility source for all owner loot. No fix proposed, no owner gameplay acceptance.