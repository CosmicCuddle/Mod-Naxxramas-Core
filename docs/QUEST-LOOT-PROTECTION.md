# Temporary Quest Loot Protection — module-only prototype

**Status: Draft, disabled by default, NOT installed or gameplay tested.** Applies only to CosmicCuddle/Mod-Naxxramas-Core. No changes to AzerothCore, Playerbots or database. The owner must review before any merge or deployment.

## Reconciliation onto current main (22 Oct 2026)

`scripts/check_quest_loot_pinned_compile.py` is copied unchanged from draft PR #25 head `e3e1bf339c8b1aba07ab065d50dbcc3fafbf0e51`. `src/Systems/QuestLootProtection.cpp` started from that head. It now permits the pickup unless the round-robin owner is found, `IsInWorld()`, and on the same live map and the same instance as the looter and corpse. The branch base is `main` `75315783e4921b47809d96094f4885f68ff42146`. `conf/mod_naxxramas_core.conf.dist` and `src/NaxxramasCore_loader.cpp` were hand-merged: every `NaxxramasCore.HallowsEnd.SoloFire.*` line and `AddHallowsEndShadeOfTheHorsemanScripts()` stays, and the quest-loot keys are appended default OFF. Rollback remains `NaxxramasCore.QuestLootProtection.Enabled = 0` plus a Worldserver restart after separate approval. No SQL.

This branch's workflow pins Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`, Playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c`, and Grimfeather individual progression `4ff4b5fcc1480348f058c632573143e62d4e3a41`. It checks out the pull-request head SHA and does not upload artifacts.

On 22 Oct 2026 the following Grimfeather blobs were downloaded from both `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd` and had identical SHA-256 values. That is file-byte identity for these paths only. It is not a claim that the whole core trees match, and it is not an in-game test.

| Path | SHA-256 (both pins) |
| --- | --- |
| `src/server/game/Loot/LootMgr.h` | `11a35fe85d0c030f58d1f6cb0f1f36ed7e9dcb207c5273e26f886fb5ae240346` |
| `src/server/game/Loot/LootMgr.cpp` | `6e221adb8ee6aef550e5e2f6b621556fead90faf1dc79a31522bb1841521b5ad` |
| `src/server/game/Handlers/LootHandler.cpp` | `ef9a84ced9f70c963877000ec96a16ae31e7912179f3100524723f0e64edb155` |
| `src/server/game/Entities/Player/Player.cpp` | `b22b8df54e6d11cfd43a49834b240ac1a237a6f88da070ca4f243e2b9770803a` |
| `src/server/game/Server/WorldSession.cpp` | `27c8d7f80bd36f72902b8074e728dfa4524de60a96dece27cec8adfe519b188e` |
| `src/server/game/Scripting/ScriptDefines/ServerScript.h` | `80b234fe3ecf93d3f0e6ff0fddb9b57ea41e42283784e6b27ed4f57f31a46d67` |
| `src/server/game/Entities/Item/ItemTemplate.h` | `b4c0e0da5df1a90ba3cf31e3962f6b183010d6688ec3cae78a550c9d21a363f4` |
| `src/server/game/Groups/Group.h` | `4b01c1d35176ce89bee4bc884b7aa0367bbaf4d57aeba94faebdc82970f4f379` |
| `src/server/game/Server/Protocol/Opcodes.h` | `9109ea4d2abd098883acd1e6b552104adf8965544478439811c75426315aa447` |
| `src/server/game/Scripting/ScriptMgr.h` | `cd6f58b7be1b5c02da0d437fad6e17e2d40b3c5edffef7451d059cbf653c72f0` |

Static read of those identical bytes, not a runtime test: `WorldSession.cpp` calls `CanPacketReceive` and then `opHandle->Call` at lines 461-464 (and the same order at 479-482, 489-492, and 505-508). `LootHandler.cpp:33-107` reads one `uint8` slot and calls `Player::StoreLootItem`. `Player.cpp:13861-13906` does not apply `roundRobinPlayer` to quest slots (`qitem` bypasses the master-loot threshold check at 13881-13883). `LootHandler.cpp:390-391` and `459-461` clear `roundRobinPlayer` when the releasing player is the current owner. Pinned Playerbots `LootAction.cpp` `StoreLootAction::Execute` at lines 487-490 queues `CMSG_AUTOSTORE_LOOT_ITEM` (blob SHA-256 `9c64c418a19d7c03d86ec5e2695fa3bb19489a30ba6d5d868cabd463b3f19c4d`, pin `037c01418b5d01506917a3db9b44fd56ac5f965c`). The direct handler call on the next line is commented out. That does not prove every Altbot or headless path.

## Pinned source and confirmed problem

