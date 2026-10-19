# F10 S1 — Hallow's End Shade solo fire: source trace and module-only design

Status: **source trace and design only**. No gameplay-affecting C++ was added. No SQL, DBC, core, Playerbots, or Individual Progression files were edited. Nothing here was run on a worldserver or a client. A passing source test is not gameplay acceptance.

Module base this trace was read against: `1f5f317c3991bbac66cc92a7112bbde3c929c232` (`main`).

Labels used below:

- **VERIFIED** — the statement matches the cited source.
- **POTENTIAL ISSUE** — the source shows a real mismatch or hazard. Gameplay effect is not proven.
- **UNKNOWN** — the fact is not in the sources that were read.
- **NOT TESTED** — not executed on a server, client, or database.

## 1. Commits that were read

Fork URL, taken from the existing workflows that already check it out (`.github/workflows/ep-module-grimfeather-worldserver-link.yml` and `.github/workflows/playerbots-talent-completion-worldserver.yml`):

- `https://github.com/Grimfeather/azerothcore-wotlk`

Those workflows pin `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7`. They do **not** check out the prospective commit. That commit was read directly on the same fork:

| Role | Commit | What it is |
| --- | --- | --- |
| Pinned core | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` | 2026-10-09, "Merge pull request #30 from mod-playerbots/Playerbot" |
| Prospective core | `8daffdabe9202c228e45d833c9a1d399597a15cd` | 2026-10-16, "Merge pull request #31 from mod-playerbots/Playerbot". First parent is the pinned commit. Compare is ahead by 165 commits and behind by 0. |
| Pinned Individual Progression | `4ff4b5fcc1480348f058c632573143e62d4e3a41` | `https://github.com/Grimfeather/mod-individual-progression`, the ref in the same Grimfeather workflow |
| Pinned Playerbots module | `037c01418b5d01506917a3db9b44fd56ac5f965c` | `https://github.com/mod-playerbots/mod-playerbots`, the ref beside that core checkout |

`src/server/scripts/Events/hallows_end.cpp` is byte-identical at both core commits. Git blob `02282feb50f24debd6bbeb0fe9b928db6adabd21` (49352 bytes). Line numbers below for that file apply to both SHAs.

Individual Progression at that ref has no Hallow's End script. A content search for spell 42074, creatures 23686 and 23543, and the script names `hallows_end` / `npc_soh_fire_trigger` finds no match. One optional Alterac Valley landmine row contains the digits 42074 inside the orientation `0.942074` (`optional/sql/world/zz_optional_av_landmines.sql`). That is not this spell. Individual Progression does not participate in this event. **VERIFIED**.

## 2. Who owns which piece

| Piece | Owner at both core SHAs | Binding |
| --- | --- | --- |
| Shade AI used in this module | This module, `src/Events/HallowsEndShadeOfTheHorseman.cpp` | World SQL already overrides creature 23543 to `npc_naxxramas_hallows_end_soh` (`data/sql/db-world/2026_09_21_00_event_script_overrides.sql:24-26`). Loader calls `AddHallowsEndShadeOfTheHorsemanScripts()` (`src/NaxxramasCore_loader.cpp:77`). |
| Stock Shade AI | Core `npc_hallows_end_soh` | `creature_template` row 23543 still says `npc_hallows_end_soh` (`data/sql/base/db_world/creature_template.sql:17572`). The module override replaces it only where that SQL has been applied. |
| Fire trigger 23686 | Core `npc_soh_fire_trigger` | `creature_template.sql:17715` ScriptName `npc_soh_fire_trigger`. Registered at `hallows_end.cpp:1519`. The module SQL does not mention 23686. |
| Spread aura 42074 | Core `spell_hallows_end_base_fire` | `spell_script_names.sql:1087`. Registered at `hallows_end.cpp:1511`. |
| Bucket landing spell 42339 | Core `spell_hallows_end_bucket_lands` | `spell_script_names.sql:1092`. Registered at `hallows_end.cpp:1512`. On a non-player hit it casts 42348 (`hallows_end.cpp:287-296`). |
| Water splash 42348 | No spell script row | Handled only by `npc_soh_fire_trigger::SpellHit` (`hallows_end.cpp:570-582`). |
| Quest offer, 400s window, Shade summon | Core `npc_costumed_orphan_matron` | `hallows_end.cpp:356-520`. Not overridden. |

