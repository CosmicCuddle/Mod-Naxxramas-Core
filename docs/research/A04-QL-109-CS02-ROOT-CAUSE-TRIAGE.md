# A04 / QL #109 — CS02 root-cause triage (read-only)

**Status:** research only. No production code, SQL, config, or workflow change. Do not merge. Do not treat this note as a fix or as in-game acceptance.

**Author:** CosmicScript02. **Date:** 23 October 2026. **Issue:** [#109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109). Related owner notes: [#48 comment 6369285968](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6369285968), [#28 comment 6369286923](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6369286923), [PR #89 comment 6369287945](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/89#issuecomment-6369287945).

**Reviewers asked:** CosmicScript01 (integration and owner evidence), CosmicScript03 (independent core / Playerbots check of the citations below).

## Label legend

| Label | Meaning in this note |
| --- | --- |
| VERIFIED | Read at the SHA cited on that row. File:line refers to that SHA. |
| POTENTIAL ISSUE | Source path that can produce the reported symptom. Not identified as the corpse Michael looted. |
| UNKNOWN | Not in the report, not in git, or not recoverable from these trees. |
| NOT TESTED | Not executed in game, and not executed against a linked worldserver. |

The owner's 23 Oct 2026 report is accepted as a real negative result: with Quest Loot Protection reportedly enabled, group members could loot the owner's quest drops and the owner could loot theirs. Item id, quest id, creature, loot method, human/bot mix, active config, and the running binary are UNKNOWN. This note does not invent them.

## Commits behind every conclusion

| Tree | SHA | What was read |
| --- | --- | --- |
| Mod-Naxxramas-Core `main` | `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` | `QuestLootProtection.cpp` blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f`, loader, dist config, workflows, `tests/test_quest_loot_protection.py` |
| PR #89 head | `c2e13d6f759ea7bc1faee53caf91603a7dde8d32` | Same cpp blob. Loader call is line 96. Dist `Enabled = 0` is line 304. |
| PR #105 head | `b5311a70f609767011f9ecc0a72e506f031c9957` | Same cpp blob. Loader call is line 98. Dist `Enabled = 0` is line 364. |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` | Loot generation, assignment, packet hook, group methods |
| Public Playerbots `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` (2026-10-16, merge of PR 2931) | `StoreLootAction` and other autostore sites |
| Playerbots commit the owner runs | `e88cc4099e69f35126b28942a412ca702d20453b` (2026-10-22, merge of PR 2962) | Same `LootAction.cpp` store/release lines as `d750b4b`. Raid files differ; they still queue the autostore opcode. |
| Owner's two local Playerbots patches | not in either public commit | UNKNOWN. Not reviewed. |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` | Symbol search only. No loot-award hooks found. |
| Older quest-loot CI Playerbots pin | `037c01418b5d01506917a3db9b44fd56ac5f965c` | Cited only to retire stale line numbers in `docs/QUEST-LOOT-PROTECTION.md`. Not the pin for this triage. |

`git rev-parse origin/main` on 23 Oct 2026 matched local `main` `80e9de1`. Blob identity of `src/Systems/QuestLootProtection.cpp` on `main`, PR #89, and PR #105 is VERIFIED (`48729dc9fdd674eea0f4bb7bd1a47762558daf6f`).

## Verdict

**Root cause of the 23 Oct session: UNKNOWN.** The source does not have one forced explanation. It has several fail-open paths that each allow both directions, plus an UNKNOWN chance that the running process never loaded the guard.

The narrow cell the guard was written to deny is real, and it is small. A successful bidirectional pickup means the session was outside that cell, or the guard was not in the process. Those two statements are not yet separable.

Existing `tests/test_quest_loot_protection.py`: 30 tests, `python3 -m unittest tests.test_quest_loot_protection`, exit 0, on this `main` tree. VERIFIED as a source-and-model run only. NOT TESTED against Grimfeather, Playerbots, a corpse, or the owner's client. A green run here does not contradict #109. `test_non_owner_cannot_collect_single_copy` only models the narrow deny. It never sees a QuestRequired=0 item, a released turn, or a MULTI_DROP copy.

## 1. What the guard actually denies

File: `src/Systems/QuestLootProtection.cpp` at blob `48729dc9` (same text on the three module SHAs above). Line numbers below are that file.

VERIFIED: the script registers only `SERVERHOOK_CAN_PACKET_RECEIVE` (lines 198-203 and 229-231). `main` loader calls `AddQuestLootProtectionScripts()` at `src/NaxxramasCore_loader.cpp:97`. The hook returns true (packet continues) unless every check below holds. The only `return false` is lines 193-194, after `SendLootError(..., LOOT_ERROR_LOCKED)`.

CS01's "~17 conjunctive predicates" is the right shape. Split at each `return true`, the deny conjunction is the following 21 checks. All must hold. The first failure permits.

| # | Deny requires | Permit site |
| --- | --- | --- |
| 1 | Opcode is `CMSG_AUTOSTORE_LOOT_ITEM` | 210 |
| 2 | `NaxxramasCore.QuestLootProtection.Enabled` is true | 211 |
| 3 | Session exists | 212 |
| 4 | Session has a player | 212 |
| 5 | Packet size is at least 1 byte (first byte is the slot; extra bytes are still inspected) | 212-218 |
| 6 | Player is in world and has a map | 44-45 |
| 7 | Player is in a group | 47-49 |
| 8 | Loot method is `GROUP_LOOT`, `ROUND_ROBIN`, or `NEED_BEFORE_GREED` | 51-60 |
| 9 | `GetLootGUID()` is a creature or vehicle | 62-64 |
| 10 | Creature exists, is dead, is within `INTERACTION_DISTANCE`, and `GetLootRecipientGroup()` is this group | 66-70 |
| 11 | `loot.loot_type == LOOT_CORPSE` | 73 |
| 12 | `roundRobinPlayer` is set | 74 |
| 13 | `roundRobinPlayer` is not the clicking player (own turn permits) | 75 |
| 14 | Client slot is at or past `loot.items.size()` (a quest-view slot, not a normal slot) | 80-82 |
| 15 | Clicker has a non-null `GetPlayerQuestItems()` vector | 84-86 |
| 16 | Personal index is inside that vector | 89-91 |
| 17 | That view is not yet looted and its `index` is inside `quest_items` | 93-95 |
| 18 | `needs_quest`, `count == 1`, not looted, not `freeforall`, not `follow_loot_rules`, not `is_blocked`, no `rollWinnerGUID` | 101-104 |
| 19 | Item template exists and does not have `ITEM_FLAG_MULTI_DROP` | 106-108 |
| 20 | `ObjectAccessor::FindPlayer(roundRobinPlayer)` returns a player still in this group and `IsInWorld()` | 127-132 |
| 21 | That owner shares the live map object, map id, and instance id with the clicker and the corpse; the owner still has an unlooted personal quest view for the same `quest_items` index; `HasQuestForItem(itemid)` and `AllowedForPlayer` are both true for the owner | 134-179 |

VERIFIED: `Debug` logs only on the deny path (lines 185-191), reason string `active_owner_still_eligible`. A permit writes nothing. Silence does not identify which row above fired.

VERIFIED: dist config on `main` is `NaxxramasCore.QuestLootProtection.Enabled = 0` and `Debug = 0` at `conf/mod_naxxramas_core.conf.dist:364` and `:369`. The owner's live values are UNKNOWN. A report that the setting was turned on is not a reading of the process.

Pinned hook semantics, Grimfeather `8daffdabe`:

- VERIFIED `src/server/game/Server/WorldSession.cpp:461-464` (and the same order at 479-482, 489-492, 505-508): `CanPacketReceive` runs before `opHandle->Call`.
- VERIFIED `src/server/game/Scripting/ScriptDefines/ServerScript.cpp:57-62` and `ScriptMgrMacros.h:76-80`: if any enabled script returns false from `CanPacketReceive`, the packet is not dispatched. Our script's true return does not get overridden by a later script into a deny. A false return from our script does deny.
- VERIFIED `LootHandler.cpp:33-107`: `HandleAutostoreLootItemOpcode` reads one `uint8` slot and calls `Player::StoreLootItem`. That is the only opcode the module watches.

## 2. Native generation and assignment (Grimfeather `8daffdabe`)

### Where an item is stored

VERIFIED `LootMgr.cpp:148-166`: `creature_loot_template.QuestRequired` is loaded into `LootStoreItem::needs_quest`. That column is the only reason a generated line goes to `quest_items`.

VERIFIED `LootMgr.cpp:481-490`: `Loot::AddItem` pushes to `quest_items` when `item.needs_quest`, otherwise to `items`.

VERIFIED `LootMgr.cpp:393-403`: `LootItem::freeforall` is `ITEM_FLAG_MULTI_DROP` (`ItemTemplate.h:158`, flag `0x00000800`). `follow_loot_rules` is custom flag `ITEM_FLAGS_CU_FOLLOW_LOOT_RULES` (`ItemTemplate.h:221`, `0x0004`). `needs_quest` is copied from the loot row, not from "this item is a quest objective".

VERIFIED `LootMgr.cpp:656-705`: `FillQuestLoot` builds a per-player view over `quest_items` for players who pass `AllowedForPlayer` (master looter is also given a view). A non-freeforall quest line increments `unlootedCount` once (`is_counted`).

VERIFIED `LootMgr.cpp:633-653`: MULTI_DROP lines in `items` get a separate per-player FFA view. Each such line increments `unlootedCount` per player.

VERIFIED `LootMgr.cpp:708-738`: non-empty `conditions`, not freeforall, not `needs_quest`, go to `PlayerNonQuestNonFFAConditionalItems`. They stay in `items`. Their client slot is the normal-item index (`LootMgr.cpp:1193`).

POTENTIAL ISSUE: a quest-objective item with `QuestRequired = 0` never enters `quest_items`. If it also has conditions (quest taken, quest not rewarded, and similar), it is a conditional normal slot. The guard's check 14 permits it before any quest logic runs. Many quest-useful drops are in this class. Which class the 23 Oct item was is UNKNOWN.

### When round-robin is set and cleared

VERIFIED `Unit.cpp:13648-13701` (`Unit::Kill`): for a grouped kill, if the method is not free-for-all and a round-robin looter guid exists, the creature's loot recipient is updated to that player. `FillLoot` then runs with that player as `lootOwner`. Afterwards `UpdateLooterGuid` advances the group's looter for the next corpse. It does not rewrite this corpse's `roundRobinPlayer`.

VERIFIED `LootMgr.cpp:565-569`: for a non-personal grouped `FillLoot`, `roundRobinPlayer = lootOwner->GetGUID()` immediately. This assignment happens for every grouped method, including free-for-all and master loot. The module's method switch, not an empty guid, is what lets those methods through.

VERIFIED `LootMgr.cpp:571-578`: personal quest/FFA/conditional views are filled only for members inside reward distance at fill time. A member who walks up later is not added by any other caller found in this tree (`FillNotNormalLootFor` callers: `LootMgr.cpp:577` and `:591`, `Player.cpp:8077` for gameobject allowed-looters, `LootItemStorage.cpp:228`). NOT TESTED in game.

VERIFIED `LootMgr.h:367`: `Loot::empty()` is `items.empty() && gold == 0`. It ignores `quest_items`. Combined with `Unit.cpp:13700`, a corpse that rolled only quest lines does not advance the group looter guid. The corpse's own `roundRobinPlayer` is still set inside `FillLoot`. This is a native quirk. It does not by itself let a non-owner past the guard.

VERIFIED `LootHandler.cpp:456-465`: on creature release, if the releasing player is `roundRobinPlayer`, the guid is cleared and the group is told there is no looter. The same clear exists for gameobjects at `LootHandler.cpp:390-391`. `Loot::clear()` also clears it (`LootMgr.h:362`) when the corpse is fully looted.

POTENTIAL ISSUE: any later autostore sees an empty `roundRobinPlayer` and the guard permits (check 12). Closing the loot window is a release. That is ordinary play, and it is enough for the other member to take a still-present one-copy quest line.

### Who is allowed to see and click

VERIFIED `PlayerStorage.cpp:5770-5793` (`Player::isAllowedToLoot`): under round robin, group loot, and need-before-greed, a player who is not `roundRobinPlayer` may still open the corpse when `hasItemFor` is true. `hasItemFor` (`LootMgr.cpp:906-919`) is true for an unlooted personal quest, FFA, or conditional line. Opening the window is why a non-owner can send autostore at all.

VERIFIED `LootMgr.cpp:1094-1157`, quest-view serialization, for a viewer who `HasQuestForItem`:

- `follow_loot_rules` under group or round robin: `LOOT_SLOT_TYPE_ALLOW_LOOT` when not blocked, else a roll slot. No `roundRobinPlayer` test.
- Otherwise, not freeforall: `partySlotType`, which is `LOOT_SLOT_TYPE_ALLOW_LOOT` unless the viewer is the master looter (`LootMgr.cpp:1094-1097` and `1154-1155`). No `roundRobinPlayer` test.
- Freeforall: `LOOT_SLOT_TYPE_ALLOW_LOOT`.

VERIFIED `LootMgr.cpp:1000-1071`: normal `items` do consult `roundRobinPlayer`. Under group / master / restricted permission, an under-threshold line is omitted for a non-owner while the guid is set (`1040-1049`). Under round robin, every normal non-FFA line is omitted for a non-owner (`1064-1066`). Conditional lines are serialized later (`1184-1222`) and do not use that round-robin omit. FFA lines are always `LOOT_SLOT_TYPE_ALLOW_LOOT` (`1178`).

VERIFIED `Group.cpp:1122-1224`: `GroupLoot` rolls over-threshold normal lines and sets `is_blocked`. Quest lines are skipped unless `follow_loot_rules` (`1222-1225`). Need-before-greed does the same skip at `1375-1378`. Master loot sets `is_blocked` on quest lines only when `follow_loot_rules` (`1455-1460`). A plain one-copy quest line is never rolled and never blocked.

VERIFIED `Player.cpp:13861-13943` (`StoreLootItem`):

- The master-loot threshold rejection at `13881-13886` is skipped when the slot is a quest view, an FFA view, or a conditional view (`!qitem && !ffaitem && !conditem` is required before that rejection).
- There is no `roundRobinPlayer` comparison on a quest slot.
- `rollWinnerGUID` still blocks a different player (`13901-13906`).
- `is_blocked` is enforced only when the slot is not a quest view (`13894-13898`). A blocked quest view can still be stored if a packet arrives. Humans are not shown an allow slot while the roll is ongoing. NOT TESTED for a forged packet.
- `13942-13943`: `item->is_looted = true` only when `!freeforall`. A MULTI_DROP line stays available for the next eligible player. Per-player `qitem->is_looted` / `ffaitem->is_looted` records that this player already took their copy (`13915-13930`).

VERIFIED direct `StoreLootItem` callers in this core, besides the definition: `LootHandler.cpp:107` (the autostore opcode) and `LootMgr.cpp:623-629` (during `FillNotNormalLootFor`, freeforall currency tokens only). The currency call does not go through `CanPacketReceive`. It is already inside the freeforall permit. It is not a path for a one-copy quest line.

`CMSG_LOOT_MASTER_GIVE` (`LootHandler.cpp:478-541`) stores by slot without `StoreLootItem` and without this module's hook. The module also permits the whole master-loot method at check 8. Both facts agree. Master-loot policy is unchanged.

### Group method defaults

VERIFIED `Group.h` via `LootMgr.h:56-62`: `FREE_FOR_ALL=0`, `ROUND_ROBIN=1`, `MASTER_LOOT=2`, `GROUP_LOOT=3`, `NEED_BEFORE_GREED=4`.

VERIFIED `Group.cpp:103` constructor starts at `FREE_FOR_ALL`. `Group.cpp:159-160` sets `GROUP_LOOT` for a new non-LFG group. `Group.cpp:298-301` sets `NEED_BEFORE_GREED` for restricted LFG. The method selected in the 23 Oct group is UNKNOWN. A normal party created on this core defaults to group loot. That is not evidence of the test.

## 3. Playerbots and Individual Progression

### Ordinary bot loot is on the packet path

VERIFIED at public `d750b4b` and at owner commit `e88cc409`, `src/Ai/Base/Actions/LootAction.cpp` (same line numbers on both SHAs):

- `StoreLootAction::Execute` `469-472`: builds `CMSG_AUTOSTORE_LOOT_ITEM` for the client slot and `QueuePacket`s it. The next line's `HandleAutostoreLootItemOpcode` call is commented out.
- `490-493`: then queues `CMSG_LOOT_RELEASE` for that guid. The direct release handler is commented out.
- `408-424`: the bot only autostores slots the loot packet marked `LOOT_SLOT_TYPE_ALLOW_LOOT` or `LOOT_SLOT_TYPE_OWNER`.
- `520-538`: `IsLootAllowed` returns true when the item is a required item on a quest in the bot's log. Quest objectives the bot can see are loot attempts.

`git diff d750b4b e88cc409 -- src/Ai/Base/Actions/LootAction.cpp` is empty. VERIFIED.

Those queued packets enter `WorldSession::Update` and therefore `CanPacketReceive`. VERIFIED for any bot session that uses this action. A bot does not skip the guard on the ordinary path.

POTENTIAL ISSUE, separate from the hook: if the bot is the round-robin player, it loots the allow-slots it wants and then releases. Release clears `roundRobinPlayer` (`LootHandler.cpp:459-461`). Whatever it did not take, including a one-copy quest line it skipped, is then open to everyone. If the bot is not the round-robin player, its release does not clear the guid.

Older pin `037c014` has the same queue-and-commented-handler pattern at `LootAction.cpp:487-490`. `docs/QUEST-LOOT-PROTECTION.md` cites those older lines. Use `469-472` for `d750b4b` and `e88cc409`.

### Other bot acquisition

VERIFIED both SHAs, `git grep StoreLootItem` and `HandleAutostoreLootItemOpcode`: the only hit is the commented call at `LootAction.cpp:472`. No Playerbots caller of `Player::StoreLootItem` on these two commits.

VERIFIED other `CMSG_AUTOSTORE_LOOT_ITEM` queues, still `QueuePacket`, so the hook still sees them:

- `d750b4b` `src/Ai/Raid/TK/TKActions.cpp:1498-1500` (Kael'thas legendary weapon slot). At `e88cc409` the same opcode is line 1508. Diff between the SHAs is raid strategy, not a new direct-store path.
- `d750b4b` `src/Ai/Raid/SSC/SSCActions.cpp:2111-2121` (open, autostore, release for a Serpentshrine core). At `e88cc409` the autostore is line 2106. Same opcode, still queued.

`QuestAction.cpp` `StoreNewItem` grants quest-reward items from the bot quest action. That is a turn-in reward, not a corpse drop. It does not pass the corpse guard, and it should not. NOT TESTED in game.

UNKNOWN: the owner's two local Playerbots patches. They are not these commits. A local patch that calls `StoreLootItem` or the handler directly would bypass the hook. No such patch was available to read.

UNKNOWN: whether the 23 Oct group contained humans only, alt-bots, random bots, or a mix.

### Individual Progression

VERIFIED at `dd96f2b`: `git grep` over `*.cpp` and `*.h` for `StoreLootItem`, `CanPacketReceive`, `roundRobinPlayer`, `OnPlayerLootItem`, `LootScript`, and `FillQuestLoot` returned no matches. IP does not award corpse loot and does not register this packet hook.

IP can still change quest status. The guard's check 21 calls `HasQuestForItem`. If IP makes the turn holder ineligible, the guard permits. That is one direction (other members take the turn holder's drop). It does not, by itself, explain both directions while both characters still need the item. Whether IP changed either character's quest state on 23 Oct is UNKNOWN.

## 4. Matrix

Actor note, VERIFIED for the public commits and UNKNOWN for the local patches: a human click and `StoreLootAction` produce the same opcode, so the guard's answer is the same. The bot only sends slots the client packet marked allow or owner. A human client does the same. A forged slot is possible and NOT TESTED; the guard's answer to a forged normal slot is still permit (check 14).

Method note: `FREE_FOR_ALL` and `MASTER_LOOT` permit every row below (check 8), for both actors, at every event. Native free-for-all then lets each eligible player take what the core already allows. Native master loot still lets a non-master autostore a plain quest line, because those lines are not blocked and their slot type is allow (`LootMgr.cpp:1154-1155` with `partySlotType` equal to allow for a restricted viewer).

The grid is group loot, round robin, and need-before-greed. "Deny" means the current module returns false. "Permit" means it returns true and core `StoreLootItem` runs.

Events:

- **T1** Active turn. Clicker is not `roundRobinPlayer`. Owner is in world, same map and instance, still grouped, still eligible, personal quest view still unlooted. Window not released.
- **T2** Clicker is `roundRobinPlayer`.
- **T3** After that owner releases. `roundRobinPlayer` is empty.
- **T4** Owner offline, not in world, other map, other instance, left the group, has no personal view, or no longer needs the item.

| Item class | T1 non-owner | T2 own turn | T3 after release | T4 owner absent or ineligible | Why |
| --- | --- | --- | --- | --- | --- |
| One-copy `quest_items` (`needs_quest`, count 1, not MULTI_DROP, not `follow_loot_rules`, not blocked, no winner), creature corpse | **Deny** | Permit | Permit | Permit | This is the only deny cell. Checks 11-21 all hold only on T1. |
| MULTI_DROP / `freeforall` quest line | Permit | Permit | Permit | Permit | Checks 18-19. Each player keeps a copy (`Player.cpp:13942-13943`). |
| `follow_loot_rules` quest line | Permit | Permit | Permit | Permit | Check 18. Core roll / `rollWinnerGUID` still applies. The guard stays out on purpose. |
| `quest_items` with `count != 1` | Permit | Permit | Permit | Permit | Check 18. |
| `QuestRequired=0` normal line, no conditions, not MULTI_DROP | Permit | Permit | Permit | Permit | Check 14, slot is below `items.size()`. While the turn is active, native display hides under-threshold lines from a non-owner (`LootMgr.cpp:1040-1049` and `1064-1066`), so a normal client usually has nothing to click. The guard would still permit a packet. |
| `QuestRequired=0` conditional line (quest conditions live here) | Permit | Permit | Permit | Permit | Check 14. Native display does **not** hide these from a non-owner (`LootMgr.cpp:1184-1222`). Both members can click. A non-freeforall copy is consumed by the first store. |
| MULTI_DROP normal line | Permit | Permit | Permit | Permit | Check 14, and the line is freeforall. Both members can take a copy. |
| Gameobject, item, bones, pickpocket, skinning, non-corpse | Permit | Permit | Permit | Permit | Checks 9-11. |

Over-threshold normal lines in group loot and need-before-greed are rolled and `is_blocked` (`Group.cpp:1179` and `1340`). The client shows a roll, not an allow slot. `StoreLootItem` rejects a blocked non-quest line (`Player.cpp:13894-13898`). The guard also permits them (check 14). They are a poor match for "I clicked their quest drop and received it" unless the roll had already finished and the clicker was the winner.

### Cells that fit a bidirectional pickup

Both directions succeeded. That excludes "the guard denied one of them". The session matched a permit cell, or the guard was not running.

1. **POTENTIAL ISSUE, strongest match if one shared copy disappeared while the window was still the other person's turn.** The drop was not the deny-row of the table. The best subtype is a `QuestRequired=0` conditional (or otherwise visible) line in `loot.items`. Both members see it. The guard permits. Core stores it for whoever clicks. The next kill, with the other player as turn holder, repeats in the other direction. A plain under-threshold normal line is a weaker match, because native display hides it from the non-owner until release.

2. **POTENTIAL ISSUE, strongest match if someone had already closed the loot window.** T3 on a real one-copy `quest_items` line. Release clears the turn. The guard permits. Bots always queue release after `StoreLootAction`. Humans often close the window. Across two corpses this is bidirectional.

3. **POTENTIAL ISSUE, strongest match if both characters ended with a copy.** MULTI_DROP / `freeforall`, either list, any method, T1 through T4. Nothing was stolen. The guard permits on purpose. A fix that denies this cell is a false deny of a per-player reward.

4. **POTENTIAL ISSUE if the group was free-for-all or master loot.** Every item class permits. Master loot is easy to misread: plain quest lines are clickable by non-masters.

5. **The deny cell does not fit a successful click.** One-copy `quest_items`, group / round robin / need-before-greed, T1, owner still eligible and present. Source says the guard returns false there for a human and for `StoreLootAction`. If that was the corpse and the click still worked, the process was not running this blob with `Enabled=1`. That is UNKNOWN, and it is sufficient on its own.

No cell above is promoted from POTENTIAL ISSUE to a diagnosed cause. The 23 Oct item was not identified.

## 5. Data the owner needs to send

Short list for CosmicScript01 to relay. No server changes, no SQL, no retest required to answer.

1. Item entry and quest id of the drop the other person took (shift-click the item, or the ids). Say whether the first person's copy vanished or both people kept one.
2. Creature or object entry they looted, and the group loot method shown in the group frame (Free for All, Round Robin, Master Looter, Group Loot, Need Before Greed).
3. Who was in the group: humans only, or Playerbots / alt-bots as well. Who had the loot turn when the other person clicked.
4. Was the loot window still open for the turn holder, or had it been closed? Were both characters online, on the same map, in the same instance?
5. Worldserver log lines containing `QuestLootProtection` for that attempt. No lines is a useful answer. Say whether `Debug` was 1.
6. From the config the running worldserver actually loaded: `NaxxramasCore.QuestLootProtection.Enabled` and `.Debug`. Plus `git rev-parse HEAD` and `git status --short` for the module, Grimfeather core, Playerbots, and Individual Progression. The two local Playerbots patches should appear in that status. Do not paste passwords or connection strings.

## 6. Test-first correction plan

Do not edit `QuestLootProtection.cpp` until the item class is known. This PR does not add the tests either. It names them so the next change can land tests first.

Constraints that stay: default off, module-only, no edits to Grimfeather core, Playerbots, or Individual Progression, no blanket "quest item" ban, no change that stops a legitimate free-for-all method or a per-player MULTI_DROP copy.

The current 30 source tests characterize the narrow guard. They are not the #109 regression. Add the following, in this order, against the current source first so today's permits stay locked. Only the single cell identified by the owner's item id is allowed to flip from permit to deny later.

| Write first | Expectation against today's guard | Must remain true after any fix |
| --- | --- | --- |
| `test_ql109_non_owner_then_rightful_owner` | T1 non-owner on a one-copy creature `quest_items` line is denied. The round-robin owner then stores that same line. | Deny, then the owner's store, stays. This is the regression that must not go green for the non-owner. |
| `test_ql109_own_turn_permits` | Clicker equals `roundRobinPlayer`. Permit. | Permit. |
| `test_ql109_after_release_permits` | Empty `roundRobinPlayer` after a modeled release. Permit, including a one-copy quest line. | Permit, unless a later explicit policy says otherwise and has its own test. Do not flip this while closing #109 on a guess. |
| `test_ql109_owner_offline_or_absent_permits` | Owner missing, not in world, other map, or other instance. Permit. | Permit. A stranded corpse is a false deny. |
| `test_ql109_multidrop_per_player_copies_permit` | Two members, `ITEM_FLAG_MULTI_DROP` / `freeforall`, quest line and normal line. Both permits. Shared `is_looted` stays false. Each personal view records only that player. | Permit. False deny if a fix consumes the shared line. |
| `test_ql109_ffa_method_permits` | `FREE_FOR_ALL` permits the one-copy quest line for a non-owner. | Permit. |
| `test_ql109_bot_store_loot_action_is_packet_path` | Static check of `LootAction.cpp` at `d750b4b` and `e88cc409`: autostore is `QueuePacket`, the direct handler call stays commented, release is queued after. | Documents the path. Does not claim the owner's two local patches. Those stay UNKNOWN until the status output in section 5 exists. |

Also keep a characterization, not a new deny, for `QuestRequired=0` conditional slots and for `count != 1`, until the item id picks one of them. A test that already expects those to deny would be choosing a policy the corpse has not confirmed.

### Candidate fixes, not implemented

| Option | When it would be the fix | False-deny risk |
| --- | --- | --- |
| A. `Debug=1` logs the permit reason (which check returned true). Still default off. Module-only. | Owner can run one more approved session. It does not change loot rights. | None for loot. Log volume only while Debug is on. |
| B. Treat a single-copy conditional `items` line like a quest line when the turn holder still `HasQuestForItem` and `AllowedForPlayer`, same map and instance rules, same three methods. | Section 4 cell 1, and only after the item id shows `QuestRequired=0` plus conditions, one shared copy. | Conditional items that are not quest drops (class, reputation, aura) lock to the turn holder until release. Fail open when the turn holder does not meet the condition. Do not require a `PlayerQuestItems` view; conditional lines do not have one. |
| C. Keep denying after release while the owner is still eligible. | Would cover section 4 cell 2. | High. Closing the window would strand the item until the owner leaves or logs out. Reject as the default fix. Release is an intentional pass. |
| D. Also deny `count != 1` or `follow_loot_rules`. | Only if the item id shows that flag and a shared copy was taken. | Stacks get locked. Rolled `follow_loot_rules` lines can deny the roll winner; core already handles that winner. Do not include these in a first patch. |
| E. Deny every quest-related item, or deny MULTI_DROP, or deny free-for-all. | Never for this bug. | False deny of per-player copies and of free-for-all groups. Out of scope. |
| F. Also hook `CMSG_LOOT_MASTER_GIVE`. | Only if section 5 says the method was master loot and a non-master click was not the path. | Can block a master looter assigning the item to the person who needs it. Leave master loot permitted unless that method is confirmed. |

A module packet hook cannot see `LootMgr.cpp:628` (freeforall currency, already out of scope) or a local Playerbots patch that calls `StoreLootItem` directly. Do not patch core or Playerbots to close that. If section 5 shows a direct call in a local patch, the choice is to stop using that patch or to keep the protection limited to the opcode path. That decision is the owner's.

## 7. What this session did not do

- NOT TESTED: the 23 Oct corpse, any client, any bot in a group, loot-window icons, release timing, corpse expiry.
- NOT TESTED: linked worldserver, SQL, item_template flags for a real entry. No database was opened.
- UNKNOWN: running binary commit, loaded config, the two local Playerbots patches, loot method, item, quest, creature, group composition.
- No edit to PR #89's branch, PR #105's branch, core, Playerbots, or Individual Progression.
- No merge, tag, or release.

## 8. Workflows and artifacts

VERIFIED on `main` `80e9de1`: every file in `.github/workflows/*.yml` has a `pull_request` `paths` filter. None list `docs/research/**`. A search of those files for `upload-artifact`, `actions/upload`, `softprops`, and `actions/download` found no matches. The only "upload" wording is a comment in `f10-event-only-pilot.yml` that the job does not upload binaries. This docs-only note should not start those workflows. They do not publish build artifacts when they do run.

## 9. Ready-to-post #48 comment

CS02 triage for #109 is a read-only draft. Do not merge. The 23 Oct failure stands. Quest, item, creature, loot method, group mix, and the loaded binary remain UNKNOWN.

Verified: main `80e9de1`, #89 `c2e13d6`, and #105 `b5311a7` share `QuestLootProtection.cpp` blob `48729dc9`. The guard only sees `CMSG_AUTOSTORE_LOOT_ITEM` and denies only when every check holds. Any miss fail-opens into Grimfeather `8daffdabe`, where one-copy `quest_items` ignore `roundRobinPlayer` and `StoreLootItem` does not apply it to quest slots. Release clears that guid. `QuestRequired=0` lines, including conditional quest drops, stay in `loot.items` and are never denied. MULTI_DROP and Free for All stay permitted. Playerbots `d750b4b` and `e88cc409` queue that opcode from `StoreLootAction`; the direct handler call is commented out. Local patches were unread. Debug logs denials only.

Best fit for both directions: the drop was outside that one-copy quest slot; the turn holder had already released; or each player got a MULTI_DROP copy. The guard may also have been inactive (`Enabled` defaults to 0). Please send item and quest ids, loot method, who was grouped, whether one shared copy was consumed, whether the window was still open, any `QuestLootProtection` log lines, and the loaded `Enabled`/`Debug` values plus git HEAD and Playerbots `git status --short`.
