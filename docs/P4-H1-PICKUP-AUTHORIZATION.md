# P4 H1 — loot pickup authorization (policy-neutral slice, default OFF)

**Status: DRAFT runtime change, default OFF.** It is not merged, not enabled,
and not tested in game. It was assigned by CS01 on #143 (6558642138) and
claimed in 6558676858. This branch is a child of #264 (`78deef6`), which is
itself a child of #262; neither of those is changed.

## What the harness found (original pinned bodies, normal open, then click)

Every award path below was run through the original Grimfeather `8daffda`
code (`FillLoot`, the `LootView` serializer and `StoreLootItem`). Two humans
are in one party, and A is the round-robin owner.

| Path | Stock result | Class |
|---|---|---|
| Quest-required loot (`quest_items`); B has no quest, or the quest is already complete | B sees no row and is refused | stock-entitled, safe |
| Quest-required loot; both A and B need it | Both see it; **the first taker gets the single copy** | owner policy (A/B/C, #117) |
| One-copy quest loot during A's round-robin turn | Visible to both; the existing default-OFF `QuestLootProtection` can reserve it for A | owner policy (existing guard) |
| **Quest item in ordinary loot** (`QuestRequired=0`); B has no quest; during A's turn | B's view **hides** the row, but if B asks for that slot index, **`StoreLootItem` awards it to B** | **server-inconsistent: fixed here** |
| Any below-threshold ordinary item during A's turn | Same: hidden from B, but awarded on request | **server-inconsistent: fixed here** |
| The same items after A releases the corpse | Shown to B and awarded | owner policy (released turn), unchanged |
| FFA/MULTI_DROP copies, Master Loot, gold | stock | unchanged |

**Why it happens.** Pinned `Player::StoreLootItem` (`Player.cpp` L13861) never
re-checks round robin, or what the player was shown. Only the view hides the
row. A stale loot window, or a hand-made `CMSG_AUTOSTORE_LOOT_ITEM`, is enough
to collect an item that the server itself shows as reserved for someone else.

**What is not proven.** The harness does not prove that this is the owner's
reported incident. The normal-client paths that end with a wrong human holding
an item are the policy rows above (both eligible, or a released turn), and this
change leaves them as they are.

## The change

`src/Systems/QuestLootPickupAuthorization.cpp` adds a
`ServerScript::CanPacketReceive` hook for `CMSG_AUTOSTORE_LOOT_ITEM`.

**Where it runs.** Pinned `WorldSession::Update` calls this hook immediately
before the handler (`WorldSession.cpp`, `STATUS_LOGGEDIN` branch). The opcode is
`PROCESS_INPLACE`, so the check and the handler run on the same map thread.

**What it checks.** Only creature corpse loot (`LOOT_CORPSE`) is checked, so
the hook:
1. works out the player's permission with `CorpsePermission`, a pure copy of
   the non-skinning creature branch of pinned `Player::SendLoot`;
2. asks the **original `LootView` serializer** which rows that player can see
   right now. It runs the #264 view guard first, so this check never writes the
   shared `is_looted`;
3. refuses the autostore, with `LOOT_ERROR_LOCKED`, **only** when the requested
   slot is not one of those rows.

**What it never does.** It never refuses a visible slot, so round robin,
release, FFA copies, Master Loot, rolls, gold and quest eligibility all behave
exactly as the core shows them. It does not choose an A/B/C policy.

**Config.** `NaxxramasCore.QuestLootPickupAuthorization.Enabled` defaults to
**0**. It is read once per config load on the world thread and published
through an atomic.

## Evidence

The harness (`tests/p4_h1_pickup/pickup_harness.cpp`) uses the unchanged #262
harness and the module's real headers. It has 26 checks. Each path is run
twice: once as stock, recording the witness, and once with the check.

| Area | Result |
|---|---|
| O2 / H1, stock | A hidden below-threshold item, and the quest item placed in ordinary loot, are **awarded to B** |
| O2 / H1, with the check | B is refused and receives nothing; A is awarded, and quest 922 reaches 1/1 COMPLETE |
| After release | B sees the item and may take it, unchanged |
| Both eligible (T4) | The first taker still gets the single copy, unchanged |
| Quest-required item, B not entitled | Refused, as in stock |
| Side effects | B's check after a banked-B view leaves the shared flag untouched, and A is then awarded |
| FFA copies, Master Loot, no rights | Unchanged. The Master Loot row is passed to the core, which still denies it. |
| `CorpsePermission` | All 9 branches match pinned `SendLoot` |

**Pinned-source facts.** `tests/test_p4_h1_pickup_authz.py` checks the blob
SHA and the exact text of each seam:
- the `SendLoot` permission switch;
- the handler calling `StoreLootItem`;
- `CanPacketReceive` immediately before the handler;
- the `PROCESS_INPLACE` opcode;
- the release that clears `roundRobinPlayer`.

**Mutants.** There are 5 must-fail mutants of the real header, and all are
caught:
- allows any slot;
- skips the view guard;
- master looter gets restricted rights;
- another group gets rights;
- round robin is treated as group loot.

**Regression and CI.** The #264 guard (24 checks) and the #262 baseline (71)
still pass. CI also compiles the new file against pinned Grimfeather, links a
full Worldserver, and checks the defined symbols.

**Workflow note.** On this branch, the #264 workflow's exact-scope step runs
only on #264's own PR. Stacked and integration PRs carry other files by design;
all of that workflow's tests still run.

## Not covered

- **Other award paths:** group rolls, Master Loot give (`CMSG_LOOT_MASTER_GIVE`),
  gameobject, item and corpse containers, and bot packets
  (`HandleBotPackets`) are outside this hook.
- **Owner policy:** both-eligible and released-turn awards are left to the
  owner (A/B/C).
- **Still to do:** H2 (viewer-specific sparkle) and P4-H (Master Loot slot
  notification).
- **Not exercised:** `SendLoot` itself, real storage, the client, and the
  owner's installed binary and database.

## Rollback

Leave `NaxxramasCore.QuestLootPickupAuthorization.Enabled = 0`, which is the
default. To remove the change entirely, revert this branch.