The module comments at the top of `HallowsEndShadeOfTheHorseman.cpp` are accurate and are not re-litigated here: the module already uses a 30s repeat (`:359`) where core uses 15s (`hallows_end.cpp:766`), and `counter > 14` (`:312`) where core uses `counter > 21` (`hallows_end.cpp:742`).

## 3. Hunch verdicts

The hunches are the ones in the CS02 check-in on issue #48. Each one is source-only.

### (a) Spread pace is the core aura, not the 30s cycle — VERIFIED

The module never casts 42079. `CastFires` only casts 42132 `SPELL_START_FIRE` (`HallowsEndShadeOfTheHorseman.cpp:479-484`). The 30s timer is `events.Repeat(30s)` after that ignition (`:359`).

Growth and spread are `spell_hallows_end_base_fire::HandleEffectPeriodicUpdate` (`hallows_end.cpp:320-337`):

- While amount is below 3, every tick increments it and does **not** consult the tick number (`:325-326`).
- The tick that raises amount from 2 to 3 falls through and casts 42079 on that same tick (`:335-336`).
- Once amount is already >= 3, ticks whose number modulo 3 is not 2 return before any work (`:327-328`). Ticks whose number modulo 3 is 2 cast 42079 again.

So a chain reaction is one tick per growth step, not one step per 30s cycle. Changing the 30s cycle cannot slow fires that are already burning. **NOT TESTED** in game.

### (b) CalcPeriodic slows every fire because the caster is the trigger — VERIFIED

`CalcPeriodic` (`hallows_end.cpp:309-317`) reads `GetCaster()`, not the Shade:

```cpp
if (!(creature->AI()->GetData(0) % 3))
    amplitude = static_cast<int32>(amplitude * 1.5f);
```

The aura is applied by the trigger itself: `me->CastSpell(me, SPELL_FIRE_AURA_BASE, true)` (`hallows_end.cpp:536` and `:554`). That call uses `Unit::CastSpell(Unit*, uint32, bool)` with the default empty original-caster GUID (`Unit.h:1681` at `a66f1be`; `Unit.h:1682` at `8daffda`, declaration text unchanged).

`Spell::Spell` then sets the original caster to that unit. The block is the same text at the same lines in both SHAs (`Spell.cpp:660-672`):

- empty original-caster argument becomes `m_caster->GetGUID()`
- when that GUID is the caster, `m_originalCaster = m_caster->ToUnit()`

`npc_soh_fire_trigger` extends `NullCreatureAI` (`hallows_end.cpp:523`) and does not override `GetData`. `NullCreatureAI` does not either (`PassiveAI.h:55-69`, identical blob at both SHAs). `UnitAI::GetData` returns 0 (`UnitAI.h:218`, identical blob). `0 % 3 == 0`, so the `!` condition is true and the 1.5 multiplier runs for every 42074 created this way, at every player count.

The Shade's own `GetData` returns `playerCount` (module `:237-241`, core `hallows_end.cpp:703-705`). That value is what **SpellHit** uses when choosing the starting amount (`hallows_end.cpp:540-545` and `:558-563`). It is not what **CalcPeriodic** uses. The player-count test and the period test are wired to different creatures.

What this does **not** establish:

- **UNKNOWN** — the Spell.dbc base amplitude. `spell_dbc.sql` is identical at both SHAs and has no row for 42074, 42079, 42132, 42339, or 42348. The number of milliseconds is not in this git tree.
- **UNKNOWN** — `SPELL_ATTR5_EXTRA_INITIAL_PERIOD` and `SPELL_ATTR5_SPELL_HASTE_AFFECTS_PERIODIC` for 42074. `CalculatePeriodic` (`SpellAuraEffects.cpp:599-687`, same function text at both SHAs) applies the script first, then spell mods and haste, and if the result is <= 0 it substitutes 1000ms (`:636-637`). A creature trigger normally has no player spell-mod owner. That is a reading of the code path, not a measured period.
- The later `Spell.cpp` edits at `8daffda` are GameObject-caster and line-of-sight changes. They do not change `Spell::Spell` lines 660-672. **VERIFIED** they do not retarget this unit self-cast.

