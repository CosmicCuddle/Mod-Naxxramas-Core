# F10 S2 — Hallow's End Shade solo fire, module-only implementation

Status: **module C++ added, default off**. Source and model tests only. No SQL, DBC, core, Playerbots, or Individual Progression files were edited. Nothing here was run on a worldserver or a client. A passing source test is not gameplay acceptance.

Base this change was written against: `e72aa3aa3dc579fff8db34fd41f42da5d8928b78` (the signed-off S1 head). The behaviour rules are the S1 design in `docs/research/F10-hallows-end-solo-fire-S1.md`.

Labels:

- **VERIFIED** — the statement matches the cited source, or a test command in this document produced that result.
- **POTENTIAL ISSUE** — the source shows a real limitation or hazard. Gameplay effect is not proven.
- **UNKNOWN** — the fact is not in the sources that were read.
- **NOT TESTED** — not executed on a server, client, or database. The Shade translation unit was not compiled against AzerothCore in this stage.

## 1. What the module does when the option is off

`NaxxramasCore.HallowsEnd.SoloFire.Enabled` defaults to `0`. Any raw value other than the integer 1 is treated as off. While it is off, `CastFires` does not remove bots from the nearby list, and the poll disarms per-trigger watches without writing a timer or a scale. The 30s repeat, `counter > 14`, quest credit, landing, failure clear, and evade path are the same statements as S1.

The numeric config parser is not used for these keys. Grimfeather `Config.cpp` substitutes the default when a token is not a number (`Config.cpp` around the `StringTo` failure return). A non-integer multiplier must be a rejection, not a silent default of 3, so the Shade reads the raw string (`GetOption<std::string>`, `showLogs = false`) and parses it in the module. **VERIFIED** against `src/common/Configuration/Config.cpp` at both core SHAs below: the bad-value path returns `def`, and `ParseFile` erases quote characters before the value is stored.

## 2. What it does when the solo path is on

The path is on only when Enabled is exactly 1 and the 60yd alive-player list contains exactly one real player. A real player is an alive `Player` who fails the bot test. That test is the one already in `src/Systems/ForcedPvP.cpp`: `GET_PLAYERBOT_AI(player) != nullptr` when `Playerbots.h` is present, and false when the header is absent. A GM is not removed. `AnyPlayerInObjectRangeCheck` is still constructed as `(me, 60.0f)`, so the defaults `reqAlive = true` and `disallowGM = false` stay in force (`GridNotifiers.h:1382`).

Before `players.size()` is read, and only on that path, bots are removed from the list. The formulas below that line are unchanged:

- `playerCount = players.size() - 1`
- initial `playerCount += 1`
- `sizeCount = (playerCount / 3) + 1`
- initial `playerCount % 2`
- later `0.5f - playerCount * 0.25f`

One real player with 0, 1, or 8 bots therefore feeds those formulas the nearby count 1. Off, zero real players, and two or more real players do not remove anyone.

`PeriodMultiplier` defaults to 3 and is read only while the path is active.

- Integers 2 through 8 may call `SetPeriodicTimer(GetAmplitude() * multiplier)` when the amplitude is in 1..60000. The write is edge-triggered: the first time that trigger's 42074 is watched, and a later poll whose `GetTickNumber()` differs. The same tick writes nothing.
- Integer 1 updates that edge memory and does not write the timer.
- 0, negatives, values above 8, and non-integers are rejected. They are not clamped. Timer writes are skipped and edge memory is not created or refreshed. Scale matching still runs. The solo player-count narrowing does not read the multiplier, so a rejected multiplier does not put bots back into the count.

Scale matching does not read the multiplier. If the observed amount is lower than the last amount seen on an active poll, and the scale is still greater than `amount / 2.0f`, the Shade sets the scale to `amount / 2.0f`. A fresh fire whose SpellHit scale is `0.5 + 0.5 * amount` is not resized just because that differs from `amount / 2`. An amount that stays the same or rises is not resized.

