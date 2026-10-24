# A02 S1 — human Hunter pet autocast, module-only functional feasibility

**Status:** S1 contract, kept as reviewed. A later default-OFF writer draft lives in `docs/research/a02-hunter-autocast-functional-s2.md`. Sentences below that say the writer is not started describe this S1 review. In-game behaviour is **NOT TESTED**. This note is not a fix and not an observer-as-fix.

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

**VERIFIED.** `IndividualProgression::checkHunterPetSpells` (`IndividualProgressionSpells.cpp:56-469`) returns immediately unless the player is in world, `VanillaHunterPets` is on, the account is not a bot account, the class is hunter, and progression has not passed `PROGRESSION_TBC_TIER_5` (`:58-68`). The reconcile lambda is `:91-111`. The Cower calls at `:445`, `:453`, `:460`, and `:467` are inside the function. `VanillaHunterPets` defaults to true (`IndividualProgression.cpp:1076`). `isBotAccount` (`:398-408`) matches `IndividualProgression.BotAccountsRegex`, default `^RNDBOT.*` (`:1118`).

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
2. `WorldObject::Update` (`Object.cpp:1074-1085`), which runs `m_Events.Update`, then the heartbeat loop, then `sScriptMgr->OnWorldObjectUpdate` — `WorldObjectScript::OnWorldObjectUpdate` (`WorldObjectScript.h:76`). `Heartbeat()` is an empty virtual (`Object.h:233`). `Object.cpp`, `Unit.cpp`, and `Pet.cpp` at this pin do not override it. An override in another translation unit was not searched in this pass, so that remainder is **UNKNOWN**. S2 re-checks the bracket if the core pin moves. The restore hook is after the heartbeat on that same update.
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
- One `Player::PetSpellInitialize()` (`Player.h:1712`, public) after at least one of those writes on that tick. `Pet::learnSpell` already calls `PetSpellInitialize` when `!m_loading` (`Pet.cpp:1909-1915`), so the client is shown the dropped state from that learn. The module packet is the later correction. What the 3.3.5 client shows after that second packet is **NOT TESTED**.

The chain key is `SpellMgr::GetFirstSpellInChain` (`SpellMgr.cpp:603-608`), which returns the spell id when `mSpellChains` has no node. Non-talent chains load from the world table `spell_ranks` (`SpellMgr::LoadSpellRanks`, query at `SpellMgr.cpp:1287`) after talent ranks load from the talent DBC (`LoadSpellTalentRanks`, `SpellMgr.cpp:1218`). `LoadSpellRanks` does not read a `SpellChain.dbc`. `SpellInfo::GetFirstRankSpell` (`SpellInfo.cpp:2934-2938`) is the same notion. Rank helpers `IsDifferentRankOf` / `IsHighRankOf` are `SpellInfo.cpp:3011-3028`. The table treats two spells as the same family only when that key matches. It does not invent a link from IP's wipe list. If the keys differ, the table returns `NO_LEARN` for the old chain and leaves the new spell at the learn default.

### Source chain identity at the pin

Source chain identity is **VERIFIED** at the pin. The owner's live `acore_world.spell_ranks` is **UNKNOWN**.