### (c) A bucket on amount > 2 drops amount by 2, resets the timer, and does not refresh scale — VERIFIED

`npc_soh_fire_trigger::SpellHit` for 42348 (`hallows_end.cpp:570-581`):

- amount > 2: `ResetPeriodic(true)` then `SetAmount(amt - 2)`. No `SetObjectScale`.
- amount <= 2: `RemoveAllAuras()`. That removes the aura. It does not write scale.

`ResetPeriodic(true)` is `m_periodicTimer = m_amplitude; m_tickNumber = 0` (`SpellAuraEffects.h:89`, identical header at both SHAs).

Scale is written in three other places only:

- on aura apply, scale 1.0 and amount 1 (`hallows_end.cpp:343-345`), then SpellHit overwrites both
- on start/spread SpellHit, scale `0.5f + 0.5f * amount` (`:548`, `:566`)
- on a periodic tick that does not return early, scale `amount / 2.0f` (`:333-334`)

A full fire has amount 3 and scale 1.5. One splash sets amount to 1 and leaves scale at 1.5 until the next tick. That next tick increments amount to 2 and only then sets scale to 1.0. The visual lags by one full period, and it never shows the post-hit amount. **VERIFIED** as control flow. **NOT TESTED** on a client.

`spell_hallows_end_bucket_lands` (42339) is what the player hits with. If the hit unit is not a player it casts 42348 (`hallows_end.cpp:295-296`). Missile speed and travel time are Spell.dbc data. **UNKNOWN** / **NOT TESTED**. Travel time would add to the delay above; it is not required to explain the scale lag.

### (d) Solo playerCount is 1 on the initial cast and 0 afterwards — VERIFIED for a one-player list, with two corrections

`CastFires` (`HallowsEndShadeOfTheHorseman.cpp:435-484`, same arithmetic in core `hallows_end.cpp:807-839`):

1. Return if nobody is in range. The search is `AnyPlayerInObjectRangeCheck(me, 60.0f)` (`:419-433`). Default `reqAlive = true`, `disallowGM = false` (`GridNotifiers.h:1379-1394`, same line at both SHAs). Dead players are excluded. GMs and Playerbots are not.
2. `playerCount = players.size() - 1`.
3. The non-initial path may return without casting. The initial path does `playerCount += 1` (`:460-463`).
4. `sizeCount = playerCount / 3 + 1`, plus `playerCount % 2` when initial and `playerCount > 0` (`:465-473`).

`Reset` schedules event 2 twice, at 25s and at 43s (`:217-218`). Both call `CastFires(true)` (`:264-266`). There are two initial waves, not one, and both get the `+1`.

For exactly one nearby player:

| Call | playerCount | sizeCount | SpellHit amount on the Shade-lit trigger |
| --- | --- | --- | --- |
| Each initial wave | 1 | 2 | 2, because `(1 % 3) > 0` (`hallows_end.cpp:542-544`) |
| Each later wave | 0 | 1 | 1, because `(0 % 3) > 0` is false |

SpellHit runs during `CastSpell`, after `playerCount` has been stored, and the caster of 42132 is the Shade. **VERIFIED** from that order.

Corrections to the check-in wording:

- "Later ones get amount 1" is true for Shade-cast 42132. It is false for 42079. The spread caster is the burning trigger, whose `GetData` is 0, and `(0 % 3) > 1` is false, so spread fires start at amount 0 (`hallows_end.cpp:557-567`).
- The 60yd list is every alive `Player`. `AnyPlayerInObjectRangeCheck` has no bot test. A solo player standing among Playerbots does not produce playerCount 0/1. **POTENTIAL ISSUE** for any future solo detector. **NOT TESTED** with bots in the village.

