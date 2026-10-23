# F11 — Hallow's End human-count scaling, independent S1 source characterization

**Scope:** Review-only, current-behaviour evidence and future acceptance contract. **NOT a proposed difficulty curve, balancing value, executable change, release, or owner gameplay test.** Tracks [F11 #82](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/82), separate from [F10 #80](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/80).

## Baseline and why work is unblocked

F10 PR [#81](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/81) merged to `main`; GitHub source now contains both `DisableSpread` and `OneBucket` default-OFF gates. [Issue #80 comment 6339277967](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/80#issuecomment-6339277967) **records the owner's successful 22 October solo no-spread in-game test** after git pull, clean build, restart and enabling the intended behaviour. [Issue #82 comment 6339290777](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/82#issuecomment-6339290777) explicitly marks F11 **UNBLOCKED FOR DESIGN**. This proves only the narrow one-human no-spread acceptance, *not* two-human scaling, drop/reward regression or joins/leaves.

**Source snapshot read:** `main` head cited as `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; `src/Events/HallowsEndShadeOfTheHorseman.cpp` blob `5c88b04263e48a1f76ac4ff40101c0c3cedda783`, plus `src/Events/HallowsEndSoloFire.h`, `conf/mod_naxxramas_core.conf.dist`; core link pin remains Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd`. No live config or connected owner server was read.

## Verified source properties

1. **Player census:** `CollectNearbyHallowsPlayers` uses 60 yards and `AnyPlayerInObjectRangeCheck`, not a quest-acceptance/participation list; nonparticipant bystanders can be included. `CountRealHallowsPlayers` excludes Playerbots using `GET_PLAYERBOT_AI` when available.
2. **Existing bot filter is limited to solo:** In `CastFires`, `players.remove_if(IsHallowsEndShadePlayerBot)` happens **only when** `SoloFirePathActive(players)` is true: `SoloFire.Enabled == 1` and exactly **one real player** near the Shade. With 2+ humans and bots, or with bots only, raw `players.size()` includes bots. The default-off path also retains the legacy raw count.
3. **Initial wave uses non-monotonic stock integer arithmetic:** In the current `CastFires(initial=true)`, after the player census `playerCount = players.size()-1`, then `playerCount += 1`. It computes `sizeCount = (playerCount / 3) + 1`; because `initial && playerCount > 0` it adds `playerCount % 2`. With ample unlit triggers and no bots, **1, 2, 3, 4 counted players yield 2, 1, 3, 2 newly ignited triggers** respectively. `RandomResize` limits these to available unlit targets. This is a source-calculated property, NOT an observed client count. Increasing from 1 to 2 or 3 to 4 can actually reduce initial fire targets.
4. **Subsequent waves use a separate threshold:** `CastFires(false)` sets `playerCount = players.size()-1` and `playerRate = max(0, 0.5 - playerCount*0.25)`. It refuses the next wave when `unlit < total*playerRate`. At 1 counted player threshold is 50% unlit, at 2 it is 25%, at 3+ it becomes zero. The subsequent wave size uses `((count-1)/3)+1` before capping to unlit triggers. This can make an unbounded-looking fire pressure change at the 2->3 participant boundary; **whether it becomes too hard is NOT tested**.
5. **Solo F10 remains a separate actual-spell guard:** It hooks spell `42079` spread, requiring `SoloFire.Enabled=1`, `DisableSpread=1`, exactly one real human and unambiguous Shade/fire ownership. One-bucket handling uses `42339` and fire aura `42074`, separate from the normal Shade ignition `42132`. Any F11 curve must *not* silently change those toggles, event outcome, quests, or neighboring fire triggers.

## Source-characterization examples (no elected future formula)

| Nearby participants | Solo Enabled | Current *counted* | Initial fire candidates, if enough unlit | Meaning |
| --- | --- | --- | --- | --- |
| 1 human, 0 bots | 1 | 1 | 2 | Existing F10 solo baseline |
| 1 human, 5 bots | 1 | 1 | 2 | Bots excluded only here |
| 1 human, 5 bots | 0 | 6 | 3 | Legacy default path includes bots |
| 2 humans, 0 bots | 1 | 2 | 1 | Initial wave falls from 2 to 1 |
| 2 humans, 3 bots | 1 | 5 | 4 | Bots inflate count despite real 2-person party |
| 3 humans, 0 bots | 1 | 3 | 3 | Higher count |
| 4 humans, 0 bots | 1 | 4 | 2 | Non-monotonic again |
| 0 humans, 3 bots | 1 | 3 | 3 | Does NOT enter 1-human solo path |

These numbers model **existing** integer arithmetic in `CastFires`. They are not an acceptable proposed difficulty curve, and actual map trigger availability, nearby players and already-ignited fires may reduce observed casts.

## S2 implementation/acceptance gates (not implemented)

- **Separate future config OFF by default** and leave all old `SoloFire` toggles + F10 solo mode byte-for-byte unchanged when the new feature is off.
- **Only humans affect F11 selected participant count**; 0 humans never turn bot-only scenes into scaled human participation. If trustworthy Playerbots identification is absent, leave stock behaviour (no guesses based on account name).
- Exactly 1 human must preserve the **owner-tested F10 behaviour**; 2 and 3+ humans should be gradually harder according to a future *explicitly approved bounded* curve, not the source's nonmonotonic current outputs.
- Sensible caps: do not try to ignite more than known unlit trigger candidates, cause burst waves, reset an existing aura timer, or change the stock `42079` spread/ `42339` bucket spell outside agreed mode.
- Stage joins/leaves, resurrection/death, a nearby nonparticipant, bots joining/leaving, off/default, ambiguous living Shade owner and missing Playerbots API **before** proposing runtime C++.
- Keep F11 independent of F10 accepted code; no SQL, DBC, core, Playerbots, Individual Progression, release, live config, Worldserver, characters or inventory changed.

**Synthetic proof only:** `tests/test_f11_current_fire_count_characterization.py` asserts the above current-source census, legacy and threshold behaviour; `naxx-f11-current-source-model.yml` runs it on the exact isolated branch/PR SHA with read-only checkout and no artifact upload. A successful run does not validate an alternative game balance, Playerbots-installed compatibility or any real two-human game.

**Status:** F11 S1 research/model prepared for independent CS02 + CS03 review, not a gameplay feature. Personal decision on actual balancing curve remains open.
