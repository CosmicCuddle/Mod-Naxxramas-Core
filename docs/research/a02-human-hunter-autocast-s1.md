# A02 S1 — human Hunter pet autocast persistence (Growl / Cower)

**Status:** read-only source trace. One markdown file. No C++, no SQL, no DBC, no config, no workflow, and no edit to AzerothCore, Individual Progression, or Playerbots.

**Author:** CosmicScript02. **Requested by:** CosmicScript01 in [#48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48) comments [6384246684](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6384246684), [6384396306](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6384396306), and [6384513301](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6384513301). **Base:** `main` `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`. Master register remains [#28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28). This note does not decide anything for the owner.

Nothing below was run on a worldserver, a client, or a characters database.

## Labels

| Label | Meaning in this note |
| --- | --- |
| VERIFIED | Read at the pinned SHA and cited `file:line`, or a `git diff` that was actually run. |
| VERIFIED preserved | The cited source path does not write a new autocast byte for that spell. This is not an in-game pass. |
| POTENTIAL ISSUE | The cited source can change or drop the spell. It is not proven that a real character hits that branch. |
| UNKNOWN | Not determined from the pinned source. |
| NOT TESTED | No worldserver, no client, no characters DB, no summon, relog, dismiss, or stable click. |

## What is new, and what is already established

Already established, and not re-argued here:

- [PR #69](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/69) (`cs02/a02-s4-autocast-cache-2026-10-20`, head `7fcdaf70f86ce0c8352c129c39e08e82e8a4a66d`) is a default-off cache. Its own body says functional ON/OFF persistence is not complete: both accepted client paths have no post-accept `PetScript` hook, `Player::RemovePet` calls `SavePetToDB` directly, and an async commit can land after dismiss. Do not revive that cache and do not apply `docs/install/manual_hunter_pet_autocast_cache.sql`.
- [PR #103](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/103) (`cs02/a02-s1-autocast-off-on-2026-10-23`, head `ec73fc77b33e185e46e7684a03a3cecd7bad770c`) already traced the general OFF/ON overwrite. Ordinary load restores a consistent `pet_spell.active` plus `character_pet.abdata`. IP rank replacement (`unlearnSpell` then `learnSpell`) discards the old `active` byte and stores `ACT_DISABLED` on the replacement. When the pet already has only the legal rank, that function does not call `unlearnSpell` or `learnSpell`. The #103 observer boundary (default off, log only, no `ToggleAutocast`) is unchanged by this note.

New in this note:

1. Growl is outside `checkHunterPetSpells`. The function never names it, and the IP trainer SQL says Growl stays on core's automatic learn. A human OFF on an already-known Growl rank is not the Bite/Claw overwrite from #103.
2. The full Cower rank list is commented out. The only live Cower call is `reconcile({ 1742 }, {})` for four WotLK family names, and that call unlearns spell 1742 without learning a replacement.
3. Stable swap, dismiss, login, level-up, and map change are separate entry points. Only the ones that construct or level the pet reach the IP pet hooks. `OnPlayerLogin` and `OnPlayerMapChanged` do not call `checkHunterPetSpells`.
4. The asked table name `character_pet_spells` is not the table at this core pin. The autocast byte is `pet_spell.active`. The bar is `character_pet.abdata`.
5. Playerbots has its own `ToggleAutocast` writer, including a hard OFF for spell 1742. That writer is a bot action. A module seam must not run it, undo it, or treat IP's account regex as the same test as `IsRealPlayer`.

## Pinned sources

Both Grimfeather IP SHAs are the ones this repo's workflows assert. They are not upstream `ZhengPeiRu21` unless a workflow still names that remote for an older job. Hunter spell logic was read at both SHAs.

| Role | Repository | Full SHA | Where this repo records it |
| --- | --- | --- | --- |
| Grimfeather AzerothCore | `Grimfeather/azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` | `.github/workflows/naxx-mc-gfpp-worldserver-8daffda.yml:30` and `:56`; `.github/workflows/naxx-current-public-dependencies-worldserver.yml:45` and `:72` |
| Grimfeather IP, historical triple | `Grimfeather/mod-individual-progression` | `4ff4b5fcc1480348f058c632573143e62d4e3a41` | `naxx-mc-gfpp-worldserver-8daffda.yml:44` and `:58`, with Playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Grimfeather IP, current-public triple | `Grimfeather/mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` | `naxx-current-public-dependencies-worldserver.yml:59` and `:74`, with public Playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |

VERIFIED: `git diff --stat 4ff4b5fcc1480348f058c632573143e62d4e3a41 dd96f2b77e3ebfa2a4726bf785525ba133f1ab61 -- src/IndividualProgressionSpells.cpp` is 20 insertions and 0 deletions. The inserted function is `TrainerRNDbotSpellsUnlock` (bot Tranquilizing Shot only). `checkHunterPetSpells` and `DelayedPetSpellCheck` are the same logic, 20 lines lower at `dd96f2b`. Citations below give the `dd96f2b` line, then the `4ff4b5f` line.

`ActiveStates` at core `src/server/game/Entities/Unit/CharmInfo.h:59-66`: `ACT_PASSIVE = 0x01`, `ACT_DISABLED = 0x81`, `ACT_ENABLED = 0xC1`, `ACT_DECIDE = 0x00`. Explicit OFF in this note means the player path stored `ACT_DISABLED` for that spell id.

Playerbots SHAs above are the workflow pins used beside each IP SHA. They were read only to see the bot writer that must be left alone. This note does not pick which Playerbots SHA the live server has loaded.

## 1. What `checkHunterPetSpells` does

### When it fires

The spell function is not called from login or from map change.

| Event | Does IP call `checkHunterPetSpells`? | Citation |
| --- | --- | --- |
| Login | The player script does not. Login reaches the pet hooks only if a current pet is loaded. | IP `IndividualProgressionPlayer.cpp:20-68` (`OnPlayerLogin` has no pet-spell call). Core `CharacterHandler.cpp:796` `HandlePlayerLoginFromDB` calls `LoadPet()` at `:1103`. `Player::LoadPet` is `PlayerStorage.cpp:6388-6396` and calls `LoadPetFromDB(this, 0, 0, true)`. |
| Level-up | Yes, after a 200 ms pet event, because level-up calls `InitStatsForLevel`. | Core `Pet::GivePetLevel` `Pet.cpp:948-961` calls `InitStatsForLevel` then `InitLevelupSpellsForLevel`. `GivePetXP` calls `GivePetLevel` at `Pet.cpp:940`. |
| Pet summon / call / load | Yes, same delayed event. | `Pet::LoadPetFromDB` calls `InitStatsForLevel` at `Pet.cpp:332` and `map->AddToMap` at `:410`. |
| Stable swap | Yes, for the pet that is loaded out of the stable. The stabled pet is saved, not re-learned, while it is despawned. | `NPCHandler.cpp:646-758` `HandleStableSwapPet`, `:493-606` `HandleUnstablePet`, `:425` `HandleStablePet`. |
| Map change | The player script does not. A far teleport that removes the pet saves it and later loads it, and that load uses the pet hooks. A near teleport that keeps the pet does not. | IP `OnPlayerMapChanged` `IndividualProgressionPlayer.cpp:816-831` calls `checkIPProgression`, not the pet-spell function. Core far teleport `Player.cpp:1588-1590` calls `UnsummonPetTemporaryIfAny`. `HandleMoveWorldportAck` resummons at `MovementHandler.cpp:286`. Near ack resummons at `MovementHandler.cpp:350` and, if the pet is still out, only `NearTeleportTo` at `:321-324`. |

The scheduler is `IndividualPlayerProgression_PetScript` (`IndividualProgressionSpells.cpp` at `dd96f2b`):

- `OnPetAddToWorld` `:1312-1317` and `OnInitStatsForLevel` `:1320-1329` (`4ff4b5f` `:1292-1297` and `:1300-1309`). Both call `ScheduleDelayedSpellCheck`.
- The schedule is skipped unless IP `enabled` is true, the owner is a player, and the class is hunter or warlock (`:1283-1294` / `4ff4b5f` `:1263-1274`). It does not test `isBotAccount` here.
- A per-pet `CustomData` flag stops the second of those two hooks from queueing a second event (`:1296-1300` / `4ff4b5f` `:1276-1280`). The delay is 200 ms (`:1304-1306` / `4ff4b5f` `:1284-1286`).
- `DelayedPetSpellCheck::Execute` (`:1339-1366` / `4ff4b5f` `:1319-1346`) waits while `pet->isBeingLoaded()` and `_attempts < 10`, then calls `checkHunterPetSpells` for a hunter. After 10 attempts it runs even if the pet is still loading.

VERIFIED: the function does not run on a map change that never destroys the pet, and it does not run from `OnPlayerLogin` itself. NOT TESTED which of those login and teleport paths a human hunter actually takes.

### Gates inside the function

`checkHunterPetSpells` (`dd96f2b` `:56-72`, `4ff4b5f` `:36-52`) returns without changing spells when any of these fail:

- player is in world and `VanillaHunterPets` is true (`:58` / `:38`). The config default in source is true: `IndividualProgression.cpp` `dd96f2b:1076`, `4ff4b5f:1028`. The installed config was not read. UNKNOWN.
- `isBotAccount(player)` is false (`:61-62` / `:41-42`). That is an account-name regex, default `^RNDBOT.*` (`dd96f2b:1118`, `4ff4b5f:1070`; match at `IndividualProgression.cpp:398-408` on `dd96f2b`). It is not `IsRealPlayer`.
- class is hunter (`:64-65` / `:44-45`).
- `hasPassedProgression(player, PROGRESSION_TBC_TIER_5)` is false (`:67-68` / `:47-48`). That enumerator is 13, commented as WotLK Naxx / EoE / OS (`IndividualProgression.h` `dd96f2b:239`, `4ff4b5f:237`).
- the controlled pet has a creature template and `CreatureFamilyEntry::Name[0]` (`:70-89` / `:50-69`).

The family compare is a literal English string such as `"Wolf"` (`dd96f2b:114`). Whether DBC index 0 is that English string was not read. UNKNOWN. A non-matching name skips every `reconcile` in the function.

### Which spells it unlearns and learns

`reconcile` (`dd96f2b:91-112`, `4ff4b5f:71-92`):

- The highest dummy id in `dummyIds` that `player->HasSpell` owns becomes `keepId = dummy - 600000`.
- Every other id in `wipeIds` that the pet knows is `pet->unlearnSpell(id, false, true)`.
- If `keepId` is non-zero and the pet does not know it, `pet->learnSpell(keepId)`.
- Empty `dummyIds` leaves `keepId` at 0, so the call only unlearns. It does not learn.

The named chains in the live calls are the ones commented in the function: Bite, Claw, Furious Howl, Dash, Prowl, Charge, Gore, Dive, Screech, Thunderstomp, Scorpid Poison, Shell Shield, Lightning Breath, Fire Breath, Warp, and the WotLK-only strips (Rake, Web, Swipe, and the rest of the `({}, {})` calls). That list is the #103 replacement path. This note does not repeat its ON-becomes-OFF proof.

**Growl.** VERIFIED absent from this function. `IndividualProgressionSpells.cpp` at `dd96f2b` contains no `Growl` string. Every `reconcile` in `checkHunterPetSpells` (`:114-468` / `4ff4b5f` `:94-448`) is commented with an ability name, and none of those names is Growl. The trainer SQL header says Growl, Stamina, Armor, and Resistances stay automatically learned (`data/sql/world/base/hunter_pet_trainers.sql:14` at `dd96f2b`). The dummy-id list in that file (`:22-38`) has no Growl row. No Growl spell id is claimed from DBC. DBC was not opened. NOT TESTED.

**Cower.** Two different source states:

- Full rank list, not compiled. Example, Wolf: `dd96f2b:128-129` and `4ff4b5f:108-109` are a comment plus `// reconcile({ 1742, 1753, 1754, 1755, 1756, 16697, 27048 }, { 601742, ... })`. The same commented shape is repeated for the other pre-WotLK families (the `// Cower` comments begin at `dd96f2b:128` and `4ff4b5f:108`). VERIFIED: those lines do not call `unlearnSpell` or `learnSpell`.
- Live call, four family names only. Serpent, Moth, Chimaera, and Silithid call `reconcile({ 1742 }, {})` with the comment `// Cower` at `dd96f2b:445`, `:453`, `:460`, `:467` (`4ff4b5f:425`, `:433`, `:440`, `:447`). `keepId` stays 0. If the pet `HasSpell(1742)`, the call unlearns 1742 with `clear_ab == true` and does not learn a replacement. Higher ids from the commented list are not in this live wipe list.

### Does that learn reset autocast?

Only for a spell the function actually learns.

`Pet::learnSpell` (`Pet.cpp:1903-1917`) calls `addSpell(spell_id)` with the default `ActiveStates` `ACT_DECIDE` (`Pet.h:112`). `Pet::addSpell` (`Pet.cpp:1810-1813`) stores `ACT_DISABLED` when `ACT_DECIDE` meets `SpellInfo::IsAutocastable()` (`SpellInfo.cpp:1148-1154`), and `ACT_PASSIVE` otherwise. A new autocastable spell is therefore OFF. There is no second default that turns a newly learned hunter pet spell ON.

If the new id is a higher rank of a spell still in `m_spells`, `addSpell` copies `petSpell.active` from that older rank (`Pet.cpp:1850-1860`) and unlearns the old rank with `clear_ab == false`. `CharmInfo::AddSpellToActionBar` (`CharmInfo.cpp:159-168`) replaces the bar action id and returns without changing the bar type. VERIFIED: core rank-up copies the old autocast byte. IP's `reconcile` does not use this copy for a spell it unlearned first: `unlearnSpell(..., false, true)` marks the old id `PETSPELL_REMOVED` (`removeSpell` at `Pet.cpp:1985-1988`), `Pet::HasSpell` is false for that state (`Pet.cpp:2332-2335`), and the later `addSpell` loop skips `PETSPELL_REMOVED` (`Pet.cpp:1841-1843`), so the copy at `:1855` does not see the old byte. That is the #103 fact, and it applies only to ids passed into `reconcile`.

`removeSpell` (`Pet.cpp:1976-2024`) does not call `sScriptMgr`. `CanUnlearnSpellSet` / `CanUnlearnSpellDefault` are consulted only by `InitLevelupSpellsForLevel` (`Pet.cpp:1930` and `:1950`). A module hook cannot veto IP's direct `unlearnSpell`.

For Growl, IP never reaches `learnSpell` or `unlearnSpell`. Core `InitLevelupSpellsForLevel` (`Pet.cpp:1920-1956`) calls `learnSpell` for each family level-up spell at or below the pet's level. If that id is already known and not `PETSPELL_REMOVED`, `addSpell` returns false at `Pet.cpp:1802` and does not change `active`. If it is a higher rank of a known rank, the copy at `:1855` keeps the previous byte, including `ACT_DISABLED`. VERIFIED for that code. Whether the loaded level-up rows contain Growl is the IP SQL comment above, not a row this trace selected. NOT TESTED.

## 2. How core persists the byte

There is no `character_pet_spells` statement in `CharacterDatabase.cpp` at `8daffdab`. VERIFIED statements:

- `CHAR_SEL_PET_SPELL`: `SELECT spell, active FROM pet_spell WHERE guid = ?` (`CharacterDatabase.cpp:575`).
- `CHAR_INS_PET_SPELL`: `INSERT INTO pet_spell (guid, spell, active)` (`:581`).
- `CHAR_DEL_PET_SPELLS`: `DELETE FROM pet_spell WHERE guid = ?` (`:578`).
- `CHAR_REP_CHAR_PET` writes `abdata` on `character_pet` (`:590`). The bound string is `GenerateActionBarData()` (`Pet.cpp:561` and `:2541-2551`).

`Pet::_LoadSpells` (`Pet.cpp:1559-1569`) passes the saved `active` byte into `addSpell(..., PETSPELL_UNCHANGED)`. `Pet::_SaveSpells` (`:1572-1601`) deletes every `pet_spell` row for the pet number, skips `PETSPELL_FAMILY` and drops `PETSPELL_REMOVED`, then inserts the rest with `PetSpell.active`. Pet numbers are the `guid` of those rows. Two pets do not share them.

`Pet::ToggleAutocast` (`Pet.cpp:2247-2286`):

- Returns if the id is missing from `m_spells` (`:2254-2256`).
- `apply == true` and the id is not already in `m_autospells`: push it and set `active = ACT_ENABLED` (`:2260-2271`).
- `apply == false` and the id is in `m_autospells`: erase it and set `active = ACT_DISABLED` (`:2274-2284`).
- `apply == false` when the id is not in `m_autospells`: no write.

Accepted human handlers, neither of which calls `SavePetToDB`:

- `HandlePetSpellAutocastOpcode` (`PetHandler.cpp:955-1008`) calls `ToggleAutocast` (`:1002-1003`) and `CharmInfo::SetSpellAutocast` (`:1007`, implementation `CharmInfo.cpp:291-300`).
- `HandlePetSetAction` (`PetHandler.cpp:696-837`) calls `ToggleAutocast(spellInfo, true)` for `ACT_ENABLED` (`:797-801`) and `ToggleAutocast(spellInfo, false)` for `ACT_DISABLED` (`:815-819`), then `SetActionBar` (`:834`).

The next successful `SavePetToDB` (`Pet.cpp:502-588`) writes both stores. It returns immediately while `m_loading` (`:510`). Callers that do save a hunter pet include character save (`Player::SaveToDB` `PlayerStorage.cpp:7303-7305`), dismiss (`Spell::EffectDismissPet` `SpellEffects.cpp:4773-4784` to `Pet::Remove(PET_SAVE_NOT_IN_SLOT)`), `Player::RemovePet` (`Player.cpp:9367`), stable (`NPCHandler.cpp` via `RemovePet`), far-teleport unsummon (`Player::UnsummonPetTemporaryIfAny` `Player.cpp:14571-14583`), and revive (`SpellEffects.cpp:5533`). The toggle opcodes are not in that list. A crash before one of those saves can drop an in-memory OFF. UNKNOWN how often that window is hit. NOT TESTED.

`Pet::LoadPetFromDB` (`Pet.cpp:216-499`) sets `m_loading`, loads `abdata` through `CharmInfo::LoadPetActionBar` (`:408`, parser `CharmInfo.cpp:249-282`), then in the async callback runs `_LoadSpells`, `LearnPetPassives`, `InitLevelupSpellsForLevel`, and `CleanupActionBar` (`Pet.cpp:435-446`) before `m_loading = false` (`:496`). `CleanupActionBar` (`:2027-2037`) calls `ToggleAutocast(spellInfo, ab->GetType() == ACT_ENABLED)` for each spell still on the bar. A parsed bar type of `ACT_DISABLED` therefore asks for OFF. If `_LoadSpells` already stored `ACT_DISABLED`, the id is not in `m_autospells`, and `ToggleAutocast(false)` is the no-op above. VERIFIED preserved when the saved spell byte and the parsed bar type are both `ACT_DISABLED`.

`LoadPetActionBar` returns without applying tokens when the token count is not `(ACTION_BAR_INDEX_END - ACTION_BAR_INDEX_START) * 2` (`CharmInfo.cpp:253-254`; indexes `:51-57`). The spell byte from `pet_spell` still loads. The bar then stays at whatever `InitPetActionBar` wrote (`CharmInfo.cpp:52-64`), and `CleanupActionBar` will not see a Growl slot that is absent. POTENTIAL ISSUE for a broken `abdata` string only. No characters row was read. UNKNOWN whether any saved hunter bar has the wrong token count. NOT TESTED.

`PetScript` ends at `PETHOOK_ON_PET_ADD_TO_WORLD` (`PetScript.h:24-32`). There is still no hook after either autocast opcode accepts the click. That limit is #69 and #103, re-read here at `PetScript.h:42-58`.

## 3. Human timeline

The human is a player with no `PlayerbotAI` (`IsRealPlayer` at Playerbots `d750b4b` `PlayerbotAI.cpp:4523-4528`: `player && !GET_PLAYERBOT_AI(player)`). IP's bot skip is the account regex, which is a different test. The timeline assumes the pet is already summoned, the player then turns autocast off, and a later IP pass is a new load or a level-up. The first 200 ms pass on a brand-new summon can run before the player clicks. NOT TESTED.

| Step | Growl (any rank core already taught) | Cower, families whose rank list is commented out | Cower spell 1742 on Serpent, Moth, Chimaera, Silithid |
| --- | --- | --- | --- |
| Player sets autocast OFF | VERIFIED preserved in memory: the handler writes `ACT_DISABLED` on the spell and the bar (`PetHandler.cpp:815-819` and `:834`, or `:1002-1007`). No save in the handler. DB stays at the previous save until `SavePetToDB`. NOT TESTED. | Same as Growl, for whichever Cower id the pet knows. VERIFIED preserved in memory. NOT TESTED. | Same write, if 1742 is known and autocastable. VERIFIED preserved in memory until a later IP pass. NOT TESTED. |
| Later IP re-learn (`checkHunterPetSpells` after load or level-up) | VERIFIED preserved. The function does not name Growl and does not pass a Growl id to `unlearnSpell` or `learnSpell`. Core rank-up, if `InitLevelupSpellsForLevel` learns the next rank, copies `active` (`Pet.cpp:1855`). An already-known rank is left alone (`:1802`). | VERIFIED preserved by IP. The `reconcile(...)` line is a C++ comment (`dd96f2b:129`, `4ff4b5f:109`, and the matching `// Cower` comments). Core rank-up uses the same copy as Growl. | POTENTIAL ISSUE. Live `reconcile({ 1742 }, {})` unlearns 1742 and does not learn it back (`dd96f2b:445` and the three calls below it). The OFF byte is not copied because the spell is removed (`removeSpell` `Pet.cpp:2012-2013` clears that bar chain). A higher Cower id is not in this live wipe list. NOT TESTED. |
| Logout / relog | VERIFIED preserved in source if the logout save ran after the click. `SaveToDB` calls `SavePetToDB(PET_SAVE_AS_CURRENT)` (`PlayerStorage.cpp:7303-7305`). Relog loads that pet (`CharacterHandler.cpp:1103`) and `CleanupActionBar` reapplies a parsed `ACT_DISABLED` (`Pet.cpp:446` and `:2036`). The post-load IP pass still does not name Growl. NOT TESTED. | Same as Growl. VERIFIED preserved in source. The commented Cower line stays commented across relog. NOT TESTED. | POTENTIAL ISSUE on the post-load IP pass, same unlearn of 1742. If that unlearn already happened and was saved, relog does not have 1742 to restore from `pet_spell`. `InitLevelupSpellsForLevel` can teach it again only if it is in the level-up list, and a fresh `learnSpell` stores `ACT_DISABLED` (`Pet.cpp:1810-1813`). Explicit OFF and the learn default are the same byte after that. NOT TESTED. |
| Dismiss / resummon | VERIFIED preserved in source. Dismiss is `EffectDismissPet` → `Remove(PET_SAVE_NOT_IN_SLOT)` (`SpellEffects.cpp:4773-4784`), which saves (`Player.cpp:9367`) and moves the pet to the unslotted list (`Player.cpp:9371-9374`). Call Pet loads through `Spell::EffectSummonPet` → `Player::SummonPet` → `LoadPetFromDB` (`SpellEffects.cpp:3452`, `Player.cpp:9186`, `GetLoadPetInfo` `Pet.cpp:203-210` when entry is 0). The following IP pass still skips Growl. `COMMAND_ABANDON` is a different button and deletes a hunter pet (`PetHandler.cpp:277-288`). NOT TESTED. | Same as Growl. VERIFIED preserved in source. NOT TESTED. | POTENTIAL ISSUE. The resummon load schedules IP again, and the live 1742 call can unlearn it after the saved OFF was loaded. NOT TESTED. |
| Stable swap | VERIFIED preserved for the pet that is put away. `HandleStableSwapPet` (`NPCHandler.cpp:646-758`) and `HandleUnstablePet` (`:493-606`) `RemovePet` the current hunter into the stable slot, and `SavePetToDB` writes that pet number's `pet_spell` rows and `abdata`. The pet taken out is a different pet number (`LoadPetFromDB` `Pet.cpp:375-387` swaps that stable slot with `CurrentPet`). Its Growl byte is its own saved byte, then the same Growl rule above. The two pets do not share `pet_spell` rows (`CharacterDatabase.cpp:575`). NOT TESTED. | Same split: the stabled pet keeps the saved byte; the pet taken out is judged by its own rows and the commented Cower line. VERIFIED preserved in source for a Cower id IP does not reference. NOT TESTED. | POTENTIAL ISSUE for the pet being loaded if its family is one of the four and it knows 1742. The pet being stabled is saved first, so its 1742 OFF is written, and the unlearn does not run while it stays despawned. The next time that pet is loaded, the live call can remove 1742. NOT TESTED. |

Map change, for the same three columns: a far teleport uses the dismiss-style save plus the load path (`Player.cpp:1588-1590`, `MovementHandler.cpp:286`), so it matches the resummon row. A near teleport that only `NearTeleportTo`s the live pet (`MovementHandler.cpp:321-324`) does not call `checkHunterPetSpells`. VERIFIED from those calls. Mounting calls `UnsummonPetTemporaryIfAny` except in arena (`Unit::Mount` `Unit.cpp:10262`, unsummon at `:10303`). `Unit::Dismount` resummons at `Unit.cpp:10371`. That is the same save/load pair, not a separate spell editor. NOT TESTED.

Level-up while the pet stays out: `GivePetLevel` runs `InitLevelupSpellsForLevel` immediately and schedules IP (`Pet.cpp:959-960`). Growl and commented Cower stay VERIFIED preserved, including a rank-up copy of `ACT_DISABLED`. The four-family 1742 call remains a POTENTIAL ISSUE 200 ms later. NOT TESTED.

`OnPlayerMapChanged` and `OnPlayerLogin` do not themselves overwrite the byte. VERIFIED from the two player-script functions cited in section 1.

## 4. Playerbots, only so it stays intact

IP's hunter function returns before any `unlearnSpell` when `isBotAccount` is true (`dd96f2b:61-62`). The delayed event is still queued for a hunter bot, then the function exits. VERIFIED: this IP function is not the bot autocast writer.

Playerbots writes autocast itself, on the bot's pet:

- `TogglePetSpellAutoCastAction::Execute` at `d750b4b` `src/Ai/Base/Actions/PetsAction.cpp:342-395` (the `ToggleAutocast` call is `:395`; `037c014` has the same function at `:342` and the same call at `:395`). It turns autocast on for every autocastable pet spell except `disabledPetSpells`.
- `disabledPetSpells` includes `PET_COWER = 1742` (`d750b4b` `PetsAction.cpp:27` and the vector entry at `:43`; the vector starts at `:41`). `037c014` has `PET_COWER = 1742` at `PetsAction.cpp:27` and the vector entry at `:43`. A bot pass forces 1742 OFF and does not list Growl in that disable vector, so Growl is forced ON for the bot.
- `PlayerbotAI::CastSpell` also `ToggleAutocast`s when the bot's pet knows the spell (`d750b4b` `PlayerbotAI.cpp:3709`; `037c014` `PlayerbotAI.cpp:3633`).
- `git grep PetScript` on `d750b4b` returned no matches. Bots do not register a `PetScript` at that SHA.

Those actions use `botAI->GetBot()`. They are not the human opcodes in `PetHandler.cpp`. A module that calls `ToggleAutocast` on every hunter pet would fight this bot writer. `IsRealPlayer` and IP's `^RNDBOT.*` regex are not the same gate: a human whose account name matches the regex is skipped by IP, and a bot whose account name does not match still reaches `checkHunterPetSpells` and still has Playerbots' own toggles. VERIFIED from the two predicates. NOT TESTED against a live bot.

## 5. Module-only options

No option here is an implementation. None of them edits IP, core, or Playerbots, and none adds SQL. #69 stays blocked for the reasons in that PR. #103's default-off observer stays the only diagnostic already specified.

| Option | What it could do | Why it is not a new fix |
| --- | --- | --- |
| Leave Growl and the commented Cower ranks alone | The cited paths keep `ACT_DISABLED` for an already-known rank. | A module `ToggleAutocast` or `learnSpell` would add a writer the source does not need, and it can run on a bot if the human gate is wrong. |
| Do not try to veto IP from `CanUnlearnSpellSet` | That hook is real (`Pet.cpp:1930`). | `removeSpell` never calls it. IP's `unlearnSpell` would ignore the module. VERIFIED. |
| Snapshot Growl/Cower on `OnPlayerUpdate` and write them back | `PlayerScript::OnPlayerUpdate` can see the pet after `isBeingLoaded()` is false. | For Growl and commented Cower the source already kept the byte, so the write has nothing to repair. It cannot see the accepted click (#69 / #103). It cannot tell explicit OFF from the learn default. On a bot it collides with `TogglePetSpellAutoCastAction`. |
| Re-`learnSpell(1742)` after the four-family unlearn | Would put the spell back. | `learnSpell` stores `ACT_DISABLED` and would undo a strip IP left live on purpose. That is a gameplay change, not persistence of the player's byte. Not recommended. |
| Revive the #69 cache or add `pet_spell` SQL | Could store a choice beside core's row. | #69 already concluded the cache is not an atomic record of an accepted click, and its manual SQL must not be applied. This note adds no SQL file. |
| Default-off log of spell id, `active`, bar type, `isBeingLoaded`, pet number | The #103 observer. | Still the only module-only way to see whether a real pet hits the 1742 unlearn or a broken `abdata`. It does not preserve anything. Not implemented here. |

No public hook runs after the client toggle and before IP's `unlearnSpell`/`learnSpell` pair. That gap is unchanged from #103. Functional module-only persistence of a spell IP actually replaces (Bite, Claw, and the other live chains) stays blocked. Growl is not in that set.

## Recommendation for CosmicScript01

Do not merge this note and do not treat it as a gameplay result. For a human hunter, Growl autocast OFF is VERIFIED preserved in source across the IP re-learn path, logout/relog, dismiss/resummon, and stable swap, as long as the saved `pet_spell.active` and a parsed `abdata` type are both `ACT_DISABLED`. The full Cower rank list is commented out and follows that same source result. The exception is POTENTIAL ISSUE: Serpent, Moth, Chimaera, and Silithid unlearn spell 1742 on every post-load IP pass and do not copy its autocast byte. Playerbots separately forces 1742 OFF and other autocastable pet spells ON; leave that code alone. Do not revive PR #69, do not add SQL, and do not edit IP, core, or Playerbots. The Bite/Claw overwrite in PR #103 is unchanged and still has no safe module writer. In-game behaviour is NOT TESTED. A later step, if you want one, is the default-off observer from #103 with Growl and spell 1742 called out in the sample, still with no `ToggleAutocast`.

## Workflow note

NOT TESTED as a GitHub Actions run at the time this file was written. On `main` `80e9de1`, no file under `.github/workflows/` contains `upload-artifact` or `actions/upload-artifact`. Every `pull_request` trigger in those files has a `paths` list, and none of those paths is `docs/research/` or this filename. A pull request whose only change is this file does not match those filters, so it should not start a job that builds or uploads a binary. This file does not add or edit a workflow.