`playerCount` also feeds the non-initial throttle `0.5 - playerCount * 0.25` (`:444-458`). With playerCount 0 the unburned fraction must be at least half the trigger list or the cycle casts nothing. That throttle does not slow auras that already exist.

## 4. Root cause

### Native core

This is the behaviour a single player feels, and it is in core at both SHAs:

1. Shade-lit solo fires start at amount 2. The first periodic tick raises them to 3 and spreads (`hallows_end.cpp:325-336`). One tick turns the easy bucket target (amount <= 2 is removed, `:580-581`) into a fire that one splash only reduces to 1.
2. Each spread fire starts at 0 and reaches a spreading tick in three periods.
3. The only period stretch in the script is the 1.5 factor, and it is applied to every fire (section 3b), not only to small groups.
4. After a partial splash the scale stays large for a full period (section 3c), so a successful hit looks like a miss until the next tick. The fire is already growing back on that tick.
5. The quest-offer window is the matron's `eventStarted >= 400 * IN_MILLISECONDS` (`hallows_end.cpp:443`), after which `allowQuest` is cleared. That script is not the Shade.

The stock Shade, if it were still bound, would use the same aura, the same bucket SpellHit, a 15s ignition repeat, and `counter > 21`.

### Module

The module replaces only the Shade. Relative to the stock Shade it:

- ignites on a 30s repeat instead of 15s
- forces the outcome when `counter` becomes 15 instead of 22

Schedule, counted from `Reset` (the first case-3 run is the 63s event, `:219`):

| | Core `npc_hallows_end_soh` | Module `npc_naxxramas_hallows_end_soh` |
| --- | --- | --- |
| Ignition repeat | 15s | 30s |
| Outcome test | `counter > 21` | `counter > 14` |
| Forced outcome | 63 + 21 * 15 = 378s | 63 + 14 * 30 = 483s |

**VERIFIED** arithmetic from the two `UpdateAI` switches. **NOT TESTED** as wall-clock time, because a casting Shade returns from `UpdateAI` before the event switch (`HallowsEndShadeOfTheHorseman.cpp:247-251`, core `hallows_end.cpp:711-712`), so a long cast delays the event clock.

The 30s change does not touch burning auras. The threshold change makes the forced ending later than stock, so the core chain reaction has a longer event to fill. That combination matches "we already slowed the cycle and it still spreads too fast."

Side effect, not the reported bug: `counter == 15` would say "more fires" (`:340-344`), but `counter > 14` finishes and returns first (`:312-333`). The talk is unreachable. **VERIFIED**. Left unchanged in this milestone. The `counter == 5` talk still runs.

On failure the module clears auras on the saved trigger list and despawns (`:495-506`). On evade it despawns without that clear (`:231-235`). **POTENTIAL ISSUE**, pre-existing, both factions, feature irrelevant. Not changed here.

On death, players inside 100yd get all four quest credits (`:598-610`): 11219, 11131, 12139, 12135. `AreaExploredOrEventHappens` is the stock call; a player without the quest is unaffected by that API's usual no-quest behaviour. **NOT TESTED**. There is no faction filter. Landing coordinates match core `GetPosToLand` for paths 235431 through 235436 (Goldshire, Kharanos, Azure Watch, Razor Hill, Brill, Falconwing Square).

### Quest rows

`quest_template.sql` is the same blob at both SHAs. `TimeAllowed` (column 72) is 0 for all four quests (rows at lines 6610, 6698, 7615, 7619). There is no quest-log countdown in that table. Flags, from `QuestDef.h:132-144` (identical blob):

- 11131 and 11219 use 4106 = daily + sharable + party-accept (`0x1000 | 0x8 | 0x2`)
- 12135 and 12139 use 4170 = daily + raid-flag + sharable + party-accept (`0x1000 | 0x40 | 0x8 | 0x2`)

`QuestDef.h` marks party-accept and the raid flag as not used by current core logic. Suggested group size is 0. The daily flag is the one that core actually consults (`QuestDef.h:288`). **NOT TESTED** as a repeatable daily.

