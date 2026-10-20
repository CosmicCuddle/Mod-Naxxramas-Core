# F10 S1 — one-bucket extinguish for the Shade fire (design only)

Status: **source trace and design only**. No gameplay C++ was added. No SQL, DBC, core, Playerbots, or Individual Progression files were edited. Nothing here was run on a worldserver or a client. A passing source test is not gameplay acceptance.

Module base this design was read against: `c193be076dedd5bbf1dafa01fb4ca15f16e07f9e` (`cs02/f10-s2-config-marker-2026-10-20`). That commit already contains the default-off solo-fire path. This branch does not change that path.

The claim checked below is GitHub issue #48, comment `6292945249`, posted by `CosmicCuddle` at `2026-10-20T14:15:00Z`:

https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6292945249

Labels:

- **VERIFIED** — the statement matches the cited source, or a command in this document produced that result.
- **POTENTIAL ISSUE** — the source shows a real mismatch or hazard. Gameplay effect is not proven.
- **UNKNOWN** — the fact is not in the sources that were read.
- **NOT TESTED** — not executed on a server, client, or database.

## 1. Verdict

A module-only, default-off one-bucket action is possible without SQL and without replacing an upstream script.

The safe public observation point is `AllSpellScript::OnDummyEffect` for spell **42339** on creature entry **23686**. That callback runs inside the accepted hit of `spell_hallows_end_bucket_lands`, after that script has already called `CastSpell` of splash **42348** on the same creature, and only because the stock script does not cancel the default dummy effect.

No public callback observes spell **42348** at `npc_soh_fire_trigger::SpellHit`. Registering a module `SpellScript` for 42348 does nothing at either pinned core: the loader is database-bound, and `spell_script_names` has no row for 42348. **VERIFIED**.

The S2 action must not use "aura amount decreased" as the reason to extinguish. The reason is the accepted 42339 dummy hit, plus the gates in section 6. Amount is not an input.

This branch does not implement that action.

CI run ids are written on the draft PR and on issue #48 after `.github/workflows/f10-s1-one-bucket.yml` finishes. They are not invented in this file.

## 2. Commits that were read

Fork: `https://github.com/Grimfeather/azerothcore-wotlk`. Not upstream AzerothCore.

