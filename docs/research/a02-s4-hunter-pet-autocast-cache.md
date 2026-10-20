# A02 S4 — hunter pet autocast cache

Draft only. The feature is default off: `NaxxramasCore.HunterPet.AutocastCache.Enabled = 0`. Michael (owner) approved this design for a draft PR. That approval is not CS01 acceptance and not permission to merge or to apply SQL.

No edit is made to AzerothCore, Individual Progression, or Playerbots. The characters SQL file is in the module and is not applied. Nothing here was run on a worldserver or against a live pet.

| Label | Meaning |
| --- | --- |
| VERIFIED | Read at the pinned SHA named in the sentence, or executed as a policy test on this machine. |
| POTENTIAL ISSUE | The source can behave this way. It was not executed on a server. |
| UNKNOWN | Not determined from the pinned trees. |
| NOT TESTED | No worldserver, no client, no character database. |

Pins: core `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd` (Pet.cpp, PetHandler.cpp, CharmInfo.cpp, CharmInfo.h, PetScript.h, PlayerScript.h, AllCreatureScript.h, and CharacterDatabase.cpp are byte-identical; SHA-256 prefixes recorded in the S4 session), IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`. Read on 2026-10-20.

S2 (`HunterPetAutocastRestore`) stays fail-closed. `AtomicModuleOnlyChoiceSourceExists()` is still false. This cache is a separate default-off path. It does not claim a post-handler choice signal. It stores a snapshot taken before IP's learn, then writes that decision back.

## What IP does

**VERIFIED** at IP `4ff4b5f`, `IndividualProgressionSpells.cpp`.

- `checkHunterPetSpells` returns immediately for bot accounts (`IPSpells.cpp:41`).
- The reconcile unlearns every non-keep id with `unlearnSpell(id, false, true)` and then `learnSpell(keepId)` (`IPSpells.cpp:83-90`).
- `learnSpell` is `addSpell` with `ACT_DECIDE`. An autocastable spell is stored `ACT_DISABLED` (`Pet.cpp:1810-1816`, both cores).
- The only caller is `DelayedPetSpellCheck::Execute` (`IPSpells.cpp:1342`). The event is queued at 200ms (`IPSpells.cpp:1284-1291`) and, while `isBeingLoaded()` and attempts are below 10, requeued at 200ms (`IPSpells.cpp:1328-1336`). Worst case is 2200ms. `IndividualProgressionSpells.cpp` has no `sScriptMgr` call.
- `Pet::Update` returns before the event processor while `m_loading` is set (`Pet.cpp:659-660`). **UNKNOWN** whether any other caller pumps `pet->m_Events` during the async load callback. **NOT TESTED.**

## Where the snapshot is taken

**VERIFIED** at both cores.

- `Pet::AddToWorld` calls `OnPetAddToWorld` at `Pet.cpp:118`.
- `LoadPetFromDB` sets `m_loading = true` (`Pet.cpp:218`) before `InitStatsForLevel` (`Pet.cpp:332`) and `LoadPetActionBar` (`Pet.cpp:408`). `AddToMap` is `Pet.cpp:410`, which reaches `OnPetAddToWorld` while the pet is still loading and `m_spells` is still empty. `_LoadSpells` runs in the async callback (`Pet.cpp:435`). `m_loading = false` is the end of that callback (`Pet.cpp:496`).
- `GivePetLevel` calls `InitStatsForLevel` then `InitLevelupSpellsForLevel` (`Pet.cpp:959-960`). `OnInitStatsForLevel` is `Pet.cpp:1434`, still inside `InitStatsForLevel`, so a level-up snapshot of `m_spells` is before the new ranks are learned.
- `Unit::InitTamedPet` calls `InitStatsForLevel`, then `SetPetNumber`, then `InitPetCreateSpells` (`Unit.cpp:13429-13437`). The charm pet number can change after the level hook and before the spell book exists. The cache re-reads the number before the restore window opens.
- `OnCreatureSaveToDB` is `Creature::SaveToDB` (`Creature.cpp:1509`). `Pet::SaveToDB` aborts (`Pet.h:167-170`). Hunter pets save through `Pet::SavePetToDB`, which does not call that hook. Player save is `OnPlayerSave` (`PlayerScript.h:377`, hook `PLAYERHOOK_ON_SAVE`).

The load snapshot order is: module cache table, else `pet_spell` (`spell`, `active`) for `guid = pet number` (`CharacterDatabase.cpp:575`, both cores), else the charm bar types. `pet_spell` is the characters table. There is no table named `character_pet_spell` in these cores.

`CleanupActionBar` copies the bar into `ToggleAutocast` after `_LoadSpells` (`Pet.cpp:2027-2036`). IP can run after that and replace the rank with `ACT_DISABLED`. The 3000ms re-apply is there so a late IP pass is written again. Each tick calls `ToggleAutocast`, `SetSpellAutocast`, and `PetSpellInitialize` only when a current non-removed rank's bit differs (`PetHandler.cpp:1002-1007` is the toggle plus the bar write; `PetSpellInitialize` is the client spell packet, `Player.cpp:9760`).

Utility first ranks are never passed to those writes. Damage first ranks that were not in the snapshot are set on. Furious Howl `24604`, Wolverine Bite `53508`, Web `4167`, and Lava Breath `58604` are not on the default damage list. A saved bit for them is still restored. A new chain is not turned on unless `OptionalSpellIds` contains the first rank.

## Spell ids

**VERIFIED** as Wowhead WotLK tooltip names on 2026-10-20, and as AzerothCore `spell_ranks` chains for the ranked ones. The repo has no Spell.dbc. The policy tests check the ids the header claims, not the DBC.

| Name | First rank | List |
| --- | --- | --- |
| Bite | 17253 | damage |
| Claw | 16827 | damage |
| Smack | 49966 | damage |
| Lightning Breath | 24844 | damage |
| Fire Breath | 34889 | damage |
| Scorpid Poison | 24640 | damage |
| Poison Spit | 35387 | damage |
| Demoralizing Screech (Screech chain, rank 6 is 55487) | 24423 | damage |
| Acid Spit | 55749 | damage |
| Gore | 35290 | damage |
| Ravage | 50518 | damage |
| Sting | 56626 | damage |
| Spore Cloud | 50274 | damage |
| Tendon Rip | 50271 | damage |
| Pin | 50245 | damage |
| Monstrous Bite | 54680 | damage |
| Savage Rend | 50498 | damage |
| Stampede | 57386 | damage |
| Snatch | 50541 | damage |
| Sonic Blast | 50519 | damage |
| Swipe | 50256 | damage |
| Venom Web Spray | 54706 | damage |
| Froststorm Breath | 54644 | damage |
| Spirit Strike | 61193 | damage |
| Dust Cloud | 50285 | damage |
| Pummel | 26090 | damage |
| Growl | 2649 | utility |
| Cower | 1742 | utility |
| Dash | 61684 | utility |
| Dive | 23145 | utility |
| Charge | 61685 | utility |
| Prowl | 24450 | utility |
| Shell Shield | 26064 | utility |
| Roar of Recovery | 53517 | utility |
| Roar of Sacrifice | 53480 | utility |
| Rabid | 53401 | utility |
| Intervene | 53476 | utility |
| Last Stand | 53478 | utility |
| Heart of the Phoenix | 55709 | utility |
| Call of the Wild | 53434 | utility |
| Taunt | 53477 | utility |
| Thunderstomp | 26094 | utility |
| Warp | 35346 | utility |
| Furious Howl | 24604 | judgement, off by default |
| Wolverine Bite | 53508 | judgement, off by default |
| Web | 4167 | judgement, off by default |
| Lava Breath | 58604 | judgement, off by default |

**VERIFIED** IP comment mismatch: the gorilla block labels `26090` Thunderstomp (`IPSpells.cpp:220-221`). The 3.3.5 tooltip for `26090` is Pummel. Thunderstomp rank 1 is `26094`. This module follows the tooltip names, so `26090` is on the damage list and `26094` is utility.

**UNKNOWN** Bad Manner. No 3.3.5a tooltip was found for that name. Crocolisk Bad Attitude is `50433` (`IPSpells.cpp:184-185`). It is not utility and not on the damage list, so a new chain is left alone and a saved bit is restored. Rake `59881` is the same: IP resets it, and it is not on the damage list.

## What is not a migration

There is no one-time migration. There is no pass that turns existing saved-off damage chains on. If `pet_spell` or the cache already says off, the snapshot says off and the re-apply leaves it off. **VERIFIED** as `CheckNoMigration` in the policy binary. **NOT TESTED** on a character database.

Cache rows are the snapshot plus the default-on decision. They are not a read of the book after IP has set `ACT_DISABLED`. `OnPlayerSave` may read the live book only when no restore is pending. **VERIFIED** as `AllowCacheWrite` and `VerifiedCacheRows`. **NOT TESTED** as a real save.

## Threading

Cycle data is `PetAutocastCacheCycle` in `Pet::CustomData`. Dismiss destroys the pet and that object. `FeatureEnabled` is an atomic flag. Spell lists are copied onto the pet when the cycle starts. There is no process-global pet map. **VERIFIED** as the source layout and `UsesProcessGlobalPetMap() == false`. **NOT TESTED** under MapUpdater or a thread sanitizer.

Synchronous `CharacterDatabase.Query` / `DirectExecute` run on the map thread that is already inside the pet hook or the pet event, the same pattern as this module's honor reset and arcane momentum scripts. **POTENTIAL ISSUE:** a missing table logs a SQL error and the load falls through to `pet_spell`. **POTENTIAL ISSUE:** `DELETE` then `INSERT` is not one transaction, so a crash between them can leave that pet's cache empty until the next successful write. **POTENTIAL ISSUE:** core pet numbers are recycled (`Pet.cpp:1574-1575`). `owner_guid` stops another player's rows matching. The same account can still see a recycled number until a verified write replaces those rows.

## SQL

`data/sql/db-characters/2026_10_20_00_hunter_pet_autocast_cache.sql` creates `mod_naxxramas_hunter_pet_autocast` (`owner_guid`, `pet_number`, `spell_first`, `active`). **DO NOT APPLY** it from CI or from this module. The owner needs to approve it and back up the characters database first. Applying the file does not update `pet_spell`.

## Limits

- A click during the 3 second window can be overwritten by the next re-apply of the pre-IP snapshot. **POTENTIAL ISSUE.** **NOT TESTED.**
- Tame saves through `SavePetToDB` in the spell effect after `AddToWorld` and before the pet event runs (`SpellEffects.cpp` `EffectTameCreature`, `Player.cpp` `CreatePet`). The in-memory default-on happens on the event. The cache write on the first loaded tick stores the decision so a later login does not have to trust that early `pet_spell` row. A crash before that tick does not. **POTENTIAL ISSUE.** **NOT TESTED.**
- Which opcode the 3.3.5 client uses for the spellbook click is **UNKNOWN**. This path does not read packets.
- In-game summon, relog, rank change, and worldserver link are **NOT TESTED**. The CI job compiles the translation unit only.