## 5. Public Aura API at both SHAs

### What is identical

These headers are byte-identical at `a66f1be` and `8daffda`:

- `src/server/game/Spells/Auras/SpellAuras.h`
- `src/server/game/Spells/Auras/SpellAuraEffects.h`
- `src/server/game/Spells/Auras/SpellAuraDefines.h`
- `src/server/game/Entities/Object/Object.h`
- `src/server/game/AI/CoreAI/UnitAI.h`
- `src/server/game/AI/CoreAI/PassiveAI.h`

`SpellAuraEffects.cpp` and `SpellAuras.cpp` are not identical. The effect diff deletes the spell-66823/67618/67619/67620 Paralytic Toxin arm inside `UpdatePeriodic`. The aura diff clears a GameObject caster GUID and refuses to save auras with an empty caster GUID. Neither edit is on the 42074 path. `CalculatePeriodic` and `AuraEffect::Update` are the same text, at the same lines, in both files.

`Unit.h` gains `IsAreaEffectPvPBlocked` at `8daffda`. Aura getters below that point shift by one line. The signatures do not change.

### Getters the Shade can call on a trigger it already holds

The Shade does not own 42074. The caster GUID is the trigger. Ownership is not required. These are public const lookups on the trigger:

| Method | `a66f1be` | `8daffda` |
| --- | --- | --- |
| `Unit::GetAuraEffect(uint32, uint8, ObjectGuid = Empty)` | `Unit.h:1439` | `Unit.h:1440` |
| `Unit::GetAura(uint32, ...)` | `Unit.h:1447` | `Unit.h:1448` |
| `Unit::HasAura(uint32, ...)` | `Unit.h:1500` | `Unit.h:1501` |
| `Unit::RemoveAllAuras()` | `Unit.h:1423` | `Unit.h:1424` |
| `Unit::HasPeriodicDummyAura()` | `Unit.h:1824` | `Unit.h:1825` |

`HasPeriodicDummyAura` is `HasAuraType(SPELL_AURA_PERIODIC_DUMMY)`. It is true for any periodic dummy, not only 42074. The existing burn check uses it. A solo poll must key off `GetAuraEffect(42074, 0)` so it does not treat some other dummy as this fire.

`GetAmount` / `SetAmount` (`SpellAuraEffects.h:64-66`), `GetPeriodicTimer` / `SetPeriodicTimer` (`:68-69`), `GetAmplitude` (`:59`), `GetTickNumber` (`:87`), `GetApplyTime` (`SpellAuras.h:129`), and `GetStackAmount` (`SpellAuras.h:149`) are public. Empty `casterGUID` on `GetAuraEffect` does not filter by caster, so the Shade can see the trigger's self-cast aura.

`SetObjectScale` is the inline `SetFloatValue(OBJECT_FIELD_SCALE_X, scale)` (`Object.h:127`, both SHAs). It is the same write the core script uses. It does not read or write aura amount, tick number, or stacks.

### What a write actually touches

`SetAmount` stores `m_amount` and sets `m_canBeRecalculated = false`. It does not change `m_stackAmount`, `m_tickNumber`, `m_periodicTimer`, `m_amplitude`, or the client aura update. `HandleEffectApply` already calls `SetAmount(1)` (`hallows_end.cpp:345`), so the recalculation flag is already false before a Shade could observe the aura.

`SetPeriodicTimer` stores only `m_periodicTimer`.

`AuraEffect::Update` (`SpellAuraEffects.cpp:926-952`, both SHAs) subtracts `diff`, and while the timer is <= 0 it increments `m_tickNumber`, adds `m_amplitude` to the timer, calls `UpdatePeriodic`, and ticks. `UpdatePeriodic` ends by calling the aura script (`SpellAuraEffects.cpp:1070` at `a66f1be`, `:1057` at `8daffda`). The script then runs the amount/scale/spread logic. There is no hook between "timer elapsed" and "script decided to spread" that a CreatureAI poll can enter.

