# Temporary Quest Loot Protection — module-only prototype

**Status: Draft, disabled by default, NOT installed or gameplay tested.** Applies only to CosmicCuddle/Mod-Naxxramas-Core. No changes to AzerothCore, Playerbots or database. The owner must review before any merge or deployment.

## Pinned source and confirmed problem

Source reviewed: `Grimfeather/azerothcore-wotlk@a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7`; `mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c`.

- `LootMgr.cpp::operator<<(ByteBuffer&, LootView const&)` applies `roundRobinPlayer` to normal loot items but displays eligible `quest_items` through `PlayerQuestItems` without an equivalent owner test. Some single-copy quest items are advertised with `LOOT_SLOT_TYPE_ALLOW_LOOT`.
- `Player.cpp::Player::StoreLootItem` resolves a viewer quest slot via `Loot::LootItemInSlot`, checks eligibility, rolls and certain Master Loot restrictions, but does **not** check round-robin ownership for those eligible quest items. For a matching creature corpse, the normal `LootHandler.cpp::HandleAutostoreLootItemOpcode` reaches `StoreLootItem`. This is the demonstrated packet-path gap.
- `WorldSession.cpp::Update` calls `ServerScript::CanPacketReceive` **before** the registered opcode handler during session update, so the hook can reject a valid-looking unauthorized packet before `StoreNewItem` / loot state changes.
- Pinned Playerbots `src/Ai/Base/Actions/LootAction.cpp` queues `CMSG_AUTOSTORE_LOOT_ITEM` via its bot session rather than calling the handler directly on its ordinary path. This suggests the same hook covers ordinary bot loot packets, but **full Playerbots coverage, headless sessions and alternate actions remain unverified in-game**.

## Implementation

New `src/Systems/QuestLootProtection.cpp` registers `ServerScript::CanPacketReceive`. Only `CMSG_AUTOSTORE_LOOT_ITEM` packets containing at least the first loot-slot byte are considered. A copied packet is read with an independent cursor, so the native handler receives its original data untouched. **Do not require exactly one byte:** the pinned core handler reads only the first `uint8` slot and logs, rather than rejects, trailing bytes. Padding a pickup packet must not bypass ownership protection. Empty or unrelated packets remain subject to native validation.

The decision is **read-only** and computed from the active creature corpse, current group, loot round-robin owner and the **viewer-specific** `PlayerQuestItems` mapping. No cached owner, no shared loot mutation, no SQL and no changes to the client loot-window serialization. Denials occur before item storage; the player gets `LOOT_ERROR_LOCKED` and optional debug logging.

To deny, ALL must be true:

1. The feature is enabled, a grouped player has a valid creature-corpse loot source, is in interaction range, and belongs to that creature's current loot recipient group.
2. Group method is `GROUP_LOOT`, `ROUND_ROBIN`, or `NEED_BEFORE_GREED`. Master Loot and Free For All are unchanged.
3. `roundRobinPlayer` is nonempty and not the requesting player.
4. The packet slot is a **player-visible quest slot** (not a normal loot slot), and its per-player mapping and underlying `quest_items` index are valid and not yet looted.
5. Item is one-copy `needs_quest` loot with `count == 1`, not `freeforall`/`ITEM_FLAG_MULTI_DROP`, not `follow_loot_rules`, and not a blocked/roll-winner item.
6. The current owner is online, in the same group, and still eligible for the quest item. If the owner no longer needs it or cannot receive it under native eligibility checks, defer to the core's existing fallback.

All other cases return TRUE and let AzerothCore process the packet unmodified. Importantly, the original owner releasing the corpse clears `roundRobinPlayer` in `LootHandler.cpp::DoLootRelease`, so a later pickup is automatically no longer blocked. No new permanent lock/cached ownership.

**Deliberate narrow scope:** Creature drops marked as `needs_quest` and `count == 1`. Ordinary non-quest loot items used for collection objectives, stacks, gameobject loot, quest-triggered loot rolls, unknown/invalid slots and alternate direct calls to `StoreLootItem` are not modified. Do not widen this until further investigation/test coverage supports it. No attempt to hide or lock icons in the loot window.

## Configuration (both OFF by default)

```ini
NaxxramasCore.QuestLootProtection.Enabled = 0
NaxxramasCore.QuestLootProtection.Debug = 0
```

`Enabled=0` preserves original behaviour. `Debug=1` logs denied player GUID, creature entry/GUID, item ID, client slot, owner GUID and reason under the existing `module` logging category. A Worldserver restart to load configuration changes is acceptable. **Do not enable on the live realm until approved and manually tested**.

Rollback: set `Enabled = 0` in the active config and restart the Worldserver (after appropriate backups and change approval). Removal in source: revert the standalone `QuestLootProtection.cpp` file, its loader registration, and these two config lines in a dedicated later PR; no migrations or cleanup are required.

## Validation checklist (required before merge/production use)

- Automated source/synthetic regression checks: correct slot translation, malformed/invalid player slot, native methods untouched, shared items and roll winners excluded, released owner, owner no longer eligible, guarded group methods, config off. All use mocks/models, not the actual loot manager.
- Pinned source compile/link: this branch must compile and link against the **exact Grimfeather core SHA** and pinned Playerbots / Individual Progression stack on an isolated GitHub runner; this is not gameplay proof.
- **Unperformed gameplay tests**: two real group members need the same single-copy quest item, verify non-owner first pickup denied, owner collects, owner no longer needs item, owner releases then other player collects; FFA/shared/multi-drop and special `follow_loot_rules`; rolls, Master Loot, Round Robin, Need Before Greed, corpse lifetime/disconnect; 3.3.5a visual state and bot packet processing. Check no duplicated/deleted/vanished loot, no unlootable corpse, and no crash.
- **Bot coverage limitation**: ordinary `LootAction` uses `QueuePacket` on pinned Playerbots, but paths calling `StoreLootItem` or other direct inventory APIs bypass `CanPacketReceive`. Don't assert that **all** bot pickup mechanisms are protected.
- Check against the actual installed module list for conflicting packet hooks. This feature registers only one server packet hook and does not edit existing class/talent/progression handlers.

**If the source build fails or legitimate gameplay is adversely affected, leave the feature disabled and the PR draft.** A universal solution that covers arbitrary direct `Player::StoreLootItem` calls would require a cancellable pre-store core hook or direct validation in the core's `Player::StoreLootItem`; neither can be added under the owner's non-negotiable module-only policy. No upstream edits are proposed or authorized.
