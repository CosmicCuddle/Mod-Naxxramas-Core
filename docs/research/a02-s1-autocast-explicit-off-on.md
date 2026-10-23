# A02 S1 — human Hunter pet autocast, explicit OFF and explicit ON

**Status:** read-only source trace. No production C++, no SQL, no DBC, no config change, no core/IP/Playerbots edit. Nothing here was run in a worldserver or in game.

**Author:** CosmicScript02. **Requested by:** CosmicScript01 in [#48 comment 6365678229](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6365678229). **Base:** `main` `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`.

**Question:** for a human (non-bot) Hunter, which code path overwrites a pet-spell autocast the player explicitly set, and is ordinary summon / call pet / relog / `pet_spell` load proven to overwrite explicit OFF as well as explicit ON, or is the proven writer the Individual Progression rank learn/unlearn?

## Labels used

| Label | Meaning in this note |
| --- | --- |
| VERIFIED | Read at the pinned SHA and cited `file:line`, or a `git diff` that was actually run. |
| POTENTIAL ISSUE | Source shows a real branch that can change state, and this trace does not prove it is the path real characters hit. |
| UNKNOWN | Not determined from the pinned source. |
| NOT TESTED | No worldserver, no client, no characters DB, no in-game summon/relog/rank change. |

A label is not a gameplay pass. This note does not claim a runtime fix.

## What this note adds

Carried forward, and re-read at the SHAs below rather than reused as line numbers:

- [#26](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/26) / [#44](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/44): human Hunter first; bots are a separate population.
- [#54](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/54): IP `checkHunterPetSpells` unlearns, then `learnSpell`, and the new autocastable spell becomes the learn default OFF. No synchronous module hook in that gap. Explicit OFF was already called out as a requirement, and `ToggleAutocast(false)` does not record OFF when the id is absent from `m_autospells`.
- [#60](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/60) / [#63](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/63): timer snapshot/restore is not an atomic hook. Fail-open bot classification and pre-handler packets are unsafe.
- [#67](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/67): `CanPacketReceive` plus a later live-state poll cannot tell an accepted explicit OFF from the learn default OFF.
- [#69](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/69): blocked. A `data/sql/db-characters` file is visible to the character autoupdater. This note does not revive that cache or add SQL.
- [#72](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/72): two accepted client paths (`CMSG_PET_SET_ACTION` and `CMSG_PET_SPELL_AUTOCAST`) and no post-accept PetScript hook.

New at the current-public IP SHA:

1. Ordinary load restores a saved ON and a saved OFF when `character_pet.abdata` parses. The action bar, not a hardcoded default, is what `CleanupActionBar` writes back. That path is not proven to reset a consistent saved choice.
2. IP rank replacement discards the old `active` byte for both ON and OFF. The replacement autocastable spell is assigned `ACT_DISABLED`. Explicit ON therefore becomes OFF. Explicit OFF stays numerically OFF because that is the learn default, and the old OFF is not copied.
3. When the pet already has only the legal rank, `checkHunterPetSpells` does not call `unlearnSpell` or `learnSpell` for that chain. IP then leaves both ON and OFF alone.
4. Compared with the older IP pin `4ff4b5fcc1480348f058c632573143e62d4e3a41`, `src/IndividualProgressionSpells.cpp` gained only `TrainerRNDbotSpellsUnlock` (bot Tranquilizing Shot). `git diff --stat` on that file is 20 insertions. `checkHunterPetSpells` and `DelayedPetSpellCheck` are the same logic, shifted down by those 20 lines. Citations below are the new lines.

## Pinned sources

Confirmed from this repo's workflows, not from memory.

| Component | Repository | Full SHA |
| --- | --- | --- |
| Grimfeather AzerothCore | `https://github.com/Grimfeather/azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| Public mod-playerbots | `https://github.com/mod-playerbots/mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |
| Grimfeather mod-individual-progression | `https://github.com/Grimfeather/mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` |

VERIFIED in `.github/workflows/naxx-current-public-dependencies-worldserver.yml` lines 44–60 and 72–74 (`git rev-parse` assertions). The same three SHAs are the current-public checkout in PR [#99](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/99) workflow `naxx-p1-warlock-portal-worldserver.yml` and in PR [#101](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/101) workflow `golemagg-reach-guard.yml` (that workflow also still builds the older triple `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` / `037c01418b5d01506917a3db9b44fd56ac5f965c` / `4ff4b5fcc1480348f058c632573143e62d4e3a41`). Local checkouts of the three SHAs were read for every citation in this note.

`ActiveStates` at core `CharmInfo.h:59-66`: `ACT_PASSIVE = 0x01`, `ACT_DISABLED = 0x81`, `ACT_ENABLED = 0xC1`, `ACT_DECIDE = 0x00`. Explicit OFF in this note means the player path stored `ACT_DISABLED`. Explicit ON means it stored `ACT_ENABLED`.

## How the player stores a choice

Two accepted handlers. Both require the pet to already know the spell. Neither is a load path.

**`CMSG_PET_SPELL_AUTOCAST` (`0x2F3`).** `Opcodes.h:785`, `Opcodes.cpp:886`, `WorldSession::HandlePetSpellAutocastOpcode` at `PetHandler.cpp:955-1008`. After the pet, spell, owner, `HasSpell`, `IsAutocastable`, and `CharmInfo` checks, a real `Pet` gets `ToggleAutocast(spellInfo, packet.AutocastEnabled)` (`1002-1003`) and `CharmInfo::SetSpellAutocast` (`1007`). `SetSpellAutocast` (`CharmInfo.cpp:291-300`) changes the bar type only when the bar action equals that exact spell id.

**`CMSG_PET_SET_ACTION` (`0x174`).** `Opcodes.h:402`, `Opcodes.cpp:503`, `HandlePetSetAction` at `PetHandler.cpp:696-837`. `ACT_ENABLED` calls `Pet::ToggleAutocast(spellInfo, true)` (`797-801`). `ACT_DISABLED` calls `ToggleAutocast(spellInfo, false)` (`815-819`). The bar slot is then `SetActionBar(position, spell_id, act_state)` (`834`).

`Pet::ToggleAutocast` (`Pet.cpp:2247-2286`):

- Returns immediately if the id is not in `m_spells` (`2254-2256`).
- `apply == true` and the id is not already in `m_autospells`: push it and set `PetSpell.active = ACT_ENABLED` (`2260-2271`).
- `apply == false` and the id **is** in `m_autospells`: erase it and set `PetSpell.active = ACT_DISABLED` (`2274-2284`).
- `apply == false` when the id is **not** in `m_autospells`: no write. OFF is the absence of an autospell entry, plus whatever `active` already is. This is the #54 fact, re-read here.

`Pet::SavePetToDB` (`Pet.cpp:502-588`) refuses to save while `m_loading` (`510`). `_SaveSpells` (`1572-1601`) deletes every `pet_spell` row for the pet number, drops `PETSPELL_REMOVED` and family passives from memory, and inserts the rest with `PetSpell.active`. `CHAR_INS_PET_SPELL` is `INSERT INTO pet_spell (guid, spell, active)` (`CharacterDatabase.cpp:581`). The bar is `GenerateActionBarData` (`Pet.cpp:2541-2551`) stored in `character_pet.abdata` (`CharacterDatabase.cpp:590`, bound at `Pet.cpp:586`).

VERIFIED: an accepted toggle writes the spell book and the bar in one handler. The next successful save writes both `pet_spell.active` and `abdata`. NOT TESTED against a live client.

There is still no public hook after either handler accepts the toggle. `PetScript` ends at `PETHOOK_ON_PET_ADD_TO_WORLD` (`PetScript.h:24-32`). `ServerScript::CanPacketReceive` (`ServerScript.h:75`) runs before those checks. `OnPacketSent` (`ServerScript.h:85`) is outbound. Reconfirmed from #67 and #72; not a new hook survey.

## Call order — summon, call pet, relog, stable

All of these that actually load a saved hunter pet enter `Pet::LoadPetFromDB` (`Pet.cpp:216`).

| Entry | Call | Load arguments |
| --- | --- | --- |
| Login | `Player::LoadPet` `PlayerStorage.cpp:6388-6396` | `LoadPetFromDB(this, 0, 0, true)` — current pet |
| Hunter Call Pet, pet not already out | `Spell::EffectSummonPet` `SpellEffects.cpp:3452` → `Player::SummonPet` `Player.cpp:9186` | `petentry` 0, `current` false. `GetLoadPetInfo` `Pet.cpp:203-210` selects `CurrentPet`, else the first unslotted pet |
| Hunter Call Pet, that pet already out | `EffectSummonPet` `SpellEffects.cpp:3406-3441` | Teleport, full heal, clear cooldowns. No `LoadPetFromDB`, no new `OnPetAddToWorld` |
| Revive when no pet object exists | `EffectResurrectPet` `SpellEffects.cpp:5498-5503` | `SummonPet(..., SUMMON_PET)`, which also calls `LoadPetFromDB` |
| Map/temp resummon | `Player::ResummonPetTemporaryUnSummonedIfAny` `Player.cpp:14586-14602` | `LoadPetFromDB` by saved pet number, `current` true |
| Stable retrieve | `NPCHandler.cpp:577-578` and `:730-731` | `LoadPetFromDB` by pet number |

`SummonPet` returns `nullptr` after a **successful** `LoadPetFromDB` (`Player.cpp:9186-9212`). `EffectSummonPet` then returns (`SpellEffects.cpp:3453-3454`). The pet is already on the map. The null return is not a failed load.

### Inside `LoadPetFromDB` (synchronous part)

1. `m_loading = true` (`Pet.cpp:218`).
2. `OnPlayerBeforeLoadPetFromDB` (`241`). This can change which pet is selected. It does not see spells.
3. Create the pet, `InitStatsForLevel(petlevel)` (`332`). `Guardian::InitStatsForLevel` calls `sScriptMgr->OnInitStatsForLevel` (`Pet.cpp:1434`). IP's pet script handles that hook and queues `DelayedPetSpellCheck` at +200 ms (`IndividualProgressionSpells.cpp:1320-1329`, `1283-1306`). The spell book is still empty here.
4. `SynchronizeLevelWithOwner` (`335`). For a hunter pet more than 5 levels under the owner, or over the owner's level, `GivePetLevel` (`Pet.cpp:2402-2406`, `948-961`) calls `InitLevelupSpellsForLevel` **before** any DB spells are loaded. Those learns use `learnSpell` → `addSpell(ACT_DECIDE)` on an empty book, so an autocastable spell is stored `ACT_DISABLED` (`1810-1813`) and placed on a new bar slot as `ACT_DISABLED` (`CharmInfo.cpp:183`, default `newstate` is `ACT_DECIDE` at `CharmInfo.h:145`).
5. `CharmInfo::LoadPetActionBar(petInfo->ActionBar)` (`408`). If `abdata` has the expected token count, this **replaces** the bar, including any slots step 4 just filled (`CharmInfo.cpp:249-267`). A spell that is not autocastable is forced to `ACT_PASSIVE` (`277-279`). If the token count is wrong, the function returns without applying `abdata` and without calling `InitPetActionBar` (`253-254`). The comment says the bar will reset to default; the code leaves the bar as it already is. POTENTIAL ISSUE, only for malformed `abdata`. Real rows are UNKNOWN / NOT TESTED.
6. `Map::AddToMap` (`410`) → `Pet::AddToWorld` (`72-118`) → `OnPetAddToWorld` (`118`). IP schedules from this hook too (`1312-1317`) and then returns because a check is already pending (`1296-1300`). One delayed check, not two.
7. Async `PetLoadQueryHolder` is queued (`416`). `CHAR_SEL_PET_SPELL` is `SELECT spell, active FROM pet_spell WHERE guid = ?` (`CharacterDatabase.cpp:575`, holder at `Pet.cpp:161-163`).

### Inside the async callback, after the pet is still the owner's pet

`Pet.cpp:416-496`:

1. `InitTalentForLevel` (`427`). May `resetTalents` if the point count is wrong (`2216-2227`). Talent reset unlearns talent spells. It is not the autocast toggle path. Whether a given pet hits it is UNKNOWN.
2. `_LoadAuras` (`430`).
3. `_LoadSpells` (`435`, function `1559-1568`). Each row calls `addSpell(spellId, ActiveStates(active), PETSPELL_UNCHANGED)`. The saved byte is stored (`1817-1818`) unless a later branch overwrites it. `ToggleAutocast(spell, active == ACT_ENABLED)` runs at `1889`. For a spell learned in step 4 above with state `PETSPELL_NEW`, the load hits the branch at `1794-1800`: state becomes `PETSPELL_UNCHANGED` and `ToggleAutocast` is called with the **saved** byte. A saved `ACT_ENABLED` turns the spell on. A saved `ACT_DISABLED` calls `ToggleAutocast(false)`, which does nothing if the id is not in `m_autospells`, and the byte is already `ACT_DISABLED`.
4. `AddSpellToActionBar` during that `addSpell` (`1875`): if the chain is already on the bar loaded in step 5, only the spell id is replaced and the **type is kept** (`CharmInfo.cpp:159-168`).
5. `LearnPetPassives` (`438`) adds family passives as `PETSPELL_FAMILY`. `_SaveSpells` does not persist those (`1584-1586`).
6. `InitLevelupSpellsForLevel` (`439`, function `1920-1956`). `learnSpell` on a spell already present returns false without changing `active` (`1786-1803`, the `PETSPELL_NEW` default does not match the `PETSPELL_UNCHANGED` branch). A **higher rank** of a spell that is still present and not `PETSPELL_REMOVED` copies `petSpell.active` from the old rank (`1838-1860`), including `ACT_DISABLED` and `ACT_ENABLED`, then `unlearnSpell(old, false, false)`. `clear_ab` is false, so the bar slot is not cleared. `AddSpellToActionBar` then updates the id and keeps the type. VERIFIED: the native rank-up path copies explicit ON and explicit OFF.
7. `CleanupActionBar` (`446`, function `2027-2037`). For each bar spell the pet still knows, `ToggleAutocast(spell, barType == ACT_ENABLED)`. The saved bar type overwrites `PetSpell.active`. A bar `ACT_ENABLED` forces ON. A bar `ACT_DISABLED` forces OFF only if the id is currently in `m_autospells` (`2274-2284`). After `_LoadSpells` that is true exactly when the loaded byte was `ACT_ENABLED` or a previous step turned it on.
8. `PetSpellInitialize` (`450`) sends the bar and each spell's `active` byte (`Player.cpp:9760-9796`).
9. `m_loading = false` (`496`). Saves are allowed only after this.

IP's delayed event is still pending across this callback. Its body is the next section. It is not inside the callback.

## Call order — IP rank relearn

`IndividualPlayerProgression_PetScript::DelayedPetSpellCheck::Execute` (`IndividualProgressionSpells.cpp:1339-1366`):

- Resolves the owner, then `player->GetPet()`.
- If `pet->isBeingLoaded()` and `attempts < 10`, requeues itself at +200 ms and returns (`1348-1356`).
- Otherwise clears the pending flag and, for a hunter, calls `checkHunterPetSpells` (`1361-1362`). On attempt 10 the check runs even when `isBeingLoaded()` is still true. That is 11 executions × 200 ms from the original schedule (the first at +200 ms, then 10 reschedules): about 2.2 s. POTENTIAL ISSUE if the async holder is slower than that. NOT TESTED.

`checkHunterPetSpells` (`56-110`) returns without touching spells when any of these hold:

- null player, player not in world, or `VanillaHunterPets` is false (`58`). The config default is true (`IndividualProgression.cpp:1076`). The owner's live config is UNKNOWN.
- `isBotAccount` (`61-62`), account name matched by `IndividualProgression.BotAccountsRegex`, default `^RNDBOT.*` (`1118`, `398-408`). A human account that does not match is not skipped.
- class is not hunter (`64-65`).
- `hasPassedProgression(player, PROGRESSION_TBC_TIER_5)` (`67-68`). A hunter past that gate is not reconciled. The owner's progression is UNKNOWN.
- no pet, no creature template, or no family name (`70-87`).

Otherwise `reconcile` (`91-112`):

1. `keepId` is the highest dummy spell the **player** knows, minus 600000. An empty dummy list leaves `keepId == 0`.
2. Every other id in `wipeIds` that `pet->HasSpell` is `unlearnSpell(id, false, true)`.
3. If `keepId` is non-zero and the pet does not have it, `learnSpell(keepId)`.

`HasSpell` ignores `PETSPELL_REMOVED` (`Pet.cpp:2332-2335`).

`unlearnSpell(id, false, true)` → `removeSpell` (`1976-2024`):

- A loaded spell becomes `PETSPELL_REMOVED` and keeps its old `active` byte in the map (`1987-1988`). A `PETSPELL_NEW` spell is erased (`1985-1986`).
- `m_autospells` is not updated here. A removed id can remain in `m_autospells` until something else erases it. Stale id, already noted in #54. It does not restore the old byte onto the new rank.
- `clear_ab == true` calls `RemoveSpellFromActionBar` (`2013`). That matches the **first rank in the chain**, not the exact id, and sets the slot to action 0, type `ACT_DISABLED` (`CharmInfo.cpp:211-224`). The whole chain button is cleared.
- If not loading, `PetSpellInitialize` is sent (`2015-2020`).

`learnSpell(keepId)` (`Pet.cpp:1903-1906`) calls `addSpell(keepId)` with `ACT_DECIDE` and `PETSPELL_NEW`.

- The old rank is `PETSPELL_REMOVED`, so the chain scan skips it (`1841-1843`). The copy at `1855` does not run.
- `ACT_DECIDE` on an autocastable spell assigns `newspell.active = ACT_DISABLED` (`1810-1813`). `SpellInfo::IsAutocastable` is false for passive and for `SPELL_ATTR1_NO_AUTOCAST_AI` (`SpellInfo.cpp:1148-1154`).
- The chain slot was cleared, so `AddSpellToActionBar` uses an empty slot and stores `ACT_DISABLED` (`CharmInfo.cpp:172-183`).
- `ToggleAutocast(spell, false)` (`1889`) does not write again if the new id is absent from `m_autospells`.
- `!m_loading` sends the learned-spell packet and `PetSpellInitialize` (`1909-1914`).

`checkHunterPetSpells` never passes `ACT_ENABLED` and never calls `ToggleAutocast`. The only autocast result it can create is the learn default `ACT_DISABLED`, or a spell deleted by `unlearnSpell`.

Public mod-playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` has no `PetScript` and no `LoadPetFromDB` call (repository search). `PlayerbotFactory::InitPet` turns every non-passive pet spell on (`PlayerbotFactory.cpp:1496`, `1613-1626`). `PlayerbotAI` and `PetsAction` also call `ToggleAutocast`. Those run on bot AI / bot factory objects. They are not on the human `LoadPetFromDB` path. NOT TESTED that no other bot command is pointed at a human pet.

## ON vs OFF by path

| Path | Explicit ON (`ACT_ENABLED` / `0xC1`) | Explicit OFF (`ACT_DISABLED` / `0x81`) | Label |
| --- | --- | --- | --- |
| Accepted `CMSG_PET_SPELL_AUTOCAST` or `CMSG_PET_SET_ACTION` | Writes book `ACT_ENABLED`, adds `m_autospells`, sets bar `ACT_ENABLED` when the bar action id matches | Writes book `ACT_DISABLED` only if the id was in `m_autospells`; sets bar `ACT_DISABLED` when the bar action id matches | VERIFIED source. Client delivery NOT TESTED |
| `SavePetToDB` after load finished | Persists `pet_spell.active` and `abdata` | Same, including `0x81` | VERIFIED source. NOT TESTED |
| Call pet while that pet is already out | No spell or bar write | No spell or bar write | VERIFIED source |
| Ordinary load, `abdata` parses, spell already the saved rank | `_LoadSpells` applies the saved byte; `CleanupActionBar` then forces the saved bar type. A consistent save stays ON | Same, stays OFF. `ToggleAutocast(false)` is a no-op when the id was never put in `m_autospells`, and the stored byte is already `ACT_DISABLED` | VERIFIED source. Not a proven reset. In-game result NOT TESTED |
| Ordinary load, native higher-rank learn (`InitLevelupSpellsForLevel` / `addSpell` chain) | Copies old `active`, `clear_ab` false, bar type kept | Copies `ACT_DISABLED` the same way | VERIFIED source. Which pets level-shift on summon is UNKNOWN |
| Ordinary load, `abdata` token count wrong | Saved bar is not applied. `CleanupActionBar` then follows whatever bar is left, which an early `GivePetLevel` learn filled as `ACT_DISABLED`. A saved ON can become OFF | Stays OFF if the leftover bar is `ACT_DISABLED` | POTENTIAL ISSUE. Real `abdata` UNKNOWN. NOT TESTED |
| IP check, pet already has only `keepId` | No `unlearnSpell`, no `learnSpell` | No `unlearnSpell`, no `learnSpell` | VERIFIED source. Whether a given pet is in this state is UNKNOWN |
| IP rank replacement: `keepId` missing, old rank unlearned, then `learnSpell(keepId)` | Old `active` is not copied. New autocastable spell and new bar slot are `ACT_DISABLED`. ON becomes OFF | Old `active` is not copied either. New spell is `ACT_DISABLED`. Visible state stays OFF. The explicit OFF record is discarded and replaced by the learn default | VERIFIED source. Which pets take this branch is UNKNOWN. NOT TESTED in game |
| IP `reconcile` with an empty dummy list (`keepId == 0`) | Spell is unlearned and not replaced. The ON spell is gone | Spell is unlearned and not replaced. The OFF spell is gone | VERIFIED source for families whose live `reconcile` call uses `{}`. Wolf/Cat Cower calls are commented out (`128-129`, `145-146`) and do not run |
| IP unlearns a same-chain extra rank while `keepId` is already known | `clear_ab` clears the chain button. The kept spell's `active` byte is not changed in that call. A later load can place the chain in a new `ACT_DISABLED` slot and `CleanupActionBar` can then force OFF | Bar slot cleared. Kept `active` stays `ACT_DISABLED` | POTENTIAL ISSUE. Core's own higher-rank learn normally leaves one rank (`1852-1861`), so two live ranks are not the steady state. NOT TESTED |
| IP attempt 10 while `isBeingLoaded()` is still true, then `_LoadSpells` loads a higher saved rank | The early `learnSpell(keepId)` stored `ACT_DISABLED`. Loading the higher rank copies that byte (`1855`) and drops the saved ON | Result is also `ACT_DISABLED` | POTENTIAL ISSUE, only if the holder is still in flight after the retry cap. NOT TESTED |
| Playerbots `InitPet` / pet AI `ToggleAutocast` | Not on the human load path | Not on the human load path | VERIFIED no `PetScript` in that tree. NOT TESTED against a human who is also a bot target |
| `Spell::EffectLearnPetSpell` (player teaches the pet) `SpellEffects.cpp:3486-3509` | Uses `learnSpell`, so a higher rank copies `active` | Same copy, including `ACT_DISABLED`. A brand-new autocastable spell starts `ACT_DISABLED` | VERIFIED source. This is the native copy path, separate from IP's clear-then-learn |

## Root cause, as far as the source proves

**Proven writer of an explicit ON that becomes OFF:** IP `checkHunterPetSpells` when it has to learn the legal rank. Order is `unlearnSpell(old, false, true)` then `learnSpell(keepId)`. `removeSpell` marks the old rank `PETSPELL_REMOVED` (`Pet.cpp:1987-1988`). `addSpell` then skips that rank (`1841-1843`), so the native copy (`1855`) does not run, and `ACT_DECIDE` stores `ACT_DISABLED` (`1810-1813`). The new bar slot is `ACT_DISABLED` (`CharmInfo.cpp:183`). The next `SavePetToDB` can persist that default, because the check runs after `m_loading` is cleared on the normal path (`Pet.cpp:496`, save gate `510`).

**Proven about explicit OFF on that same replacement:** the function does not read the old `ACT_DISABLED` and does not write `ACT_ENABLED`. The new spell is the learn default `ACT_DISABLED`. Visible autocast stays off. The player's explicit OFF and "never toggled, core default OFF" are the same byte after this replacement. That is why a later observer cannot tell them apart (#67), and it is also why this path is an overwrite of the **record** for both choices and a visible change only for ON.

**Proven about ordinary summon / call pet / relog / DB load when `abdata` parses and the saved rank is already the rank that stays:** the load copies `pet_spell.active` (`1559-1567`) and `CleanupActionBar` reapplies the saved bar type (`2027-2036`). Both accepted player handlers wrote those two stores together. This path reloads ON as ON and OFF as OFF. It is not proven to be the writer that resets a consistent explicit choice.

**Not proven:** that every human hunter pet on the owner's realm takes the IP replacement branch. That depends on `VanillaHunterPets`, the TBC tier-5 gate, the family list, and whether `pet_spell` already contains `keepId`. Installed config and character rows were not read. NOT TESTED.

## Next safe module-only diagnostic

Do not implement a restore. Do not call `ToggleAutocast`, `learnSpell`, `unlearnSpell`, `addSpell`, or `SavePetToDB`. Do not add a file under `data/sql/` or any other path the character autoupdater scans. That is the #69 block. Do not edit core, IP, or Playerbots.

**Observer, default off, log only:**

1. `PetScript::OnInitStatsForLevel` and `PetScript::OnPetAddToWorld` (`PetScript.h:43` and `:58`). Log pet number (`CharmInfo::GetPetNumber`), creature entry, `isBeingLoaded()` (`Pet.h:65`), and `m_spells.size()` (`Pet.h:121`, public). Both hooks fire before the async `_LoadSpells` (order `Pet.cpp:332`, `:410`, `:435`). The expected size here is 0. This sample shows the hooks are early. It cannot show the player's choice.
2. `PlayerScript::OnPlayerUpdate` (`PlayerScript.h:302`), hunter only, for a few seconds after the controlled pet GUID changes or `isBeingLoaded()` goes from true to false. Whenever the tuple `(spell id, PetSpell.active, PetSpell.state, whether the id is in m_autospells, bar index, bar type, bar action)` changes, log one line: pet number, live GUID, `isBeingLoaded`, milliseconds since the true-to-false transition, and the tuple. `GetActionBarEntry` is public (`CharmInfo.h:154`). `GetPetAutoSpellOnPos` is public (`Pet.h:75-80`).

**Why this is safe:** it reads public fields and writes a log line. It adds no SQL, so the autoupdater cannot apply a table. Default off means an unconfigured worldserver does not log. It does not change spell book, bar, or characters rows.

**What a later change in that log would mean:**

- A sample taken after `isBeingLoaded() == false` that still shows the saved spell id, followed by a later sample whose id changed and whose `active` is `0x81`, matches IP's learn default and does not match `CleanupActionBar` (that function keeps the id and copies the bar type). That is the observation that separates path (b) from path (a). It is correlation with the cited function, not a stack trace.
- A change already present on the first `!isBeingLoaded` sample is ambiguous. IP is queued at `InitStatsForLevel` + 200 ms and its body runs once the pet is no longer loading (`1348-1362`). That can be the same world tick as the load callback, before the next `OnPlayerUpdate`. No public hook sits between `_LoadSpells`, `InitLevelupSpellsForLevel`, and `CleanupActionBar`.
- A change while `isBeingLoaded()` is still true matches the attempt-10 forced check, which is the separate POTENTIAL ISSUE above.

**What it cannot prove:**

- Which client click was accepted. `CanPacketReceive` is before the handler's `HasSpell` / `IsAutocastable` checks.
- The characters DB row. This diagnostic must not `SELECT` or write `pet_spell` / `character_pet`.
- That the owner's `VanillaHunterPets` is on, or that the character is still before `PROGRESSION_TBC_TIER_5`.
- A fix, a worldserver pass, or an in-game pass.

## Still UNKNOWN or NOT TESTED

- In-game summon, call pet, relog, dismiss, rank change, and the client's autocast glow. NOT TESTED.
- The owner's `IndividualProgression.VanillaHunterPets`, `BotAccountsRegex`, and progression gate. UNKNOWN.
- Whether any saved hunter pet's rank differs from `keepId`, and whether any `abdata` string has the wrong token count. UNKNOWN. No characters DB was read.
- World-update order between the async load callback and `pet->m_Events` inside one tick. The queue order is VERIFIED (IP schedules first, at `InitStatsForLevel`). Same-tick interleaving with `OnPlayerUpdate` is NOT TESTED.
- Spell-book click opcode other than `CMSG_PET_SPELL_AUTOCAST` and `CMSG_PET_SET_ACTION`. UNKNOWN, same limit as #67.
- DBC autocast flags for each pet spell. `IsAutocastable` was read (`SpellInfo.cpp:1148-1154`). Per-spell DBC rows were not. NOT TESTED.

No runtime fix is claimed. A02 stays blocked as a functional change until a later, separately reviewed step. PR #69 stays blocked.
