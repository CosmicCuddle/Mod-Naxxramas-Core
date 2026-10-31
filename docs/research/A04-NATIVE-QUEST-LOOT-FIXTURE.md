# A04/P4 — extracted pinned-source native C++ quest-loot harness

**Status: DRAFT test-only harness. Not a fix, not a Worldserver test, not a
"native Core regression", not the owner's server.** Nothing in the module
runtime, config, SQL, DBC, Core, Playerbots or Individual Progression changes.

Assignment: CS01 on #143 (6546297859, selected in 6546374798), claimed in
6546954986. The base is `main` `80e9de1`. Coordination is in A04 #109, and the
worksheet is in #255 (`docs/A04-P4-BANKED-QUEST-LOOT-REGRESSION-FIXTURE.md`).

## What this is

The **original** loot and quest function bodies from Grimfeather
`8daffdabe9202c228e45d833c9a1d399597a15cd` are compiled and run with g++ and
clang++. Two human players, A and B, are in one party.

- **Pinned headers are used unchanged:** `LootMgr.h`, `ObjectGuid.h`,
  `ByteBuffer.h`, `SharedDefines.h`, `RefMgr.h`, `ItemTemplate.h` and
  `Errors.h`. So `Loot`, `LootItem`, `QuestItem` and `LootView` are the real
  types. Only `ConditionMgr.h` is replaced, by a 2-line stand-in
  (`ConditionList` and a `WorldObject` forward declaration).
- **Bodies are copied byte for byte.** `tests/a04_native/prepare_pinned.py`
  first checks 17 pinned git blob SHAs. It then copies each body starting at
  its exact signature line (which must occur exactly once) and ending at the
  first line that is exactly `}`. A `#line` marker in front of each body points
  compiler messages at the original file and line.

**Executed original definitions (22 loot/quest + 6 link support):**

| File (pinned) | Definitions |
|---|---|
| `Loot/LootMgr.cpp` | `LootItem::LootItem(LootStoreItem)`, `LootItem::AllowedForPlayer`, `LootItem::AddAllowedLooter`, `Loot::AddItem`, `Loot::FillLoot`, `Loot::FillNotNormalLootFor`, `FillFFALoot`, `FillQuestLoot`, `FillNonQuestNonFFAConditionalLoot`, `NotifyItemRemoved`, `NotifyQuestItemRemoved`, `LootItemInSlot`, `GetMaxSlotInLootFor`, `hasItemForAll`, `hasItemFor`, `hasOverThresholdItem`, `operator<<(LootItem)`, `operator<<(LootView)` (the `SMSG_LOOT_RESPONSE` body) |
| `Entities/Player/Player.cpp` | `Player::StoreLootItem` |
| `Entities/Player/PlayerQuest.cpp` | `Player::HasQuestForItem`, `Player::ItemAddedQuestCheck`, `Player::ItemRemovedQuestCheck` |
| `Entities/Object/ObjectGuid.cpp`, `shared/Packets/ByteBuffer.cpp` | support only: `ObjectGuid::Empty`, `Global`, `MapSpecific`; `ByteBuffer::append`, `put`; `ByteBufferPositionException` ctor |

**Fixture data comes from the pinned public SQL.** It is parsed as text and no
SQL is executed. The rows are:
- quest **922** (and prerequisite 918, from `quest_template_addon`);
- item **5168** (`Flags=0`, so not MULTI_DROP);
- loot row **2030/5168** (`QuestRequired=1`, `Chance=100`);
- MULTI_DROP control item **1931** and quest **176**.

No owner or private data is used. Two items are synthetic and labelled so in
the code: an ordinary junk item (900001) and the T5 two-slot quest item/quest
(900002/900003).

## How the harness tells original code from a reimplementation

1. **Blob and fact checks.** 17 blob SHAs are checked, plus 11 pinned
   single-line facts the stubs rely on. Among them are the quest constants and
   status values, the load-time `QUEST_SPECIAL_FLAGS_DELIVER`, and the stock
   "no enabled script" boolean-hook default of `true`. Three exact multi-line
   **call orders** are also checked: `StoreNewItem`, and `SwapItem` bag→bank
   and bank→bag.
2. **Byte-for-byte test.** The test re-reads every body from the pinned file
   and requires it verbatim in the generated file.
3. **No loot logic in the harness.** A test scans the driver and stubs: they
   may not define any `Loot::`/`LootItem::`/tested `Player::` member, and may
   not write `is_looted`, `is_counted`, `unlootedCount`, quest lists and so on.
   Planting `LootItem::AllowedForPlayer` or `l.unlootedCount = 0` in the
   harness fails it.
4. **10 must-fail mutants**, each applied to the **extracted original text**,
   never to the harness. Every one turns at least one check red.

