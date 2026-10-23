# A04 / QL #109 — human fail-open paths and per-viewer sparkle mismatch

**Status:** research only. No production code, SQL, config, or loot-rule change. Do not merge. Do not treat this note as a fix, as in-game acceptance, or as proof that a unique quest item moved.

**Author:** CosmicScript02. **Revised:** 23 October 2026, second revision after CS01 re-review `5632118504` on head `3cc7292b52fb21c7c8f060d00c8e88583b5940eb`. Earlier pass: CS01 review `5631632097` on head `1b4fc9a37f65ac7bcfe51bf254c5213bf93a8b21`, controlling addendum [PR #110 comment 6370306293](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/110#issuecomment-6370306293), and the loot-window addendum [6370542316](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/110#issuecomment-6370542316). **Issue:** [#109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109).

**Cross-read, not reimplemented:** CS03 [6369926271](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6369926271) (sparkle via `Unit::PatchValuesUpdate` / `isAllowedToLoot` / `Loot::hasItemFor`), CS01 [6370148999](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6370148999) (per-viewer `UnitDynamicFlagsPos` and `OnPatchValuesUpdate`), CS01 [6370540733](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6370540733) (`LootView` quest row emits `LOOT_SLOT_TYPE_ALLOW_LOOT` without a round-robin-holder check). CS01 draft PR [#111](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/111) head `c1d5b39898d212f04b789e30723bca5126f1bcbf` owns the H01–H08 characterization matrix. This note uses those H01–H05 meanings and does not redefine H06–H08. H09 and H10 are the two cells from CS03 [6370796678](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/111#issuecomment-6370796678). They are recorded here as current source, not as a chosen fix. CS01 [6371087087](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6371087087) is the shared-reference caution on `OnPlayerBeforeFillQuestLootItem`.

## Label legend

| Label | Meaning in this note |
| --- | --- |
| VERIFIED | Read at the SHA cited on that row. File:line refers to that SHA. |
| POTENTIAL ISSUE | A source path that can produce one of the owner reports. It is not identified as the owner's reported corpse. |
| UNKNOWN | Not in the report, not in git, or not recoverable from these trees. |
| NOT TESTED | Not executed in game, and not executed against a linked worldserver. A green synthetic run is still NOT TESTED for gameplay. |

Item, quest, creature, loot method, human/bot mix, loaded binary, and loaded config remain UNKNOWN. The phrase in the previous legend that named a person is removed. Later rows say "owner's reported corpse".

## Two owner reports, kept distinct

Both are accepted as owner reports. Neither is a code-proved transfer, and this note does not claim the human guard succeeded on the owner's reported corpse.

| Report | What the owner described | What this note is willing to say |
| --- | --- | --- |
| (a) Sparkle, then denial | A non-entitled member sees the corpse sparkle, tries to loot, and the protected quest item is denied. | UNVERIFIED as gameplay. Source has a matching shape: per-viewer `UNIT_DYNFLAG_LOOTABLE` can stay set from `Loot::hasItemFor`, and the module can still return false for one narrow autostore cell (H01). That shape is not evidence this corpse took that cell. |
| (b) Human friend takes the quest loot | A real human friend repeatedly accidentally takes the owner's quest loot because it appears available. | UNVERIFIED as gameplay. Several human fail-open paths hand the click to native `Player::StoreLootItem`, and the loot window can label the quest row `LOOT_SLOT_TYPE_ALLOW_LOOT` while another member holds `roundRobinPlayer`. Which path, whether one shared copy was consumed, and whether a second copy was created are UNKNOWN. Theft and duplication are not code-proved. |

Report (b) is not a bot-only report. Bot bypass is a separate source fact in section 10. It does not replace (a) or (b).

## Commits behind every conclusion

| Tree | SHA | What was read |
| --- | --- | --- |
| Mod-Naxxramas-Core `main` | `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` | `QuestLootProtection.cpp` blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f`, loader, dist config |
| PR #89 head | `c2e13d6f759ea7bc1faee53caf91603a7dde8d32` | Same cpp blob. Loader call is line 96. Dist `Enabled = 0` is line 304. |
| PR #105 head | `b5311a70f609767011f9ecc0a72e506f031c9957` | Same cpp blob. Loader call is line 98. Dist `Enabled = 0` is line 364. |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` | Loot generation, `LootView`, `StoreLootItem`, `PatchValuesUpdate`, packet hook, group methods |
| Public Playerbots | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` | `LootAction.cpp` sha256 `70e23039d87bc96bdc6d2613f01222af1a0459fc23c5be9aadd6e621f3637f73`, `PlayerbotMgr.cpp` sha256 `b5a5d7236af6e71312c8c89c10d0d1008ece4d86a3373eab8ab6fa06a9750610` |
| Playerbots the owner runs | `e88cc4099e69f35126b28942a412ca702d20453b` | Those two files are byte-identical to `d750b4b`. Raid strategy files were not re-read for this revision. |
| Owner's two local Playerbots patches | not in either public commit | UNKNOWN |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` | All 65 `*.cpp` / `*.h` files. No `StoreLootItem`, `CanPacketReceive`, `roundRobinPlayer`, `OnPlayerLootItem`, `OnPatchValuesUpdate`, `FillQuestLoot`, `LootScript`, or `OnAllowedForPlayerLootCheck`. |
| CS01 PR #111 | `c1d5b39898d212f04b789e30723bca5126f1bcbf` | `docs/research/A04-HUMAN-QUEST-LOOT-SOURCE-MATRIX.md` and its synthetic test. Not merged here. |

`QuestLootProtection.cpp` on this branch is still blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f`. VERIFIED by not editing `src/`.

## Verdict

**The owner's reported corpse is UNKNOWN.** The pinned trees do not force one explanation. They do show two human-facing mechanisms that have to be diagnosed together:

1. **Pickup fail-open.** `CanPacketReceive` denies one conjunction only. Each missed predicate returns true and `WorldSession::Update` then calls `opHandle->Call`. For a human that reaches `Player::StoreLootItem`. Quest-view slots in that function do not consult `roundRobinPlayer`.
2. **Per-viewer sparkle mismatch.** `Unit::PatchValuesUpdate` clears `UNIT_DYNFLAG_LOOTABLE` for one viewer only when `!isAllowedToLoot`. Under group, need-before-greed, and round robin, a non-holder is allowed when `Loot::hasItemFor` is true. An unlooted personal quest view makes `hasItemFor` true. The module can still deny that viewer's autostore. The corpse sparkles, the quest row can say `LOOT_SLOT_TYPE_ALLOW_LOOT`, and the click can still be refused. That is report (a)'s shape. It is not a proof of report (a)'s item.

Report (b) fits any fail-open in section 3, including a quest row that was only a label until `roundRobinPlayer` was cleared, a `QuestRequired = 0` line, master loot, free-for-all, or `ITEM_FLAG_MULTI_DROP`. Those are POTENTIAL ISSUE paths. None is promoted to the corpse. A sparkle-only mask does not close a fail-open, and a packet deny does not correct a sparkle.

The historical 21-check human packet guard remains useful. It is not every loot handler. Master give, money, bot `opHandle->Call`, and freeforall currency inside `FillNotNormalLootFor` never enter it.

## 1. What the human packet guard denies

File: `src/Systems/QuestLootProtection.cpp` at blob `48729dc9`. Line numbers are that file. VERIFIED on this branch.

The script registers only `SERVERHOOK_CAN_PACKET_RECEIVE` (lines 198-203 and 229-231). `main` loader calls `AddQuestLootProtectionScripts()` at `src/NaxxramasCore_loader.cpp:97`. The hook returns true unless every check below holds. The only `return false` is lines 193-194, after `SendLootError(..., LOOT_ERROR_LOCKED)`.

| # | Deny requires | Permit site |
| --- | --- | --- |
| 1 | Opcode is `CMSG_AUTOSTORE_LOOT_ITEM` | 210 |
| 2 | `NaxxramasCore.QuestLootProtection.Enabled` is true | 211 |
| 3 | Session exists | 212 |
| 4 | Session has a player | 212 |
| 5 | Packet size is at least 1 byte | 212-218 |
| 6 | Player is in world and has a map | 44-45 |
| 7 | Player is in a group | 47-49 |
| 8 | Loot method is `GROUP_LOOT`, `ROUND_ROBIN`, or `NEED_BEFORE_GREED` | 51-60 |
| 9 | `GetLootGUID()` is a creature or vehicle | 62-64 |
| 10 | Creature exists, is dead, is within `INTERACTION_DISTANCE`, and `GetLootRecipientGroup()` is this group | 66-70 |
| 11 | `loot.loot_type == LOOT_CORPSE` | 73 |
| 12 | `roundRobinPlayer` is set | 74 |
| 13 | `roundRobinPlayer` is not the clicking player | 75 |
| 14 | Client slot is at or past `loot.items.size()` | 80-82 |
| 15 | Clicker has a non-null `GetPlayerQuestItems()` vector | 84-86 |
| 16 | Personal index is inside that vector | 89-91 |
| 17 | That view is not yet looted and its `index` is inside `quest_items` | 93-95 |
| 18 | `needs_quest`, `count == 1`, not looted, not `freeforall`, not `follow_loot_rules`, not `is_blocked`, no `rollWinnerGUID` | 101-104 |
| 19 | Item template exists and does not have `ITEM_FLAG_MULTI_DROP` | 106-108 |
| 20 | `FindPlayer(roundRobinPlayer)` is in this group and `IsInWorld()` | 127-132 |
| 21 | Same live map and instance; owner still has an unlooted personal view for that `quest_items` index; `HasQuestForItem` and `AllowedForPlayer` are both true | 134-179 |

VERIFIED: `Debug` logs only on the deny path (lines 185-191), reason `active_owner_still_eligible`. A permit writes nothing.

VERIFIED: dist config on `main` is `Enabled = 0` and `Debug = 0` at `conf/mod_naxxramas_core.conf.dist:364` and `:369`. The loaded values are UNKNOWN.

Pinned hook order, Grimfeather `8daffdabe`:

- VERIFIED `WorldSession.cpp:414` and `:461-464` (same order at 479-482, 489-492, 505-508): the receive loop runs only `while (m_Socket && _recvQueue.next(...))`, and `CanPacketReceive` runs before `opHandle->Call`.
- VERIFIED `ServerScript.cpp:57-62` and `ScriptMgrMacros.h:76-80`: the action is `!script->CanPacketReceive`. A false return stops dispatch. A later enabled script that returns false also stops dispatch. A later true return leaves the packet on course.
- VERIFIED `LootHandler.cpp:33-107`: `HandleAutostoreLootItemOpcode` reads one `uint8` slot and calls `Player::StoreLootItem`.

## 2. Where generated lines live

VERIFIED `LootMgr.cpp:151-184` and `:481-490`: `QuestRequired` is selected as `needsquest` and passed into `LootStoreItem`. `Loot::AddItem` then pushes `needs_quest` lines to `quest_items` and every other line to `items`.

VERIFIED `LootMgr.cpp:393-403`: `freeforall` is `ITEM_FLAG_MULTI_DROP` (`0x00000800`). `follow_loot_rules` is `ITEM_FLAGS_CU_FOLLOW_LOOT_RULES`. `needs_quest` is the loot-row flag, not "someone's quest log mentions this item".

VERIFIED `LootMgr.cpp:656-705`: `FillQuestLoot` builds a per-player view. A non-freeforall quest line counts once.

VERIFIED `LootMgr.cpp:565-569`: grouped non-personal `FillLoot` sets `roundRobinPlayer = lootOwner` for every grouped method, including free-for-all and master loot. The module's method switch is what lets those methods through.

VERIFIED `LootMgr.cpp:571-577`: personal quest, FFA, and conditional views are filled for members inside reward distance at fill time.

VERIFIED `LootHandler.cpp:456-467`: if the releasing player is `roundRobinPlayer`, the guid is cleared and `ForceValuesUpdateAtIndex(UNIT_DYNAMIC_FLAGS)` runs. Gameobject release clears the guid at `LootHandler.cpp:390-391`. `Loot::clear()` clears it at `LootMgr.h:362`.

VERIFIED `Player.cpp:13861-13954` (`StoreLootItem`): the master-loot threshold rejection is skipped for a quest, FFA, or conditional view (`13881-13886`). `is_blocked` is enforced only when the slot is not a quest view (`13894-13898`). There is no `roundRobinPlayer` comparison on a quest slot. `rollWinnerGUID` still blocks a different player (`13901-13906`). A successful store calls `OnPlayerLootItem` (`13954`) and does not call `ForceValuesUpdateAtIndex`.

VERIFIED `Group.cpp:1106-1120`: `CanRollOnItem` calls `LootItem::AllowedForPlayer`, which calls `OnAllowedForPlayerLootCheck`. `GroupLoot` rolls quest lines only when `follow_loot_rules` (`1222-1224`). Need-before-greed does the same (`1375-1378`). Master loot sets `is_blocked` on quest lines only when `follow_loot_rules` (`1455-1460`).

VERIFIED `LootMgr.h:56-62`: `FREE_FOR_ALL=0`, `ROUND_ROBIN=1`, `MASTER_LOOT=2`, `GROUP_LOOT=3`, `NEED_BEFORE_GREED=4`. The 23 Oct method is UNKNOWN.

## 3. Human pickup fail-open paths

A fail-open here means the module returns true and the human opcode handler runs. It is a candidate for native storage. It is not, by itself, a stored item. Inventory, `AllowedForPlayer`, bind, and unique-count checks still apply. NOT TESTED on the owner's reported corpse.

| Path | Guard miss | What native code then does | Report it can resemble |
| --- | --- | --- | --- |
| Any of the 21 predicates | That row's `return true` | `StoreLootItem` for a human autostore | (b) if the rest of native checks pass |
| `QuestRequired = 0` | Check 14. The line lives in `loot.items`, so the client slot is below `items.size()` | Under-threshold normal lines are omitted from a non-holder while `roundRobinPlayer` is set (`LootMgr.cpp:1040-1049` and `1064-1066`). Conditional lines are serialized later and do not use that omit (`1184-1222`). The first successful store of a non-freeforall line sets `is_looted` (`Player.cpp:13942-13943`). | (b) when the friend can see the line. A plain under-threshold line is a weaker match while the turn is active, because the window omits it. |
| Round-robin release / `roundRobinPlayer` clear | Check 12 | Later autostore is permitted, including a one-copy `quest_items` line. Release is ordinary play. Bots queue release after store (`LootAction.cpp:490-493`). | (b), including "the window was already closed". |
| Master loot | Check 8 | `CMSG_LOOT_MASTER_GIVE` never enters this hook (`LootHandler.cpp:478-541`). The method is outside the deny cell for every viewer. VERIFIED `Player::SendLoot`: only the master looter (`GetMasterLooterGuid() == GetGUID()`) receives `MASTER_PERMISSION`. Every other recipient-group member receives `RESTRICTED_PERMISSION` (`Player.cpp:8329-8330` for a creature corpse; the same split at `8124-8125` for an activated chest). An ordinary `!follow_loot_rules` quest row then uses `partySlotType` (`LootMgr.cpp:1097`, `1154-1155`): `LOOT_SLOT_TYPE_MASTER` for the master looter, `LOOT_SLOT_TYPE_ALLOW_LOOT` for the restricted viewer. | (b) if the method was master loot. The row label is not the same for every group member. Policy for master give is unchanged. |
| Free-for-all method | Check 8 | `isAllowedToLoot` returns true for grouped members (`PlayerStorage.cpp:5772-5774`). | (b) only if a shared copy was the expectation. Per-player FFA copies are legitimate. |
| `ITEM_FLAG_MULTI_DROP` / `freeforall` | Checks 18-19 | Each eligible player keeps a personal view. `is_looted` on the shared line stays false when `freeforall` (`Player.cpp:13942-13943`). | Both players still holding a copy. That is not theft. |
| Group eligibility | Checks 10, 20, 21 | No recipient-group match, owner missing, owner offline, other map or instance, owner without a personal view, or owner failing `HasQuestForItem` / `AllowedForPlayer` all permit. `FillLoot` only builds views for members in range (`LootMgr.cpp:571-577`). | (b) if the turn holder had already become ineligible. A stranded item is the false-deny this guard chose to avoid. |
| Client slot mapping | Checks 14-17 | Quest window index is `items.size() + index in that viewer's quest vector` (`LootMgr.cpp:1123-1129`). `LootItemInSlot` uses the same subtraction (`821-834`). FFA and conditional rows use the normal `items` index (`1175`, `1194`). A slot that misses the vector permits. | A forged or mismatched slot is NOT TESTED. Do not rewrite `SMSG_LOOT_RESPONSE` until those indexes are proved stable. |
| Loot-window quest row | None. This path is display, not the guard. | See section 4. The row can say available while the guard still denies the click, and it still says available after the guard fail-opens. | (a) and (b) can share this label. The label is not the award. |

`SMSG_LOOT_RESPONSE` visibility is not authorization. The chain is four steps long: sparkle (`PatchValuesUpdate`), row slot type (`LootView`), human autostore verdict (`CanPacketReceive`), storage (`StoreLootItem`). A later step does not rewrite an earlier packet that was already sent.

## 4. Loot-window quest row, separate from sparkle and from the packet verdict

VERIFIED `LootMgr.cpp:974-1230`, `operator<<(ByteBuffer&, LootView const&)`.

Normal `loot.items` under `GROUP_PERMISSION`, `MASTER_PERMISSION`, and `RESTRICTED_PERMISSION` consult `roundRobinPlayer` before an under-threshold allow slot (`1040-1049`). `ROUND_ROBIN_PERMISSION` omits every normal non-FFA line for a non-holder while the guid is set (`1064-1066`).

The personal `quest_items` loop (`1104-1157`) does not consult `roundRobinPlayer`. When `HasQuestForItem` is true and the line is not `follow_loot_rules` and not `freeforall`, the row is `partySlotType` (`1154-1155`). `partySlotType` is `LOOT_SLOT_TYPE_MASTER` only for master permission (`1097`). For group, restricted, and round-robin permission it is `LOOT_SLOT_TYPE_ALLOW_LOOT`. `follow_loot_rules` under group or round robin sends `ALLOW_LOOT` when the line is not blocked, otherwise `LOOT_SLOT_TYPE_ROLL_ONGOING` (`1142-1147`), again without a holder check.

VERIFIED `Player.cpp:8329-8330`: under `MASTER_LOOT`, `permission` is `MASTER_PERMISSION` only when `recipientGroup->GetMasterLooterGuid() == GetGUID()`. Other members of that recipient group get `RESTRICTED_PERMISSION`. The same split is at `8124-8125` for an activated chest. Treating every `MASTER_LOOT` viewer as master permission is wrong. A restricted viewer's ordinary quest row (`HasQuestForItem`, not `follow_loot_rules`, not `freeforall`) is `partySlotType` = `LOOT_SLOT_TYPE_ALLOW_LOOT` (`1097`, `1154-1155`). `follow_loot_rules` under `RESTRICTED_PERMISSION` is `slotType` (`ALLOW_LOOT`, because `slotType` is `OWNER` only for `OWNER_PERMISSION`, `1094`) when the line is not blocked, and `LOOT_SLOT_TYPE_LOCKED` when it is (`1139-1140`). That locked value is separate from group and round-robin, which use `LOOT_SLOT_TYPE_ROLL_ONGOING` while blocked (`1142-1147`). A viewer who does not `HasQuestForItem` but still `showInLoot` gets `MASTER` only under `MASTER_PERMISSION`, otherwise `LOCKED` (`1125`).

POTENTIAL ISSUE: a human friend's loot window can show the quest line as collectible while another member holds the turn. If the module then denies, the friend sees report (a): available, then refused. If any fail-open in section 3 has already tripped, the same label is followed by native storage, which is the source shape of report (b). The owner's item is still UNKNOWN, so this is not a finding that their copy moved.

A future per-viewer sparkle clear does not rewrite this row. A corpse that also holds gold or another line the friend may open will still show the quest row. Slot indexes must stay aligned with `LootItemInSlot` if anyone later filters the packet. That filter is not in this branch.

## 5. Per-viewer sparkle mismatch

VERIFIED `Unit.cpp:13822-13824`: a creature that is not fully looted gets `UNIT_DYNFLAG_LOOTABLE` (`0x0001`, `SharedDefines.h:3354`) on the unit. That flag is global creature state.

VERIFIED `Unit.cpp:16594-16618`: while building one viewer's update, `PatchValuesUpdate` rewrites `UNIT_DYNAMIC_FLAGS` in that viewer's buffer. It clears `LOOTABLE` when `creature && !target->isAllowedToLoot(creature)`. It then calls `sScriptMgr->OnPatchValuesUpdate` (`16661`).

VERIFIED `PlayerStorage.cpp:5746-5796`:

- Empty loot returns false (`5755-5756`). `Loot::isLooted` is `gold == 0 && unlootedCount == 0` (`LootMgr.h:368`).
- `hasItemForAll` is true when `gold` is set (`LootMgr.cpp:892-897`), and also for an unlooted non-FFA unconditional normal line.
- Under round robin, a non-holder is allowed only when `hasItemFor` is true (`5775-5781`).
- Under group loot and need-before-greed, a non-holder is also allowed when `hasOverThresholdItem` is true (`5782-5793`).
- Free-for-all and master loot return true for a member of the recipient group (`5772-5774`).
- `LOOT_SKINNING` is allowed only for `GetLootRecipientGUID() == GetGUID()` (`5761-5762`).

VERIFIED `LootMgr.cpp:906-948`: `hasItemFor` is true for an unlooted personal quest view, FFA view, or conditional view. The quest-view arm (`916-918`) does not ask whether `roundRobinPlayer` is someone else. That is the disagreement with the module: core sparkle and quest-row label use "this viewer has an unlooted quest view"; the module uses "the turn holder is still eligible for this one-copy line".

POTENTIAL ISSUE for report (a): non-holder, active turn, one-copy quest view, no other right. Sparkle stays on. Quest row says `ALLOW_LOOT`. Human autostore hits the deny cell. NOT TESTED in a client. Whether the owner's reported corpse was this cell is UNKNOWN.

VERIFIED `PlayerStorage.cpp:5775-5793`: once a non-holder is inside the `ROUND_ROBIN`, `GROUP_LOOT`, or `NEED_BEFORE_GREED` arm, that arm does not read `gold` and does not call `hasItemForAll`. Round robin returns `hasItemFor(this)`. Group loot and need-before-greed return true for `hasOverThresholdItem()`, otherwise `hasItemFor(this)`. An earlier gate at `5758` does call `hasItemForAll()`, and gold makes that function true (`LootMgr.cpp:894-897`). Passing the gate is not a sparkle grant. `isLooted()` is `gold == 0 && unlootedCount == 0` (`LootMgr.h:368`), so gold can also keep the corpse from looking empty (`5755-5756`) without putting the non-holder into the true branch of `5775-5793`. Native behaviour: gold alone does not set this viewer's sparkle under those three methods. NOT TESTED in a client.

V01 is a different statement. It is a conservative future design prohibition: a per-viewer clear must not remove `UNIT_DYNFLAG_LOOTABLE` when this grouped viewer can still take a money share. `HandleLootMoneyOpcode` (`LootHandler.cpp:122-275`) does not read `roundRobinPlayer`. The grouped split is `goldPerPlayer` at `216`. A clear that fired only because a quest line is protected would hide that cue. The prohibition does not claim the pin sparkles for gold alone.

## 6. `UnitScript::OnPatchValuesUpdate` at the core pin

Question: can a module, with no core edit, clear a false `LOOTABLE` on one human viewer's outgoing update, without writing creature state, and can it refresh after a real pickup and after release?

### Position mapping

VERIFIED `UnitUtils.h:63-106`. `BuildValuesCachePosPointers::UnitDynamicFlagsPos` is constructed as `-1`. `ApplyOffset` adds the offset only when the mark is `>= 0`. An absent field stays `-1`.

VERIFIED fresh path, `Unit.cpp:16477-16517`:

1. When `UNIT_DYNAMIC_FLAGS` is included, `UnitDynamicFlagsPos` is set to `fieldBuffer.wpos()` before the `uint32` is written (`16479-16481`).
2. The cache buffer receives the update-mask header, then the field buffer (`16504-16507`).
3. `ApplyOffset(fieldBufferPos)` shifts the mark past that header (`16508`).
4. The cache bytes are appended to the outgoing `data` buffer (`16510-16511`).
5. A copy of the marks, `dataAdjustedPos`, receives `ApplyOffset(cachePos)` only when `data->wpos()` before the append was non-zero (`16513-16515`).
6. `PatchValuesUpdate(*data, dataAdjustedPos, target)` runs (`16517`). The cached buffer is inserted after that call (`16519`) and was already copied into `data` before the patch, so the patch writes the outgoing bytes.

VERIFIED cache-hit path, `Unit.cpp:16410-16420`: the stored marks (header offset already applied, packet offset not stored) are copied, `ApplyOffset(cachePos)` runs when the append point is non-zero, and `PatchValuesUpdate` runs on `*data` again. Both layouts therefore call the hook with a position in the outgoing packet, not with a fixed update-field index.

`Unit::Update` clears the cache at `Unit.cpp:645` through private `InvalidateValuesUpdateCache` (`Unit.h:2233`). `SetUInt32Value(UNIT_FIELD_HEALTH)` also clears it (`Unit.cpp:17003-17004`). `UNIT_DYNAMIC_FLAGS` is not in that switch. `ForceValuesUpdateAtIndex` only sets the changes bit and queues an object update (`Object.cpp:2156-2159`). It does not clear the cache. After the next `Unit::Update`, a values build sees the bit and can include the field (`Unit.cpp:16432-16437`). NOT TESTED against a live map's ordering of `Unit::Update` and object-update send.

### Endian and bounds

VERIFIED `ByteBuffer.h:136-141` and `:351-367`, `ByteConverter.h:46-55`, `Define.h:28-33`. `put<uint32>` and `read<uint32>(pos)` both run `EndianConvert`. That function is empty unless `ACORE_ENDIAN == ACORE_BIGENDIAN`. The default is little endian unless Boost reports a big-endian host. A module that reads with `read<uint32>(pos)`, clears `UNIT_DYNFLAG_LOOTABLE` (`0x0001`) in that host value, and writes with `put<uint32>` follows the same pair the core uses. A raw store of a host integer skips that pair and is wrong on a big-endian host. The owner's host endian is UNKNOWN. The safe pattern is the typed pair.

VERIFIED `ByteBuffer.cpp:143-149`: `put` of the raw bytes `ASSERT`s `pos + cnt <= size()`. `read<uint32>(pos)` throws `ByteBufferPositionException` when `pos + 4 > size()` (`ByteBuffer.h:358-363`). `PatchValuesUpdate` has no try/catch around the script call (`Unit.cpp:16661`). An ASSERT aborts the process. A module must reject `UnitDynamicFlagsPos < 0` and reject `pos + 4 > valuesUpdateBuf.size()` before `put`. The core has just written that position when the mark is `>= 0` (`16618` then `16661`), so a module that reuses the same mark without moving the buffer is inside the bytes the core accepted. NOT TESTED if another script resizes the buffer first.

### Registration and what the hook is allowed to touch

VERIFIED `UnitScript.h:39` and `:96`, `UnitScript.cpp:102-104` and `:142-152`, `ScriptMgrMacros.h:72-74`. `ScriptMgr::OnPatchValuesUpdate` is `CALL_ENABLED_HOOKS(UnitScript, UNITHOOK_ON_PATCH_VALUES_UPDATE, ...)`. A `UnitScript` whose `enabledHooks` vector contains `UNITHOOK_ON_PATCH_VALUES_UPDATE`, or whose vector is empty (empty enables every unit hook), is invoked. The current module does not construct a `UnitScript`. VERIFIED by reading `QuestLootProtection.cpp` (no `UNITHOOK_ON_PATCH_VALUES_UPDATE`).

The first argument is `Unit const*`. The buffer is the outgoing packet for `target`. The mark struct is the local `dataAdjustedPos` copy, not the cache entry. A `put` on that buffer does not write `m_uint32Values`, `Creature::loot`, or the cached template. VERIFIED from the call arguments at `Unit.cpp:16420` and `:16517`.

The signature does not enforce that discipline. The same process can still reach the creature through `target` or a const cast. "Copy only, never global" is a rule for a future patch, not a property the hook guarantees.

Hook order is `EnabledHooks` registration order (`ScriptMgrMacros.h:72-74`). Another module that later sets `LOOTABLE` in the same buffer would undo a clear. IP's C++ tree at `dd96f2b` does not register this hook. Other loaded modules are UNKNOWN. Clearing a bit that is already clear is a no-op. Setting the bit is outside the rule: the native filter already decided, and this hook runs after it (`16609-16618`, then `16661`).

### False-positive-only clear, and refresh

A module-only clear is source-feasible for the outgoing human packet when all of the following hold: the mark is `>= 0`, four bytes fit, the bit is currently set, and a conservative helper says this viewer has no remaining money share, ordinary line, FFA or `MULTI_DROP` copy, roll or master right, skinning right, or post-release right. V01–V08 are that refusal list. V01's money clause is the design prohibition in section 5, not a transcript of `isAllowedToLoot`. The helper is not written in this branch. The synthetic test models it. NOT TESTED in game.

Refresh is only partly available:

- VERIFIED release of the turn holder already calls `ForceValuesUpdateAtIndex(UNIT_DYNAMIC_FLAGS)` (`LootHandler.cpp:467`). The next values build re-runs `PatchValuesUpdate`, so a hook would see the cleared guid.
- VERIFIED `StoreLootItem` does not call `ForceValuesUpdateAtIndex` (`Player.cpp:13861-13961`). A packet already sent keeps the previous sparkle until some later update includes the field.
- `PlayerScript::OnPlayerLootItem` exists (`PlayerScript.h:458`) and runs on a successful store (`Player.cpp:13954`). A module could call the public `ForceValuesUpdateAtIndex(UNIT_DYNAMIC_FLAGS)` from there. That is still module-only. It is NOT TESTED, and it does not run when the store fails. Quest abandon and group leave do not dirty the field. Client handling of a flag change while the loot window is open is UNKNOWN.

### What this proves, and what it refutes

**Source-level, VERIFIED:** the pin has a per-viewer hook, a real dynamic-flags mark on both the fresh and the cached layout, an endian-consistent `read`/`put` pair, and a buffer that is the outgoing copy for that target. A future module can clear `0x0001` there without a core patch, if it pre-checks bounds and does not write creature state.

**Refuted as a sufficient fix:** the hook does not run for a packet that is not being built, so it cannot repair a sparkle already on the client until something dirties `UNIT_DYNAMIC_FLAGS`. It does not rewrite the `LootView` quest row. It does not run inside `StoreLootItem`. It does not see Playerbots loot selection (section 10). It is not proof of a correct entitlement predicate. CS01's warning in comment 6370148999 still stands: the API's existence is not a working hook. This branch does not add one.

## 7. Acceptance cases H01–H05

These IDs match CS01 PR #111 head `c1d5b39898d212f04b789e30723bca5126f1bcbf`, file `docs/research/A04-HUMAN-QUEST-LOOT-SOURCE-MATRIX.md`, plus H09 and H10 from CS03 comment `6370796678`. They describe current source. They are not desired end state, and they are not gameplay passes. H06 (other legitimate loot), H07 (no quest view and no other right), and H08 (missing or ineligible owner) stay defined in that PR so this note does not collide with them. V01–V08 below are the extra negative list from review `5631632097`, with V01 and V06 corrected for review `5632118504`.

| Case | Sparkle model | Quest row | Human autostore guard | Toward `StoreLootItem`? | Owner report |
| --- | --- | --- | --- | --- | --- |
| H01. Eligible non-holder, quest view, active protected owner | Yes. `hasItemFor` | `ALLOW_LOOT` | Deny, only if all 21 checks hold | No for that intercepted opcode | Shape of (a). NOT TESTED. |
| H02. Same, after `roundRobinPlayer` is cleared | Yes | `ALLOW_LOOT` (the row never consulted the guid) | Permit (check 12) | Candidate | Shape of (b). Not a proved transfer. |
| H03. `QuestRequired = 0` line the viewer can see (conditional or other `hasItemFor`) | Yes when `hasItemFor` or the viewer is the holder | No quest row. Conditional normal row uses `partySlotType` and can be `ALLOW_LOOT` (`LootMgr.cpp:1218-1219`) | Permit (check 14) | Candidate | Shape of (b) for a shared non-FFA line. |
| H04. Guard disabled or not loaded | Yes | `ALLOW_LOOT` | Permit (check 2) | Candidate | Either report. Loaded `Enabled` is UNKNOWN. Dist default is 0. |
| H05. `MULTI_DROP` / personal FFA copy | Yes, and that sparkle is legitimate | `ALLOW_LOOT` for the viewer's own copy | Permit (checks 18-19) | Candidate for that viewer's copy | Not theft. A fix that denies this cell is a false deny. |
| H09. Friend holds this corpse's turn | Yes. The holder arm returns true before `hasItemFor` (`PlayerStorage.cpp:5778-5779`) | `ALLOW_LOOT`. The quest loop still does not test the guid | Permit. `PermitPickup` returns true at `roundRobinPlayer == player->GetGUID()` (`QuestLootProtection.cpp:74-76`) | Candidate, by native turn design | The owner can experience this as "my quest loot". Native allocation is the rotating turn, not a named owner. Not a guard bug. NOT TESTED. |
| H10. Turn holder does not need the item; an eligible friend does | Yes when the friend has a quest view (`hasItemFor`) | `ALLOW_LOOT` for that friend | Permit. Check 21 fail-opens at `!owner->HasQuestForItem` (`QuestLootProtection.cpp:177-179`) | Candidate. Eligible clickers can each reach `StoreLootItem` for one shared copy (`Player.cpp:13942-13943` sets `is_looted` when `!freeforall`) | Native fail-open so the drop is not stranded. Distinct from the owner's expectation that the item stays theirs. NOT TESTED. |

H09 and H10 are valid native turn rules. They are not the owner's expected ownership, which would reserve the quest drop for one named player on every corpse. VERIFIED `Unit.cpp:13654-13662`: on a grouped creature kill, `UpdateLooterGuid(creature, true)` runs, and when `GetLooterGuid()` is set, the method is not `FREE_FOR_ALL`, and `FindPlayer` returns that player, that player becomes `looter` and `SetLootRecipient(looter)`. VERIFIED `Unit.cpp:13687`: `FillLoot` is called with that `looter`. VERIFIED `LootMgr.cpp:569`: grouped non-personal `FillLoot` sets `roundRobinPlayer = lootOwner->GetGUID()`. VERIFIED `Unit.cpp:13696-13701`: after a non-empty corpse, `UpdateLooterGuid(creature)` advances the group looter for a later corpse. VERIFIED `Group.cpp:2081-2140`: the advance walks member slots for the next player in reward distance. It is not a uniform random draw, and this note does not adopt a corpse-count ratio. Gameplay of who held the 23 Oct turn is UNKNOWN.

A true shared-item theft, meaning the guard permitting a non-holder while an eligible, present, still-needing turn holder is active, is not what H09 or H10 are. H01 is the cell where that conjunction can deny. H09 is the friend's own turn. H10 is the holder-no-longer-needs fail-open. POTENTIAL ISSUE for report (b) remains any of those source shapes. None is identified as the owner's reported corpse.

**Personal copies are UNSELECTED.** Setting `freeforall` so each eligible member receives an independent copy is an owner trade-off, not a chosen fix, and it is not implemented on this branch. VERIFIED `LootMgr.cpp:665-669`: the per-player loop does `LootItem& item = quest_items[i]` and then `OnPlayerBeforeFillQuestLootItem(player, item)`. That is the shared `quest_items` element, not a per-viewer copy. The signature is `PlayerScript::OnPlayerBeforeFillQuestLootItem(Player*, LootItem&)` (`PlayerScript.h:461`, dispatch `PlayerScript.cpp:390-392`). A mutation of that reference is visible to every later viewer and to `unlootedCount` (`683-691`). It cannot safely hide an item for one human. CS01 comment `6371087087` records the same limit: the hook may be a whole-corpse transformation point, and it is not a per-viewer row filter. `OnAfterLootTemplateProcess` (`LootMgr.cpp:563`) fires earlier, before `roundRobinPlayer` assignment. Its use as a module hook is not designed here. No flag is changed by this revision. NOT TESTED.

A sparkle clear that passes H01's visual half still leaves H01's `ALLOW_LOOT` row in place, and it leaves H02–H05 storage candidates in place. The same clear would be the wrong tool for H09 and H10: those viewers are allowed to take the copy under the native turn rule, so dropping their `LOOTABLE` bit would hide a corpse the pin says they may open. Visibility and award need separate acceptance. Both reports stay open until the item id, method, and whether one copy disappeared are known.

## 8. Negative cases V01–V08

These are refusal cases for a future per-viewer `LOOTABLE` clear, and for any broader deny. The synthetic model returns "do not clear" for each. That model is not the module. NOT TESTED in game.

| Case | Future clear refuses | Why, at `8daffdabe` |
| --- | --- | --- |
| V01. Money | Future clear must not drop the sparkle while this grouped viewer can still receive a share. Design prohibition, not native sparkle. | The non-holder arms do not call `hasItemForAll` (`PlayerStorage.cpp:5775-5793`). Gold alone does not sparkle that viewer. `HandleLootMoneyOpcode` still splits creature gold and does not read `roundRobinPlayer` (`LootHandler.cpp:122-275`, split at `216`). Gold makes `hasItemForAll` true (`LootMgr.cpp:894-897`). A clear that fired only because a quest line is protected would hide the money cue. |
| V02. Other ordinary items | Sparkle and the normal row the viewer may take | Conditional lines are visible without the round-robin omit (`LootMgr.cpp:1184-1222`). After release, under-threshold normal lines become visible (`1040-1049`). The guard already permits those slots (check 14). |
| V03. Free-for-all | Method and per-player FFA copies | `isAllowedToLoot` returns true (`PlayerStorage.cpp:5773-5774`). FFA rows are `ALLOW_LOOT` (`LootMgr.cpp:1178`). The guard permits the method (check 8) and `freeforall` lines (check 18). |
| V04. `MULTI_DROP` | The viewer's own copy | `freeforall` storage does not consume the shared line (`Player.cpp:13942-13943`). Same permit as V03's item flag (checks 18-19). |
| V05. Roll | Roll UI and the winner | Over-threshold lines make `isAllowedToLoot` true for group and need-before-greed (`PlayerStorage.cpp:5790-5791`). `follow_loot_rules` quest lines use roll slot types (`LootMgr.cpp:1142-1147`). `CanRollOnItem` depends on `AllowedForPlayer` (`Group.cpp:1117`). The guard permits `follow_loot_rules` and `is_blocked` (check 18). |
| V06. Master loot | Future clear must not drop the sparkle for a master-loot group. Do not treat every viewer as the master looter. | `isAllowedToLoot` returns true for every recipient-group member under `MASTER_LOOT`, not only the master looter (`PlayerStorage.cpp:5772-5774`). `SendLoot` gives `MASTER_PERMISSION` only to the master looter and `RESTRICTED_PERMISSION` to the others (`Player.cpp:8329-8330`). The master looter's ordinary quest row is `LOOT_SLOT_TYPE_MASTER`. A restricted viewer's ordinary `!follow_loot_rules` quest row is `LOOT_SLOT_TYPE_ALLOW_LOOT` (`LootMgr.cpp:1097`, `1154-1155`). `CMSG_LOOT_MASTER_GIVE` is outside the packet guard (`LootHandler.cpp:478-541`). The guard permits the method (check 8) for both viewers. |
| V07. Release | Sparkle and pickup once the guid is cleared | Check 12 permits. `LootHandler.cpp:459-467` clears the guid and forces a dynamic-flags update. A clear that sticks after release hides a corpse the core just reopened. |
| V08. Skinning, and stale quest or group | Skinning for the recipient; decisions from live state | `UNIT_FLAG_SKINNABLE` is `0x04000000` on `UNIT_FIELD_FLAGS` (`UnitDefines.h:283`), a different word from `UNIT_DYNFLAG_LOOTABLE`. `AllLootRemovedFromCorpse` sets the unit flag when skinning loot exists (`Creature.cpp:3176-3182`). `LOOT_SKINNING` is loot type 6 (`LootMgr.h:85`) and `isAllowedToLoot` allows only the recipient (`PlayerStorage.cpp:5761-5762`). Bots also notice `UNIT_FLAG_SKINNABLE` directly (`LootObjectStack.cpp:73-79` at `e88cc409`). A stale "still on the quest" or "still in the group" snapshot must not clear or deny: the live checks are `HasQuestForItem`, `GetGroup()`, and `GetLootRecipientGroup()` (`QuestLootProtection.cpp:134-179`, `PlayerStorage.cpp:5764-5768`). |

## 9. Matrix, current source only

"Deny" means the current module returns false for `CMSG_AUTOSTORE_LOOT_ITEM`. "Permit" means it returns true and human `StoreLootItem` runs. Sparkle is the `isAllowedToLoot` result for a non-holder. This grid is group loot, round robin, and need-before-greed. Free-for-all and master loot permit every item class (check 8). Master loot sparkles for every recipient-group member (`PlayerStorage.cpp:5772-5774`), including a restricted viewer. That viewer's ordinary quest row is `ALLOW_LOOT`, not `MASTER`. See section 4. H09 is the "own turn" column. H10 is the active-turn column with check 21 already failed open.

| Item class | Active turn, non-holder | Own turn or after release | Sparkle for the non-holder during the active turn |
| --- | --- | --- | --- |
| One-copy `quest_items` on a creature corpse | Deny | Permit | Yes, via `hasItemFor` |
| `MULTI_DROP` / `freeforall` | Permit | Permit | Yes, legitimate copy |
| `follow_loot_rules` | Permit | Permit | Yes when the viewer has a quest view or an over-threshold line |
| `count != 1` | Permit | Permit | Yes when a quest view exists |
| `QuestRequired = 0` normal, no conditions | Permit | Permit | No, while the turn is active and the line is under threshold. The window omits it. The guard would still permit a packet. |
| `QuestRequired = 0` conditional | Permit | Permit | Yes, `hasItemFor` on the conditional view. The window shows it. |
| Gameobject, item, bones, pickpocket, skinning loot type, non-corpse | Permit | Permit | Skinning uses the recipient test and `UNIT_FLAG_SKINNABLE`. The packet guard does not cover it (checks 9-11). |

No cell is the diagnosed cause of the owner's reported corpse.

## 10. Bot safety, separate from the human sparkle

The previous revision of this note said `StoreLootAction`'s queued packets enter `WorldSession::Update` and therefore `CanPacketReceive`. That claim is withdrawn. It is false at both Playerbots SHAs below.

VERIFIED `e88cc409` and `d750b4b`, identical bytes, `src/Bot/PlayerbotMgr.cpp:308-320`:

```cpp
while (std::unique_ptr<WorldPacket> packet = session->NextQueuedPacket()) {
    ...
    opHandle->Call(session, *packet);
}
```

There is no `CanPacketReceive` call on that path. VERIFIED `WorldSession.cpp:312-313`: `SendPacket` returns immediately when `m_Socket` is null, after `OnPacketSent`. VERIFIED `WorldSession.cpp:414`: incoming session update does not dequeue without `m_Socket`. A human viewer-field filter never runs for a bot that does not receive that update.

VERIFIED `LootAction.cpp` (same lines on both SHAs):

- `OpenLootAction::DoLoot` `124-128` reads raw `UNIT_DYNFLAG_LOOTABLE` and queues `CMSG_LOOT`. The direct handler call on the next line is commented out.
- `StoreLootAction::Execute` `408-426` autostores slots marked `LOOT_SLOT_TYPE_ALLOW_LOOT` or `LOOT_SLOT_TYPE_OWNER`.
- `469-472` queues `CMSG_AUTOSTORE_LOOT_ITEM`. The direct `HandleAutostoreLootItemOpcode` call is commented out. The queue is drained by `HandleBotPackets`, so the comment does not put the bot on the human hook.
- `490-493` queues `CMSG_LOOT_RELEASE`.
- `IsLootAllowed` `520-538` returns true when the item is a required quest item in the bot's log.

VERIFIED `LootObjectStack.cpp:52-79` and `:286-307`: `LootObject::Refresh` treats server `UNIT_DYNFLAG_LOOTABLE` and `UNIT_FLAG_SKINNABLE` as enough to remember the corpse. `IsLootPossible` then calls `bot->isAllowedToLoot(creature)`, the same broad predicate as the human sparkle, with a skinning exception. A per-viewer `OnPatchValuesUpdate` clear does not change those reads.

`OnAllowedForPlayerLootCheck` is the hook that does run for bots, because `LootItem::AllowedForPlayer` calls it (`LootMgr.cpp:465-466`) and `StoreLootItem` calls `AllowedForPlayer` (`Player.cpp:13888-13891`). VERIFIED `GlobalScript.h:98` and `GlobalScript.cpp:107-109`: the virtual receives `(Player const*, ObjectGuid source)` and returns false by default. `CALL_ENABLED_BOOLEAN_HOOKS` turns a true return into "not allowed". The hook is item-blind. The same `AllowedForPlayer` call is on the roll path (`Group.cpp:1117`), on `FillQuestLoot` (`LootMgr.cpp:671`), and on loot display (`1004` and the other `AllowedForPlayer` sites in `LootView`). A blanket true return would deny rolls, gold is unaffected by this hook, and FFA and ordinary lines on that corpse would fail `AllowedForPlayer` together. No blanket denial.

Owner preference, recorded from the review addendum: module-only fixes, and no edits inside other modules. Any Playerbots change or core change needs explicit owner approval. This note does not propose one. Until that approval, bots are unprotected by `CanPacketReceive`. Whether the 23 Oct group contained bots is UNKNOWN. Local Playerbots patches are UNKNOWN.

IP at `dd96f2b` does not award corpse loot and does not register these hooks (pin table above). It can still change quest status, which changes `HasQuestForItem` and therefore check 21. Whether it did so on 23 Oct is UNKNOWN.

## 11. Data still UNKNOWN

No server change is required to answer these. They are unanswered.

1. Item entry and quest id. Whether the first person's copy vanished or both people kept one.
2. Creature or object entry, and the loot method shown in the group frame.
3. Humans only, or Playerbots as well. Who held the turn when the friend clicked.
4. Whether the turn holder's loot window was still open. Same map and instance or not.
5. Worldserver lines containing `QuestLootProtection` for that attempt. Silence does not identify which permit fired.
6. Loaded `Enabled` and `Debug`, plus `git rev-parse HEAD` and `git status --short` for the module, Grimfeather core, Playerbots, and Individual Progression. The two local Playerbots patches should appear in that status.

## 12. Synthetic test evidence

Command, from the module root, Python 3 unittest, no core checkout mounted:

`python3 -m unittest discover -s tests -p 'test_ql109_cs02_failopen_and_sparkle.py' -v`

Recorded local result on Python 3.12.3: 32 tests, OK, exit code 0. Verbose names:

```
test_allowed_for_player_hook_is_item_blind_and_denies_on_true ... ok
test_already_sent_buffer_keeps_sparkle_until_rebuild ... ok
test_bot_dispatch_bypasses_the_human_guard ... ok
test_clear_does_not_set_a_missing_lootable_bit ... ok
test_clear_is_false_positive_only_on_a_copy ... ok
test_dynamic_flags_position_on_fresh_and_cached_layouts ... ok
test_every_guard_miss_fail_opens ... ok
test_h01_sparkle_and_allow_loot_row_while_packet_denies ... ok
test_h02_release_fail_opens_storage_candidate ... ok
test_h03_quest_required_zero_bypasses_guard ... ok
test_h04_disabled_guard_does_not_stop_native_candidate ... ok
test_h05_multi_drop_is_not_modeled_as_theft ... ok
test_h09_friend_turn_is_native_design_not_named_ownership ... ok
test_h10_holder_without_need_lets_eligible_friend_pick_up ... ok
test_module_source_is_still_packet_only ... ok
test_named_fail_open_paths_hand_off_to_native_storage ... ok
test_negative_restricted_viewer_ordinary_quest_row_is_allow_loot ... ok
test_personal_copy_freeforall_policy_is_unselected ... ok
test_positive_master_looter_ordinary_quest_row_is_master ... ok
test_quest_row_ignores_active_round_robin_holder ... ok
test_research_doc_keeps_both_reports_and_drops_the_personal_name ... ok
test_skinning_flag_word_is_not_the_dynamic_flags_word ... ok
test_sparkle_clear_does_not_change_row_or_packet_verdict ... ok
test_v01_money_refuses_clear ... ok
test_v02_ordinary_item_refuses_clear ... ok
test_v03_ffa_refuses_clear ... ok
test_v04_multi_drop_refuses_clear ... ok
test_v05_roll_refuses_clear ... ok
test_v06_master_refuses_clear ... ok
test_v07_release_refuses_clear_and_refuses_deny ... ok
test_v08_skinning_and_stale_snapshot_refuse_clear ... ok
test_workflow_is_read_only_and_uploads_nothing ... ok

Ran 32 tests in 0.002s

OK
```

The run locks the model and the module source contract. It does not mount Grimfeather `8daffdabe`, Playerbots, or IP, and it does not execute `QuestLootProtection.cpp`. A pass here is NOT TESTED for the owner's reported corpse, for a client sparkle, or for a stored item. PR #111's suite is a different file and was not executed in this revision.

Existing `tests/test_quest_loot_protection.py` was not the subject of this revision. Its earlier 30-test run on `main` remains a source-and-model run only. It was not re-executed for this note. NOT TESTED against Grimfeather.

## 13. Workflows, and what this revision did not do

`.github/workflows/naxx-a04-ql109-cs02-model.yml` checks out `ref: ${{ github.event.pull_request.head.sha || github.sha }}` with `persist-credentials: false` and permission `contents: read`. The next step asserts `git rev-parse HEAD` equals that SHA, so a `pull_request` run certifies the branch head rather than the synthetic merge commit. It then runs the unittest above. It has no `upload-artifact`, `actions/upload`, `actions/download`, or release step. Push and `pull_request` path filters list only this note, the test, and that workflow. Whether a given Actions run checked out this commit is a property of that run's log, not of this paragraph. NOT TESTED until that log is read.

NOT TESTED: the owner's reported corpse, any client, any bot in a group, loot-window icons, release timing, corpse expiry, a linked worldserver, SQL, or item_template flags. No database was opened.

No edit to `src/`, SQL, config, PR #89, PR #105, core, Playerbots, or Individual Progression. No implementation of `OnPatchValuesUpdate`. No merge, tag, or release. PR #110 stays a draft.

## 14. Corrections relative to head `1b4fc9a`

| Earlier text | Replacement |
| --- | --- |
| Intro treated group members as able to loot each other's protected drops, and the verdict looked for one bidirectional cause. | Reports (a) and (b) are both kept. Item, method, and copy semantics stay UNKNOWN. Theft is not code-proved. The human guard is not claimed to have worked. |
| No first-class sparkle section. | Section 5, with `PatchValuesUpdate`, `isAllowedToLoot`, and `hasItemFor` at the pin. |
| No `OnPatchValuesUpdate` feasibility pass, no V01–V08. | Section 6 and section 8. The hook can express a per-viewer clear. It is not a sufficient fix and it is not implemented. |
| `StoreLootAction` was described as entering `CanPacketReceive`. | Withdrawn. `HandleBotPackets` calls `opHandle->Call` and skips the hook. Section 10. |
| The legend named a person as the looter of the corpse. | "owner's reported corpse". |
| Loot-window `ALLOW_LOOT` was mentioned inside generation notes. | Section 4 states the quest-row asymmetry as its own surface, separate from sparkle and from the packet verdict, matching CS01 `6370540733` and PR #111. |

## 15. Corrections relative to head `3cc7292`

These answer CS01 re-review `5632118504`. No `src/` edit. Gameplay remains NOT TESTED.

| Earlier text at `3cc7292` | Replacement |
| --- | --- |
| `quest_row_slot_type` and V06 treated every `MASTER_LOOT` viewer as master permission, so an ordinary quest row was `MASTER`. | `viewer_is_master_looter` selects `MASTER_PERMISSION` versus `RESTRICTED_PERMISSION`. Positive case: the master looter's ordinary row is `MASTER`. Negative case: a restricted viewer's ordinary `!follow_loot_rules` row is `ALLOW_LOOT`. Section 4 and V06. VERIFIED at `Player.cpp:8329-8330` and `LootMgr.cpp:1094-1157`. |
| V01 read as "must keep the sparkle because of money", close to a claim that core sparkles for gold. | V01 is a future design prohibition. The non-holder GROUP/NBG/RR arms do not call `hasItemForAll`. Section 5. VERIFIED at `PlayerStorage.cpp:5775-5793`. |
| The workflow checked out with `actions/checkout` and no `ref`. | `ref: ${{ github.event.pull_request.head.sha || github.sha }}` plus `git rev-parse HEAD` equality. No upload step. Section 13. |
| H09 and H10 were not in this note. Personal-copy `freeforall` was not marked as an owner decision. | H09 is the friend's own turn, a native permit. H10 is the holder who does not need the item, a native fail-open. Both differ from named-player ownership. Personal-copy policy is UNSELECTED and not implemented. `OnPlayerBeforeFillQuestLootItem` receives shared `quest_items[i]` (`LootMgr.cpp:667-669`) and cannot safely hide one viewer's row. Section 7. See CS03 `6370796678` and CS01 `6371087087`. |