`m_amplitude` is private (`SpellAuraEffects.h:142`, `private:` at `:121`). Friends are aura construction, stacking, and the aura destructor. The Shade AI is not a friend. There is no `SetAmplitude`.

### Calls that restart ticks

`CalculatePeriodic(Unit*, bool create = false, bool load = false)` (`SpellAuraEffects.h:72`, body `SpellAuraEffects.cpp:599-687`):

- reloads `m_amplitude` from spell data and runs `CalcPeriodic` again (so the 1.5 factor is reapplied, not replaced by a caller-chosen period)
- on the non-load path sets `m_tickNumber = 0`
- for `SPELL_AURA_PERIODIC_DUMMY`, resets the timer even when `create` is false, because the reset condition is "create, or not a damage-over-time aura" (`:668-678`)

Calling it on a poll restarts the tick count and the countdown every time. That is the "restart ticks indefinitely" failure.

`ResetPeriodic(true)` (`SpellAuraEffects.h:89`) sets the timer back to the current amplitude and zeroes the tick number. Core already uses it for a partial bucket. Calling it from a poll freezes the fire for as long as the poll keeps winning the race, and it scrambles the every-third-tick phase.

`SetStackAmount` / `ModStackAmount` (`SpellAuras.h:150-151`) are the real stack counters. The fire level is effect amount, not stacks. Those two must not be called. `ChangeAmount` (`SpellAuraEffects.h:75`) unapplies and reapplies the effect. It is not needed for a timer or a scale write, and this milestone does not treat it as safe.

### Feasibility verdict

Approach A can do two things reliably, and only those, behind a default-off solo path:

1. **Slow the next interval** with one `SetPeriodicTimer` when a 42074 aura is first seen, and again when `GetTickNumber()` changes. The value is a bounded multiple of `GetAmplitude()`. That does not write amplitude, tick number, or stacks. Core's growth and every-third-tick rules keep running, on a longer clock.
2. **Match scale to a drop that core already applied.** If the observed amount fell and the scale is still larger than `amount / 2.0f`, call `SetObjectScale`. That uses the same field core writes on the next tick. It does not cast 42348, does not call `SpellHit`, and does not remove the aura. It is not a bucket hit. The hit already happened inside core.

Approach A cannot:

- Change the permanent amplitude without `CalculatePeriodic`, which restarts ticks.
- Stop the 2→3 tick from spreading. That decision happens inside the core script before the Shade's next poll (`hallows_end.cpp:325-336` together with `SpellAuraEffects.cpp:940-944`).
- Make `SpellHit` drop more than 2. A later `RemoveAllAuras` would be a second, delayed delete. It can also confuse a spread reapply (SpellHit sets a low amount and a matching scale in one cast, `:552-567`) with a bucket (amount falls, scale stays large, `:576-578`). This design does not do that delete.
- See the player's throw. It can only see the amount after 42348 has already been processed.
- Touch the matron's 400s window, the bucket missile, or spell 42339. Those are not on the Shade.

So approach A is a reliable solo pace and visual correction. It is not a reliable rewrite of core's spread or bucket formulas. If the desired rule is "one splash always removes 42074" or "amount never reaches 3", that has to live in the aura script or the trigger `SpellHit`. That is approach B.

### Approach B, not implemented

A module `AuraScript` for 42074 or a `CreatureScript` for 23686 would need a `spell_script_names` or `creature_template.ScriptName` row so the core registration is not the one that loads. The existing Shade override does not cover those rows. New script SQL is owner approval. This branch does not add it, and it does not register a second script for those IDs.

No other module-only hook was found that runs inside `AuraEffect::Update` before the Hallow's End script.

### Poll safety limits

Any later implementation has to stay inside the list `Reset` already builds: entry 23686 within 100yd (`HallowsEndShadeOfTheHorseman.cpp:202-213`). On use, re-check the entry and require `GetAuraEffect(42074, 0)`. Do not scan the map again. Do not call `RemoveAllAuras` from the poll. The failure path may keep its existing clear.