| Role | Commit |
| --- | --- |
| Pinned core | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` |
| Prospective core | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| `hallows_end.cpp` blob at both | `02282feb50f24debd6bbeb0fe9b928db6adabd21` |
| `spell_script_names.sql` blob at both | `e93f9e13d5ab2c98b134c5c632fa1f6f688afa15` |
| `creature_template.sql` blob at both | `899a56b0f5d7bac6536a48e038acb23ba8a70812` |
| Pinned Playerbots | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Pinned Individual Progression | `4ff4b5fcc1480348f058c632573143e62d4e3a41` |

`src/server/game/Scripting/` is byte-identical at both core SHAs. **VERIFIED** by `diff -rq` on the extracted trees. Hook line numbers in that directory apply to both SHAs.

`Spell::EffectDummy` is the same text at both SHAs, including the `OnDummyEffect` calls at `SpellEffects.cpp:796-804`. The file blobs differ (`cfb69c5d266a23f3a120278f2131a7260b72d7ba` at the older pin, `d684660c9959422202546e944f039beb392a117f` at the newer pin) because other functions in that file differ. **VERIFIED**.

`hallows_end.cpp` line numbers below apply to both SHAs.

## 3. CS01 claim, checked

The comment's behaviour claims match the source. A few line ranges are the class or the whole `SpellHit`, not the single statement. That does not change the behaviour.

| Claim | Source | Label |
| --- | --- | --- |
| `spell_hallows_end_bucket_lands::HandleDummy` forwards a creature hit to splash 42348, and a player hit to 42349 | Class `hallows_end.cpp:281-303`. Handler `287-297`. Player: `GetHitPlayer()` then `CastSpell(..., SPELL_CREATE_BUCKET, true)` at `293-294`. `SPELL_CREATE_BUCKET = 42349` at `256`. Creature: `GetHitUnit()` then `CastSpell(..., SPELL_WATER_SPLASH, true)` at `295-296`. `SPELL_WATER_SPLASH = 42348` at `257`. | **VERIFIED** |
| Normal fire `npc_soh_fire_trigger::SpellHit` on 42348 subtracts 2 from 42074 when amount > 2, otherwise `RemoveAllAuras` | Function `532-584`. Splash branch `570-582`. Amount read at `574`. `amt > 2` resets the timer and `SetAmount(amt - 2)` at `575-578`. Else `RemoveAllAuras()` at `580-581`. | **VERIFIED** |
| Amount 3 therefore stays lit at amount 1 and needs another splash to go out | `3 > 2`, so the result is amount 1 and the aura remains. The next splash sees `1 <= 2` and removes it. A later growth tick can raise amount again before that second splash. | **VERIFIED** arithmetic. Regrowth before the second splash is the existing S1 bucket model. **NOT TESTED** in a village. |
| `HandleEffectPeriodicUpdate` grows amount up to 3 and spreads at >= 3 | `hallows_end.cpp:320-337`. Below 3, amount increments at `325-326`. The tick that reaches >= 3 falls through. `SetAmount` at `330`. Spread `CastSpell(..., SPELL_SPREAD_FIRE, true)` at `335-336`. `SPELL_SPREAD_FIRE = 42079` at `255`. | **VERIFIED** |
| Training fire uses different splash math | `npc_hallows_end_train_fire::SpellHit` `920-935`. Splash only if `caster->ToPlayer()` at `922`. Amount > 1 becomes amount - 1 at `927-928`. Else `RemoveAllAuras()` at `929-930`. Entry 23537, ScriptName `npc_hallows_end_train_fire`, `creature_template.sql:17567`. | **VERIFIED**. The player-caster requirement is in the source and was not in the comment. It is an extra guard, not a contradiction. |
| The module Shade does not handle bucket hits. 23686 keeps the stock script | `HallowsEndShadeOfTheHorseman.cpp` has no `SpellHit` and does not mention 42339 or 42348. World SQL overrides only entry 23543 (`data/sql/db-world/2026_09_21_00_event_script_overrides.sql:24-26`). Core still binds 23686 to `npc_soh_fire_trigger` (`creature_template.sql:17715`) and registers it at `hallows_end.cpp:1519`. | **VERIFIED** |
| PRs #65 and #66 do not implement one-bucket | #65 is the config-reader marker on this base. #66 is the linked worldserver proof. The Shade poll stretches a timer and may match scale. It does not cast 42348 and does not remove 42074 from the poll. | **VERIFIED** from this tree and the PR titles. **NOT TESTED** as a worldserver run. |

The comment's "no in-game test" sentence is still true for this branch. **NOT TESTED**.

## 4. What can see a hit

### 4.1 Accepted hit path

`Spell::DoAllEffectOnTarget` sets `spellHitTarget` only when `missCondition == SPELL_MISS_NONE` (`Spell.cpp:2709` at `a66f1be`, `Spell.cpp:2705` at `8daffda`). It then calls `DoSpellHitOnUnit` (`Spell.cpp:2744` at `a66f1be`, `Spell.cpp:2740` at `8daffda`). A non-`SPELL_MISS_NONE` return clears `spellHitTarget` (`Spell.cpp:2749-2754` at `a66f1be`, `Spell.cpp:2745-2750` at `8daffda`).

`DoSpellHitOnUnit` returns `SPELL_MISS_IMMUNE` for a spell with `Speed > 0` that fails the impact immunity check, and that return is before any effect handler (`Spell.cpp:3095-3097` at `a66f1be`, `Spell.cpp:3091-3093` at `8daffda`). Effect handlers run later: `Spell.cpp:3341` at `a66f1be`, `Spell.cpp:3342` at `8daffda`. **VERIFIED**.

`Spell::HandleEffects` runs spell-script effect hooks first. It runs the core effect only when the script did not prevent it (`Spell.cpp:5861-5865` at `a66f1be`, `Spell.cpp:5862-5866` at `8daffda`).

`spell_hallows_end_bucket_lands` registers `OnEffectHitTarget` for `EFFECT_0`, `SPELL_EFFECT_DUMMY` (`hallows_end.cpp:301`). `HandleDummy` does not call `PreventHitDefaultEffect`. **VERIFIED**. So whenever that handler runs, `Spell::EffectDummy` still runs afterwards.

`EffectDummy` calls `sScriptMgr->OnDummyEffect(m_caster, m_spellInfo->Id, effIndex, unitTarget->ToCreature())` when the hit unit is a creature (`SpellEffects.cpp:798-800`, both SHAs). That reaches `AllSpellScript::OnDummyEffect` through `CALL_ENABLED_HOOKS` (`AllSpellScript.cpp:72-74`, `AllSpellScript.h:92`). The call is additive. It does not replace `spell_hallows_end_bucket_lands`. **VERIFIED**.

Order for an accepted 42339 hit on a creature:

1. `HandleDummy` runs and, for a non-player unit, `CastSpell` of 42348 on that unit (`hallows_end.cpp:295-296`).
2. `EffectDummy` then calls `OnDummyEffect` with spell id 42339 and that creature.
3. Later, `AI()->SpellHit` runs for 42339 if the hit still stands. The fire trigger ignores every id except 42132, 42079, and 42348 (`hallows_end.cpp:534-570`). A 42339 `SpellHit` does not change the fire.

`CastSpell` of an immediate 42348 finishes, including the stock splash `SpellHit`, before `HandleDummy` returns. A 42348 with `Speed > 0` is only scheduled there (`Spell.cpp:4131-4139` and `4156-4159` at `a66f1be`; `Spell.cpp:4132-4140` and `4157-4160` at `8daffda`). **UNKNOWN**: Spell.dbc speed of 42348 and of 42339. `spell_dbc.sql` has no row whose tuple starts with 42339, 42348, 42349, 42074, 42079, or 42132. `spell_linked_spell.sql` and `spell_scripts.sql` do not name those ids either. **VERIFIED** those SQL files. **NOT TESTED** against a client DBC.

### 4.2 Hooks that do not see a validated 42348 hit

| Hook | Why it is not the splash hit | Label |
| --- | --- | --- |
| `AllSpellScript::OnSpellCast` | Runs at the end of `Spell::_cast` (`Spell.cpp:4212` at `a66f1be`, `Spell.cpp:4213` at `8daffda`), after `handle_immediate` only when speed is not > 0. When speed is > 0 the hit has not happened. 42348's speed is **UNKNOWN**, so this hook is not a validated impact. | **VERIFIED** call site. **UNKNOWN** which side 42348 lands on. |
| `PlayerScript::OnPlayerSpellCast` | Called from `Spell::_cast` with the comment "should be done before the spell is actually executed" (`Spell.cpp:3946-3948` at `a66f1be`, `Spell.cpp:3947-3949` at `8daffda`). Declaration says "Called in Spell::Cast" (`PlayerScript.h:348-349`). Fires only when the caster is a `Player`. | **VERIFIED** |
| `AllCreatureScript` | No `SpellHit` callback. The virtuals are update, level, world add/remove, save, gossip, quest, `GetCreatureAI`, and FFA PvP (`AllCreatureScript.h:30-104`). | **VERIFIED** |
| `UnitScript::OnDamage` | No spell id (`UnitScript.h:64`). | **VERIFIED** |
| `UnitScript::ModifySpellDamageTaken` | Has a spell id (`UnitScript.h:74`). It is a damage hook. Whether 42348 deals damage is **UNKNOWN** without Spell.dbc. A zero-damage splash does not enter the `m_damage > 0` path in `DoAllEffectOnTarget`. | **VERIFIED** the hook shape. **UNKNOWN** the spell's damage. |
| `UnitScript::OnAuraApply` / `OnAuraRemove` | Fire when an aura is applied or removed (`UnitScript.h:84-86`). 42348's effect type is **UNKNOWN**. Removal of 42074 is the result we want, not the evidence of a bucket. | **UNKNOWN** for 42348. Rejected as a bucket signal. |
| Shade `PollSoloFires` | Sees amount and tick after the fact. An amount drop is not a bucket. Section 5. | **VERIFIED** the current poll does not remove the aura. |

Creature `AI()->SpellHit` is the stock splash handler. The call is `Spell.cpp:3067` at `a66f1be` (`SpellHit(unitCaster, m_spellInfo)`) and `Spell.cpp:3063` at `8daffda` (`SpellHit(unitCaster ? unitCaster : m_originalCaster, m_spellInfo)`). There is no `sScriptMgr` call beside it. **VERIFIED**.

## 5. Spell-script registration at both pins

`SpellScriptsContainer` is `std::multimap<uint32, uint32>` (`ObjectMgr.h:390`, both SHAs). Each `spell_script_names` row is inserted (`ObjectMgr.cpp:6392` at `a66f1be`, `ObjectMgr.cpp:6405` at `8daffda`). Several rows for one spell id are all stored.

`ScriptMgr::CreateSpellScripts` walks every bound row and pushes every loader that returns a `SpellScript` (`SpellScriptLoader.cpp:22-40`). Several different script names on one spell id all run. **VERIFIED**.

One name does not stack. `SpellScriptLoader::IsDatabaseBound` returns true (`SpellScriptLoader.h:31`). `isAfterLoadScript` returns that flag (`ScriptObject.h:49`). At database bind time, a second loader with the same name deletes the previous one (`ScriptMgr.h:856-866`) and keeps the new one (`ScriptMgr.h:870`). **VERIFIED**.

A loader whose name is not in the database is logged and not stored for later lookup (`ScriptMgr.h:878-883`). `RegisterSpellScript` uses the class name (`SpellScriptLoader.h:88`). A module script named anything other than `spell_hallows_end_bucket_lands` or `spell_hallows_end_base_fire` is therefore not attached to 42339 or 42074, and a new name for 42348 is not attached either. **VERIFIED**.

Rows in `spell_script_names.sql` (same blob at both SHAs):

| Spell | Rows | Script |
| --- | --- | --- |
| 42074 | 1, line 1087 | `spell_hallows_end_base_fire` |
| 42339 | 1, line 1092 | `spell_hallows_end_bucket_lands` |
| 42348 | 0 | none |
| 42349 | 0 | none |
| 42079 | 0 | none |
| 42132 | 0 | none |

What that means if a later change registers a module spell script:

| Registration | Result at both pins |
| --- | --- |
| New `SpellScript` name aimed at 42348, no SQL | Not called. Log: script name is not assigned. Stock splash `SpellHit` is unchanged. |
| Second SQL row for 42348 plus that new name | Both would run. 42348 has no stock spell script to collide with. The new script's `AfterHit` would run after `AI()->SpellHit` (`CallScriptAfterHitHandlers` is after the AI call, `Spell.cpp:3084` at `a66f1be` and `Spell.cpp:3080` at `8daffda`). This needs SQL. Out of scope here. |
| Same C++ name `spell_hallows_end_bucket_lands` | Replaces the stock loader. Every 42339 hit would use the module script instead of the stock forward, including training fires and groups. That is a broad override. Not the S2 plan. |
| Same C++ name `spell_hallows_end_base_fire` | Replaces the stock aura script. Not the S2 plan. |

`AllCreatureScript::GetCreatureAI` is consulted before the database creature script (`CreatureScript.cpp:160-171`). A non-null return replaces `npc_soh_fire_trigger` for that creature (`CreatureAISelector.cpp:84-86`). That is a broad override of every 23686 which receives the module AI. Not the S2 plan.

## 6. S2 implementation to write later, not in this branch

Default off. No SQL. No DBC. No edit to AzerothCore, Playerbots, or Individual Progression. Do not register a `SpellScript`. Do not return an AI from `GetCreatureAI`. Do not read aura amount to decide.

Add one `AllSpellScript` in the existing Shade translation unit, so it can see `npc_naxxramas_hallows_end_soh`. Register it from `AddHallowsEndShadeOfTheHorsemanScripts`. Pass only `ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE`. An empty hook list enables every `AllSpellScript` hook (`AllSpellScript.cpp:100-103`). Do not use an empty list.

Proposed key, absent from `conf/mod_naxxramas_core.conf.dist` in this branch:

| Key | Default | Rule |
| --- | --- | --- |
| `NaxxramasCore.HallowsEnd.SoloFire.OneBucket` | `0` | Exactly the integer 1 arms the hook. Any other token is off. Not clamped. |

The existing `NaxxramasCore.HallowsEnd.SoloFire.Enabled` key stays the solo-path switch. One-bucket also requires that switch to be exactly 1. Reusing `Enabled` alone would change bucket rules for an operator who already turned on the period stretch. **POTENTIAL ISSUE** if a later patch folds the two switches together. This design keeps them separate.

On `OnDummyEffect(caster, spellId, effIndex, creature)`:

1. Return unless `spellId == 42339`.
2. Return unless `creature` is non-null and `GetEntry() == 23686`.
3. Return unless the one-bucket key is exactly 1.
4. Return unless `caster->ToPlayer()` is non-null and the existing bot test is false. That test is `IsHallowsEndShadePlayerBot` in `HallowsEndShadeOfTheHorseman.cpp:58-68`: `GET_PLAYERBOT_AI(player) != nullptr` when `Playerbots.h` is present, otherwise false. A bot throw does nothing here even if one real player is standing nearby.
5. Find living creatures with entry 23543 within 100 yards of the hit trigger whose AI dynamic-casts to `npc_naxxramas_hallows_end_soh`, whose `unitList` contains the trigger GUID, and who still have `UNIT_FLAG_NON_ATTACKABLE`. The list is the one `Reset` already builds (`HallowsEndShadeOfTheHorseman.cpp:255-267`). The flag is set in `Reset` (`277-278`) and cleared when the combat phase starts (`421-422`).
6. If that set is not exactly one Shade, return. Zero means the fire event is not active for this trigger. Two means the hit is ambiguous.
7. On that Shade, reuse `SoloFirePathActive` (`HallowsEndShadeOfTheHorseman.cpp:470-476`): Enabled exactly 1 and exactly one real player in the existing 60-yard list. Bots are not real players. A GM is real, same as the current solo path. If the path is not active, return.
8. Call `creature->RemoveAllAuras()`. That is the same call the stock splash uses when amount is <= 2 (`hallows_end.cpp:581`). Do not call `SetAmount`. Do not cast 42348 again. Do not touch another creature.

Training fire 23537 fails step 2. A 23686 that is not in the Shade list fails step 5 or 6. Two real players fail step 7. The key being off fails step 3. The stock `SpellHit` still runs on its own and is not edited.

Immediate splash: stock `SpellHit` of 42348 has already finished before step 8. Amount <= 2 is already removed; step 8 is a second clear. Amount > 2 is now amount - 2 and still has the aura; step 8 removes it. Delayed splash: step 8 clears the aura at the 42339 hit, and the later 42348 `SpellHit` sees no 42074 (`hallows_end.cpp:572`) and does nothing. **UNKNOWN** which of those two timings 42348 uses. Both timings end with the hit fire out when the gates pass. **NOT TESTED** in a village.

A tick that already cast 42079 is not recalled. The child fire is another creature. It stays until something hits that child. **VERIFIED** as control flow. **POTENTIAL ISSUE** for a player who expects one bucket to erase a spread that has already left the target. **NOT TESTED**.

A tick that has not run yet cannot grow an aura that step 8 already removed. **VERIFIED** as control flow. **NOT TESTED** against world-update order.

`RemoveAllAuras` on the trigger also clears auras that are not 42074. That matches the stock small-fire extinguish. **POTENTIAL ISSUE** if a 23686 ever carries an unrelated aura during the event. **NOT TESTED**.

The 30-second repeat, `counter > 14`, quest credit, the period multiplier, and the scale match stay as they are. The poll must still not treat an amount drop as a reason to remove the aura.

## 7. Rejected approaches

| Approach | Why it is not S2 |
| --- | --- |
| Extinguish because 42074's amount fell | Can fire with no bucket. A spread reapply and a partial splash both change amount. Forbidden by the task and by this design. |
| `OnSpellCast` of 42348 | Not an impact hook when speed > 0. Speed is **UNKNOWN**. |
| Module `SpellScript` for 42348 with no SQL | Not loaded. Section 5. |
| Re-register `spell_hallows_end_bucket_lands` or `spell_hallows_end_base_fire` | Deletes the stock loader. |
| `GetCreatureAI` for 23686 | Replaces `npc_soh_fire_trigger`. |
| New `spell_script_names` row | Owner SQL. Not module-only. It is the way to put an `AfterHit` on 42348 itself if the owner later wants the callback's spell id to be 42348. |

Owner options if this 42339 hook is declined:

1. Approve one `spell_script_names` row for 42348 and a module `AfterHit` that uses the same gates. No stock spell script exists to replace.
2. Approve a wrapper AI for 23686. That is the broad override this design refuses.
3. Leave one-bucket unimplemented. Amount 3 still needs a second stock splash.

## 8. Negative matrix

Rows marked **model** are executed by `tests/test_f10_hallows_end_one_bucket_s1.py`. They are not a worldserver run.

| Id | Case | Required result | Where |
| --- | --- | --- | --- |
| B1 | Gates on, normal fire amount 1 | Stock splash removes it. The feature also calls `RemoveAllAuras`. End state is out. | model |
| B2 | Gates on, amount 2 | Same as B1. | model |
| B3 | Gates on, amount 3 | Stock splash leaves amount 1. The feature then removes the aura. End state is out. | model |
| B4 | Gates otherwise on, training fire 23537, amount 3 and amount 1 | Feature does not act. Stock training rule: 3 becomes 2, 1 is removed. | model |
| B5 | One real player nearby, bot throws, amount 3 | Feature does not act. Stock result amount 1. | model |
| B6 | Two real players, real thrower, amount 3 | Feature does not act. Stock result amount 1. | model |
| B7 | Event inactive, amount 3 | Feature does not act. Stock result amount 1. | model |
| B8 | Wrong NPC, amount 3 | Feature does not act. Stock fire script does not run. Amount stays 3. | model |
| B9 | Entry 23686 but not in the Shade list, amount 3 | Feature does not act. Stock result amount 1. | model |
| B10 | One-bucket key off, solo path on, amount 3 | Feature does not act. Stock result amount 1. | model |
| B11 | One-bucket key on, solo Enabled off, amount 3 | Feature does not act. Stock result amount 1. | model |
| B12 | Tick raises 2 to 3 and spreads, then the gated bucket hits the parent | Parent ends out. Spread count stays 1. The child is not removed. | model |
| B13 | Gated bucket removes amount 2, then a tick is attempted | No spread from that aura. | model |
| B14 | Same tick-then-bucket as B12 with the feature off | Parent stays at amount 1. Child remains. | model |
| B15 | 42339 miss, gates otherwise on | No stock splash and no feature clear. | model |
| B16 | Spell id 42348 presented without an accepted 42339 dummy hit | Feature does not act. | model |
| B17 | Amount falls and no bucket landed | The rejected amount observer would clear it. This policy does not. | model |
| B18 | Bots only, amount 3 | Feature does not act. Stock result amount 1. | model |
| B19 | One real player plus bots, the real player throws, amount 3 | Feature acts. Fire ends out. | model |
| B20 | Delayed splash, gates on, tick would have fallen during flight | Aura is already gone, so the tick does not spread. | model |
| B21 | Delayed splash, feature off, tick during flight | Stock tick can spread before the splash. | model |
| B22 | Two Shades both list the same trigger | Feature does not act. | model |
| B23 | GM thrower, no other real player, amount 3 | GM counts as real. Feature acts. Fire ends out. | model |
| B24 | Decision does not read amount | The same gate set accepts amount 1, 2, and 3. | model |

## 9. Not tested

- No worldserver, no client, no database apply, no packet capture.
- No Spell.dbc, so no 42339 or 42348 missile speed, effect type, or damage.
- No proof that a live `creature_template` row still says `npc_soh_fire_trigger` after the module SQL. The module SQL does not update 23686. **VERIFIED** in the file. Applying SQL was not done.
- No Playerbot threw a bucket. B5 and B19 are the model.
- No measurement of update order between an aura tick and a spell hit.
- The local unittest, when it is recorded below, is a source and model run. It is not gameplay acceptance.

## 10. Local source run

Command, from the module root, after the pinned trees were extracted:

```text
F10_CORE_OLD=/tmp/core-old \
F10_CORE_NEW=/tmp/core-new \
F10_IP=/tmp/f10-ip \
F10_PLAYERBOTS=/tmp/f10-playerbots \
python3 -m unittest tests/test_f10_hallows_end_one_bucket_s1.py -v
```

The result line is filled only after that command is run. A missing line means it was not run. CI is a separate run and is cited on the PR and on issue #48.

Local result, **VERIFIED** as a source and model run only. It is not a worldserver run and it is not CI.

```text
Ran 35 tests in 1.030s

OK
```

The neighbour search looks for script names and for `spell_` / `npc_` rows on these spell ids. It does not treat a bare number as a binding. Inspected leftovers at the pinned neighbour SHAs: Individual Progression `pvp_vendors.sql:927` and `:1228` are vendor item 42348; Playerbots `playerbots_travelnode_path.sql:402917` and `:1153799` are coordinates `3.42339` and `1.42339`; Playerbots `0000_playerbots_names.sql:42349` and `:42358` are name rows `(42339,'Karaei',6)` and `(42348,'Karis',6)`. **VERIFIED** by reading those lines. No script-name hit remained.
