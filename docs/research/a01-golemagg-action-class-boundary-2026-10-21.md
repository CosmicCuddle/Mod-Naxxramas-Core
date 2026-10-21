# A01 Golemagg — pinned retreat action-class boundary (S1 research, NO FIX)

**21 October 2026 | CosmicScript01 | Draft source-only investigation**

**Status:** A01 functional movement correction BLOCKED. This note proves only what
one exact Playerbots revision checks. It does not identify which AI action
actually caused the owner's observed repeated forward/backward running.

## Source provenance

Pinned upstream `mod-playerbots/mod-playerbots` commit
`037c01418b5d01506917a3db9b44fd56ac5f965c`. The read-only CI script
checks the **entire real Git blob contents** of the following files before
interpreting familiar source tokens:

| Reviewed source | Git blob SHA-1 |
| --- | --- |
| `src/Ai/Raid/MC/MCMultipliers.cpp` | `99cda3cdcec54af0f3d95fc3a223593a5410515b` |
| `src/Ai/Raid/MC/MCTriggers.cpp` | `be44880217dbea3b6834463cde866cfd5a70b4a8` |
| `src/Ai/Raid/MC/MCActions.cpp` | `3707c59f5f519561baea852d26d551a3d1e3ad77` |
| `src/Ai/Raid/MC/MCHelpers.h` | `0c90fcd95f10181dc375c386d03c7089e90bd6ef` |

Additional exact whole-file action hierarchy coverage from the SAME Playerbots
revision:

| Pinned base-action source | Git blob SHA-1 |
| --- | --- |
| `src/Ai/Base/Actions/MovementActions.h` | `3932cdfb602cfd438604966f19f603e6fecbb416` |
| `src/Ai/Base/Actions/ReachTargetActions.h` | `26b96d36593ac4ffc9b6efc3a70bcad3aeec49f7` |
| `src/Ai/Base/Actions/ReachTargetActions.cpp` | `c889265520c7cea621f2dc5953225f2b7ab47beb` |
| `src/Ai/Base/Actions/AttackAction.h` | `2911924f00557891e5ab977986b71ca0d08d5fa2` |

Git blob IDs are content fingerprints, not independent authentication or
a claim about the versions installed on the operator's server.

## Narrow source interpretation

- `MCHelpers.h` defines Magma Splash spell **13880**, retreat at **20
  stacks**, **12-yard** threshold. `McGolemaggMagmaSplashTrigger::IsActive`
  excludes tanks and turns off the retreat trigger when the boss reaches
  **10% HP or lower**.
- `McGolemaggBackOffAction::Execute` stops casting and calls
  `MoveAway(boss, distToTravel)`. After a bot reaches the safe distance the
  trigger stops firing. This says what the intended retreat action does, not
  what other queued actions subsequently do.
- `GolemaggMultiplier::GetValue` gates the known re-engagement categories
  `AttackAction`, `MeleeAction`, `CastReachTargetSpellAction`, with an
  exception for `McGolemaggBackOffAction`, when a non-tank bot has the high
  Magma Splash stack and the boss is above 10% HP. Ranged melee-fallback has a
  separate guard.
- **It does not demonstrate a generic `MovementAction` veto.** The same
  source file explicitly checks `dynamic_cast<MovementAction*>` for Baron
  Geddon but not in `GolemaggMultiplier`. This is a verifiable class-coverage
  distinction, not proof that an uncovered movement action occurred in the
  owner's raid or that every MovementAction would cause re-engagement.
- **Concrete uncovered candidate narrowed by exact inheritance:** `ReachMeleeAction`
  derives `ReachTargetAction` → `MovementAction` → `Action`. Separately,
  `AttackAction` derives `MovementAction` and `MeleeAction` derives
  `AttackAction`; `ReachMeleeAction` is **not** a subclass of `AttackAction`.
  In `ReachTargetActions.cpp`, the shared `ReachTargetAction::Execute`
  calls `ReachCombatTo` against the action's `current target`. The pinned
  `GolemaggMultiplier` checks `AttackAction`, `MeleeAction`, and
  `CastReachTargetSpellAction` but not `ReachTargetAction` or the generic
  `MovementAction`, so **`reach melee` is not covered by that guard**.
  This is a *substantive class coverage finding*, not observation that the
  scheduler selected it while backed off. `CombatFormationMoveAction`,
  `RearFlankAction` and `SetBehindTargetAction` also inherit movement
  classes but may serve different safety/position purposes; never veto all
  movement based on this document.

- The inspection is scoped to this exact pinned version and these source
  files. It does not prove the absence of other safe hooks in the codebase.

The source regression tests reject changed thresholds, missing action-category
filters, new generic movement guards, unknown Playerbots source revisions and
modified files. **A green test means this source class-coverage limitation persists, not that a fix
exists.** The production checker verifies all eight reviewed file blobs first;
the standalone lexical helper is not a source identity verification.

## Engineering gate before any movement mutation

1. Confirm the actual installed **Playerbots** SHA and whether the operator has
   local engine modifications. Historical GitHub pins are not proof of installed
   API parity.
2. Preserve the independently reviewed **OFF-by-default** one-bot read-only
   action-history observer in draft PRs #40/#41. Do not install it without
   owner approval, a verified backup and rollback, and a strictly bounded
   private pilot.
3. Capture whether a **specific** movement/targeting action is selected during
   a verified **20+ stacks / boss >10% HP / 12-yard** retreat/re-engagement cycle.
   An action-history tail and sampling at 2.5-second intervals are not an
   atomic action callback; distinguish observable correlation from cause.
4. Only after causal evidence, prove access to a **public, module-safe**
   Playerbots action-level interception or strategy factory. Existing pinned
   research [PR #64](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/64)
   found the current engine and strategy registry unavailable to normal module
   scripts. Do not use private casts, undocumented engine fields, universal
   movement suppression or changes to other raid encounters.
5. Independently review the focused fix, CI compile/link a Worldserver against
   approved exact dependencies, and request explicit owner approval for
   backed-up S5/S6 private game testing. Until then A01 remains BLOCKED.

**No change:** AzerothCore, Playerbots, module combat behaviour, SQL, DB, DBC,
boss, gear, AI strategy, live config, installed Worldserver or players.