`UpdateAI` returns early while the Shade is casting (`:247-251`), and `AuraEffect::Update` can run more than one tick inside a single large `diff` (`SpellAuraEffects.cpp:933-944`). A poll cannot cancel a tick that already happened in that burst. Under a normal world diff shorter than the amplitude, one edge-triggered write lands before the next tick. **NOT TESTED** against a real update order. **POTENTIAL ISSUE** during a multi-second stall: the ticks that fit in that one aura update still use the core amplitude.

Setting the timer on every poll, rather than on tick change, never lets it reach 0. That is forbidden. The source test models it.

## 6. Proposed solo mode (design for a later change, not in this branch)

Default off. With the switch off, this file's behaviour stays the current module behaviour, including the 30s repeat, `counter > 14`, the existing playerCount formula, and the fact that Playerbots currently count as players. No new config key is added to `conf/mod_naxxramas_core.conf.dist` in this milestone, so an operator cannot enable a feature that has no reader.

Proposed keys, read by the Shade AI only in a future change:

| Key | Default | Bounds |
| --- | --- | --- |
| `NaxxramasCore.HallowsEnd.SoloFire.Enabled` | `0` | 0 or 1. Any other value is treated as 0. |
| `NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier` | `3` | Integers 1 through 8. 1 means "no extra delay". 0, negatives, and values above 8 are rejected and the solo timer writes are skipped. They are not clamped. Clamping 0 to 1 would hide a bad setting; accepting 0 would freeze fires if it were ever written into the timer. |

`PeriodMultiplier` multiplies the aura's current `GetAmplitude()`. That amplitude already includes core's 1.5 factor. A multiplier of 3 is three times the live core period, not three seconds. Seconds cannot be promised until the DBC amplitude is known.

### When the solo path is active

Use the same 60yd `AnyPlayerInObjectRangeCheck` as `CastFires`. Then:

- A real player is an alive `Player` for whom the existing module bot test is false.
- That test is the one already in `src/Systems/ForcedPvP.cpp:46-52`: `GET_PLAYERBOT_AI(player) != nullptr` when `Playerbots.h` is present, and false when the header is absent. The macro is `sPlayerbotsMgr.GetPlayerbotAI(object)` (`mod-playerbots` `src/Script/Playerbots.h:31` at `037c014`).
- Solo path iff `Enabled == 1` and that real-player count is exactly 1.
- Two or more real players: stock formula, even if bots are also nearby and even if `Enabled` is 1.
- Zero real players (bots only, or nobody): stock formula. Bot-only events are not given a special difficulty.
- GMs stay in the real-player count. `disallowGM` is false today; excluding them would make a GM helper silently turn a group into "solo". This is a review point for CS01, not an owner decision.
- Do not use group size. An out-of-range party member does not count. A bot in the party does not count while the solo path is on.

While the solo path is active, and only then:

- On first sight of a trigger's 42074, and again whenever `GetTickNumber()` changes (including a tick number that goes backwards after a new aura or a core `ResetPeriodic`), set the periodic timer to `GetAmplitude() * PeriodMultiplier` if the amplitude is in `1 .. 60000`.
- If amount fell since the last observation and scale is still greater than `amount / 2.0f`, set scale to `amount / 2.0f` (0 stays 0, matching the periodic formula). Do this only for that decrease. Do not resize a freshly lit fire just because SpellHit's `0.5 + 0.5 * amount` differs from `amount / 2`.
- Do not change `sizeCount`, the 30s repeat, `counter`, quest credit, faction, landing, fail clear, evade, or despawn.

While the solo path is inactive, the poll does not write timers or scale.

### Event coverage the design must keep

| Surface | Stock behaviour that stays |
| --- | --- |
| Quests 12135, 12139, 11131, 11219 | Still all credited from `CompleteQuest` on Shade death. No new quest filter. |
| Start | Still the core matron accepting 12135 or 12139 and summoning 23543. The module does not start the event. |
| Success | Still "no periodic dummy left" at a case-3 check, then land, then aggro. |
| Failure | Still `counter > 14` with a fire left, then clear the saved triggers and despawn. |
| Evade / despawn | Still the current early despawn. Fires are not newly cleared on evade. |
| Factions | Same script and the same six path ids. Solo detection is not team-based. |
| Feature off, and any group of 2+ real players | Current module AI, including bot-inclusive playerCount. |

