# P4-H follow-on — gameobject loot and packet-hook interop (tests only)

**Status: DRAFT, tests and docs only.** This branch changes no module source.
It tests #272 (`9d6f5a3`) exactly as it is, and the config default stays OFF.
CS01 assigned it (#143, 6560034135), and I claimed it in 6560277301.

**Result: no new defect found.** #272 needs no change for gameobject loot or for
the other packet hooks in the pinned build.

## 1. Seam equivalence: stock handler checks vs the module's pass-through

Both sides are compiled from the original text:
- **Stock:** `build_interop.py` extracts the **original prefix** of pinned
  `HandleLootMasterGiveOpcode` byte for byte, under a blob-SHA check. The
  prefix is everything before the slot range check.
- **Module:** it also extracts #272's **original** `PermitMasterGive` and
  `CanPacketReceive` bodies from `src/Systems/MasterLootQuestGive.cpp`.

Both are compiled against one stub environment (`tests/p4_h_interop/seam_env.h`)
that records every reply and every call into `GiveQuestSlot`. Each request runs
through both.

| Request | Stock prefix | Module |
|---|---|---|
| No group / not master looter / Group Loot / Need Before Greed / Free for All | `DIDNT_KILL` | passes through; no call, no reply |
| Target not found | `PLAYER_NOT_FOUND` | passes through |
| Loot GUID ≠ the leader's open loot | `DIDNT_KILL` | passes through |
| Not in raid / target out of play time | `MASTER_OTHER` | passes through |
| Creature or gameobject not found | silent return | passes through |
| Creature or gameobject loot, quest or normal slot | reaches the tail | calls `GiveQuestSlot` with the **same** leader, target, loot object and slot |
| Slot out of range | the tail's range check returns | passes through |

So wherever the core rejects a request, the module lets the core reject it
with the core's own reply. A non-Master-Loot method stays stock.

**Reply mapping** (`PermitMasterGive`):

| `GiveQuestSlot` outcome | Module reply |
|---|---|
| `PassThrough` | lets the core run |
| `Given` | consumes the packet, no reply |
| `AlreadyLooted` | consumes the packet and sends `EQUIP_ERR_ALREADY_LOOTED` |
| `Error` | consumes the packet and sends `SendLootError` with the loot GUID and the code |

**Packet filter** (`CanPacketReceive`). These are left to the core:
- module disabled;
- another opcode;
- a packet shorter than 17 bytes;
- no player, or player not in world.

The fields are read in the handler's order (loot GUID, slot, target), and
trailing bytes are ignored as the handler ignores them.

**Totals:** 28 checks. There are 12 must-fail mutants of the real `.cpp`, all
caught. One of them, "missing target not passed through", is caught by a
**crash** (a null target is dereferenced), which is what a real Worldserver
would do as well.

## 2. Gameobject (chest) loot on the original loot bodies

Pinned `Player::SendLoot` (gameobject branch) fills chest loot on the
**first open**:

```
bool groupRules = (group && chest && chest.groupLootRules);
loot->FillLoot(lootid, LootTemplates_Gameobject, this, !groupRules, false, go->GetLootMode(), go);
```

- **Group-rules chests** fill like a corpse. Group members in range of the
  chest get lists, and the master looter at fill time gets a row for every
  quest item.
- **Other chests** fill personally: only the opener gets a quest list.
- **Either way**, a grouped viewer under Master Loot gets `MASTER` or
  `RESTRICTED` permission.

The harness (`go_loot_harness.cpp`) fills the chest with exactly that call:
the original `FillLoot` with `personal = !groupRules` and a chest as
`lootSource`. It then runs the #272 original handler tail (stock) against the
real #272 header.

| Scene | Stock | #272 |
|---|---|---|
| Group-rules chest, D3 (M has every row; A has Q1 only) | A told slot 1, which A doesn't have | only A gets Q1; **A told 0, M told 1** |
| Group-rules chest, D2 (A autostored Q1 first) | second copy given | refused, already looted |
| Personal chest opened by M | award correct; A, who has no row, is also sent slot 1 | same award; only the row holder is notified |
| Personal chest opened by A (M is shown no quest row) | a hand-made slot gives an item M is not shown | refused; A still loots its own row |
| Normal slot | — | left to the core |

The personal chest opened by A can only be reached with a hand-made packet,
because the leader's client shows no quest row to give. Refusing it doesn't
change anything a normal client can do.

**Totals:** 15 checks, including two zero-count template negatives. There are 3 must-fail header mutants, all caught:
- leader's slot sent to every looter;
- shared looted flag not checked;
- normal slots taken over.

## 2a. Zero-count quest template — original-source negative

A bounded, **synthetic malformed-template** case now exercises the original
`Loot::FillLoot` → `Loot::AddItem` path with `mincount=maxcount=0`.
This bypasses database `LootStoreItem::IsValid` (so it is NOT a claim that
real loot-table data permits this row). The pinned original `AddItem`
computes `count=0`, `stacks=0`, and the item-append loop executes zero
times. **Neither player receives a quest loot row**, and a crafted Master
Give request is refused without award, counter update, packet notification
or `unlootedCount` underflow.

The extra two executable GO checks demonstrate that **ordinary template
generation cannot produce** `item.count=0` with both looted flags unset
because it produces **no item at all**. They do NOT prove an installed
custom `OnAfterLootTemplateProcess` script, memory corruption or another
module could never rewrite a previously generated positive count to zero.
That separate artificial state remains an unproven possibility, not a
reported owner-server defect. No runtime source or stock loot policy changed.

**Not modelled:**
- `Group::MasterLoot` and `UpdateLooterGuid`, which are not on the give path;
- the group-rules `FillNotNormalLootFor(allowedLooters)` call, which never
  refills a list that already exists;
- chest traps, money and fishing loot;
- whether a given chest has `groupLootRules`, which is world data.

## 3. Other packet hooks in the pinned build

Pinned `ScriptMgr::CanPacketReceive` → `CALL_ENABLED_BOOLEAN_HOOKS`
(`ScriptMgrMacros.h` L76–80):
- calls scripts in `EnabledHooks` order, which is registration order
  (`ScriptMgr.h`, `AddScript`);
- **stops at the first `false`**.

So when #272 consumes a quest-slot give, scripts registered after it don't see
that packet. Every implementer in the pinned build is pinned by blob SHA and
text:

| Script | Acts on | Effect of a consumed `CMSG_LOOT_MASTER_GIVE` |
|---|---|---|
| `PlayerbotsServerScript` (Playerbots `037c014`) | forwards every master packet to `HandleMasterIncomingPacket` and returns `true` | none. `AddPacket` keeps only opcodes with a handler, and nothing in Playerbots `src/` mentions `CMSG_LOOT_MASTER_GIVE` |
| `PlayerbotsSecureLoginServerScript` | `CMSG_PLAYER_LOGIN` only | none |
| `PlayerbotsSelfBotAfkServerScript` | `CMSG_LOGOUT_REQUEST` only | none |
| `NaxxramasQuestLootProtection`, `NaxxramasQuestLootPickupAuthorizationPacket` (this module) | `CMSG_AUTOSTORE_LOOT_ITEM` only | none |
| Individual Progression `4ff4b5f` | no `CanPacketReceive` | — |
| Core content scripts (`src/server/scripts`) | no `CanPacketReceive` | — |

**Load order therefore doesn't matter** for this opcode. The tests check what
each script does rather than assume an order. For reference, static modules
register in the order of the module directory listing (`ConfigureModules.cmake`
`file(GLOB …)`); this isn't relied on.

**Bots.** A bot's own packets go through `PlayerbotHolder::HandleBotPackets`
(Playerbots `PlayerbotMgr.cpp` L308–321), which calls `opHandle->Call`
directly, not through this hook (pinned). A bot acting as master looter is
therefore stock, as the #268 limits already say.

## Results by level

| Level | Result |
|---|---|
| Local (g++ and clang++) | Previous developer baseline: 8 tests, 28 + 13 checks, 15/15 mutants. **This new 15-GO-check head has not yet been rerun or verified locally/hosted.** |
| Hosted native | the workflow runs the same steps on both compilers. **Not yet run** |
| Full Worldserver link | covered by #272's own workflow (no source change here) |
| In game | **none**. Gameplay acceptance is still 0/5 |

## Rollback

Tests only. Revert the branch to remove it.
