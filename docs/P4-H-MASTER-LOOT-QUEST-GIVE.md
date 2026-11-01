# P4-H — Master Loot quest-slot give (policy-neutral, default OFF)

**Status: DRAFT runtime change, default OFF.** Not merged, not enabled, and
not tested in the client. This is a child of #270 (`e3a4aa2`). CS01 assigned
it (#143, 6559834710) with Information's acceptance scenario (6559634205),
and I claimed it in 6559852029.

## The defects in pinned Grimfeather `8daffda`

`WorldSession::HandleLootMasterGiveOpcode` (`LootHandler.cpp` L478–573)
handles the leader's "give to player" click. For a **quest** slot it has three
problems:

- **It resolves the slot with a global index:**
  `quest_items[slotid - items.size()]`. But the `LootView` serializer numbers
  each viewer's quest rows by position in that viewer's **own** quest list
  (`LootMgr.cpp`: `l.items.size() + (qi - q_list->begin())`).
- **It tells every looter the leader's slot number:** `NotifyItemRemoved(slotid)`.
  `Player::StoreLootItem` uses the per-viewer `NotifyQuestItemRemoved(qitem->index)`
  for the same kind of item (`Player.cpp` L13922).
- **It never checks whether the item was already looted.**

| | Scenario | Stock result |
|---|---|---|
| **D3** (Information's case) | Leader M has quest rows Q0 and Q1; A has only Q1. M gives Q1 (M's slot `N+1`) to A. | A gets Q1, but **A is told to remove slot `N+1`**, which A doesn't have. A's Q1 row at `N+0` stays in the open window. |
| **D1** | The master-loot role moves to M **after** the corpse filled. M needs only Q1; A needs Q0 and Q1. M clicks Q1 (M's `N+0`). | **A is given Q0**, not the clicked Q1. M is told to remove the Q1 row, which is still on the corpse. |
| **D1, no row** | Same role change; M needs nothing, so M is shown no quest row. A crafted give of slot `N+0`. | A is given Q0, an item the leader is not shown. |
| **D2** | A autostores its own Q1. M's window is stale and M gives the same Q1. | **A second copy is created.** `StoreLootItem` leaves `count` intact and the handler doesn't check `is_looted`. |

**Why D1 needs a role change.** Pinned `FillQuestLoot` (`LootMgr.cpp`
L663–676) gives whoever is master looter **when the corpse fills** a row for
every quest item. That player's slots therefore match the global indices.
Another player's list holds only their own items, and it is not rebuilt if the
role moves to them later. The claim in 6559852029 described D1 without this
condition; the harness showed it, and this document corrects it.

## The change

`src/Systems/MasterLootQuestGive.cpp` hooks `ServerScript::CanPacketReceive`
for `CMSG_LOOT_MASTER_GIVE`.

**Where it runs.** The opcode is `PROCESS_THREADSAFE`, so it is processed in the
map update, and pinned `WorldSession::Update` calls the hook immediately
before the handler. The packet is `const`, so a wrong slot can't be corrected
in place. Instead:

1. **Same checks, same order.** The script repeats the handler's own checks
   (master looter, loot method, target found, loot GUID, raid and no-play-time,
   loot found, slot range). If **any** of them fails, the request goes to the
   core unchanged, so the core sends its own error.
2. **Normal slots go to the core.**
3. **Quest slots are given here** (`MasterLootQuestGive.h`):
   - Use the **leader's own row**, mapped exactly as `Loot::LootItemInSlot` maps
     a requester's slot. Its "allowed for the requester" check is skipped,
     because the leader gives to someone else; the target is checked as in
     stock.
   - Refuse with `EQUIP_ERR_ALREADY_LOOTED` if there is no such row, or the row
     or the item is already looted.
   - Refuse a free-for-all quest copy with `LOOT_ERROR_MASTER_OTHER`. Every
     player has their own copy, and the leader is shown it as `ALLOW_LOOT`,
     never as a Master Loot row.
   - Otherwise run the stock steps in the stock order, with the stock error
     mapping:
     1. `CanStoreNewItem`;
     2. `AllowedForPlayer(target)`;
     3. `StoreNewItem` with the allowed looters;
     4. `SendNewItem`;
     5. `UpdateLootAchievements`;
     6. `count = 0` and `is_looted = true`;
     7. **`NotifyQuestItemRemoved(row.index)`**;
     8. `--unlootedCount`.

   The packet is then consumed.

**Unchanged.** Who may give, and to whom, is decided exactly as in stock. Stock
WoW group-loot parity is the owner's choice (#117 clarification). The change
has no SQL, no core edit and no new rights.

**Config.** `NaxxramasCore.MasterLootQuestGive.Enabled` defaults to **0**. It is
read on the world thread and published through an atomic.

## Evidence (original pinned bodies, 29 checks)

**How the stock path is run.** `build_master_loot.py` extracts the **original
tail** of the pinned handler, from the slot range check to the end of the
function, byte for byte with a `#line` marker:
- It checks the `LootHandler.cpp` blob SHA (`a18781f…`) first.
- Only the three `_player->SendLootError(lootguid, …)` calls are redirected to
  a recorder, because the #262 harness `Player` has no `SendLootError`.
- Two `InventoryResult` values the #262 stub enum lacks are defined from
  pinned `Item.h` L57 and L64. The build checks those lines.

The loot comes from the #262 harness: the original `FillLoot`, `LootView`,
`LootItemInSlot`, `NotifyItemRemoved`, `NotifyQuestItemRemoved` and
`StoreLootItem` bodies.

| Case | Stock (original tail) | Module |
|---|---|---|
| D3: M has Q0+Q1, A has Q1, give Q1 to A | A gets Q1; A and M are both told to remove slot 1 | A gets Q1, M nothing; **A told slot 0, M told slot 1**; item looted, count 0, `unlootedCount` −1; M's reopened window shows only Q0 |
| D1: role moved; M has Q1 only | **A gets Q0**, M told to remove Q1, which is still there | **A gets Q1**; M told 0, A told 1; A can still loot Q0 |
| D1, no row | A gets an item the leader is not shown | refused; nothing awarded or flagged |
| D2: A autostored Q1 first | **second copy given** | refused, already looted |
| Inventory full / target can't use / both | `MASTER_INV_FULL` / `MASTER_OTHER` / `MASTER_OTHER` | identical errors; nothing awarded, flagged or notified |
| Normal slot | — | left to the core, nothing changed |
| FFA quest copy | — | refused; both copies still lootable by their owners |
| Leader at fill time, both need both | — | same result as stock |

**Fixture checks.** These confirm the scenes are as described: quest item
order, each viewer's slots, the leader-at-fill gets every row, and A
autostored first.

**Mutants.** There are 9 must-fail mutants of the real header, all caught:
- stock leader-slot notification;
- stock global index;
- shared looted flag not checked;
- FFA copy given;
- item not marked looted;
- `unlootedCount` not lowered;
- inventory full reported as other;
- target eligibility skipped;
- normal slots taken over.

**Pinned seam facts.** `tests/test_p4_h_master_loot.py` checks blob SHAs and
exact text for:
- the handler's checks and the three defect lines;
- serializer numbering;
- the `FillQuestLoot` master-looter rows;
- `NotifyQuestItemRemoved`;
- `StoreLootItem`'s per-viewer notification;
- the hook immediately before the handler;
- `PROCESS_THREADSAFE`, and the map filter.

A source contract checks:
- the order of the pass-through checks;
- that the header's only state writes are `count`, `is_looted` and
  `unlootedCount`;
- that the header has no `NotifyItemRemoved` call.

**Regression and CI.** H2 (21), H1 (36), #264 (24) and #262 (71) still
pass. CI compiles `MasterLootQuestGive.cpp` against pinned Grimfeather, links
a full Worldserver, and checks the defined symbols.

## Limits

- **Not changed:**
  - normal-slot gives, including a repeated give of a normal slot (stock zeroes
    `count` on the first give);
  - group rolls;
  - autostore, which H1 covers;
  - the Master Loot candidate list (`SMSG_LOOT_MASTER_LIST`).
- **Gameobject loot.** It goes through the same path, but the harness only
  builds creature loot.
- **Hook side effect.** The give happens inside a hook named `CanPacketReceive`,
  on the same thread and immediately before the handler would run. Another
  module's later `CanPacketReceive` hook for this opcode is not consulted when
  this one consumes the packet.
- **Not exercised:** the client, the real handler's earlier checks (they are
  passed through, not reimplemented), real storage, achievements, and the
  owner's binary and database.

## Rollback

Leave `NaxxramasCore.MasterLootQuestGive.Enabled = 0`, which is the default.
To remove the change entirely, revert this branch.