Turning the path off mid-event writes nothing. Each per-trigger watch is disarmed and its stored tick is dropped. The watch stays known. The next active poll re-arms by storing the tick it sees then, with no timer write. A tick change after that re-arm is an ordinary edge. `Reset()` clears the map so a new event is not a re-arm of the previous one.

The poll walks the trigger GUID list `Reset` already built. It re-checks entry 23686 and requires `GetAuraEffect(42074, 0)`. `EFFECT_0` is 0 (`SharedDefines.h:31`). It does not scan for triggers again. It does not call `RemoveAllAuras`. The failure path still clears the saved triggers.

## 3. Limitation — instant extinguish is not implemented

A true one-splash extinguish cannot be done safely from this Shade script.

Core `npc_soh_fire_trigger::SpellHit` for splash 42348 (`hallows_end.cpp:570-581`) already owns the bucket. Amount above 2 becomes amount - 2 and the tick restarts inside that script. Amount at or below 2 removes the aura there. The spread decision on the tick that raises amount from 2 to 3 is inside `spell_hallows_end_base_fire::HandleEffectPeriodicUpdate` (`hallows_end.cpp:320-336`), which runs from `AuraEffect::Update` before this AI can see it.

Doing that from the Shade would mean a second, delayed `RemoveAllAuras`, a fake cast of 42348, or a new script binding for 42074 or creature 23686. Those are not in this change. There is no module SQL, no `spell_script_names` row, and no edit to `spell_hallows_end_base_fire` or `npc_soh_fire_trigger`.

What this stage can do is the S1 approach A only: an edge-triggered longer countdown for multipliers 2..8, and a scale write after core has already lowered the amount. It does not make one splash remove 42074. **POTENTIAL ISSUE** for anyone who wanted instant extinguish. **NOT TESTED** in a village. CS01 review should treat that as an open limitation, not as a completed bucket change.

Other source limits, unchanged from S1 and not worked around here:

- The poll sits after the existing `UNIT_STATE_CASTING` return. A cast that skips `UpdateAI`'s event switch also skips the poll. **POTENTIAL ISSUE** during a long cast. **NOT TESTED**.
- A replaced 42074 whose new tick number equals the stored tick is not a new edge. A new aura that starts at 0 after a stored tick of 0 does not get a first-sight write. **POTENTIAL ISSUE**. **NOT TESTED**.
- The matron `eventStarted >= 400 * IN_MILLISECONDS` window and the module `counter > 14` / 30s schedule are still both present. The ~400s versus ~483s acceptance risk from S1 is unchanged. **POTENTIAL ISSUE**. **NOT TESTED** as wall-clock time.
- Spell.dbc amplitude and the 42339 missile speed are not in this git tree. **UNKNOWN**. The multiplier is a factor on `GetAmplitude()`, not a number of seconds.

## 4. Provenance

Fork: `https://github.com/Grimfeather/azerothcore-wotlk`. Not upstream AzerothCore.

