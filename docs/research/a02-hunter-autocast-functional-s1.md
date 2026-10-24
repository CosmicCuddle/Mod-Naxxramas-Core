# A02 S1 — human Hunter pet autocast, module-only functional feasibility

**Status:** design only. No production C++, no config entry, no SQL, no DBC, no loader change. The writer described below is not built. In-game behaviour is **NOT TESTED**. This note is not a fix and not an observer-as-fix.

**Author:** CosmicScript02. Draft for independent review by CosmicScript01, with CosmicScript03 optional.

**Module base:** `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` (`main`).

**Prior traces this design uses, and does not replace:**

- PR #121 head `3bfa2ce900ca2436ed5769a9c8024827e92327ac` (read-only S1 plus diagnostics plan).
- PR #103 head `ec73fc77b33e185e46e7684a03a3cecd7bad770c` (explicit OFF/ON overwrite trace).
- Assignment: issue #48 comment `6385633108`. A02 stays a module-only feasibility. Core, Individual Progression, and Playerbots stay unedited. PR #69 stays blocked.
- PR #69 head `7fcdaf70f86ce0c8352c129c39e08e82e8a4a66d` is still an open draft and was not modified.

## Pins

Read on 24 October 2026 from published git objects. No live worldserver, database, or DBC file was opened.