| Mutant on original text | First failing check |
|---|---|
| view no longer sets shared `item.is_looted` (LootMgr.cpp L1116–1119) | `T1.WITNESS_B_view_marks_shared_item_looted` |
| `showInLoot` counts bags only (PlayerQuest.cpp L2375) | `T1.B_view_shows_no_row` |
| `AllowedForPlayer` skips the quest check | `T0.only_A_in_quest_list` |
| `StoreLootItem` skips `AllowedForPlayer` | `T3.WITNESS_H2_B_store_denied_with_release` |
| `StoreLootItem` ignores shared `is_looted` (Player.cpp L13870) | `T1.WITNESS_A_stale_row_store_denied` |
| `FillQuestLoot` keeps disallowed players | `T0.only_A_in_quest_list` |
| FFA quest item marked looted globally | `C1b.B_awarded_own_copy` |
| `ItemRemovedQuestCheck` does not re-read bags (L1973) | `T5.WITNESS_whole_slot_move_double_subtracts` |
| bank move does not re-open the quest | `T1.setup_B_banked_counter0_incomplete` |
| `ItemAddedQuestCheck` does not count (PlayerQuest.cpp L1935) | `T0.A_award_runs_quest_counter_to_complete` |

## Stand-ins (not executed)

- **`Player::SendLoot` itself.** The harness performs its two loot steps:
  serialize the original `LootView`, then `AddLooter`. Permission is a fixture
  input. For a party with group loot, pinned `SendLoot` gives every member
  `GROUP_PERMISSION`; for Master Loot it gives `MASTER_PERMISSION` or
  `RESTRICTED_PERMISSION`.
- **`WorldSession::HandleAutostoreLootItemOpcode`.** Its creature branch only
  finds the loot and calls `StoreLootItem`.
- **`Group::GroupLoot`, `NeedBeforeGreed`, `MasterLoot`**, rolls and the master
  give opcode.
- **`LootTemplate::Process`/`Roll`.** The stub hands each fixture row to the
  original `AddItem`.
- **Real item storage.** `SwapItem`, `StoreItem`, `BankItem`, `CanBankItem` and
  Item/Bag objects are not run. Bag and bank are counters; the original
  `ItemAddedQuestCheck`/`ItemRemovedQuestCheck` run in the pinned call order.
  On a loot award, the `StoreNewItem` stub follows the pinned order (sum the
  `dest` counts, then the original `ItemAddedQuestCheck`, then store), so the
  winner's quest objective moves as it would in the pinned code.
- **`CanCompleteQuest`, `CompleteQuest`, `IncompleteQuest`.** These are reduced
  to "all item objectives met ⇒ COMPLETE / re-open ⇒ INCOMPLETE".
- **`UNIT_DYNFLAG_LOOTABLE` per-viewer serialization** (corpse sparkle), the
  client UI, conditions, DisableMgr, other script hooks, Playerbots, and the
  module's `QuestLootProtection` (which defaults to OFF).

## Proof matrix (pinned source, all 71 checks PASS = behaviour reproduced)

In this table, **WITNESS** means the pinned code shows the unsafe behaviour.
That is a red result for the safety invariant, recorded on purpose; it is not
a fix. **STOCK** means stock behaviour that is recorded only; no owner policy
is chosen.

| Case | Setup / order | Pinned result | Safety invariant |
|---|---|---|---|
| **T0** control | A needs 922; B has no quest. A opens, then takes | A gets exactly 1×5168 and the original counter takes quest 922 to 1/1 COMPLETE; count 1→0; corpse `isLooted`. B sees no row; B's store after opening gets nothing | **PASS** |
| **H1 negative** | B already COMPLETE (seed in bags) | B is not in the quest list, sees no row, and a direct store gets nothing; A is awarded | **PASS**: no wrong-human award |
| **T1** | B banked the seed (counter 0, INCOMPLETE, bank 1). A opens (ALLOW_LOOT row), then B opens, then A clicks | B's view shows no row and **sets the shared `Q.is_looted`** without any award or count change. A's stale row is denied **silently** (no error, no release). `unlootedCount` stays 1, so the corpse never reaches `isLooted()` | **FAIL (witness)**: a view consumes A's right |
| **T2** | B (banked) opens first, then A | A sees **no row** although A needs Q and is listed; A's store is denied; count stays 1 | **FAIL (witness)** |
| **T3** | Corpse fills while B's seed is banked; B retrieves it (COMPLETE), then opens | B's cached quest slot remains; **B sees a LOCKED row** (H2 shape); B's store is denied with a loot release. A's row and award are intact | H2 shape reproduced; A **PASS** |
| **T4** | A and B both need Q; A is round-robin owner; either order | Both see ALLOW_LOOT; **the first taker gets the single copy** and reaches COMPLETE, round robin is not consulted; the other stays INCOMPLETE at 0 and is told the slot was removed | **STOCK**, under the unselected A/B/C policy gate |
| **T5** (optional, counter level, synthetic 2-count quest) | B has two Q×1 bag slots (2/2); one whole slot goes to the bank in the `SwapItem` order | **Counter goes to 0** with 1 in bags and 2 including bank; status INCOMPLETE. At the next corpse, B is listed again and B's view marks the shared item looted, so A is denied | **FAIL (witness)** at counter level |
| **O1** | T1 setup, but B's loot GUID is set **directly**, with no `SendLoot`/view | B is awarded a second seed and A is then denied. The bank check exists only on the view path | **DIRECT-API observation only.** A normal client always gets `SendLoot` (view, then GUID) before it can autostore, and B's view would mark the item looted first (T1/T2). Not a client-reachable H1 path |
| **C1** MULTI_DROP (1931/176) | B banked; or both need | B's view hides only B's own row and the shared item stays unlooted; A is awarded; when both need, both get their own copy and both quest counters reach COMPLETE | **PASS** |
| **C2** ordinary group item | Below threshold, round-robin owner A | B opens and the view hides the row, but **storing that hidden slot index succeeds** (`StoreLootItem` does not re-check round robin), and A then gets "already looted" | **API observation O2**: needs a hand-made or stale-UI request for a slot B was not shown; reachability by a normal client is not shown. Normal loot, not quest loot |
| **C3** Master Loot | B is master looter without the quest | B is listed without a right, sees a MASTER row, and self-store is denied; A sees ALLOW_LOOT and is awarded | **PASS** |
| **C4** gold | T1 mutation plus gold | `hasItemForAll()` stays true and the corpse is not looted | control |

