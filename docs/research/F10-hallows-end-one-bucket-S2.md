# F10 S2 — one-bucket extinguish prototype (default off)

Status: **module source prototype**. No SQL, DBC, core, Playerbots, or Individual Progression files were edited. This is not a worldserver link and it is not gameplay acceptance. A passing policy test or translation-unit compile is not a village test.

The S1 design this implements is `docs/research/F10-hallows-end-one-bucket-S1.md` at `ae41f91be43e4983693d3b24d7f189bbd082a8a2`. CosmicScript01 passed that design for source feasibility only in PR #70 review `5587661659` and issue #48 comments `6294931759` and `6295218927`.

Labels:

- **VERIFIED** — the statement matches the cited source, or a command in this document produced that result.
- **POTENTIAL ISSUE** — the source shows a real mismatch or hazard. Gameplay effect is not proven.
- **UNKNOWN** — the fact is not in the sources that were read.
- **NOT TESTED** — not executed on a server, client, or database.

## 1. What the prototype does

Both keys have to be exactly 1. The missing-key default of each is `"0"`.

| Key | Default | Role |
| --- | --- | --- |
| `NaxxramasCore.HallowsEnd.SoloFire.Enabled` | `0` | Existing solo-path switch. Still required. |
| `NaxxramasCore.HallowsEnd.SoloFire.OneBucket` | `0` | New switch. Exactly 1 arms the hook. Any other token is off. Not clamped. |

`DecideOneBucket` in `src/Events/HallowsEndSoloFire.h` is the gate. It does not remove an aura. `ApplyHallowsEndOneBucket` in `src/Events/HallowsEndShadeOfTheHorseman.cpp` is the only new writer. When the decision says so, it calls `RemoveAurasDueToSpell(42074)` on the struck creature. It does not call `RemoveAllAuras`, `CastSpell`, `KilledMonsterCredit`, or `AreaExploredOrEventHappens`.

The hook is `spell_naxxramas_hallows_end_one_bucket`, an `AllSpellScript` registered with only `ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE`. An empty hook list is not used. `AllSpellScript::IsDatabaseBound` returns false (`AllSpellScript.h:53`), so no `spell_script_names` row is added. **VERIFIED** from the header and from this registration.

## 2. Pins

Fork: `https://github.com/Grimfeather/azerothcore-wotlk`. Not upstream AzerothCore.