| Role | Commit |
| --- | --- |
| Pinned core | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` |
| Prospective core | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| `hallows_end.cpp` blob at both | `02282feb50f24debd6bbeb0fe9b928db6adabd21` |
| Pinned Playerbots | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Pinned Individual Progression | `4ff4b5fcc1480348f058c632573143e62d4e3a41` |

Symbols the Shade calls, and the core symbols it deliberately does not replace:

| Symbol | Where |
| --- | --- |
| `spell_hallows_end_base_fire` | `hallows_end.cpp:305`, registered at `:1511`. Not edited. |
| `HandleEffectPeriodicUpdate` | `hallows_end.cpp:320`. Not edited. |
| `npc_soh_fire_trigger` | `hallows_end.cpp:523`, registered at `:1519`. Not edited. |
| Self-cast of 42074 | `hallows_end.cpp:536`. |
| `GetAuraEffect(..., EFFECT_0)` | `hallows_end.cpp:537`. The Shade uses spell 42074 and effect index 0. |
| Splash `SpellHit` | `hallows_end.cpp:570`, `ResetPeriodic(true)` at `:577`, `SetAmount(amt - 2)` at `:578`, `RemoveAllAuras` at `:581`. The Shade does not call these. |
| `AuraEffect::SetPeriodicTimer` | `SpellAuraEffects.h:69`. Used only from `PollSoloFires` when the policy sets `writeTimer`. |
| `GetAmplitude` / `GetAmount` / `GetTickNumber` | `SpellAuraEffects.h:59`, `:64`, `:87`. |
| `m_amplitude` private, no setter | `SpellAuraEffects.h:142`. |
| `Unit::GetAuraEffect` | `Unit.h:1439` at the pinned SHA, `Unit.h:1440` at the prospective SHA. |
| `GetObjectScale` / `SetObjectScale` | `Object.h:126` and `:127`. |
| `AnyPlayerInObjectRangeCheck` | `GridNotifiers.h:1379`. |
| `EFFECT_0 = 0` | `SharedDefines.h:31`. |
| `GET_PLAYERBOT_AI` | `mod-playerbots` `src/Script/Playerbots.h:31` at `037c014`. |

Individual Progression at the pinned ref has no Hallow's End fire script. **VERIFIED** in S1 and re-checked by the S2 source workflow when `F10_IP` is set. **NOT TESTED** as a build of that module.

## 5. Tests

Local command, from the module root. `F10_CORE_OLD` and `F10_CORE_NEW` were file trees of the two Grimfeather SHAs above (the cited paths only). `F10_IP` was a detached checkout of `4ff4b5fcc1480348f058c632573143e62d4e3a41`. `F10_PLAYERBOTS_H` was `Playerbots.h` at `037c01418b5d01506917a3db9b44fd56ac5f965c`.

```text
F10_CORE_OLD=/tmp/f10-core-old \
F10_CORE_NEW=/tmp/f10-core-new \
F10_PLAYERBOTS_H=/tmp/f10-playerbots/src/Script/Playerbots.h \
F10_IP=/tmp/f10-ip \
python3 -m unittest discover -s tests -p 'test_f10_hallows_end_solo_fire_s*.py' -v
```

Result: **VERIFIED** `Ran 55 tests in 1.411s` / `OK`. No skips. That run compiles `tests/f10_s2_solo_fire_policy_tests.cpp` with `g++ -std=c++17 -Wall -Wextra -Werror` and requires `F10_S2_POLICY_OK` plus a TRACE match against the S1 model. It does not compile `HallowsEndShadeOfTheHorseman.cpp`.

These are source/model results only.

Covered by those tests:

- 0, 1, and 8 bots beside one real player, option on, effective nearby count 1 in the unchanged formulas
- option off, zero real players, and two or more real players stay on the legacy count
- multiplier 1 does not write a partially elapsed timer
- rejected and out-of-range multiplier values do not write the timer and do not create edge memory; they are not clamped to the default
- same-event disarm drops the stored tick, and the next active poll re-arms without a timer write
- a later tick change after re-arm writes again
- scale moves to `amount / 2` only when the amount fell; a fresh SpellHit scale and a rising amount do not
- `events.Repeat(30s)` and `counter > 14` remain single code statements
- the poll does not contain a splash cast, `RemoveAllAuras`, `SetAmount`, `ResetPeriodic`, or `CalculatePeriodic`
- distributed config defaults are Enabled 0 and PeriodMultiplier 3
- the S2 workflow grants `contents: read` and does not upload artifacts

## 6. Not tested

- No worldserver, no client, no database apply, no live server.
- The Shade `.cpp` was not compiled or linked into `worldserver`. Include resolution against Grimfeather headers is **NOT TESTED**.
- No packet capture and no stopwatch on a village.
- No Playerbot walked the fire event. The 0/1/8 cases are the source model plus the policy binary.
- No proof of aura-update versus creature-AI order under lag.
- No measurement of the Spell.dbc amplitude.
