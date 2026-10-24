# Molten Core — Golemagg melee reach guard

**Status:** draft, default OFF. Source, standalone tests and pinned compile only; not yet tested in game. Tracked in [#27](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/27) and [#28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) (A01).

## Problem

Playerbots' Molten Core strategy backs non-tank melee away from Golemagg once their Magma Splash (13880) stack reaches 20, as long as the boss is above 10% health. Its `GolemaggMultiplier` then blocks their attacks until the stack expires. The multiplier does not cover the generic `reach melee` movement, which is requested whenever the current target is outside combat range:
- the generic melee strategy requests it at priority 21;
- Warrior and Rogue strategies at 21;
- Enhancement Shaman at 40;
- Fury Warrior through its `charge` → `intercept` → `reach melee` fallback chain.

The bot therefore walks back toward the boss, is pushed out again by the back-off (priority 61) once inside 12 yards, and repeats until the stack expires. It deals no melee damage throughout.

The owner's one-bot diagnostic on 23 October 2026 recorded `reach melee - OK` at 20 stacks while the bot was backed off, with distance moving between roughly 1 and 12 yards. Source references are for Playerbots `e88cc409` (identical to `d750b4b` for every file involved):
- `src/Ai/Raid/MC/MCMultipliers.cpp` L105–144;
- `MCTriggers.cpp` L46–67;
- `MCActions.cpp` L115–130;
- `src/Ai/Base/Strategy/MeleeCombatStrategy.cpp` L10–16.

## What the guard does

The guard attaches one listener to the named bot's **combat** engine through the public Playerbots `ActionExecutionListener` API. Its `Before()` hook returns `false` for the action named `reach melee` only when **all** of the following hold:

- `NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 1`;
- the bot's name exactly matches `AllowedBotName`. An empty value guards nobody;
- the bot is alive, on map 409, an Altbot, and a non-tank melee DPS. `PlayerbotAI::IsAltBot()` requires a game-client master and excludes random bots and self-bots; human players never have a bot AI;
- the unit this `reach melee` would move toward is Golemagg (entry 11988), alive, in combat and above 10% health. `Action::GetTarget()` resolves the same `current target` value that `ReachTargetAction` moves to;
- the bot's own Magma Splash stack is 20 or more.

When `Before()` returns `false`, Playerbots does not run the action, logs it as failed, and moves on to the next queued action (`Engine::ListenAndExecute` and `Engine::DoNextAction`). `reach melee` has no fallback actions in Playerbots `e88cc409`, so nothing else is queued in its place. The multiplier already blocks attacks at this stack count, so the bot waits near the back-off distance. Once the stack expires (about 30 seconds after the last application in the owner's log), or the boss drops to 10% or below, the guard stops applying and normal combat resumes.

Every other action passes untouched. `AllowExecution()` always returns `true`, because Playerbots reports a `false` there as a successful execution. `After()` and `OverrideResult()` are pass-through.

## Not affected

- Tanks and the assist tanks holding Core Ragers.
- Healers and ranged: they use different movement actions.
- Lava escape (`mc move from lava`) and every other named action.
- Any target other than Golemagg; any encounter outside Molten Core.
- Golemagg's final 10% burn phase.
- Bots below 20 stacks.
- The read-only P5 observer, which keeps working independently.

## Known limits

- While the guard applies, a player-issued `do reach melee` on that bot is also refused: Playerbots routes direct commands through the same listeners.
- Other movement (follow, formation, AoE avoidance) is not changed. If bots still return through another action, that needs its own evidence first.
- Melee uptime follows Playerbots' own engage, back-off, re-engage cycle. The guard removes the wasted shuttling; it does not change damage or the encounter.
- Requires a Playerbots revision with a public `PlayerbotAI::GetCurrentEngine()`, such as `d750b4b` or `e88cc409`. On older revisions such as `037c014`, the guard compiles but stays inactive and logs one warning.

## Configuration

```
NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 0
NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName = ""
NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug = 0
```

- **`AllowedBotName`:**
  - takes exactly one character name, matched case-insensitively, using the same rule as the P5 observer;
  - empty, wildcard and comma-separated values guard nobody;
  - covering every melee Altbot would be a separate, reviewed change.
- **`Debug = 1`:**
  - logs one line when a bot's listener is registered;
  - logs at most one line per bot every 5 seconds when the guard refuses `reach melee`, including the bot's stack count and remaining duration.

Settings are read once at startup, so changes need a Worldserver restart.

## Lifecycle

- **Registration hook:** happens from `PlayerScript::OnPlayerUpdate`. Playerbots runs bot AI from `OnPlayerAfterUpdate` on the same player-update thread, so adding a listener cannot race the engine.
- **When:** registration only happens while the bot is in Molten Core, in combat, with Playerbots in its combat state (`GetState() == BOT_STATE_COMBAT`).
- **Ownership:** the listener belongs to the engine. Playerbots deletes it together with the bot's AI. The module never deletes or removes it.
- **Duplicates:** a per-Player record holds the AI object, the engines already registered, and a liveness flag that the listener clears when it is deleted. The record is never erased, which is what prevents duplicate listeners.
- **AI replacement:** Playerbots can replace a live player's AI object. A changed AI or a cleared flag starts a fresh record, and the new combat engine is registered once.
- **One combat engine per AI:** at Playerbots `d750b4b`/`e88cc409`, the `PlayerbotAI` constructor creates exactly one combat engine, and it is never reassigned (`PlayerbotAI.cpp` L160–163). `ChangeEngine` and `Reset` only switch between the existing engines. So in practice the record holds at most one engine per AI, and repeated pulls, wipes, map changes and combat exits register it once. That is verified for these revisions only; a Playerbots update that rebuilds engines would need this re-checked.

## Tests

- **`tests/golemagg_reach_guard_policy.cpp`** — standalone C++ tests:
  - every deny and allow condition, including the 19/20 stack and 10% health boundaries;
  - the single-name gate;
  - registration bookkeeping: first registration, repeat ticks, engine switch, deleted listener, replaced AI.
- **`tests/test_golemagg_reach_guard.py`** — source contract:
  - default-OFF keys;
  - `Before()` as the only deny path, `AllowExecution()` never denying;
  - no listener removal or deletion;
  - only `reach melee` named;
  - loader registration;
  - no SQL;
  - P5 observer unchanged.
- **`.github/workflows/golemagg-reach-guard.yml`:**
  - the source and policy tests;
  - the real translation unit and a full Worldserver link on core `8daffda` + Playerbots `d750b4b` + IP `dd96f2b`;
  - a translation-unit compile on the old pin `a66f1be` + `037c014` + `4ff4b5f`, to prove the inactive fallback compiles.

## Suggested in-game acceptance (owner-approved only)

1. Back up the Worldserver binary and active config as for any release. No SQL or DBC is involved.
2. Set `Enabled = 1`, `AllowedBotName = "Grau"` and `Debug = 1`. Optionally keep the P5 observer on Grau as well.
3. Pull Golemagg.
   - Expected: at 20 stacks Grau backs off once and waits near 12 yards with no in-and-out movement.
   - The log shows `denied 'reach melee'` lines.
   - When the stack expires, Grau re-engages.
   - Below 10% boss health Grau stays in melee.
4. Check that tanks, Core Rager handling, healers, ranged and lava escape behave as before.
5. Repeat with one Fury Warrior and one Enhancement Shaman by changing `AllowedBotName`. Covering all melee Altbots at once needs a separate, reviewed change.
6. **Rollback:** set `Enabled = 0` and restart.

Earlier feasibility notes in `PLAYERBOTS-GOLEMAGG-MELEE-GUARD-FEASIBILITY.md` describe the old Playerbots pin `037c014`, where no public engine accessor existed. That limitation does not apply to `d750b4b` or `e88cc409`.
