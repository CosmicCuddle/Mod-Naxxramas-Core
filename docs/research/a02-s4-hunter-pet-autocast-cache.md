# A02 S4 — hunter pet autocast cache

Draft only. The feature is default off: `NaxxramasCore.HunterPet.AutocastCache.Enabled = 0`. The owner approved a draft. That approval is not CS01 acceptance, not permission to merge, and not permission to apply SQL. `NaxxramasCore.HunterPet.AutocastCache.RestoreUtility` is a separate flag and also defaults to 0. The owner has not been asked whether that flag should be turned on.

No edit is made to AzerothCore, Individual Progression, or Playerbots. The characters SQL file is manual and is not applied. Nothing here was run on a worldserver or against a live pet.

| Label | Meaning |
| --- | --- |
| VERIFIED | Read at the pinned SHA named in the sentence, or executed as a policy test on this machine. |
| POTENTIAL ISSUE | The source can behave this way. It was not executed on a server. |
| UNKNOWN | Not determined from the pinned trees. |
| NOT TESTED | No worldserver, no client, no character database. |
| BLOCKED | The module-only source cannot prove the outcome. The code fails closed where it can and does not claim the rest. |

Pins read on 2026-10-20: core `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd`. `UpdateFetcher.cpp`, `DBUpdater.cpp`, `DatabaseWorkerPool.cpp`, `MySQLConnection.cpp`, and `Transaction.cpp` are byte-identical between those two SHAs. `Pet.cpp` and `CharacterDatabase.cpp` were already byte-identical (SHA-256 `825a9d66238d3dc2a3f5d8cb700b241b4c8b2e613aa030c78a9e31809ce1a356` for `Pet.cpp`). IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`. `WorldSession.cpp` callback lines below match on both pins.

## Ordering

**VERIFIED** at both cores and at IP `4ff4b5f`.

1. `Pet::LoadPetFromDB` sets `m_loading = true` (`Pet.cpp:218`).
2. `InitStatsForLevel` (`Pet.cpp:332`) calls `OnInitStatsForLevel` (`Pet.cpp:1434`). IP's `ScheduleDelayedSpellCheck` queues `DelayedPetSpellCheck` at `CalculateTime(200)` (`IndividualProgressionSpells.cpp:1284-1286`, hook `1300-1309`). A second schedule from `OnPetAddToWorld` returns because `PendingPetSpellCheck` is already set (`1276-1280`).
3. The charm bar is loaded (`Pet.cpp:408`) and `map->AddToMap` calls `OnPetAddToWorld` (`Pet.cpp:118`) while `m_loading` is still true and `m_spells` is still empty.
4. Only the async `PetLoadQueryHolder` callback calls `_LoadSpells` (`Pet.cpp:435`), `CleanupActionBar` (`446`), `PetSpellInitialize` (`450`), and `m_loading = false` (`496`). There is no script hook between `_LoadSpells` and `m_loading = false`.
5. `Pet::Update` returns before `Creature::Update` while `m_loading` is set (`Pet.cpp:659-660`). `Creature::Update` reaches `Unit::Update` (`Creature.cpp:777`) and `WorldObject::Update` calls `m_Events.Update` (`Object.cpp:1074-1076`, `Unit.cpp:517`). Pet event time does not advance during load on that path. **UNKNOWN** whether any other caller pumps `pet->m_Events` while `m_loading` is set. **NOT TESTED.**
6. `EventProcessor::Update` runs due events in ascending exec time (`EventProcessor.cpp`, `std::multimap`). IP's exec time is `m_time + 200` from the schedule. This module's snapshot event is `CalculateTime(0)` from the same hooks, so its exec time is earlier. The snapshot step does not apply. It requeues by at least 1ms (`SameUpdateGuardMs`), which is past the current `m_time`, so that apply cannot run in the same `Update` as an IP event that is already due. IP's original event at +200 still runs in a lag tick before the later apply.
7. IP retries while `isBeingLoaded()` and `attempts < 10`, then runs `checkHunterPetSpells` anyway (`IndividualProgressionSpells.cpp:1328-1342`). That retry runs only if something executes the event during load. On the normal path the first execution sees `!isBeingLoaded()` and runs the check once. `learnSpell(keepId)` is `addSpell` with `ACT_DECIDE`, which stores an autocastable spell as `ACT_DISABLED` (`Pet.cpp:1810-1816`). `unlearnSpell` does not erase `m_autospells`; only `ToggleAutocast` does (`Pet.cpp:2247-2286`). A restored chain therefore also drops other autocast ids of that chain.

Normal path (no load-time pump): snapshot on the first loaded tick, wait, then apply **once** when event time is at least 201ms after that snapshot tick. IP's original deadline is 200ms after the same frozen base. **VERIFIED** as `AdvanceOrder` and `DueThisTick` in the policy binary. `MaxApplies` is 1. A later tick does not apply again.

Load-time pumps observed: this module cannot read IP's attempt counter (`PendingPetSpellCheck` is a different RTTI type in IP's `CustomData`). The single apply then waits out the full 2200ms budget. **BLOCKED:** a click in that cover is still overwritten by the one apply. There is no module hook for an accepted client toggle. PR #67 showed packet-before-handler inference is unsound, and this module does not read packets (`PacketBeforeHandlerIsAcceptedChoice()` is false). **NOT TESTED** on a client.

`OnPlayerSave` runs before `pet->SavePetToDB` (`PlayerStorage.cpp:7270` then `:7304-7305`). **VERIFIED** as source order. The save hook does not call the reconcile. Before the single apply it does not write a choice (`MayPersistChoiceBeforeSingleApply(0)` is false). After the single apply it records the live book and does not toggle. **NOT TESTED** as a real save.

`RemovePet` calls `SavePetToDB` directly (`Player.cpp:9367`) with no module hook in front of it. **BLOCKED:** a dismiss or swap before the single apply can persist Individual Progression's reset. This module does not toggle and does not write a restored cache in that window (`DismissBeforeApplyPreservesChoice()` is false). A later login whose `character_pet.savetime` no longer matches `seen_savetime` does not apply the old cache. **NOT TESTED.**

There is no module-only hook after `_LoadSpells` and before IP's event. The event-clock order above is the slot that exists. It is not a silent 3 second sleep.

## Saved book and identity

**VERIFIED** at `CharacterDatabase.cpp:575-590` on both cores.

- `pet_spell` is `SELECT spell, active FROM pet_spell WHERE guid = ?`. `guid` is the pet number. There is no `character_pet_spell` table in these prepared statements.
- `character_pet` is selected with `WHERE owner = ?`. The replace writes `id` and `owner`. Ownership is that pair. `pet_spell` has no owner column.
- `MySQLConnection::_Query` returns false when `mysql_query` fails (`MySQLConnection.cpp:335-345`) and again when the result has zero rows (`:357-361`). `DatabaseWorkerPool::Query` turns both into a null `QueryResult` (`DatabaseWorkerPool.cpp:183-186`). **VERIFIED** from those lines. A null result is not a verified empty read (`NullQueryResultIsVerifiedEmpty()` is false).
- `COUNT(*)` still produces one row when the count is 0, so a successful count survives `Query`. **VERIFIED** as that control flow plus the policy test `InterpretCountQuery`. A null count stays `DatabaseRead::Failed`. A count of 0 is `verifiedEmpty`. **NOT TESTED** on a database.
- A failed owner count stays **Unproven**. It does not delete cache rows and it does not default-on. A verified count of 0 is **Absent** and that pet number's cache is deleted. More than one row is **Ambiguous**. No `pet_spell` read and no default-on.
- A failed cache count, or a row select that comes back null after a non-zero count, does not fall through to `pet_spell` and does not default-on. No pet changes. **VERIFIED** as `DecideLoad`. **NOT TESTED** on a database.
- A failed `pet_spell` count after a verified empty cache does not default-on. A tame (`bornThisSession`) with a verified empty cache still default-ons damage chains, because those saved bits are `ACT_DECIDE` defaults rather than a proven failure.
- The charm bar is not an input to `DecideLoad`. `CharmBarIsAuthoritativeSavedSpellbook()` is false. **VERIFIED** as a policy test.
- A schema probe that returns null is **Unknown**. It is not cached as "table missing". No pet changes and no default-on. A verified column count other than 7 is **Absent**: `pet_spell` may still be restored and nothing is written. **NOT TESTED** against a server.

`Pet::_SaveSpells` deletes every `pet_spell` row for the number before insert, and the comment says numbers are recycled (`Pet.cpp:1574-1575`). `GeneratePetNumber` on these pins is `++_hiPetNumber` after `SELECT MAX(id) FROM character_pet` (`ObjectMgr.cpp:8117-8166`). A running process does not reuse an id below that max. **VERIFIED** as those two facts together. A dump, a counter reset, or a later core could still reuse an id. The cache key is owner, pet number, creature entry, create spell, and `seen_savetime`.

- Entry or create spell differs: delete the cache, do not apply it. **VERIFIED** as `DecideLoad`.
- Savetime differs on a normal login: do not apply the cache. Fall through to `pet_spell`. Do not delete it unless this pet was born this session (tame). If the savetime refresh callback did not report success, `seen_savetime` stays at the previous value, so the next login takes this path. **POTENTIAL ISSUE:** a good cache is then ignored. **NOT TESTED.**
- Abandon removes `character_pet` (`Pet::DeleteFromDB`, `Pet.cpp:599-616`). The orphan delete drops cache rows for numbers that owner no longer has, and only after a unique owner read. **VERIFIED** as `OrphanPetNumbers`. The delete itself is not marked verified. **NOT TESTED** as SQL.
- **BLOCKED / POTENTIAL ISSUE:** same owner, same entry, same create spell, recycled number, and a savetime that this module already rebound to that row. `SameEntryRecycleAfterSavetimeRebindIsIndistinguishable()` is true. `DecideLoad` accepts that tuple. A module cannot add a generation column to `character_pet`. The generator above does not produce that recycle by itself.

## Writes

`CommitTransaction` only enqueues `TransactionTask` and returns void (`DatabaseWorkerPool.cpp:248-268`). `DirectCommitTransaction` calls `ExecuteTransaction` and returns void either way (`:297-325`), so the caller never sees the error code. Neither is a success signal.

`AsyncCommitTransaction` returns `TransactionCallback`. `TransactionWithResultTask::Execute` sets the bool true only when `ExecuteTransaction` returns 0, and false after a failed retry (`Transaction.cpp:141-178`). `AfterComplete` takes `void(bool)` (`Transaction.h:117-120`). `WorldSession::AddTransactionCallback` (`WorldSession.h:1223`) stores it, and `ProcessQueryCallbacks` runs it on the session update (`WorldSession.cpp:592`, `:1407-1410`), not inside the submitting call. **VERIFIED** as those lines on both pins.

`lastWritten` is assigned only inside that callback when the bool is true and the same pet generation and write epoch are still current. `seen_savetime` in memory is updated only from the savetime callback's true result. A false callback leaves both unchanged. No session means the write is not submitted. **POTENTIAL ISSUE:** the callback can also fail to see the pet if it was already dismissed; the database row may still have changed. **NOT TESTED** on a database.

Deleting a mismatched or abandoned cache uses the same async callback and does not set a verified-deleted flag. **POTENTIAL ISSUE:** a failed delete can leave the old rows. The next load still rejects an entry, create spell, or savetime mismatch.

## What is restored

`eligible_for_default_on` is the damage allowlist plus `OptionalSpellIds`. Utility is never in it. `eligible_for_preference_restore` is every other autocastable chain, plus utility only when `RestoreUtility` is 1.

With `RestoreUtility` at 0 (the default, and the behaviour the owner approved): utility chains are not read into the snapshot, not written, and not toggled. A newly learned utility ability is not turned on. This module does not undo an Individual Progression reset of a utility rank while the flag stays 0. That is the untouched default, not a claim that the owner has accepted or rejected the flag.

With `RestoreUtility` at 1: an explicit ON or OFF already in the pre-reset snapshot is restored onto the current rank, including an old rank that was ON and a new rank that Individual Progression stored OFF, and the opposite OFF choice. A utility chain that is absent from that snapshot is not turned on. The owner will be asked separately whether this flag should be enabled. This document does not answer that.

A chain in the accepted snapshot keeps its saved bit, including explicit off. There is no one-time migration. A chain absent from that snapshot is turned on only when default-on is allowed and the first rank is on the damage list or `OptionalSpellIds`.

`ApplyReconcile` toggles only spell ids present in `PlanReconcile`, then erases only `StaleAutocastIds` of those chains. Utility and unrelated autocast ids stay when they are not targets. **VERIFIED** as `ApplyReconcileModel` in the policy binary. **NOT TESTED** in a client spellbook.

A tame calls `InitStatsForLevel` before `InitPetCreateSpells` (`Unit.cpp:13441-13449`) and `CreatePet` saves before the pet event can run (`Player.cpp:9490`). Those saved bits are `ACT_DECIDE` defaults, not a player click. `bornThisSession` is set only when `!isBeingLoaded()` and `m_spells` is empty. A born pet with a verified empty cache table ignores those default bits and default-ons damage chains. Without the table, the saved bits are restored and nothing extra is turned on. **VERIFIED** as `DecideLoad` / `PlanApply`. **NOT TESTED** in game.

Furious Howl `24604`, Wolverine Bite `53508`, Web `4167`, and Lava Breath `58604` are not on the default damage list. **UNKNOWN** Bad Manner. No 3.3.5a tooltip was found. Bad Attitude is `50433`. Rake is `59881`. Neither is utility and neither is defaulted on.

**VERIFIED** IP comment mismatch: the gorilla block labels `26090` Thunderstomp (`IndividualProgressionSpells.cpp:220-221`). The 3.3.5 tooltip for `26090` is Pummel. Thunderstomp rank 1 is `26094`, and this module treats `26094` as utility.

`ToggleAutocast` plus `SetSpellAutocast` plus `PetSpellInitialize` still follow `PetHandler.cpp:1002-1007` and `Player.cpp:9760`, and only when a live rank's bit changes or a stale autocast id of an owned chain was removed.

Disabled feature: `MayTouchDatabase(false)` is false, and the hooks return before any `CharacterDatabase` call. **VERIFIED** as the source layout. **NOT TESTED** under a query log.

## Spell ids

**VERIFIED** as Wowhead WotLK tooltip names on 2026-10-20, and as AzerothCore `spell_ranks` chains for the ranked ones. The repo has no Spell.dbc. The policy tests check the ids the header claims, not the DBC.

Damage first ranks: Bite `17253`, Claw `16827`, Smack `49966`, Lightning Breath `24844`, Fire Breath `34889`, Scorpid Poison `24640`, Poison Spit `35387`, Demoralizing Screech `24423`, Acid Spit `55749`, Gore `35290`, Ravage `50518`, Sting `56626`, Spore Cloud `50274`, Tendon Rip `50271`, Pin `50245`, Monstrous Bite `54680`, Savage Rend `50498`, Stampede `57386`, Snatch `50541`, Sonic Blast `50519`, Swipe `50256`, Venom Web Spray `54706`, Froststorm Breath `54644`, Spirit Strike `61193`, Dust Cloud `50285`, Pummel `26090`.

Utility first ranks: Growl `2649`, Cower `1742`, Dash `61684`, Dive `23145`, Charge `61685`, Prowl `24450`, Shell Shield `26064`, Roar of Recovery `53517`, Roar of Sacrifice `53480`, Rabid `53401`, Intervene `53476`, Last Stand `53478`, Heart of the Phoenix `55709`, Call of the Wild `53434`, Taunt `53477`, Thunderstomp `26094`, Warp `35346`.

## SQL

`docs/install/manual_hunter_pet_autocast_cache.sql` creates `mod_naxxramas_hunter_pet_autocast`. **DO NOT APPLY** it from CI or from this module. The owner needs to approve it and back up the characters database first.

**VERIFIED** at both pins: `UpdateFetcher::FillFileListRecursively` stops at `MAX_DEPTH` 10 (`UpdateFetcher.cpp:74-84`) and module discovery is `data/sql/` plus a directory name containing `_dbModuleName` (`:165-179`). Character updates use the name `characters` (`DBUpdater.cpp:195-198`) and `ApplyUpdateFile` runs `MODULE` entries (`UpdateFetcher.cpp:401-406`). `db-characters` matches. The manual file is outside that tree. The policy test fails if any `.sql` under `data/sql/` contains the cache table name. The SQL text is not executed.

## Not tested

In-game summon, relog, dismiss, rank change, client spellbook, and a live characters database are **NOT TESTED**. The CI job compiles the translation unit only. Login, relog, and dismiss were not run on a worldserver.
