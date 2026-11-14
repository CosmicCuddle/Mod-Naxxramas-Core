# P4 — quest loot view guard (policy-neutral fix for T1/T2)

**Status: DRAFT runtime change, default OFF.** Not merged, not enabled, not
tested in game. Assigned by CS01 on #143 (6557301373) after the owner's
development-first direction, and claimed in 6557457978. This branch is a child
of the #262 harness (`4926379`); #262 itself is unchanged.

## The bug (reproduced on the original pinned code by #262)

Grimfeather `8daffda` `operator<<(ByteBuffer&, LootView const&)`
(`LootMgr.cpp` L1099–1121) builds each player's loot window. For a quest row
the viewer is listed for, it asks `HasQuestForItem(item, 0, false, &showInLoot)`.

- If the viewer no longer needs the item, because they already own enough
  **counting the bank**, the call returns false with `showInLoot = false`.
- The serializer then hides the row from that viewer, and for a single-copy
  (non-FFA) item it **also sets the shared `LootItem::is_looted`**.
- Nobody receives the item and `unlootedCount` is not lowered.

So another player who still needs the item is then refused (T1), or never sees
it (T2), and the corpse never finishes looting.

## The fix

`src/Systems/QuestLootViewGuard.cpp` registers
`PlayerScript::OnPlayerBeforeSendLoot`. Pinned `Player::SendLoot` calls that
hook at `Player.cpp` L8383, right after setting the loot GUID and right before
serializing the `LootView` at L8388. That is the only place a `LootView` is
built.

The shared header `src/Systems/QuestLootViewGuard.h` runs the serializer's own
test on the **viewer's own** quest rows, and marks only those rows'
`QuestItem::is_looted`. The serializer only examines rows that are not yet
looted, so:

- the viewer sees exactly the rows the core would show them;
- the shared flag is never written by a view;
- nothing is awarded, and no count, round robin, FFA/MULTI_DROP, Master Loot,
  roll or gold state changes.

No A/B/C ownership policy is chosen. If two players both genuinely need the
item, the first taker still gets the single copy, as in stock.

**Config.** `NaxxramasCore.QuestLootViewGuard.Enabled` defaults to **0**. It
is read once per config load on the world thread (`OnAfterConfigLoad`) and
published through an atomic. The map-thread hook only reads the atomic.

## Evidence

`tests/p4_view_guard/guard_harness.cpp` includes the unchanged #262 harness,
which runs the original pinned bodies, and the module's **real** guard header.
Each case runs on two fresh corpses: once without the guard (pinned) and once
with it, at the position where `SendLoot` calls the hook.

| Case | Pinned (no guard) | With guard |
|---|---|---|
| T1: A opens, banked B opens, A takes | **RED**: B's view sets the shared flag, A is denied, the corpse never settles | only B's own row is marked; **A gets exactly one seed** (quest 1/1 COMPLETE); corpse settles; B gets nothing |
| T2: banked B opens first, then A | **RED**: A sees no row and is denied | A sees an ALLOW_LOOT row and is awarded; corpse settles; B, after its own view, cannot take the seed |
| T3: B retrieves the seed (quest COMPLETE) | LOCKED row for B, B denied, A awarded | **identical rows**; the guard does not touch this H2 shape |
| T0, T4 (one or both need it) | stock | unchanged: A only, or first taker gets the single copy |
| FFA/MULTI_DROP, Master Loot, ordinary item, gold | stock | unchanged, and Master Loot rows are identical |

The rows each viewer sees are compared between pinned and guarded runs, and
they are identical in T1, T2 (B), T3 and Master Loot. In total 24 checks pass.

There are 4 must-fail mutants of the real guard header, all caught:
- marks nothing;
- ignores `showInLoot`;
- also writes the shared flag;
- reads the wrong player's list.

The #262 baseline suite still passes unchanged (71 checks, 10 mutants).
Hosted CI also compiles `QuestLootViewGuard.cpp` against pinned Grimfeather
and links a full Worldserver, with pinned Playerbots and Individual
Progression, then checks the linked symbols.

## Not solved, not shown

- **H1** (the owner's report of the wrong human actually receiving an item)
  and **H2** (corpse sparkle, then denied) are separate acceptance outcomes.
  This guard fixes only the T1/T2 view mutation. The T3 LOCKED row is
  intentionally unchanged.
- **Corpse stays lootable when B was the only one listed.** If the item is
  hidden from B, `unlootedCount` stays as the core leaves it, so the corpse may
  stay lootable. That is the same as stock; it is not made worse.
- **Not exercised:** `Player::SendLoot` itself, real Item/Bag/bank storage, the
  client, per-viewer `UNIT_DYNFLAG_LOOTABLE`, Playerbots behaviour, and the
  owner's installed binary and database. The harness is an extracted-source
  test, not a Worldserver run.
- **Other callers.** Code that calls `StoreLootItem` without opening the loot
  window (the O1 direct-API path) is outside this hook.
- **Not included:** the Master Loot two-quest slot-notification control
  (Information P4-H). It is left for a follow-up, so T1/T2 is not delayed.

## Rollback

Set `NaxxramasCore.QuestLootViewGuard.Enabled = 0` (the default). To remove the
change entirely, revert this branch: two new source files, two added lines in
the loader, one config block, and the tests/doc/workflow.
