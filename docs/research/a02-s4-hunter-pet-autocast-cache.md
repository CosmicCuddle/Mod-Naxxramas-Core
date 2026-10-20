# A02 S4 — hunter pet autocast cache

Draft only. The feature is default off: `NaxxramasCore.HunterPet.AutocastCache.Enabled = 0`. Michael (owner) approved a draft. That approval is not CS01 acceptance, not permission to merge, and not permission to apply SQL.

No edit is made to AzerothCore, Individual Progression, or Playerbots. The characters SQL file is in the module and is not applied. Nothing here was run on a worldserver or against a live pet.

| Label | Meaning |
| --- | --- |
| VERIFIED | Read at the pinned SHA named in the sentence, or executed as a policy test on this machine. |
| POTENTIAL ISSUE | The source can behave this way. It was not executed on a server. |
| UNKNOWN | Not determined from the pinned trees. |
| NOT TESTED | No worldserver, no client, no character database. |

Pins read on 2026-10-20: core `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd`. `Pet.cpp` and `CharacterDatabase.cpp` are byte-identical between those two SHAs (SHA-256 `825a9d66238d3dc2a3f5d8cb700b241b4c8b2e613aa030c78a9e31809ce1a356` for `Pet.cpp`). IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`.

This revision answers CS01's two audits on issue #48. A fixed 3000ms re-apply is not the ordering model. The charm bar is not the saved spellbook. The cache is not keyed by pet number alone.

## Ordering

**VERIFIED** at both cores and at IP `4ff4b5f`.

1. `Pet::LoadPetFromDB` sets `m_loading = true` (`Pet.cpp:218`).
2. `InitStatsForLevel` (`Pet.cpp:332`) calls `OnInitStatsForLevel` (`Pet.cpp:1434`). IP's `ScheduleDelayedSpellCheck` queues `DelayedPetSpellCheck` at `CalculateTime(200)` (`IndividualProgressionSpells.cpp:1284-1286`, hook `1300-1309`). A second schedule from `OnPetAddToWorld` returns because `PendingPetSpellCheck` is already set (`1276-1280`).
3. The charm bar is loaded (`Pet.cpp:408`) and `map->AddToMap` calls `OnPetAddToWorld` (`Pet.cpp:118`) while `m_loading` is still true and `m_spells` is still empty.
4. Only the async `PetLoadQueryHolder` callback calls `_LoadSpells` (`Pet.cpp:435`), `CleanupActionBar` (`446`), `PetSpellInitialize` (`450`), and `m_loading = false` (`496`). There is no script hook between `_LoadSpells` and `m_loading = false`.
5. `Pet::Update` returns before `Creature::Update` while `m_loading` is set (`Pet.cpp:659-660`). `Creature::Update` reaches `Unit::Update` (`Creature.cpp:777`) and `WorldObject::Update` calls `m_Events.Update` (`Object.cpp:1074-1076`, `Unit.cpp:517`). Pet event time does not advance during load on that path. **UNKNOWN** whether any other caller pumps `pet->m_Events` while `m_loading` is set. **NOT TESTED.**
6. `EventProcessor::Update` runs due events in ascending exec time (`EventProcessor.cpp`, `std::multimap`). IP's exec time is `m_time + 200` from the schedule. This module's snapshot event is `CalculateTime(0)` from the same hooks, so its exec time is earlier. The snapshot step does not apply. It requeues by at least 1ms (`SameUpdateGuardMs`), which is past the current `m_time`, so that apply cannot run in the same `Update` as an IP event that is already due. IP's original event at +200 still runs in a lag tick before the later apply.
7. IP retries while `isBeingLoaded()` and `attempts < 10`, then runs `checkHunterPetSpells` anyway (`IndividualProgressionSpells.cpp:1328-1342`). That retry runs only if something executes the event during load. On the normal path the first execution sees `!isBeingLoaded()` and runs the check once. `learnSpell(keepId)` is `addSpell` with `ACT_DECIDE`, which stores an autocastable spell as `ACT_DISABLED` (`Pet.cpp:1810-1816`). `unlearnSpell` does not erase `m_autospells`; only `ToggleAutocast` does (`Pet.cpp:2247-2286`). A restored chain therefore also drops other autocast ids of that chain.

Normal path (no load-time pump): snapshot on the first loaded tick, then apply until event time is at least 201ms after that snapshot tick. IP's original deadline is 200ms after the same frozen base. **VERIFIED** as `AdvanceOrder` and `DueThisTick` in the policy binary.

Load-time pumps observed: this module cannot read IP's attempt counter (`PendingPetSpellCheck` is a different RTTI type in IP's `CustomData`). The cover is then the full 2200ms budget. **POTENTIAL ISSUE:** a click in that cover is overwritten by the pre-IP snapshot. **NOT TESTED.**

`OnPlayerSave` runs before `pet->SavePetToDB` (`PlayerStorage.cpp:7270` then `:7304-7305`). If the cover is still open, the save hook applies the snapshot first so the core write is the decision, not the `ACT_DISABLED` book. **VERIFIED** as source order. **NOT TESTED** as a real save.

`RemovePet` calls `SavePetToDB` directly (`Player.cpp:9367`) with no module hook in front of it. A dismiss inside the cover can persist the reset. **POTENTIAL ISSUE.** **NOT TESTED.**

There is no module-only hook after `_LoadSpells` and before IP's event. The event-clock order above is the slot that exists. It is not a silent 3 second sleep.

## Saved book and identity

**VERIFIED** at `CharacterDatabase.cpp:575-590` on both cores.

- `pet_spell` is `SELECT spell, active FROM pet_spell WHERE guid = ?`. `guid` is the pet number. There is no `character_pet_spell` table in these prepared statements.
- `character_pet` is selected with `WHERE owner = ?`. The replace writes `id` and `owner`. Ownership is that pair. `pet_spell` has no owner column.
- A read with zero rows and a failed read both come back as a null `QueryResult` in this core. A null owner read is **Unproven**. It does not delete cache rows and it does not default-on. **POTENTIAL ISSUE:** abandon (row really gone) and a broken connection look the same on that select. Orphan cleanup is a separate `DELETE ... LEFT JOIN character_pet` that removes cache numbers whose row is gone, and only after a unique owner read has already succeeded. **NOT TESTED** on a database.
- More than one `character_pet` row for the same owner and id is **Ambiguous**. No `pet_spell` read, no default-on.
- The charm bar is not an input to `DecideLoad`. `CharmBarIsAuthoritativeSavedSpellbook()` is false. **VERIFIED** as a policy test.

`Pet::_SaveSpells` deletes every `pet_spell` row for the number before insert, and the comment says numbers are recycled (`Pet.cpp:1574-1575`). `GeneratePetNumber` on these pins is `++_hiPetNumber` after `SELECT MAX(id) FROM character_pet` (`ObjectMgr.cpp:8117-8166`). A running process does not reuse an id below that max. **VERIFIED** as those two facts together. A dump, a counter reset, or a later core could still reuse an id. The cache key is owner, pet number, creature entry, and create spell, and the row is applied only when `seen_savetime` equals `character_pet.savetime`.

- Entry or create spell differs: delete the cache, do not apply it. **VERIFIED** as `DecideLoad`.
- Savetime differs on a normal login: do not apply the cache. Fall through to `pet_spell`. Do not delete it unless this pet was born this session (tame). **POTENTIAL ISSUE:** if the post-save refresh never ran, a good cache is ignored. `pet_spell` is then the authority. If that save happened before the restore, the stored off bit remains off. No migration.
- Abandon removes `character_pet` (`Pet::DeleteFromDB`, `Pet.cpp:599-616`). The orphan delete drops cache rows for numbers that owner no longer has. **VERIFIED** as `OrphanPetNumbers`. **NOT TESTED** as SQL.
- Same owner, same entry, same create spell, recycled number, and a refreshed savetime that collides: the module would treat the old cache as this life. **POTENTIAL ISSUE.** The generator above does not produce that recycle by itself. A module cannot add a generation column to `character_pet`.

Cache writes are one transaction (`BeginTransaction`, delete, inserts, `CommitTransaction`). **POTENTIAL ISSUE:** `CommitTransaction` is asynchronous. A crash before the commit lands can leave the previous rows. **NOT TESTED.**

The schema probe is `information_schema.columns` for the seven names. Count other than 7 means the table is missing or is the first draft shape. Default-on and cache writes stay off. Restoring `pet_spell` bits still happens when the owner row is unique. **VERIFIED** as `DecideLoad` with `cacheTablePresent == false`. **NOT TESTED** against a server.

A null per-pet cache select after a good probe is treated as no rows. **POTENTIAL ISSUE:** a transient error on that select looks like an empty cache.

## What is restored

Utility first ranks are never written. A chain in the accepted snapshot keeps its saved bit, including explicit off. There is no one-time migration. A chain absent from that snapshot is turned on only when default-on is allowed and the first rank is on the damage list or `OptionalSpellIds`.

A tame calls `InitStatsForLevel` before `InitPetCreateSpells` (`Unit.cpp:13441-13449`) and `CreatePet` saves before the pet event can run (`Player.cpp:9490`). Those saved bits are `ACT_DECIDE` defaults, not a player click. `bornThisSession` is set only when `!isBeingLoaded()` and `m_spells` is empty. A born pet with a readable cache table ignores those default bits and default-ons damage chains. Without the table, the saved bits are restored and nothing extra is turned on. **VERIFIED** as `DecideLoad` / `PlanApply`. **NOT TESTED** in game.

Furious Howl `24604`, Wolverine Bite `53508`, Web `4167`, and Lava Breath `58604` are not on the default damage list. **UNKNOWN** Bad Manner. No 3.3.5a tooltip was found. Bad Attitude is `50433`. Rake is `59881`. Neither is utility and neither is defaulted on.

**VERIFIED** IP comment mismatch: the gorilla block labels `26090` Thunderstomp (`IndividualProgressionSpells.cpp:220-221`). The 3.3.5 tooltip for `26090` is Pummel. Thunderstomp rank 1 is `26094`, and this module treats `26094` as utility.

`ToggleAutocast` plus `SetSpellAutocast` plus `PetSpellInitialize` still follow `PetHandler.cpp:1002-1007` and `Player.cpp:9760`, and only when a live rank's bit changes or a stale autocast id of an owned chain was removed.

Disabled feature: `MayTouchDatabase(false)` is false, and the hooks return before any `CharacterDatabase` call. **VERIFIED** as the source layout. **NOT TESTED** under a query log.

## Spell ids

**VERIFIED** as Wowhead WotLK tooltip names on 2026-10-20, and as AzerothCore `spell_ranks` chains for the ranked ones. The repo has no Spell.dbc. The policy tests check the ids the header claims, not the DBC.

Damage first ranks: Bite `17253`, Claw `16827`, Smack `49966`, Lightning Breath `24844`, Fire Breath `34889`, Scorpid Poison `24640`, Poison Spit `35387`, Demoralizing Screech `24423`, Acid Spit `55749`, Gore `35290`, Ravage `50518`, Sting `56626`, Spore Cloud `50274`, Tendon Rip `50271`, Pin `50245`, Monstrous Bite `54680`, Savage Rend `50498`, Stampede `57386`, Snatch `50541`, Sonic Blast `50519`, Swipe `50256`, Venom Web Spray `54706`, Froststorm Breath `54644`, Spirit Strike `61193`, Dust Cloud `50285`, Pummel `26090`.

Utility first ranks: Growl `2649`, Cower `1742`, Dash `61684`, Dive `23145`, Charge `61685`, Prowl `24450`, Shell Shield `26064`, Roar of Recovery `53517`, Roar of Sacrifice `53480`, Rabid `53401`, Intervene `53476`, Last Stand `53478`, Heart of the Phoenix `55709`, Call of the Wild `53434`, Taunt `53477`, Thunderstomp `26094`, Warp `35346`.

## SQL

`data/sql/db-characters/2026_10_20_00_hunter_pet_autocast_cache.sql` creates `mod_naxxramas_hunter_pet_autocast`. **DO NOT APPLY** it from CI or from this module. The owner needs to approve it and back up the characters database first.

## Not tested

In-game summon, relog, dismiss, rank change, client spellbook, and a live characters database are **NOT TESTED**. The CI job compiles the translation unit only.