| Tree | Commit | Role |
| --- | --- | --- |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` | Core pet spell, action bar, script hooks, world-update order |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` | `checkHunterPetSpells` and the delayed pet event |
| `mod-playerbots` public CI pin | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` | Bot pet autocast writer and `IsRealPlayer` |
| `mod-playerbots` owner published base | `e88cc4099e69f35126b28942a412ca702d20453b` | Descendant of the CI pin. Cited pet files match the CI pin byte for byte |

`git merge-base e88cc4099e69f35126b28942a412ca702d20453b d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` is the CI pin. `git diff` of `PetsAction.cpp`, `PlayerbotAI.h`, `PlayerbotAI.cpp`, and `Playerbots.h` between those two commits is empty. **VERIFIED** for those published blobs.

The two owner working-tree edits on top of `e88cc409` are **UNKNOWN**. They were not in the published commit and were not read. This design does not patch Playerbots, so those edits stay in place.

## Root-cause paths

Labels below are source facts at the pins. None of them were played.

### Where a human click stores the choice

**VERIFIED.** `WorldSession::HandlePetSetAction` (`PetHandler.cpp:696-834`) is the client action-bar packet. For a known pet spell it calls `Pet::ToggleAutocast(spellInfo, true)` on `ACT_ENABLED` (`:801`) and `Pet::ToggleAutocast(spellInfo, false)` on `ACT_DISABLED` (`:819`), then `CharmInfo::SetActionBar` (`:834`). There is no script hook in this function. The packet path is the store, and it is not the drop.

`Pet::ToggleAutocast` (`Pet.cpp:2247-2286`) writes `m_spells[].active` to `ACT_ENABLED` (`0xC1`) or `ACT_DISABLED` (`0x81`) and adds or erases `m_autospells`. The OFF branch runs only when the id is already in `m_autospells` (`:2274-2286`). `CharmInfo.h:59-67` defines the bytes. `SetSpellAutocast` (`CharmInfo.cpp:291-300`) changes the bar type only on a slot whose action id equals the spell id.

### Where load and save keep a consistent choice

**VERIFIED.** `pet_spell` is `(guid, spell, active)` and `character_pet.abdata` is the bar (`CharacterDatabase.cpp:575, 578, 581, 584, 590`). There is no `character_pet_spell` table.

`Pet::_LoadSpells` (`Pet.cpp:1559-1569`) feeds the saved active byte to `addSpell`. `Pet::_SaveSpells` (`:1572-1601`) deletes the pet's rows, skips `PETSPELL_FAMILY` and `PETSPELL_REMOVED`, and inserts the live `active` byte. `SavePetToDB` (`:562`) and `FillPetInfo` (`:2479`) persist `GenerateActionBarData()` (`:2541`).

The load callback (`Pet.cpp:416-496`) runs `_LoadSpells` (`:435`), `InitLevelupSpellsForLevel`, then `CleanupActionBar` (`:446`), then sets `m_loading = false` (`:496`). `CleanupActionBar` (`:2027-2037`) calls `ToggleAutocast(spell, barType == ACT_ENABLED)` for a known spell. After a later load, the bar type is what the spell active byte becomes. A restore that changes `m_spells[].active` and leaves the bar type behind is undone on the next load.

### Where core would have copied the byte

**VERIFIED.** `Pet::addSpell` (`Pet.cpp:1766-1900`) defaults `ACT_DECIDE` to `ACT_DISABLED` for an autocastable spell (`:1810-1813`). When the new spell is a higher rank of a spell that is still live, it copies `petSpell.active` and only then unlearns the old rank (`:1838-1861`). The scan skips `PETSPELL_REMOVED` (`:1841-1842`). A lesser rank of a spell that is still live is rejected (`:1864-1865`). `Pet::learnSpell` (`:1903-1906`) calls `addSpell(spell_id)` with that default.

### Where Individual Progression drops the byte

**VERIFIED.** `IndividualProgression::checkHunterPetSpells` (`IndividualProgressionSpells.cpp:56-112`) returns immediately unless the player is in world, `VanillaHunterPets` is on, the account is not a bot account, the class is hunter, and progression has not passed `PROGRESSION_TBC_TIER_5` (`:58-68`). `VanillaHunterPets` defaults to true (`IndividualProgression.cpp:1076`). `isBotAccount` (`:398-408`) matches `IndividualProgression.BotAccountsRegex`, default `^RNDBOT.*` (`:1118`).

The reconcile lambda (`IndividualProgressionSpells.cpp:91-111`) picks `keepId = dummyId - 600000` from the highest dummy the hunter knows (`:94-100`). It then `unlearnSpell(id, false, true)` for every other wipe id the pet still has (`:103-106`), and `learnSpell(keepId)` when `keepId` is missing (`:109-110`). It never calls `ToggleAutocast`.

`unlearnSpell(id, false, true)` reaches `removeSpell` with `learn_prev == false` and `clear_ab == true` (`Pet.cpp:1959-1973`, `:1976-2024`). The row is erased or marked `PETSPELL_REMOVED` (`:1985-1988`) without copying `active`. `RemoveSpellFromActionBar` (`CharmInfo.cpp:211-221`) sets that chain's slot to action `0`, type `ACT_DISABLED`.

The following `learnSpell` therefore sees a removed old rank. The copy at `Pet.cpp:1853-1860` does not run, and the lesser-rank rejection does not run either. The new autocastable spell is stored as `ACT_DISABLED`. `AddSpellToActionBar` (`CharmInfo.cpp:159-183`) does not find the cleared chain slot, so it uses an empty slot and, for `ACT_DECIDE`, stores `ACT_DISABLED`.

That order is the drop. Explicit ON becomes OFF because the new row is the learn default. Explicit OFF is the same numeric default; the old OFF byte is not read. **VERIFIED** as control flow. Which characters hit a non-empty dummy list in game is still **UNKNOWN**, as in #121.

Representative live calls, all in `checkHunterPetSpells`:

- Wolf Bite, non-empty dummy list: `:117`. Wolf Claw, empty dummy list: `:120`.
- Cat Claw, non-empty dummy list: `:137`.
- Serpent, Moth, Chimaera, and Silithid `reconcile({ 1742 }, {})` at `IndividualProgressionSpells.cpp:445`, `:453`, `:460`, and `:467`.
- The full Cower rank list is a comment (first one at `:129`) and does not unlearn.

Growl is not named in this function. **VERIFIED** by reading the function. No Growl spell id is claimed.

### Who calls the check

**VERIFIED.** The only caller found is `DelayedPetSpellCheck::Execute` (`IndividualProgressionSpells.cpp:1361-1362`). `IndividualPlayerProgression_PetScript` schedules that event from `OnPetAddToWorld` (`:1312-1317`) and `OnInitStatsForLevel` (`:1320-1329`) at `+200 ms` on `pet->m_Events` (`:1304-1306`). A `CustomData` flag avoids a second schedule (`:1298-1302`). While `pet->isBeingLoaded()` and attempts are under 10, the event reschedules itself (`:1348-1356`). `Pet::isBeingLoaded` is `m_loading` (`Pet.h:65`).

`CanUnlearnSpellSet` and `CanUnlearnSpellDefault` are called from `InitLevelupSpellsForLevel` (`Pet.cpp:1930`, `:1950`). `removeSpell` does not call them. Returning false from those hooks leaves the IP `unlearnSpell` running.

### Why the early pet hooks see an empty book

**VERIFIED.** `LoadPetFromDB` sets `m_loading` (`Pet.cpp:218`) and calls `InitStatsForLevel` (`:332`, hook at `:1434`) before `Map::AddToMap` (`:410`). `Pet::AddToWorld` calls `OnPetAddToWorld` (`:118`) before the async callback. Spell rows arrive in that callback (`:435`). `Pet::Update` returns while `m_loading` is set (`Pet.cpp:659-660`), so `m_Events` is not drained during the load. The first `Pet::Update` after `m_loading = false` is the first time the delayed event can run, and the spell book is already filled.

### Playerbots writer, left untouched

**VERIFIED** at both published Playerbots commits above. `TogglePetSpellAutoCastAction::Execute` (`PetsAction.cpp:342-404`) calls `pet->ToggleAutocast` (`PetsAction.cpp:395`). `disabledPetSpells` includes `PET_COWER = 1742` (`:27`, `:41-46`), so that action forces 1742 OFF and other autocastable pet spells ON. `IsRealPlayer` (`PlayerbotAI.h:84`, `PlayerbotAI.cpp:4523-4528`) is true only for a player pointer with no `PlayerbotAI`. `GET_PLAYERBOT_AI` is `Playerbots.h:31`.

IP already returns before the reconcile for an account matching the bot regex. A player with `PlayerbotAI` whose account does not match `^RNDBOT.*` is outside that return. Applying this module's writer there would fight `TogglePetSpellAutoCastAction`. That interaction is **NOT TESTED** and is out of scope.

## Chosen seam

**VERIFIED** as source order. Feasible for a later default-OFF module writer. The writer is not in this PR.

`Pet::Update` (`Pet.cpp:736`) calls `Creature::Update`, which calls `Unit::Update` for an alive creature (`Creature.cpp:777`). `Unit::Update` (`Unit.cpp:510-517`) does three things in this order:

1. `sScriptMgr->OnUnitUpdate` — `UnitScript::OnUnitUpdate` (`UnitScript.h:104`).
2. `WorldObject::Update` (`Object.cpp:1074-1085`), which runs `m_Events.Update` and then `sScriptMgr->OnWorldObjectUpdate` — `WorldObjectScript::OnWorldObjectUpdate` (`WorldObjectScript.h:76`).
3. The rest of the unit update.

IP's check is step 2's event queue. `Object::m_Events` is public (`Object.h:749`, access `public` at `:485`). The same `Pet::Update` both reaches the snapshot hook and drains the event. A grid that skips the pet also skips the IP event. The two stay on the same call.

`World::Update` runs `UpdateSessions` (`World.cpp:1227`, query callbacks at `WorldSession.cpp:592`) before `sMapMgr->Update` (`World.cpp:1254`). The load callback therefore finishes, including `m_loading = false`, before that world tick's map update. The human click path is also in the session update, so a click is already in `m_spells` and the bar when `OnUnitUpdate` runs.

### Snapshot

On `OnUnitUpdate`, for a pet this module is allowed to touch, read the live autocastable rows and their bar types into `Pet::CustomData` (`Object.h:237`, public). Replace that baseline every such call. The read is before `m_Events` on that tick, so it still has the loaded book and any click from the session update that just ran.

`OnPetAddToWorld` and `OnInitStatsForLevel` stay schedule points for IP. They run before `_LoadSpells`. A baseline taken there is the wrong book. `OnPlayerBeforeLoadPetFromDB` (`Pet.cpp:241`, `PlayerScript.h:525`) runs before the spell query. `OnPlayerUpdate` (`PlayerScript.h:302`) follows player-update order inside the map, which this note did not tie to `Pet::m_Events`. `OnPlayerSave` (`PlayerScript.h:377`) is after the byte has already changed. `AllSpellScript` has no pet learn hook (`AllSpellScript.h`).

### Restore

On `OnWorldObjectUpdate` of that same pet update, run the decision table below against the baseline just taken and the book after `m_Events`. The only writes, and only when the table says so, are:

- `Pet::ToggleAutocast(spellInfo, true)` and `CharmInfo::SetSpellAutocast(spellInfo, true)` for `RESTORE_ENABLED`.
- `Pet::ToggleAutocast(spellInfo, false)` and `CharmInfo::SetSpellAutocast(spellInfo, false)` for `RESTORE_DISABLED`.
- One `Player::PetSpellInitialize()` (`Player.h:1712`, public) after at least one of those writes on that tick.

The chain key is `SpellMgr::GetFirstSpellInChain` (`SpellMgr.cpp:603-608`), which returns the spell id when the chain map has no node. `SpellInfo::GetFirstRankSpell` (`SpellInfo.cpp:2934-2938`) is the same notion. Rank helpers `IsDifferentRankOf` / `IsHighRankOf` are `SpellInfo.cpp:3011-3028`. The table treats two spells as the same family only when that key matches. It does not invent a link from IP's wipe list.

Whether the server DBC chain map links each wiped id to its `keepId` (for example Wolf Bite `17253` with `17261`) is **UNKNOWN**. This note did not open `SpellChain.dbc` or `spell_ranks`. If the keys differ, the table returns `NO_LEARN` for the old chain and leaves the new spell at the learn default.

### What the other tokens do

`NO_LEARN` is a removed chain with no successor. `learnSpell` of `1742`, or of a wiped Claw/Bite rank, would put back a spell IP just removed. The table does not call `learnSpell` or `unlearnSpell`.

`NO_WRITE` leaves the pet alone. That includes Growl when its spell id is unchanged, an explicit OFF successor that is already `ACT_DISABLED` on both the row and the bar, a same-id active flip inside the event queue, a passive row, a split baseline, and more than one live spell in the chain.

`NO_BAR` means the successor spell has no action-bar slot. `SetSpellAutocast` would not see it (`CharmInfo.cpp:295`). Creating a slot is out of this design. `ToggleAutocast` without the matching bar type would be undone by the next `CleanupActionBar`, or would save a split the next load does not repair. The table does not write.

`OUT_OF_SCOPE` performs no read and no write.

A log from `OnPetAddToWorld` leaves the active byte where `learnSpell` put it. The calls in this section are the writer. This PR does not add them.

## Config

Proposed key, **not** added to `conf/mod_naxxramas_core.conf.dist` and not read by any C++ in this PR:

```
NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0
```

`0` is the only default. A future reader uses the bool option default `false`, so a missing key stays off. `1` is what would arm the snapshot and the table. This S1 does not arm it.

## Scope

The future writer would require all of the following on both hooks:

- The config value is true.
- `owner` is a `Player` in the world, class hunter, and `IsRealPlayer(owner)` is true at the Playerbots pin cited above.
- The unit is a `Pet` with `getPetType() == HUNTER_PET` (`Pet.h` `IsPermanentPetFor` treats `HUNTER_PET` as permanent at `:2302-2303`).
- `!pet->isBeingLoaded()`.

If `IsRealPlayer` cannot be linked, the writer stays off. Guessing from the IP account regex is not a substitute: the regex misses a `PlayerbotAI` whose account is outside `^RNDBOT.*`, and this module does not reimplement IP's account cache.

Warlock demons, guardians, charmed creatures, and any player with `PlayerbotAI` (random bot, alt bot, self-bot) produce `OUT_OF_SCOPE`. IP's own bot-account return stays as it is. Playerbots' `ToggleAutocast` stays as it is.

## Thread safety

The owner states `MapUpdate.Threads = 8`. This note did not read the live `worldserver.conf`. The design still keeps pet spell writes on the map thread that is already inside `Pet::Update`.

The baseline lives in that `Pet::CustomData`. It dies with the pet object. `OnUnitUpdate` and `OnWorldObjectUpdate` for that pet run on the thread that updates the pet's map. A process-global `unordered_map` of players or pets is not part of the design. `WorldScript::OnUpdate` is not the seam: it runs on the world thread (`World.cpp` world update, `WorldScript.h:71`) and would touch pet spell maps from the wrong thread.

`ToggleAutocast` and `SetSpellAutocast` run only from `OnWorldObjectUpdate`, after the baseline read, and without a lock held across the pet call. There is no shared container to lock. Issue #114's shared update-hook maps are a different pattern; this design does not add one.

## Decision table

Normative for one chain. `baseline` and `current` use `spell,chain,active,autocastable,bar`. Several spells are joined with `+`. `-` means no spells. `active` and `bar` are `81` (`ACT_DISABLED`), `C1` (`ACT_ENABLED`), `01` (`ACT_PASSIVE`), or `NONE` when the spell has no bar slot. The synthetic ids are chain keys for the contract, not DBC proof. `python3 -m unittest discover -s tests -p 'test_a02_hunter_autocast_functional_s1.py' -v` executes this table.

Check order for an in-scope call, per baseline chain: one baseline spell, active in `{81, C1}`, baseline bar equal to that active byte, then current count, same spell id, autocastable flag, bar present, already-matching row and bar, otherwise restore the baseline byte.

<!-- DECISION-TABLE-BEGIN -->
| case | enabled | human | baseline | current | expect |
| --- | --- | --- | --- | --- | --- |
| switch-off | 0 | 1 | 801,800,C1,1,C1 | 800,800,81,1,81 | OUT_OF_SCOPE |
| not-human | 1 | 0 | 801,800,C1,1,C1 | 800,800,81,1,81 | OUT_OF_SCOPE |
| rank-swap-on | 1 | 1 | 801,800,C1,1,C1 | 800,800,81,1,81 | RESTORE_ENABLED |
| rank-swap-off-already | 1 | 1 | 801,800,81,1,81 | 800,800,81,1,81 | NO_WRITE |
| rank-swap-off-bar-on | 1 | 1 | 801,800,81,1,81 | 800,800,C1,1,C1 | RESTORE_DISABLED |
| removal-no-successor | 1 | 1 | 1742,1742,C1,1,C1 | - | NO_LEARN |
| same-spell-on | 1 | 1 | 9001,9001,C1,1,C1 | 9001,9001,81,1,81 | NO_WRITE |
| same-spell-off | 1 | 1 | 9001,9001,81,1,81 | 9001,9001,81,1,81 | NO_WRITE |
| split-baseline | 1 | 1 | 801,800,C1,1,81 | 800,800,81,1,81 | NO_WRITE |
| two-baseline-ranks | 1 | 1 | 801,800,C1,1,C1+802,800,81,1,81 | 800,800,81,1,81 | NO_WRITE |
| two-current-ranks | 1 | 1 | 801,800,C1,1,C1 | 800,800,81,1,81+802,800,81,1,81 | NO_WRITE |
| not-autocastable | 1 | 1 | 801,800,C1,1,C1 | 800,800,81,0,81 | NO_WRITE |
| missing-bar | 1 | 1 | 801,800,C1,1,C1 | 800,800,81,1,NONE | NO_BAR |
| passive | 1 | 1 | 801,800,01,0,01 | 800,800,01,0,01 | NO_WRITE |
| chain-mismatch | 1 | 1 | 801,800,C1,1,C1 | 800,999,81,1,81 | NO_LEARN |
| already-enabled | 1 | 1 | 801,800,C1,1,C1 | 800,800,C1,1,C1 | NO_WRITE |
<!-- DECISION-TABLE-END -->

`rank-swap-on` is the #103 explicit ON drop, once the successor shares the chain key. `rank-swap-off-already` is the explicit OFF case where the learn default already equals the old byte, so the module has nothing to write. `removal-no-successor` is Cower `1742` and every empty dummy list. `chain-mismatch` is the DBC-unknown case. `same-spell-on` is a same-id flip, which this seam leaves alone so a click or another event-time `ToggleAutocast` on the same id is not overwritten one hook later.

## Negative cases

- Config `0` or a missing key: `OUT_OF_SCOPE`.
- Playerbots-owned pet, including an alt bot the IP regex does not name: `OUT_OF_SCOPE`.
- Warlock pet, guardian, non-hunter owner, non-hunter pet type: `OUT_OF_SCOPE`.
- `m_loading`: `Pet::Update` returns before either hook.
- Spell removed and no same-chain successor: `NO_LEARN`. The spell stays unlearned.
- Successor not autocastable, or baseline active and bar disagree, or two live spells share the chain: `NO_WRITE`.
- Successor missing from the bar: `NO_BAR`. No new slot is created.
- Same spell id, whatever the active byte did inside `m_Events`: `NO_WRITE`.
- Another `WorldObjectScript::OnWorldObjectUpdate` that runs after this module can still change the bar. Script list order is not a contract. **UNKNOWN** which other scripts on this server run there.
- A full action bar (`AddSpellToActionBar` returns false, `CharmInfo.cpp:208`) is the `NO_BAR` path. How often a hunter pet fills all ten slots (`CharmInfo.h:56`) is **UNKNOWN**.

## Rollback

With the key at `0`, the module does not read or write pet spells. Turning a future `1` back to `0` stops later restores. Rows already saved by core `SavePetToDB` stay until the player toggles the button or IP reconciles again. There is no SQL undo in this design, and no character backup step, because this PR writes no rows. Reverting the future patch is the code rollback. PR #69's cache SQL stays unused.

## NOT TESTED

- Any character, pet family, relog, resummon, stable swap, level-up, or client bar.
- The owner's DBC spell-chain map, so the link from a wipe id to `keepId` is **UNKNOWN**.
- The owner's two local edits on Playerbots `e88cc409`.
- Live `MapUpdate.Threads` and the installed binary.
- That `PetSpellInitialize` after a restore matches what the 3.3.5 client shows.
- That the next `SavePetToDB` runs before a crash. A crash before save keeps the previous `pet_spell` and `abdata`.
- Compile and link of the future writer against Grimfeather core, IP, and either Playerbots pin.
- PR #69's cache, which stays blocked.

## Labels

| Finding | Label |
| --- | --- |
| Click path writes `ToggleAutocast` and the bar, and has no script hook | **VERIFIED** |
| Load callback applies bar type over the spell byte; save writes both `pet_spell.active` and `abdata` | **VERIFIED** |
| Core rank copy runs only while the old rank is still live and the new rank is higher | **VERIFIED** |
| IP reconcile unlearns with `clear_ab` before `learnSpell`, so the new autocastable spell is `ACT_DISABLED` and the bar slot is not given the old type | **VERIFIED** |
| Explicit ON on a non-empty dummy replacement becomes OFF in that control flow | **VERIFIED** source. Player-visible result remains a **POTENTIAL ISSUE** and is **NOT TESTED** in game |
| Explicit OFF matches the learn default numerically; the old byte is not read | **VERIFIED** source |
| Growl is absent from `checkHunterPetSpells`; no Growl spell id claimed | **VERIFIED** source, **NOT TESTED** in game |
| Cower `1742` on Serpent, Moth, Chimaera, and Silithid is removal with an empty dummy list | **VERIFIED** source. **POTENTIAL ISSUE** for the lost spell. Putting the byte back is infeasible without `learnSpell`, which this design refuses |
| Empty dummy lists (Wolf Claw and the same shape) are the same removal | **VERIFIED** source |
| `OnPetAddToWorld` / `OnInitStatsForLevel` run before the spell book is loaded | **VERIFIED** |
| `OnUnitUpdate` then `m_Events` then `OnWorldObjectUpdate` inside one `Unit::Update` brackets the IP event | **VERIFIED** source order. Future writer **NOT TESTED** |
| DBC chain identity of wipe id and `keepId` | **UNKNOWN** |
| Playerbots `IsRealPlayer` and the Cower-off autocast action at both published SHAs | **VERIFIED**. The two local edits on top of `e88cc409` are **UNKNOWN** |
| In-game autocast after IP, relog, resummon, or stable | **NOT TESTED** |
| PR #69 | Open draft, unchanged, still blocked |

## Commands

Pins were checked out read-only under `/tmp/pins` on 24 October 2026. Citations are `file:line` against those commits. The synthetic contract does not clone them again:

```
python3 -m unittest discover -s tests -p 'test_a02_hunter_autocast_functional_s1.py' -v
```

Workflow scan from the module root, expected to print nothing:

```
rg -n --glob '*.yml' 'upload-artifact|actions/upload' .github/workflows
```

Every `.github/workflows/*.yml` `pull_request` trigger on this branch's base has a `paths` filter. None of those paths is `docs/research/a02-hunter-autocast-functional-s1.md` or `tests/test_a02_hunter_autocast_functional_s1.py`. This PR adds no workflow. **VERIFIED** by reading the workflow files in the same working tree. No artifact upload step exists in those files.