**View-only mutation and actual award are recorded separately.** In every case
the observation lines record:
- the shared `is_looted` and `is_counted` flags and each player's own row flag;
- `unlootedCount`, `isLooted()` and `hasItemFor(A/B)`;
- what each player actually received (the stub's `StoreNewItem`), the errors
  sent, loot releases, and the removed slots.

No view-only witness is counted as an award.

### Relation to the owner reports (#109)

- **H1, wrong human actually receives Q.** It is **not reproduced** for quest
  items:
  - a non-entitled B (no quest, or quest complete) is denied on every path tried;
  - the only awards to B go to a B whom the stock counter still marks as
    needing Q: T4 (normal open order), and O1 (direct API only, not reached
    by a normal client because the view runs first);
  - normal (non-quest) loot has a separate API-level path (O2) that needs a
    request for a slot the client was not shown.

  O1 and O2 are API behaviour observations, not a client-reachable wrong-human
  exploit; that would need a separate end-to-end packet and open-order
  reproduction.

  Whether any of these matches the owner's incident is unknown.
- **H2, sparkle or row, then denied.** Two source shapes are reproduced:
  - T1/T2: a shared item silently consumed by another player's view, leaving
    the corpse unfinished;
  - T3: a LOCKED row for a player who no longer needs Q.

  Whether the client sparkle matches is **not** shown, because per-viewer
  `UNIT_DYNFLAG_LOOTABLE` is not executed.

## Source gaps and blockers

- **Genuine T5 storage.** `Player::SwapItem` (PlayerStorage.cpp L3640) needs
  the full inventory model: `GetItemByPos`, `CanStoreItem`/`CanBankItem`
  (L2110–2295), `RemoveItem` (L3009), `StoreItem`/`_StoreItem` (L2690/L2716),
  `BankItem`, real `Item`/`Bag` objects with update state, and the `m_items`
  slots. T5 here runs only the original quest-counter step in the pinned call
  order, with a synthetic two-count quest.
- **Per-viewer corpse flag and client UI.** These need
  `Unit::PatchValuesUpdate` and a real client.
- **Owner's installed binary, DB rows, config** and the effective
  `QuestLootProtection` state are all unknown. This harness is the public
  historical baseline only.

## Review revision (31 Oct 2026)

Information reviewed `6df606f` on #262 (comment 6547304680):

1. **Loot award skipped the quest counter.** The `StoreNewItem` stub did not
   call the original `ItemAddedQuestCheck`, so T0/T4/FFA proved receipt but not
   the objective update. It now follows the pinned order, and the
   `StoreNewItem` call-order fact covers that whole snippet. New checks:
   - `T0.A_award_runs_quest_counter_to_complete` (replaces a check that
     asserted the stub's unchanged counter);
   - `T4a/T4b.taker_complete_other_still_incomplete`;
   - `C1b.both_quest_counters_complete`.

   A new mutant on the original counter increment is caught.
2. **O1 and C2 reachability.** The loot GUID is now set only by `open()`, as
   `SendLoot` does, and `take()` aborts if a player has not opened. O1 sets the
   GUID itself and is renamed `DIRECT_API`; C2 opens first and is renamed
   `O2_API`. Both are qualified above as API behaviour, not H1.

The T1/T2/T3/T5 witnesses are unchanged.

## Rollback

Delete the nine added files (`tests/a04_native/`,
`tests/test_a04_native_quest_loot.py`, this document and the workflow), or
close the draft PR. Nothing else depends on them.

## Run locally

```sh
git clone --filter=blob:none https://github.com/Grimfeather/azerothcore-wotlk.git core
git -C core checkout 8daffdabe9202c228e45d833c9a1d399597a15cd
A04_CORE=$PWD/core python3 -I -B -W error tests/test_a04_native_quest_loot.py -v
A04_CORE=$PWD/core python3 -I tests/a04_native/mutants.py
```