## 7. Negative test matrix

Rows marked **source model** are executed by `tests/test_f10_hallows_end_solo_fire_s1.py`. They replay the rules above. They are not a worldserver run.

| Id | Case | Required result | Where |
| --- | --- | --- | --- |
| N1 | Enabled off, one real player | playerCount 1 on each initial wave, 0 on later waves; 30s and `counter > 14` unchanged; no timer write | source model |
| N2 | Enabled off, one real player plus bots | bots remain inside the stock player count | source model |
| N3 | Enabled on, one real player plus any bots | solo path | source model |
| N4 | Enabled on, two real players plus bots | stock path | source model |
| N5 | Enabled on, zero real players | stock path | source model |
| N6 | Multiplier 0, negative, 9, non-integer | rejected, no timer write | source model |
| N7 | Poll calls `ResetPeriodic` or assigns the long timer on every update | tick never completes | source model |
| N8 | Scale write only | amount unchanged, so a later growth tick still spreads | source model |
| N9 | Amount held at 2 until the core tick runs | the 2→3 tick still spreads inside that tick | source model |
| N10 | Trigger not in the saved 23686 list, or no 42074 | poll does not write it | design rule, not a runtime test |
| N11 | Shade death | all four quest ids still passed to `AreaExploredOrEventHappens` | source contract |
| N12 | Failure | still clears the saved list and despawns; solo mode must not add a second clear | source contract |
| N13 | Success | still lands and schedules the aggro event | source contract |
| N14 | Evade | still despawns without the failure clear | source contract |
| N15 | Both factions and all six paths | same AI, same coordinates as core | source contract |
| N16 | Solo path on | does not replace 30s or `counter > 14` | design rule |
| N17 | Dead player in range | already excluded by `reqAlive` | source contract |
| N18 | GM in range | counts as a real player in this proposal | review point |
| N19 | Partial bucket | amount 3 becomes 1, tick number 0, scale stays 1.5 until the next tick | source model |
| N20 | Amount <= 2 bucket | aura removed; scale write is not what removes it | source model |
| N21 | Feature off in this branch | no `HallowsEnd.SoloFire` key in the distributed config, no `SetPeriodicTimer` in the module AI | source contract |

N10, N16, and N18 are not runtime tests because the C++ poll does not exist yet. N21 is the milestone guard.

## 8. Not tested

- No worldserver, no client, no packet capture, no stopwatch on a village.
- No installed Spell.dbc, so no millisecond amplitude and no 42339 missile speed.
- No count of 23686 spawns per village.
- No confirmation that the live database has applied the 23543 ScriptName override. The SQL file is in the repo; applying it is an operator action and was not done here.
- No Playerbot walking the fire event.
- No proof of aura-update versus creature-AI order under lag.
- Individual Progression was checked for conflicting files only. It was not built.
- CI source pins, if they pass, still are not gameplay acceptance.

## 9. What CS01 can review, and what would need the owner

This milestone does not ask the owner to pick a behaviour. Live enablement, new script SQL, and S5–S7 remain owner gates. Nothing in this file is an owner decision.

Review points for CS01:

1. Approach A is accepted only for the edge-triggered timer stretch and the post-drop scale match. It is rejected for rewriting amount growth, faking a splash, or calling `CalculatePeriodic` / `ResetPeriodic` from the poll.
2. One-splash deletion of a full fire is approach B if it is wanted. It is not in the proposed defaults.
3. Proposed multiplier is 3 times the live (already 1.5x) amplitude, default off, integers 1..8 otherwise ignored.
4. GMs count as real players. Bots do not, and only while the solo path is on.
5. The unreachable `counter == 15` talk, the evade-without-clear, and the matron's 400s window versus the module's 483s outcome are recorded and left alone.
6. S2, if it happens, stays in the Shade AI, default off, with the N1–N21 matrix still true. No new SQL.