| Role | Commit |
| --- | --- |
| Pinned core | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` |
| Prospective core | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| `hallows_end.cpp` blob at both | `02282feb50f24debd6bbeb0fe9b928db6adabd21` |
| `spell_script_names.sql` blob at both | `e93f9e13d5ab2c98b134c5c632fa1f6f688afa15` |
| `creature_template.sql` blob at both | `899a56b0f5d7bac6536a48e038acb23ba8a70812` |
| `AllSpellScript.h` blob at both | `b9f2fa1f6bb2a49377617a193bef1580223fd247` |
| `AllSpellScript.cpp` blob at both | `2c310e5ec9479121d0cba9ec0fe7fc13f5269d0f` |
| Pinned Playerbots | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Pinned Individual Progression | `4ff4b5fcc1480348f058c632573143e62d4e3a41` |

`src/server/game/Scripting/` has an empty diff between the two core SHAs. **VERIFIED** by `git diff --stat`. `Spell::EffectDummy` text is the same at both SHAs, including `SpellEffects.cpp:691-806`. The file blobs differ (`cfb69c5d266a23f3a120278f2131a7260b72d7ba` at the older pin, `d684660c9959422202546e944f039beb392a117f` at the newer pin) because other functions differ. **VERIFIED**.

`hallows_end.cpp` line numbers below apply to both SHAs.

## 3. Call path

1. `data/sql/base/db_world/spell_script_names.sql:1092` is `(42339,'spell_hallows_end_bucket_lands'),`. There is no row for 42348. **VERIFIED**.
2. `spell_hallows_end_bucket_lands::HandleDummy` (`hallows_end.cpp:287-297`) does not call `PreventHitDefaultEffect`. A creature hit forwards `CastSpell(..., SPELL_WATER_SPLASH, true)` at `hallows_end.cpp:295-296`. `SPELL_WATER_SPLASH = 42348` at `hallows_end.cpp:257`. **VERIFIED**.
3. `Spell::EffectDummy` returns unless `effectHandleMode == SPELL_EFFECT_HANDLE_HIT_TARGET` (`SpellEffects.cpp:694-695`, both SHAs). A miss or a cancel does not reach the hook. **VERIFIED** as control flow. **NOT TESTED** as a thrown miss.
4. The hardcoded dummy returns in `SpellEffects.cpp:707-776` are spell ids 67866, 66867, 59086, 31789, and 51662. 42339 is not one of them. **VERIFIED**.
5. `SpellEffects.cpp:780-787` returns early when `GetPetAura` finds a row. `data/sql/base/db_world/spell_pet_auras.sql` has no `(42339,` row at either pin. **VERIFIED** in that file. **UNKNOWN** whether a live database adds one. **POTENTIAL ISSUE** if it does: `OnDummyEffect` would not run. **NOT TESTED** against an owner database.
6. `SpellEffects.cpp:798-800` then calls `sScriptMgr->OnDummyEffect(..., Creature*)`. `AllSpellScript.cpp:72-74` forwards that to scripts that enabled `ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE` (`AllSpellScript.h:35` and `:92`). **VERIFIED**.

`spell_dbc.sql`, `spell_linked_spell.sql`, and `spell_scripts.sql` have no `(42339,`, `(42348,`, or `(42074,` row at either pin. **VERIFIED**. Spell.dbc speed of 42348 and of 42339 is **UNKNOWN**. **NOT TESTED** against a client DBC.

## 4. Gates

The hook returns before any config read unless the spell is 42339, the effect index is 0, and the entry is 23686. It returns before the grid search unless the remaining cheap gates also match: both config readers equal 1, the caster is a `Player` (`Object.h:208` at both SHAs) and not a bot, and `HasAura(42074)` is already true. `DecideOneBucket` refuses the same inputs.

`HasAura` is `Unit.h:1500` at `a66f1be` and `Unit.h:1501` at `8daffda`. The removal is `RemoveAurasDueToSpell` at `Unit.h:1408` and `Unit.h:1409` respectively. That call names one spell id. It is not `RemoveAllAuras`. **VERIFIED** as the API. **NOT TESTED** on a live creature that also carries some other aura.

Bot test: `IsHallowsEndShadePlayerBot` is the existing helper. With `Playerbots.h` it is `GET_PLAYERBOT_AI(player) != nullptr` (`mod-playerbots` `src/Script/Playerbots.h:31` at `037c014`). Without that header it returns false. **VERIFIED** from this tree. The translation-unit job checks out that Playerbots commit so the real compile can see the header. Whether a given compile command's include path actually contains it is printed by the job (`playerbots_include=yes|no`). Do not treat a missing include as a bot-branch compile.

### 4.1 Same player, not merely some real player

Owners are living entry 23543 creatures within 100 yards (`Object.h:666` `GetCreaturesWithEntryInRange`, same radius as stock `hallows_end.cpp:680`) whose AI dynamic-casts to `npc_naxxramas_hallows_end_soh`, whose `OneBucketFirePhaseActive()` is true, and whose `unitList` contains the trigger GUID.

`IsAlive` is `Unit.h:1798` at `a66f1be` and `Unit.h:1799` at `8daffda`. `Creature::AI()` is `Creature.h:144` at both.

When that set has size 1, the census is the existing `CollectNearbyHallowsPlayers`: `AnyPlayerInObjectRangeCheck(me, 60.0f)`. The constructor defaults are `reqAlive = true` and `disallowGM = false` (`GridNotifiers.h:1379` and `:1382` at both SHAs). Real players are `CountRealHallowsPlayers` (bots omitted, a GM kept). The caster's GUID has to be in that list, and the real count has to be 1.

A real thrower outside that list does not pass, even when a different human inside makes the real count 1. **VERIFIED** as the decision in `DecideOneBucket` and as the model cases. **NOT TESTED** in a village.

### 4.2 Actively burning phase

`UNIT_FLAG_NON_ATTACKABLE` is set in stock `Reset` before any fire is cast (`hallows_end.cpp:686-692`). The same assignment is in the module `Reset`. The flag alone is not the burning signal. **VERIFIED**.

Stock event 2 calls `CastFires(true)` (`hallows_end.cpp:719-722`). Stock event 3 treats `HasPeriodicDummyAura()` as the burning check (`hallows_end.cpp:727-729`). `HasPeriodicDummyAura` is any `SPELL_AURA_PERIODIC_DUMMY` (`Unit.h:1824` at `a66f1be`, `Unit.h:1825` at `8daffda`). Aura 42074's effect 0 is that aura type (`hallows_end.cpp:350`) and is applied by the fire trigger on spell 42132 (`hallows_end.cpp:534-536`). The prototype requires that specific aura, not every periodic dummy.

The module latch `fireCycleStarted` is set when module event 2 or event 3 begins, and cleared in `Reset` and at the start of `FinishEvent`. `OneBucketFirePhaseActive` is that latch and `HasUnitFlag(UNIT_FLAG_NON_ATTACKABLE)`. Stock event 4 clears the flag (`hallows_end.cpp:769-771`). A Shade that has only run `Reset` is not in the fire phase. **VERIFIED** as control flow in this tree. The latch is not a core field. **POTENTIAL ISSUE**: it records entry into the stock event cases; it is not itself a core phase enum. **NOT TESTED** at runtime.

`FinishEvent` is the stock end of the burning phase (`hallows_end.cpp:842` in the core, the module method of the same name). Clearing the latch there refuses the hook during the landing flight. **VERIFIED** as control flow. **NOT TESTED**.

## 5. Stock splash is not replaced

The hook does not cast 42348. Stock `HandleDummy` still does, once, on an accepted creature hit.

Two timings are modeled. Which one Spell.dbc uses is **UNKNOWN**.

| Timing | Amount > 2 | Amount <= 2 |
| --- | --- | --- |
| Immediate. `CastSpell` of 42348 finishes inside `HandleDummy` before `OnDummyEffect`. | Stock `SpellHit` leaves 42074 at amount - 2 (`hallows_end.cpp:575-578`). The hook then removes 42074 only. An unrelated aura stays. | Stock `RemoveAllAuras` (`hallows_end.cpp:581`) has already run. The hook sees no 42074 and writes nothing. Unrelated auras are already gone because of that stock call. |
| Delayed. 42348 is only scheduled. | The hook removes 42074. The later `SpellHit` sees no aura (`hallows_end.cpp:572`) and does nothing. Unrelated auras stay. | Same hook removal. Unrelated auras stay. Stock does not get a second clear. |

**POTENTIAL ISSUE**: the immediate small-fire path still wipes unrelated auras, and that wipe is the stock `RemoveAllAuras`, not this hook. **NOT TESTED** which timing a client uses.

The model does not add a second splash cast, a second quest credit, or a child-fire clear. Training fire 23537 (`creature_template.sql:17567`, script `npc_hallows_end_train_fire`) fails the entry gate. Its stock credit stays at `hallows_end.cpp:932`. Normal fire 23686 is `creature_template.sql:17715`, script `npc_soh_fire_trigger`. **VERIFIED** in those files. **NOT TESTED** against a migrated creature row.

A spread child is another creature. The hook names only the struck creature. Hitting the parent does not erase the child. **VERIFIED** as control flow. A later accepted hit on that child is a separate target and can pass the same gates. **POTENTIAL ISSUE** if a reviewer wanted a child to be immune even to a direct bucket. **NOT TESTED**.

The solo poll still does not remove 42074 and does not read this decision. Amount is not an input to `DecideOneBucket`.

## 6. Negative matrix

Rows are executed by `tests/test_f10_hallows_end_one_bucket_s2.py` through `tests/f10_s2_one_bucket_policy_tests.cpp`. They are not a worldserver run.

| Id | Case | Result |
| --- | --- | --- |
| N1 | Both flags on, sole real player in the census, 23686 has 42074, one active Shade | Remove 42074 only |
| N2 | Zero real players | No removal |
| N3 | Two real players, caster is one of them | No removal |
| N4 | Real thrower outside the census, a different human inside | No removal |
| N5 | Bots only | No removal |
| N6 | Bot throws while one real player is inside | No removal |
| N7 | One real player plus bots, the real player throws | Removal |
| N8 | Training NPC 23537 | No removal. Stock training math remains in the model |
| N9 | Fire cycle not active, or the Shade does not own the trigger | No removal |
| N10 | Two owning active Shades | No removal |
| N11 | Spell 42348, or any id other than 42339 | No removal |
| N12 | Effect index other than 0 | No removal |
| N13 | Miss or cancel (`hitAccepted` false) | No splash in the model and no removal |
| N14 | 23686 without 42074 | No removal, unrelated aura kept |
| N15 | OneBucket off, or Enabled off, or both off | No removal. Stock splash still modeled |
| N16 | Parent hit after a child already exists | Child stays. No second cast. No quest credit |
| N17 | Immediate splash, amount 1 or 2, gates on | Stock `RemoveAllAuras` already cleared the fire. Feature writes 0 |
| N18 | Delayed splash, amount 1 or 2, gates on | Feature removes 42074 only. Unrelated aura stays |

## 7. Not tested

- No worldserver, no client, no database apply, no packet capture.
- No Spell.dbc, so no missile speed.
- No proof that a live `creature_template` row still says `npc_soh_fire_trigger`. The module SQL still updates only entry 23543.
- No Playerbot threw a bucket. N5, N6, and N7 are the model.
- The 100 yard owner search can miss a Shade that flew farther than the Reset scan. **POTENTIAL ISSUE**. **NOT TESTED**.
- `EnterEvadeMode` despawns without clearing fire auras (`hallows_end.cpp:698-700`). A new Shade's `Reset` clears the latch, so the hook waits for event 2 even if a trigger still has 42074. Stock splash can still run. **NOT TESTED**.
- Native translation-unit compile of the real `HallowsEndShadeOfTheHorseman.cpp` and `HallowsEndSoloFireConfig.cpp` is the workflow job, not this file. A green job is still not a linked worldserver. **NOT TESTED** as gameplay.
- CI run ids are written on the draft PR and on issue #48 after the workflow finishes. They are not invented here.

## 8. Local policy and source run

Command, from the module root, after the pinned trees were extracted:

```text
F10_CORE_OLD=/tmp/f10-core-old \
F10_CORE_NEW=/tmp/f10-core-new \
python3 -m unittest tests/test_f10_hallows_end_one_bucket_s2.py -v
```

The result line is filled only after that command is run. A missing line means it was not run. CI is a separate run.

Local result, **VERIFIED** as a source and model run only. It is not a worldserver run and it is not CI.

```text
Ran 33 tests in 0.330s

OK
```
