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
6. The current owner is online, in the same group, **has an unlooted player-specific quest-item slot for the same underlying corpse item**, and still needs/is eligible for it. If the owner was outside reward range, lacks a mapped slot, has already taken their copy, no longer needs the item, or fails native eligibility, defer to the core's existing fallback.

All other cases return TRUE and let AzerothCore process the packet unmodified. Importantly, the original owner releasing the corpse clears `roundRobinPlayer` in `LootHandler.cpp::DoLootRelease`, so a later pickup is automatically no longer blocked. No new permanent lock/cached ownership.

**Deliberate narrow scope:** Creature drops marked as `needs_quest` and `count == 1`. Ordinary non-quest loot items used for collection objectives, stacks, gameobject loot, quest-triggered loot rolls, unknown/invalid slots and alternate direct calls to `StoreLootItem` are not modified. Do not widen this until further investigation/test coverage supports it. No attempt to hide or lock icons in the loot window.

## Configuration (both OFF by default)

```ini
NaxxramasCore.QuestLootProtection.Enabled = 0
NaxxramasCore.QuestLootProtection.Debug = 0
```

`Enabled=0` preserves original behaviour. `Debug=1` logs denied player GUID, creature entry/GUID, item ID, client slot, owner GUID and reason under the existing `module` logging category. A Worldserver restart to load configuration changes is acceptable. **Do not enable on the live realm until approved and manually tested**.

Rollback: set `Enabled = 0` in the active config and restart the Worldserver (after appropriate backups and change approval). Removal in source: revert the standalone `QuestLootProtection.cpp` file, its loader registration, and these two config lines in a dedicated later PR; no migrations or cleanup are required.

## Controlled S5/S6 operator acceptance matrix (NOT YET RUN)

This is a proposed checklist for a separately approved staging build only. No tests in this table have been performed on the owner's realm. The default-OFF configuration must be proven inactive before enabling any scenario. Record exact Naxxramas / AzerothCore / IP / Playerbots SHAs, world/characters DB snapshots, backup restore rehearsal, actual eligible quest item ID, and the loot observation for each case. Never infer live success from synthetic tests.

| ID | Scenario (one corpse unless stated) | Expected behavior with guard ON |
| --- | --- | --- |
| QL-01 | Two eligible group members need the same single-copy creature quest item; non-owner tries first | Non-owner denied; item not consumed or duplicated; owner still able to collect |
| QL-02 | Actual round-robin owner collects their quest item | Normal native pickup succeeds |
| QL-03 | Owner releases loot turn; eligible second member tries | Native fallback allowed; no permanent new lock |
| QL-04 | Owner offline/leaves party or lacks eligible personal quest slot | No new guard denial; check native behavior |
| QL-05 | Viewer has multiple quest slots; client slot maps to a different underlying quest item | Uses viewer-index mapping, never raw slot as global index |
| QL-06 | Owner mapping refers to different quest item or matching owner view already looted | No stale-owner denial |
| QL-07 | Owner completed quest or fails native item eligibility | Guard defers to core, cannot strand quest loot |
| QL-08 | Normal slot, unrelated opcode, empty or padded autostore packet | Unrelated/empty use native handling; padding may not bypass active protection |
| QL-09 | FREE_FOR_ALL and MASTER_LOOT group modes | Native ownership behavior |
| QL-10 | GROUP_LOOT, ROUND_ROBIN, NEED_BEFORE_GREED with eligible owner | Narrow guard, no legitimate roll suppression |
| QL-11 | ITEM_FLAG_MULTI_DROP, shared or follow_loot_rules items | Not intercepted |
| QL-12 | Blocked/rolled quest item with winner, or multiple-count quest item | Native loot/roll handling remains authoritative |
| QL-13 | Gameobject loot, non-creature corpse, distant/not-reward-group corpse | No new guard denial |
| QL-14 | Playerbots normal LootAction packet queue versus headless/direct store paths | Trace which paths hit CanPacketReceive; do not claim universal direct-storage coverage |
| QL-15 | Guard OFF baseline, relog, corpse expiry, complete inventory before/after | OFF mirrors native; no orphaned/unlootable corpse, inventory mutation or crash |

**Capture and abort rules:** Verify the owner has authorized the exact candidate and that known-good Worldserver binary/config plus **complete characters database** backups are independently proven **restorable**. Keep personal/account IDs and server credentials private. Abort on duplication/loss, stranded legitimate loot, skipped hook paths, unexpected Playerbot behavior or crash. Disable the feature through approved restart/restore; never delete items manually to improvise rollback. Record each row as PASS / FAIL / NOT RUN with evidence before checking S6. This matrix is not permission to install or enable anything.

**Important source limitation:** A packet guard only protects paths entering the native CMSG_AUTOSTORE_LOOT_ITEM handler through CanPacketReceive. A direct caller of Player::StoreLootItem bypasses it. Random Bots, Altbots and headless Playerbots must be independently checked where applicable; do not assume every route is covered.

## Validation checklist (required before merge/production use)

- Automated source/synthetic regression checks: correct slot translation, malformed/invalid player slot, padded packet cannot bypass the guard, native methods untouched, shared items and roll winners excluded, released owner, missing owner quest slot, owner no longer eligible, guarded group methods, config off. All use mocks/models, not the actual loot manager.
- Pinned source compile/link: this branch must compile and link against the **exact Grimfeather core SHA** and pinned Playerbots / Individual Progression stack on an isolated GitHub runner; this is not gameplay proof.
- **Unperformed gameplay tests**: two real group members need the same single-copy quest item, verify non-owner first pickup denied, owner collects, owner no longer needs item, owner releases then other player collects; FFA/shared/multi-drop and special `follow_loot_rules`; rolls, Master Loot, Round Robin, Need Before Greed, corpse lifetime/disconnect; 3.3.5a visual state and bot packet processing. Check no duplicated/deleted/vanished loot, no unlootable corpse, and no crash.
- **Bot coverage limitation**: ordinary `LootAction` uses `QueuePacket` on pinned Playerbots, but paths calling `StoreLootItem` or other direct inventory APIs bypass `CanPacketReceive`. Don't assert that **all** bot pickup mechanisms are protected.
- Check against the actual installed module list for conflicting packet hooks. This feature registers only one server packet hook and does not edit existing class/talent/progression handlers.

**If the source build fails or legitimate gameplay is adversely affected, leave the feature disabled and the PR draft.** A universal solution that covers arbitrary direct `Player::StoreLootItem` calls would require a cancellable pre-store core hook or direct validation in the core's `Player::StoreLootItem`; neither can be added under the owner's non-negotiable module-only policy. No upstream edits are proposed or authorized.