This pass read `data/sql/base/db_world/spell_ranks.sql` at Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd`. The blob is `ca2ca5916cca570d219ff11088688eb4c80d24a6`, 58147 bytes, 3552 lines, 3502 `(first_spell_id, spell_id, rank)` tuples. No live database was queried. No DBC file was opened. The file is not copied into this module.

| Family | `first_spell_id` | Rows | Spell ids in rank order |
| --- | --- | --- | --- |
| Bite | 17253 | 11 | 17253, 17255, 17256, 17257, 17258, 17259, 17260, 17261, 27050, 52473, 52474 |
| Claw | 16827 | 11 | 16827, 16828, 16829, 16830, 16831, 16832, 3010, 3009, 27049, 52471, 52472 |
| Furious Howl | 24604 | 6 | 24604, 64491, 64492, 64493, 64494, 64495 |
| Prowl | 24450 | 3 | 24450, 24452, 24453 |

11 + 11 + 6 + 3 = 31. Bite ranks 10–11 (`52473`, `52474`), Claw ranks 10–11 (`52471`, `52472`), and Furious Howl rank 6 (`64495`) use the same `first_spell_id` as the lower ranks. Cower `1742` has no `spell_ranks` row, and neither do `1753`, `1754`, `1755`, `1756`, `16697`, or `27048`. Cower stays `NO_LEARN`. This design does not call `learnSpell` to put it back.

IP `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` `checkHunterPetSpells` does not name `52471`, `52472`, `52473`, `52474`, or `64495`. A pet that knows only one of those ids is the same-id path, because the reconcile does not unlearn it. The rank 1–9 Bite and Claw ids, and Furious Howl through `64494`, which that function does name, share the `first_spell_id` values above. Every uncommented non-empty dummy list in that function (52 calls) keeps its wipe ids and its `keepId` values (`dummy - 600000`) on one chain key in this file. Empty dummy lists stay `NO_LEARN`.

Owner-run read-only check. The expected count under this pinned base is 31 rows. A different live count is an owner difference to record, and it is not a link this module invents.

```sql
SELECT first_spell_id, spell_id, `rank` FROM spell_ranks
WHERE first_spell_id IN (17253, 16827, 24604, 24450)
ORDER BY first_spell_id, `rank`;
```

### What the other tokens do

`NO_LEARN` is a removed chain with no successor. `learnSpell` of `1742`, or of a wiped Claw/Bite rank, would put back a spell IP just removed. The table does not call `learnSpell` or `unlearnSpell`.

`NO_WRITE` leaves the pet alone. That includes Growl when its spell id is unchanged, an explicit OFF successor that is already `ACT_DISABLED` on both the row and the bar, a same-id active flip inside the event queue, a passive row, a split baseline, a successor whose row and bar disagree, and more than one live spell in the chain.

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

Check order for an in-scope call, per baseline chain: one baseline spell, active in `{81, C1}`, baseline bar equal to that active byte, then current count, same spell id, autocastable flag, bar present, current row and bar agree, already-matching row and bar, otherwise restore the baseline byte. `m_autospells` membership is not a column in this table. The S2 write model rejects a successor-split-vector before any call.

<!-- DECISION-TABLE-BEGIN -->
| case | enabled | human | baseline | current | expect |
| --- | --- | --- | --- | --- | --- |
| switch-off | 0 | 1 | 801,800,C1,1,C1 | 800,800,81,1,81 | OUT_OF_SCOPE |
| not-human | 1 | 0 | 801,800,C1,1,C1 | 800,800,81,1,81 | OUT_OF_SCOPE |
| rank-swap-on | 1 | 1 | 801,800,C1,1,C1 | 800,800,81,1,81 | RESTORE_ENABLED |
| rank-swap-off-already | 1 | 1 | 801,800,81,1,81 | 800,800,81,1,81 | NO_WRITE |
| rank-swap-off-bar-on | 1 | 1 | 801,800,81,1,81 | 800,800,C1,1,C1 | RESTORE_DISABLED |
| successor-split-row-off | 1 | 1 | 801,800,81,1,81 | 800,800,81,1,C1 | NO_WRITE |
| successor-split-row-on | 1 | 1 | 801,800,C1,1,C1 | 800,800,C1,1,81 | NO_WRITE |
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

`rank-swap-on` is the #103 explicit ON drop, once the successor shares the chain key. `rank-swap-off-already` is the explicit OFF case where the learn default already equals the old byte, so the module has nothing to write. `rank-swap-off-bar-on` restores OFF when the successor row and bar are both `C1`. `successor-split-row-off` and `successor-split-row-on` are current books whose row and bar disagree, and they stay `NO_WRITE`. `removal-no-successor` is Cower `1742` and every empty dummy list. `chain-mismatch` is a successor whose chain key differs. The hunter families counted above share a key at the pin, so that row is the contract for a key this file does not link. `same-spell-on` is a same-id flip, which this seam leaves alone so a click or another event-time `ToggleAutocast` on the same id is not overwritten one hook later.

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
- `InitPetActionBar` (`CharmInfo.cpp:52-64`) puts commands on slots 0–2, spells on indices 3–6 (`ACTION_BAR_INDEX_PET_SPELL_START` / `ACTION_BAR_INDEX_PET_SPELL_END`, `CharmInfo.h:54-55`), and reactions on slots 7–9. The bar length is 10 (`CharmInfo.h:56`). `IsActionBarForSpell` is true for `ACT_DISABLED`, `ACT_ENABLED`, and `ACT_PASSIVE` (`CharmInfo.h:103-107`), so only the four spell slots take a pet spell.
- IP's `clear_ab` leaves the old slot as action `0`, type `ACT_DISABLED` (`CharmInfo.cpp:221`). That counts as an empty spell slot. `AddSpellToActionBar` (`CharmInfo.cpp:172-183`) fills the first empty spell slot, which is the cleared slot unless a lower spell slot was already empty. The restore does not move slots.
- A full set of four spell slots (`AddSpellToActionBar` returns false, `CharmInfo.cpp:208`) is the `NO_BAR` path. How often a hunter pet fills all four is **UNKNOWN**.

## S2 acceptance criteria

The S2 writer is not started. This section is the gate for a later default-OFF patch. It is not that patch. In-game behaviour stays **NOT TESTED**. No production C++, config entry, SQL, or DBC is added here. Core, Individual Progression, and Playerbots stay unedited. PR #69 stays blocked.

Acceptance is a source and synthetic contract. It is not a gameplay pass and not a worldserver link. The writer stays unstarted until CS01 and CS03 accept this S1 delta.

### Post-write consistency

**VERIFIED** as the shape of the pinned calls. Whether a later writer leaves a saved pet consistent is **NOT TESTED**.

`Pet::ToggleAutocast` (`Pet.cpp:2247-2286`) returns without a write when the spell is missing or not autocastable. `ToggleAutocast(true)` is a no-op when the id is already in `m_autospells`, and that no-op leaves `m_spells[].active` unchanged. `ToggleAutocast(false)` is a no-op when the id is absent from `m_autospells`, and that no-op leaves `active` unchanged. `CharmInfo::SetSpellAutocast` (`CharmInfo.cpp:291-300`) changes the type of an existing spell slot whose action id equals the spell id. It does not create a slot.

The decision table has no `m_autospells` column. A successor whose `active` byte and bar type disagree is `NO_WRITE` (`successor-split-row-off`, `successor-split-row-on`). A successor whose `m_autospells` membership disagrees with the `active` byte is `NO_WRITE` (`successor-split-vector`). The writer does not call `ToggleAutocast` to repair either split. Those no-op gates would leave the split in place.

A call that does run is followed by a read of `active`, `m_autospells` membership, and the bar type. Disagreement is recorded as `NO_WRITE` and is not claimed as persistence. `NO_BAR` still creates no slot.

On the IP learn path the successor is a consistent OFF, so `RESTORE_ENABLED` is not a no-op. `addSpell` stores `ACT_DISABLED` for an autocastable `ACT_DECIDE` (`Pet.cpp:1812-1813`). The closing `ToggleAutocast(spellInfo, false)` at `Pet.cpp:1889` does nothing, because the id was never pushed onto `m_autospells`. `AddSpellToActionBar` stores `ACT_DISABLED` for that `ACT_DECIDE`. The three stores agree on OFF. `ToggleAutocast(true)` then pushes the id and sets `ACT_ENABLED`, and `SetSpellAutocast(true)` sets the existing slot.

### Hot-path filter order

Both hooks run for every unit or world object on every map tick, on each map thread. The future scripts register only these hooks on the enabled-hook lists (`UnitScript` constructor, `UnitScript.h:57`; `WorldObjectScript` constructor, `WorldObjectScript.h:37`). `CALL_ENABLED_HOOKS` is `UnitScript.cpp:109` and `WorldObjectScript.cpp:54`.

The synthetic tests execute this filter order:

1. A cached config bool, read when config loads. The tick does not call `sConfigMgr`. A false cache returns with no allocation.
2. `IsPet()` and `HUNTER_PET`. Any other unit returns with no allocation.
3. Baseline storage is one `CustomData.GetDefault` struct (`DataMap.h:50-59`), mutated in place. The first call allocates. Later ticks do not. `DataMap::Set` (`DataMap.h:65`) replaces the object on every call and is not used on this path.
4. `Pet::Update` already returns while `m_loading` is set (`Pet.cpp:659-660`), so these hooks do not run during load. The writer still refuses a loading pet.

### Human-only fail-closed Playerbots check

The check runs only when a restore is about to be written. The snapshot tick does not call it.

`GET_PLAYERBOT_AI` is `sPlayerbotsMgr.GetPlayerbotAI` (`src/Script/Playerbots.h:31`). `IsRealPlayer` (`src/Bot/PlayerbotAI.cpp:4523-4528`) is true only for a player pointer with no `PlayerbotAI`. `PlayerbotsMgr::GetPlayerbotAI` (`src/Bot/PlayerbotMgr.cpp:1858-1875`) reads `_playerbotsAIMap` without a lock in that function (`:1868`). Login and logout erase and emplace that map (`:1828-1834`, `:1842-1845`). `src/Bot/PlayerbotMgr.cpp` and `src/Script/Playerbots.h` are byte-identical at `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` and `e88cc4099e69f35126b28942a412ca702d20453b`. The `.cpp` sha256 is `b5a5d7236af6e71312c8c89c10d0d1008ece4d86a3373eab8ab6fa06a9750610`.

The owner states `MapUpdate.Threads = 8`. This note still has not read the live `worldserver.conf`, so the live value is **UNKNOWN**. Concurrent map threads are the reason that unlocked map is not read on every tick. Upstream already reads it from map threads. This design does not add a per-tick read.

A missing `Playerbots.h` fails closed. The precedent in this module is `HallowsEndShadeOfTheHorseman.cpp:57`, where the header guard leaves `IsRealPlayer` false (`ReadOneBucketCaster`, `:110-120`). A missing header is not a human. Both the header-present path and the header-absent path are part of acceptance. The IP account regex is not a substitute.

### `owner->GetPet() == pet`

IP's event uses `player->GetPet()` (`IndividualProgressionSpells.cpp:1344`), the owner's current pet, rather than a pointer saved from the object whose `m_Events` ran. `Pet::Update` returns before `Creature::Update` when `m_removed` (`Pet.cpp:656-657`) and, for a living controlled pet, when `owner->GetPetGUID()` differs (`Pet.cpp:684-691`). The writer still requires `owner->GetPet() == pet` before a write. A mismatch is `NO_WRITE`.

### Competing subscribers

Same-thread order of `OnUnitUpdate` and `OnWorldObjectUpdate` does not make this module the last writer. Another `OnWorldObjectUpdate` that runs later can still change the bar. This module's sources do not define `OnUnitUpdate` or `OnWorldObjectUpdate`. Subscribers in the owner's other modules, and any Eluna scripts, are **UNKNOWN**. S2 does not add a process-global map or a world-thread poll. The acceptance record is that limitation.

### Warlock pets

Warlock pets are out of A02 scope. The scope check returns `OUT_OF_SCOPE`. `checkWarlockPetSpells` (`IndividualProgressionSpells.cpp:471-585`, called at `:1364`) uses the same reconcile shape, so a warlock demon can drop an autocast byte the same way. That drop is a **POTENTIAL ISSUE** for a future warlock design and is not an A02 fix. Four of those calls mix chain keys in the pinned `spell_ranks`, so extending this table would return `NO_LEARN` for the old key:

| Mixed wipe | Keys at the pin |
| --- | --- |
| Devour Magic / Shadow Bite `19505` through `54053` | `19505` and `54049` |
| Spell Lock `19244`, `19647`, `24259` | `19244`, and `24259` has no `spell_ranks` row |
| Intercept `30151`, `30154`, `30199`, `30200` | `30151` and `30154` |
| Cleave `30213`, `30214`, `30222`, `30224` | `30213` and `30214` |

## Rollback

With the key at `0`, the module does not read or write pet spells. Turning a future `1` back to `0` stops later restores. Rows already saved by core `SavePetToDB` stay until the player toggles the button or IP reconciles again. There is no SQL undo in this design, and no character backup step, because this PR writes no rows. Reverting the future patch is the code rollback. PR #69's cache SQL stays unused.

## NOT TESTED

- Any character, pet family, relog, resummon, stable swap, level-up, or client bar.
- The owner's live `acore_world.spell_ranks`. The pinned base file above is **VERIFIED**. Whether the running world matches those 31 rows is **UNKNOWN**.
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
| Cower `1742` on Serpent, Moth, Chimaera, and Silithid is removal with an empty dummy list, and `1742` has no `spell_ranks` row | **VERIFIED** source. **POTENTIAL ISSUE** for the lost spell. The spell stays unlearned. `NO_LEARN`. This design does not call `learnSpell` to put it back |
| Empty dummy lists (Wolf Claw and the same shape) are the same removal | **VERIFIED** source |
| Source chain identity of Bite `17253` (11), Claw `16827` (11), Furious Howl `24604` (6), and Prowl `24450` (3), total 31, at blob `ca2ca5916cca570d219ff11088688eb4c80d24a6` | **VERIFIED** at the pin |
| Owner live `acore_world.spell_ranks` | **UNKNOWN** |
| `OnPetAddToWorld` / `OnInitStatsForLevel` run before the spell book is loaded | **VERIFIED** |
| `OnUnitUpdate`, then `m_Events`, then `Heartbeat()`, then `OnWorldObjectUpdate` inside one `Unit::Update` brackets the IP event | **VERIFIED** source order. An override of `Heartbeat()` outside `Object.cpp`, `Unit.cpp`, and `Pet.cpp` is **UNKNOWN**. Future writer **NOT TESTED** |
| Non-talent chain load is `spell_ranks` (`SpellMgr.cpp:1287`), not a `SpellChain.dbc` read in `LoadSpellRanks` | **VERIFIED** source. No DBC file was opened |
| Playerbots `IsRealPlayer` and the Cower-off autocast action at both published SHAs | **VERIFIED**. The two local edits on top of `e88cc409` are **UNKNOWN** |
| In-game autocast after IP, relog, resummon, or stable | **NOT TESTED** |
| `ToggleAutocast` no-op gates and `SetSpellAutocast` existing-slot-only, at `Pet.cpp:2247-2286` and `CharmInfo.cpp:291-300` | **VERIFIED** source. Post-write persistence is **NOT TESTED** |
| Successor row/bar split (`successor-split-row-off`, `successor-split-row-on`) and successor-split-vector | **NO_WRITE**. Synthetic model only. **NOT TESTED** in game |
| Hot path: cached config bool, then hunter pet, `GetDefault` in place, no `DataMap::Set` on the tick | **VERIFIED** as the acceptance order. The writer is not started |
| Human-only Playerbots read, only when a restore is about to be written; `_playerbotsAIMap` read without a lock in `GetPlayerbotAI` | **VERIFIED** source at both published Playerbots pins. Live `MapUpdate.Threads` **UNKNOWN**. Missing header fails closed |
| `owner->GetPet() == pet` before a write | Required. Mismatch is `NO_WRITE`. **NOT TESTED** in game |
| Competing `OnUnitUpdate` / `OnWorldObjectUpdate` subscribers in the owner's other modules | **UNKNOWN**. This module does not define those hooks. Hook order is not last-writer proof |
| Warlock pets | Out of A02 scope. `OUT_OF_SCOPE`. Mixed warlock chains at the pin are a **POTENTIAL ISSUE** only for a future warlock design |
| S2 writer | Not started |
| PR #69 | Open draft, unchanged, still blocked |

## Commands

Pins were checked out read-only under `/tmp/pins` on 24 October 2026. Citations are `file:line` against those commits. The synthetic contract does not clone them again. The `spell_ranks` count is blob `ca2ca5916cca570d219ff11088688eb4c80d24a6`, fetched read-only the same day. The tests assert the recorded rows. They do not download the file.

```
python3 -m unittest discover -s tests -p 'test_a02_hunter_autocast_functional_s1.py' -v
```

Workflow scan from the module root, expected to print nothing:

```
rg -n --glob '*.yml' 'upload-artifact|actions/upload' .github/workflows
```

Every `.github/workflows/*.yml` `pull_request` trigger on this branch's base has a `paths` filter. None of those paths is `docs/research/a02-hunter-autocast-functional-s1.md` or `tests/test_a02_hunter_autocast_functional_s1.py`. This PR adds no workflow. **VERIFIED** by reading the workflow files in the same working tree. No artifact upload step exists in those files.