Source originally reviewed for the notes below: `Grimfeather/azerothcore-wotlk@a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7`; `mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c`. The loot-path files listed above are the same bytes at `8daffda`.

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
6. The owner is found, `IsInWorld()`, and on the **same live map and the same instance** as the looter and the corpse. Otherwise the guard permits the pickup. Pinned `LootItem::AllowedForPlayer` checks item, conditions, quest status, and scripts. It does not check map, instance, or range. the **map-scoped** `ObjectAccessor::GetPlayer(*player, guid)` (reviewed separately in draft #132) returns only a found owner on the requester's map, while the denial path still checks `IsInWorld()`, live map and instance itself. `GetPlayer` itself reads `IsInWorld()` / `GetMap()` after the global container lock is released; therefore it reduces known cross-map field access but is **not a proof of complete lifetime synchronization** under eight map threads.
7. That owner is in the same group, **has an unlooted player-specific quest-item slot for the same underlying corpse item**, and still needs/is eligible for it. If the owner was outside reward range, lacks a mapped slot, has already taken their copy, no longer needs the item, or fails native eligibility, defer to the core's existing fallback.

Distance and death are not extra denies. An owner who is dead, or who is elsewhere inside the same instance, keeps the round-robin turn. A missing owner, an owner who is not in world, a different map, or the same map in a different instance does not block the other looter.

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
| QL-04 | Owner offline, not found, not in world, on another map, in another instance of the same map, leaves the party, or lacks an eligible personal quest slot | No new guard denial; a present eligible owner still blocks others. Check native behavior |
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

## What the Python tests exercise, and what they do not

`tests/test_quest_loot_protection.py` reads this module's source and runs an in-process decision model. It does not link AzerothCore, open a loot window, or talk to Playerbots.

The assignment check is `roundRobinPlayer` + whitespace + a single `=`. A raw pattern with a doubled backslash matched a literal backslash instead of whitespace, so `roundRobinPlayer = x;` could slip past it. The test now flags an in-memory copy of the source that contains that write, and it does not flag a fixture that only uses `==`.

Explicit limits, kept here so a docs edit cannot drop them silently:

- NOT TESTED: in-game human or Altbot loot
- NOT TESTED: direct Player::StoreLootItem callers
- NOT TESTED: native DoLootRelease and corpse expiry
- NOT TESTED: live database, SQL, or inventory mutation
- NOT TESTED: headless Playerbots sessions
- NOT TESTED: client loot-window icon state
- NOT TESTED: packet bytes on a live session

Synthetic coverage that does exist: default OFF, Hallow's End keys still present, opcode-before-config-before-slot-read order inside this module's hook, padded-size source condition (`size() < 1`, not `size() != 1`), group / round-robin / need-before-greed versus other methods, count 1 and quest eligibility, empty or incorrect owner, release modeled as an empty `roundRobinPlayer`, owner present on the same map and instance still blocks, owner not found / not in world / other map / other instance permits, in-memory mutations that remove those fail-open guards fail the source contract, and no Altbot exemption string in this module. Those are source and model checks only. Distance and death are not extra denies in that model.

## Validation checklist (required before merge/production use)

- Automated source/synthetic regression checks: correct slot translation, malformed/invalid player slot, padded packet cannot bypass the guard, native methods untouched, shared items and roll winners excluded, released owner, missing owner quest slot, owner no longer eligible, guarded group methods, config off. All use mocks/models, not the actual loot manager.
- Pinned source compile/link: `.github/workflows/quest-loot-protection-pinned.yml` must compile and link Worldserver against Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd`, Playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c`, and Grimfeather individual progression `4ff4b5fcc1480348f058c632573143e62d4e3a41`, checking out the exact pull-request head. It must not upload artifacts. This is not gameplay proof.
- **Unperformed gameplay tests**: two real group members need the same single-copy quest item, verify non-owner first pickup denied, owner collects, owner no longer needs item, owner releases then other player collects; FFA/shared/multi-drop and special `follow_loot_rules`; rolls, Master Loot, Round Robin, Need Before Greed, corpse lifetime/disconnect; 3.3.5a visual state and bot packet processing. Check no duplicated/deleted/vanished loot, no unlootable corpse, and no crash.
- **Bot coverage limitation**: ordinary `LootAction` uses `QueuePacket` on pinned Playerbots, but paths calling `StoreLootItem` or other direct inventory APIs bypass `CanPacketReceive`. Don't assert that **all** bot pickup mechanisms are protected.
- Check against the actual installed module list for conflicting packet hooks. This feature registers only one server packet hook and does not edit existing class/talent/progression handlers.

**If the source build fails or legitimate gameplay is adversely affected, leave the feature disabled and the PR draft.** A universal solution that covers arbitrary direct `Player::StoreLootItem` calls would require a cancellable pre-store core hook or direct validation in the core's `Player::StoreLootItem`; neither can be added under the owner's non-negotiable module-only policy. No upstream edits are proposed or authorized.

### Part28 A04 live configuration snapshot (SOURCE-ONLY REVIEW, no activation)

At exact pinned core `8daffdabe9202c228e45d833c9a1d399597a15cd`, `ConfigMgr::GetValueDefault<std::string>` searches `_configOptions` without taking `_configLock`, while config load/reload holds that mutex for mutation. `CMSG_AUTOSTORE_LOOT_ITEM` is `PROCESS_INPLACE` and can run via world/map dispatch. Repeated `GetOption<bool>` inside its module callback therefore unnecessarily relies on external config-reload serialization with eight map threads. We do **not** claim owner runtime has reproduced a race.

This isolated stacked draft makes the quest-loot packet callback and debug logging read a **startup-only immutable `LootConfig` snapshot**. `WORLDHOOK_ON_AFTER_CONFIG_LOAD` reads all three existing booleans once before map workers start, with the same default OFF values. `.reload config` compares settings and logs a warning if different, but **does not activate/deactivate the feature or debug flag**; an owner-approved server restart is required. This is a deliberate behaviour change, not an invisible equivalence claim. Both A04 loot policies remain separate, default OFF, and no entitlement, inventory or drop logic is changed. This source change is NOT enabled on the owner's server, and still needs exact-head full linked CI plus independent review and eight-thread staging evidence before S5/S6.
