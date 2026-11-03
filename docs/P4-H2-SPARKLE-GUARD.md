# P4 H2 — corpse sparkle guard (policy-neutral, default OFF)

**Status: DRAFT runtime change, default OFF.** Not merged, not enabled, and
not tested in the client. This is a child of #268 (`e976b22`). It was assigned
by CS01 (#143, 6558642138, item 3) and claimed in 6559507995.

## The defect in pinned Grimfeather `8daffda`

`Unit::PatchValuesUpdate` (`Unit.cpp` L16594–16611) builds each viewer's copy
of the corpse's `UNIT_DYNFLAG_LOOTABLE`, the "sparkle". It clears the flag
only when `Player::isAllowedToLoot` (`PlayerStorage.cpp` L5746–5797) returns
false. Under group loot, a player who isn't the round-robin owner gets a
sparkle whenever `Loot::hasItemFor(viewer)` finds **any** cached quest row.
That includes rows the viewer can no longer use:

- **T3:** the corpse filled while B still needed the item. B then retrieved
  the item from the bank, so B's quest is complete. B's cached row stays, so
  B gets a sparkle, opens a window with one LOCKED row, and is denied.
- **T1 (banked B):** B already owns enough of the item, counting the bank.
  B gets a sparkle and opens an empty window. In stock, that view also
  consumes A's copy (#264).

## The change

`src/Systems/QuestLootSparkleGuard.cpp` adds a hook on
`UnitScript::OnPatchValuesUpdate`. `PatchValuesUpdate` calls it per viewer
(`Unit.cpp` L16661) after the core has set the dynamic flags. The hook acts only
when **all** of these hold:

- the core already set LOOTABLE for this viewer;
- the unit is a dead creature;
- the loot is corpse loot (`LOOT_NONE` before anyone opens it, or
  `LOOT_CORPSE` after; skinning and pickpocket loot are not touched);
- the viewer has corpse permission (using the same `CorpsePermission` as #268).

When it acts, it asks the **original `LootView` serializer** what this viewer
would see, **without changing any loot state**:

- The pinned serializer writes only two flags (`LootMgr.cpp` L1115 for the
  viewer's own `QuestItem` row, and L1118 for the shared item).
- The #264 helper pre-marks those rows, so the serializer skips both writes.
- The viewer's own row flags are saved first and restored when the check
  returns, so the net change to loot state is **zero**. This matters because
  the check runs while an update packet is being built, possibly before the
  player has opened anything.

The hook then clears LOOTABLE **in this viewer's packet only** when the window
would hold:

- no gold, **and**
- no rows at all, or only quest rows marked LOCKED.

**Kept exactly as stock** (stock group-loot parity is the owner's choice,
#117 clarification):
- every normal row, including Master Loot's MASTER and LOCKED rows on normal
  items;
- roll rows, FFA copies, ALLOW_LOOT and OWNER quest rows, and gold.

The hook never adds a sparkle. It never changes the creature's own field, and
it never forces an update.

**Config.** `NaxxramasCore.QuestLootSparkleGuard.Enabled` defaults to **0**.
It is read on the world thread and published through an atomic.

## Evidence (original pinned bodies, 21 checks)

**How the stock sparkle is computed.** The pinned `isAllowedToLoot` body needs
a full Creature, so it is not extracted. Instead, the harness rebuilds its
group-loot decision from the original `hasItemForAll`, `hasItemFor`,
`hasOverThresholdItem` and `isLooted` bodies. The test pins those
`isAllowedToLoot` lines by blob SHA and exact text.

| Case | Stock sparkle | With guard |
|---|---|---|
| T3: B's stale LOCKED quest row | yes (B is denied on click) | **cleared for B**; A keeps it and is awarded; no shared side effect |
| T1: banked B, H0 off and on | yes (empty window) | **cleared for B**; shared flag untouched; A awarded |
| Both need the item | yes | kept for both |
| Round-robin owner with ordinary loot | yes | kept (B already had none in stock) |
| Gold | yes | kept |
| FFA copies | yes | kept for both |
| Master Loot: MASTER row, own quest row, LOCKED normal row | as stock | kept |
| **No mutation**: passive reads for A and B before any window opens, in T1, T3 and FFA | — | **exact snapshot equality** of every player's own rows, the quest and normal item flags, `unlootedCount`, gold and round robin |
| B needs the item again after a passive read | — | B still gets an ALLOW_LOOT row on opening and is awarded |

**Mutants.** There are 6 must-fail mutants of the real header, all caught:
- locked quest rows count as something;
- locked normal rows count as nothing;
- gold ignored;
- the view guard helper skipped;
- **the restore removed** (personal-row write kept);
- always offers something.

**Regression and CI.** The H1 (36), #264 (24) and #262 (71) suites still pass.
CI compiles `QuestLootSparkleGuard.cpp` against pinned Grimfeather, links a
full Worldserver, and checks the defined symbols.

## Limits

- **Refresh timing.** The sparkle changes only when the core next sends
  `UNIT_DYNAMIC_FLAGS` to that viewer, which is the same timing as stock. A
  client that already received a sparkle keeps it until that field is resent.
- **Cost.** Each check serializes one `LootView`. It happens only for dead
  creatures that the core already marked lootable for that viewer, and only
  when their values update is built.
- **Bots.** Playerbots reads the server-side flag, so bot looting is unchanged.
- **Not changed.** Gameobject and container sparkle, and P4-H (Master Loot
  slot notification).
- **Not exercised.** The client, `SendLoot` itself, and the owner's binary and
  database.

## Review revision (1 Nov 2026)

Information (#270, 6559597559) found a blocker: the first version left the
viewer's own `QuestItem::is_looted` set after a passive sparkle read. That
could strand the row if the player later needed the item again. The check now
saves and restores those flags, so it changes nothing. The tests now compare
full loot snapshots before and after, cover a player who needs the item again,
and include a mutant that removes the restore.

## Build fix (1 Nov 2026)

The first hosted full build of this file failed: it included pinned
`UnitUtils.h` directly, but that header has no include guard and already
arrives through `Creature.h` → `Unit.h`, so its classes were defined twice.
The direct include is removed, and nothing else changes. A source-contract
test now forbids the include, and a pinned test records that the header is
unguarded. The real `.cpp` was syntax-compiled locally against the configured
pinned build before this push.

## Rollback

Leave `NaxxramasCore.QuestLootSparkleGuard.Enabled = 0`, which is the default.
To remove the change entirely, revert this branch.

## Part 18 (2 Nov 2026) — H2 false-sparkle regression fix candidate

**Owner gameplay failure:** two humans in Group Loot, Centaur Bracers
quest855: the unentitled viewer could not take their friend's protected
one-copy quest item and correctly collected ordinary loot, but the corpse
still sparkled after all legitimate normal items were gone, even after
leaving view and returning; the rightful friend could collect their item.
This is a confirmed visual FAIL (issue #109), not proof of its unique cause.

**New DRAFT source-only change:** The H1
`NaxxramasQuestLootProtection::PermitPickup` now calls a shared
`WouldDenyQuestSlotForViewer` function containing the same narrow
source/owner/quest-item/instance/round-robin eligibility. Only its outer
packet wrapper requires the looter to have a current `GetLootGUID` and be
inside interaction range; a passive H2 per-viewer create/update packet does
not have a loot GUID yet. H2 serializes the original per-viewer LootView
exactly as before and skips a displayed quest row only when the **enabled**
H1 pickup guard would refuse that exact viewer/slot. It still counts all
normal loot, gold, FFA, roll, Master Loot and legitimate quest entries.
The H1 switch is mirrored to an atomic during config loading, preventing
a false hide when H1 is disabled. No direct loot write or loot-error
packet is sent while evaluating sparkles.

**Register/ownership:**
- Intended feature: eliminate false per-viewer corpse sparkle when only
  another eligible player's actively protected single-copy quest row remains.
- Files: `src/Systems/QuestLootProtection.cpp`,
  `src/Systems/QuestLootTurnGuard.h`,
  `src/Systems/QuestLootSparkleGuard.{h,cpp}`,
  `tests/test_p4_h2_sparkle.py`, this document.
- Dependencies: pinned Grimfeather `8daffdabe` LootView/UnitScript,
  H0 view guard, H1 pickup gate, group/round-robin quest row mapping;
  config `NaxxramasCore.QuestLootProtection.Enabled` and
  `NaxxramasCore.QuestLootSparkleGuard.Enabled` both remain default OFF.
  No SQL, DBC or client patch changes.
- Risks: unintended suppression if shared predicate drifts from true
  autostore authority, quest-row slot maps diverge, or per-viewer hook
  executes outside safe map-thread state. Review config reload and
  overlapping loot rights; full build and owner-approved disposable
  two-human game acceptance essential.
- Evidence: source commits and GitHub CI on isolated child PR (report
  exact head/result separately; no pass is claimed by this document).
- Live status: NOT INSTALLED/NOT TESTED IN-GAME for this change.
- Rollback: leave both config switches OFF; discard unmerged child or
  revert these four C++ paths and source-only test/doc. Preserve prior
  H1 pickup protection and all existing owner custom behaviour.

**Acceptance cases:** viewer with only friend's one-copy restricted quest
row loses sparkle, rightful friend retains sparkle/collectibility; any
legal normal loot, gold, skinning/FFA/multi-drop/roll/Master Loot remains
stock; H1 OFF cannot suppress a pickup that would otherwise succeed;
H0/H1 no-write regressions, party changes and logout/map mismatches
fail open; two-human quest855 and one secondary quest independent of it.
The owner's actual installed module/core/config remain unverified. No
permission to merge, install or enable is inferred.

**3 Nov — shared-roll fixture correction:** A new regression check originally asserted that B would see a below-threshold ordinary item while A remained the round-robin owner. Pinned Core correctly hides that item. The test now sets this ordinary item to an over-threshold blocked group-roll row, which is legitimately visible to B; the quest row remains separately denied by the simulated H1 callback. No runtime predicate or loot permission was loosened. This only repairs the test fixture, and does **not** establish the actual owner scenario until native and in-game validation.
