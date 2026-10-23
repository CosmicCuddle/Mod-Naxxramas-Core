# A02 S1 — Human Hunter pet autocast persistence

Research only. This document does not implement a fix, does not change Individual Progression, AzerothCore, or Playerbots, and is not an owner decision. S2 stays blocked pending CS01 and owner direction.

**Headline: no safe module-owned synchronous hook is source-proven** at IP's rank unlearn/relearn boundary. Editing IP is only a possible separately owner-approved alternative, and it is not permitted under the module-only rule. No S2 module code is included. Section 5 records a module-only save/restore idea as research. It is **FEASIBLE WITH CAVEATS** and **NOT TESTED**. It is not an implementation, and it does not reopen S2.

| Label | Meaning in this document |
| --- | --- |
| VERIFIED | Read at the pinned SHA. The citation checker recomputes the line. |
| POTENTIAL ISSUE | The source can behave this way. It was not executed on a server. |
| UNKNOWN | Not determined from the pinned trees. |
| NOT TESTED | No worldserver, no client, no character database. |

## Pins and how they were read

| Tree | SHA | Role |
| --- | --- | --- |
| Grimfeather/azerothcore-wotlk | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` | Old pinned core |
| Grimfeather/azerothcore-wotlk | `8daffdabe9202c228e45d833c9a1d399597a15cd` | Proposed new core |
| Grimfeather/mod-individual-progression | `4ff4b5fcc1480348f058c632573143e62d4e3a41` | Pinned IP |
| mod-playerbots/mod-playerbots | `037c01418b5d01506917a3db9b44fd56ac5f965c` | Pinned Playerbots |

Local checkouts of those four commits were read on 2026-10-20. `Pet.cpp` is byte-identical at both core SHAs (SHA-256 `825a9d66238d3dc2a3f5d8cb700b241b4c8b2e613aa030c78a9e31809ce1a356`). The same is true of `Pet.h`, `CharmInfo.cpp`, `CharmInfo.h`, `PetHandler.cpp`, `PetScript.h`, `PetScript.cpp`, `ScriptMgr.h`, `PlayerScript.h`, `Player.cpp`, `CharacterDatabase.cpp`, `PetAI.cpp`, and `SpellInfo.h`. `SpellInfo.cpp` and `ObjectMgr.cpp` differ; the autocast predicate and the pet-number query were compared separately. IP `IndividualProgressionSpells.cpp` SHA-256 is `8ed6792bacf80a5c7fa23b05142f48f90ae71c9f069862a6c151c90e7d9f8456`.

Line numbers below are the old core unless the new core is named. Where the file hash matches, the new core has the same lines.

## 1. What core already preserves

### `pet_spell.active`

`CHAR_SEL_PET_SPELL` reads `spell, active` for one pet number (`CharacterDatabase.cpp:575`). `CHAR_INS_PET_SPELL` writes `guid, spell, active` (`CharacterDatabase.cpp:581`). `_LoadSpells` passes that byte straight into `addSpell` as `ActiveStates` (`Pet.cpp:1559-1567`). `_SaveSpells` deletes every row for the pet number, then inserts `itr->second.active` (`Pet.cpp:1572-1597`).

The values are not a boolean (`CharmInfo.h:59-66`):

| Name | Value | Meaning for an autocastable pet spell |
| --- | --- | --- |
| `ACT_DECIDE` | `0x00` | Caller did not supply a state. `addSpell` replaces it. |
| `ACT_PASSIVE` | `0x01` | Not an autocast toggle. |
| `ACT_DISABLED` | `0x81` | Present and not autocasting. |
| `ACT_ENABLED` | `0xC1` | Present and autocasting. |

**VERIFIED:** explicit ON is `ACT_ENABLED` (`0xC1`). Explicit OFF is `ACT_DISABLED` (`0x81`). A brand-new autocastable spell also becomes `ACT_DISABLED` (`Pet.cpp:1810-1813`). The column cannot tell "the player turned this off" from "nobody has turned this on".

`_SaveSpells` says pet numbers are recycled, so a partial update could hand a new pet the previous pet's rows (`Pet.cpp:1574`). The save therefore deletes the whole set first. `ObjectMgr::LoadPetNumber` seeds the next number from `SELECT MAX(id) FROM character_pet` (old core `ObjectMgr.cpp:8104-8108`, new core `ObjectMgr.cpp:8117-8121`). **VERIFIED** as a counter, not as a guarantee that a deleted number is never reused. **POTENTIAL ISSUE** for any future key that treats pet number as a permanent incarnation. This research does not add a key.

### Player toggle writes both stores

`HandlePetSpellAutocastOpcode` ignores a spell the pet does not know or that fails `IsAutocastable` (`PetHandler.cpp:991`). For a real pet it calls `Pet::ToggleAutocast` and then `CharmInfo::SetSpellAutocast` (`PetHandler.cpp:1002-1007`). The action-bar move packet does the same pair: `ToggleAutocast(true/false)` for `ACT_ENABLED` / `ACT_DISABLED`, then `SetActionBar` (`PetHandler.cpp:797-834`).

`ToggleAutocast` returns immediately when the spell is not autocastable (`Pet.cpp:2251`). Turning ON inserts the id into `m_autospells` and sets `ACT_ENABLED` (`Pet.cpp:2266-2268`). Turning OFF removes the id and sets `ACT_DISABLED` only when the id is already in `m_autospells` (`Pet.cpp:2276-2281`). A second OFF is a no-op. `SetSpellAutocast` writes the bar type only (`CharmInfo.cpp:291-297`). It does not write `pet_spell`.

`IsAutocastable` is false for `SPELL_ATTR0_PASSIVE` and for `SPELL_ATTR1_NO_AUTOCAST_AI`, and true otherwise (`SpellInfo.cpp:1148-1154` at both core SHAs). **UNKNOWN** which hunter pet spell ids carry those attributes. Spell.dbc is not in either git tree. Only spells that pass this predicate can be explicit ON.

### Native rank replacement copies ON and OFF

`addSpell`, when the new spell `IsDifferentRankOf` an existing spell and `IsHighRankOf` it, sets `newspell.active = petSpell.active` (`Pet.cpp:1850-1855`). That assignment copies `ACT_ENABLED` and `ACT_DISABLED` alike. If the copied state is ON it turns the old rank's autocast off, then `unlearnSpell(old, false, false)` (`Pet.cpp:1857-1860`). The `false` clear-bar argument leaves the bar slot in place. `AddSpellToActionBar` then finds the same chain and replaces the spell id without changing the type (`CharmInfo.cpp:164-167`). A lesser rank is ignored (`Pet.cpp:1863-1865`).

**VERIFIED:** for one rank chain, core's own higher-rank learn preserves explicit ON and explicit OFF in `PetSpell.active` and in the existing bar type. The policy test `test_higher_rank_copies_on_and_off` pins that shape. It uses a larger spell id as a stand-in for `IsHighRankOf`. DBC rank order was **NOT TESTED**.

`learnSpell` is `addSpell` plus, once loading has finished, a learned-spell packet and `PetSpellInitialize` (`Pet.cpp:1903-1914`). `Pet::learnSpell` does not call `OnPlayerLearnSpell`. That hook is reached from `Player::learnSpell` (`Player.cpp:3428`, `Player.cpp:3443`).

### Summon order

`LoadPetFromDB` sets `m_loading`, creates the pet, and loads the action-bar string from that pet's stable record (`Pet.cpp:216`, `Pet.cpp:408`). `OnPlayerBeforeLoadPetFromDB` has already fired, before the pet's spells exist (`Pet.cpp:241`). `InitStatsForLevel` fires `OnInitStatsForLevel` and `OnPlayerAfterGuardianInitStatsForLevel` (`Pet.cpp:1434`, `Pet.cpp:1442`). `AddToWorld` then fires `OnPetAddToWorld` (`Pet.cpp:118`). Only after that does the async holder run (`Pet.cpp:416`).

Inside the callback, still on this pet, the order is:

1. `InitTalentForLevel` (talent-point hook, spells not loaded yet) at `Pet.cpp:427`.
2. `_LoadAuras`, then `_LoadSpells` at `Pet.cpp:435`.
3. `InitTalentForLevel` again at `Pet.cpp:436`, so `OnCalculateMaxTalentPointsForLevel` (`Pet.cpp:2242`) can see the loaded book.
4. `LearnPetPassives`, then `InitLevelupSpellsForLevel` at `Pet.cpp:439`.
5. `CleanupActionBar` at `Pet.cpp:446`.
6. `PetSpellInitialize` (`Player.cpp:9760`), which sends each remaining spell's `active` byte (`Player.cpp:9796`).
7. `m_loading = false` at `Pet.cpp:496`.

`SavePetToDB` returns without writing while `m_loading` is set (`Pet.cpp:510`). A successful save writes `_SaveSpells` and the generated bar string on that pet number (`Pet.cpp:536`, `Pet.cpp:561-586`).

`CleanupActionBar` calls `ToggleAutocast(spell, barType == ACT_ENABLED)` for every bar spell the pet still knows (`Pet.cpp:2036`). **VERIFIED:** after load, a bar spell's type overwrites the value just read from `pet_spell`. A consistent toggle wrote both, so they agree. **POTENTIAL ISSUE** if the two stores diverge: the bar wins, and the next save persists the bar's choice. The policy test `test_cleanup_reapplies_bar_over_saved_active` pins the overwrite.

`PetAI` casts from `m_autospells` and does not check `HasSpell` before building the cast (`PetAI.cpp:247-249`). **POTENTIAL ISSUE**, described with the IP path below.

### Level-up spells are not the IP path

`InitLevelupSpellsForLevel` walks the family level-up list in reverse. If the entry's level is above the pet and `CanUnlearnSpellSet` returns true, it unlearns. Otherwise it `learnSpell`s (`Pet.cpp:1930-1934`). The default-spell list uses `CanUnlearnSpellDefault` the same way (`Pet.cpp:1950`). A hook that returns false does not veto the learn; the `else` branch learns the spell. At a pet level that is already at or above every entry, `CanUnlearnSpellSet` is not called. **VERIFIED** from the `if/else`. **NOT TESTED** against a real family list, because that list is database data and was not opened.

`removeSpell` does not mention `m_autospells` (`Pet.cpp:1976-2025`). The native higher-rank path removes the old id first, by `ToggleAutocast(old, false)`, only when the copied state is ON (`Pet.cpp:1857-1858`).

## 2. What IP does to that preference

`checkHunterPetSpells` (`IndividualProgressionSpells.cpp:36`) returns immediately unless all of these hold:

- the player is in world and `VanillaHunterPets` is on (`:38`, config default true at `IndividualProgression.cpp:1028`)
- `isBotAccount` is false (`:41`)
- the class is hunter (`:44`)
- the player has not passed `PROGRESSION_TBC_TIER_5` (`:47`)
- `player->GetPet()` has a creature family (`:50-67`)

`isBotAccount` (`IndividualProgression.cpp:351-360`) loads the account name and `std::regex_match`es it against the member `botAccountsRegex`. That member is filled by `sConfigMgr->GetOption("IndividualProgression.BotAccountsRegex", "^RNDBOT.*")` (`IndividualProgression.cpp:1070`). The same default is in `conf/individualProgression.conf.dist:513`. The conf comment says that default excludes randombots, and that any other account is added by changing the expression (`:508-509`). The literal is the config default. It is not hardcoded inside `isBotAccount`, and `isBotAccount` is not a Playerbots API call.

**Any future exclusion in this module must reuse that configured behaviour.** It must call `isBotAccount`, or match the account name with the same `IndividualProgression.BotAccountsRegex` value IP loaded. It must not paste `^RNDBOT.*` into Naxx Core as a literal, and it must not treat every Playerbots-controlled player as the same kind of account. A random-bot name that matches the default, an altbot, and a bot account the owner named some other way are not equivalent. Accounts that do not match the configured expression fall through `IndividualProgressionSpells.cpp:41` and are reconciled. **VERIFIED** as the gate and the config load. **UNKNOWN** which account names on the owner's server match the live expression.

The only call of `checkHunterPetSpells` in the pinned IP tree is `DelayedPetSpellCheck::Execute` (`IndividualProgressionSpells.cpp:1342`). The declaration is `IndividualProgression.h:430` and the definition is `:36`. IP's `PetScript` schedules that event from `OnPetAddToWorld` and `OnInitStatsForLevel` (`:1292-1309`), at `CalculateTime(200)` on `pet->m_Events` (`:1284-1286`). Its comment says those hooks run before the async spell load (`:1276`), which matches `InitStatsForLevel` at `Pet.cpp:332` and `AddToMap` at `Pet.cpp:410`. `PendingPetSpellCheck` (`IndividualProgressionSpells.cpp:1252-1282`) makes the second hook return without queuing again. That object is stored with `CustomData.GetDefault` (`:1278`). `DataMap::Get` returns it only to a caller that names the stored type (`DataMap.h:29`). The class is not declared in `IndividualProgression.h`. A module cannot read `pending`.

Two timing notes stay separate. Neither one is the rank-migration result below, and neither one has been watched on a server. Both are pending observation.

**POTENTIAL ISSUE (owner GUID).** The event stores the owner GUID, not the pet number (`IndividualProgressionSpells.cpp:1315`). On fire it looks the player up and reads `player->GetPet()` again (`:1321-1324`). The event sits on `pet->m_Events`, so this pet's processor owns the callback, but the spell check uses whatever `GetPet()` returns then. Those can differ. Normal summon refuses to load a second pet while one exists (`Pet.cpp:237`), so this is not the ordinary dismiss-then-summon path. It was **NOT TESTED**. The explicit-ON to default-OFF path does not depend on it.

**POTENTIAL ISSUE (still loading, 10 tries of 200 ms).** While `pet->isBeingLoaded()` and `_attempts < 10`, `Execute` queues another event at `CalculateTime(200)` and returns (`IndividualProgressionSpells.cpp:1328-1336`). `isBeingLoaded()` is `m_loading` (`Pet.h:65`). When the attempt cap is reached it still clears `pending` and calls the hunter check, including if the pet is still loading (`:1338-1342`). `CalculateTime` is `m_time + offset` (`EventProcessor.cpp:159-161`). `m_time` advances only inside `EventProcessor::Update` (`:40-43`). `Pet::Update` returns before `Creature::Update` while `m_loading` is set (`Pet.cpp:659-660`, `:736`). The pump is `WorldObject::Update` (`Object.cpp:1076` at both core SHAs), reached from `Unit::Update` (`Unit.cpp:517` at both) from the alive branch of `Creature::Update` (`Creature.cpp:777`). On that path, `pet->m_Events` does not run during the load flag. Whether any other caller pumps that processor during the async load is **UNKNOWN**. The retry was **NOT TESTED**. If a fire did land while `m_loading` was still true, `addSpell` of a saved higher rank can then copy `active` from the rank IP just defaulted to OFF (`Pet.cpp:1855` overwrites the loaded byte). That race is independent of the owner-GUID note.

### The lambda discards the old active byte

For each family ability the lambda (`:71-91`):

1. Walks the dummy id list backwards. The first dummy the player knows becomes `keepId = dummy - 600000` (`:74-78`).
2. `unlearnSpell(id, false, true)` for every other listed id the pet knows (`:83-86`). `learn_prev` is false, so core will not teach the previous chain rank. `clear_ab` is true, so `RemoveSpellFromActionBar` clears the slot whose chain-first matches, not merely the exact id (`CharmInfo.cpp:219-221`).
3. If `keepId` is non-zero and missing, `pet->learnSpell(keepId)` (`:89-90`).

`learnSpell` → `addSpell(ACT_DECIDE)`. The other ranks were already removed, so the copy at `Pet.cpp:1855` does not see them. An autocastable new spell becomes `ACT_DISABLED` (`Pet.cpp:1812-1813`). `ToggleAutocast(false)` does nothing, because the new id is not in `m_autospells`. The bar slot was cleared, so `AddSpellToActionBar` uses a free slot and stores `ACT_DISABLED` (`CharmInfo.cpp:183`).

There is no `sScriptMgr` call on lines 83-90. The citation checker asserts that.

| Case | Explicit ON (`ACT_ENABLED`) | Explicit OFF (`ACT_DISABLED`) |
| --- | --- | --- |
| IP returns at the gates above, including a bot account | Unchanged. **VERIFIED** | Unchanged. **VERIFIED** |
| Pet already knows `keepId` and no other listed id is known | Unchanged in `PetSpell.active` and on the bar. **VERIFIED** | Same. **VERIFIED** |
| Pet knows a different listed id, then IP learns `keepId` | Lost. The new spell is the learn default `ACT_DISABLED`, and the new bar type is `ACT_DISABLED`. The old id can remain in `m_autospells` because `removeSpell` does not erase it. **VERIFIED** mechanism. **NOT TESTED** in game. | The new `PetSpell.active` is also `ACT_DISABLED`. That matches OFF, and it was not copied from the old rank. **VERIFIED** mechanism. **NOT TESTED** in game. |
| Dummy list empty, so `keepId` stays 0 | The spell is removed. Absence is not an OFF rank. Putting it back would teach an illegal rank. **VERIFIED** | Same removal. **VERIFIED** |

So the hunch is right for explicit ON, and only half right for explicit OFF. Core would have copied both bits. IP's unlearn-before-relearn throws the bit away. OFF survives a rank change only because the replacement default is OFF. A later change that made the default ON, or a restore that treated "not copied" as "turn it on", would violate explicit OFF.

Dismiss, summon, logout, and relog all use this load path and then this delayed check. Once a post-check save runs, `pet_spell.active` for the new rank is the default OFF, so the next load has nothing left to copy. **VERIFIED** as the write path. **NOT TESTED** against a character database.

`PetAI` may still see the stale old id (`PetAI.cpp:247`). **POTENTIAL ISSUE:** the old rank can be offered to the cast loop after it was unlearned. Whether `CanAutoCast` fails closed was **NOT TESTED**.

### Original pet and multiple pets

Stabled pets are separate `character_pet` rows and separate `pet_spell` rows, keyed by pet number. The lambda closes over the `Pet*` from `GetPet()` at the start of the check and does not iterate the stable. A pet that is not summoned is not rewritten. **VERIFIED.**

The delayed event does not close over that `Pet*`. The owner-GUID note above is the separate timing issue for that lookup. It is not folded into the still-loading note.

A module that stored a preference on the player, or on the spell family without the pet number, would spill across pets. The native rows do not.

### Family inventory

`checkHunterPetSpells` names 26 families and contains 89 active `reconcile` calls and 22 commented-out calls. The citation checker recounts them from the pinned file. Growl ids `2649`, `14916`-`14921`, `27047`, and `61676` do not appear in the function. **VERIFIED** absence. Growl's autocast, if the pet has it, is left to core.

Commented Cower lines (the seven-rank list beginning `1742`) are not executed for the families that carry them. Serpent, Moth, Chimaera, and Silithid actively reconcile `{1742}` with an empty dummy list, so rank-1 Cower is removed and not replaced. **VERIFIED** from the source text. Whether Cower is autocastable is **UNKNOWN** (no DBC).

Empty dummy lists are the illegal-rank removal. They are used for WotLK-only abilities (Rake, Web, Swipe, Bad Attitude, Pin, Smack, Savage Rend, Dust Cloud, Sonic Blast, Tendon Rip, Snatch, Ravage, Spore Cloud, Nether Shock, and the whole Serpent, Moth, Chimaera, and Silithid blocks) and for some abilities a family is not allowed to keep (Wolf Claw, Carrion Bird Bite, Tallstrider Claw). Boar Gore uses the dummy list only after `PROGRESSION_PRE_TBC`; before that the same six ids are removed (`IndividualProgressionSpells.cpp:167-171`).

List mismatches, all **VERIFIED** as text and **UNKNOWN** as DBC chains:

- Dash comments name dummy ids `623099`, `623109`, `623110` (spells `23099`, `23109`, `23110`). The active wipe list is only `61684`, kept only when the player knows `661684`. The older ids are not passed to `unlearnSpell`.
- Wolf Furious Howl wipes five ids and has four dummies. `64494` has no dummy, so it cannot be `keepId`.
- Ravager Gore wipes six ids and has five dummies. `35295` cannot be `keepId`.
- Dragonhawk Fire Breath wipes six ids and has two dummies. The comment says ranks 3-5 are WotLK-only. Those higher ids cannot be kept even if a later trainer spell existed, because the dummy list stops.

`keepId` is chosen only from player spells of the form `rank + 600000`. Pet talent ranks are not read. `addSpell`'s talent branch removes other talent ranks and does not copy `active` (`Pet.cpp:1820-1835`); those spells are the pet's own talents, not the autocast family list. Hunter talent auras that scale a pet are not spell-id changes in this function. Learning a new trainer dummy does not call `checkHunterPetSpells`; the only call site is the delayed pet event. The new rank is applied the next time that event runs for a summoned pet. **VERIFIED** call site. **NOT TESTED** in game.

### Playerbots

`TogglePetSpellAutoCastAction::Execute` (`PetsAction.cpp:342-395`) walks every known autocastable pet spell, skips a hard-coded denylist (Prowl, one Cower id, Leap, Spell Lock, Devour Magic, Spirit Wolf Leap), and calls `Pet::ToggleAutocast` when the bot policy disagrees. It does not call `SetSpellAutocast`. IP already returns before the lambda for accounts `isBotAccount` accepts, so this research's conclusion does not require a Playerbots change. A module that toggled pets of those accounts would fight this action. Accounts that fail the configured regex are not skipped, including a Playerbots account whose name is outside `IndividualProgression.BotAccountsRegex`. That is the bot-exclusion rule above, not a second regex and not a "all Playerbots" switch. **POTENTIAL ISSUE** for bot accounts the configured expression does not match. **NOT TESTED** against the owner's account list.

## 3. Module hooks that actually exist

`PetScript` at both SHAs ends at `PETHOOK_END` after exactly these hooks (`PetScript.h:26-32`, `:43-58`):

| Hook | When it fires on summon | Can it restore between IP unlearn and learn? |
| --- | --- | --- |
| `OnPlayerBeforeLoadPetFromDB` | Before the pet is created (`Pet.cpp:241`). | No. No spell book. |
| `OnPlayerBeforeGuardianInitStatsForLevel` / `OnPlayerAfterGuardianInitStatsForLevel` / `OnInitStatsForLevel` | `InitStatsForLevel`, before the async callback (`Pet.cpp:1060`, `:1434`, `:1442`). | No. IP only schedules its timer here. Spells are not loaded. |
| `OnPetAddToWorld` | `AddToWorld`, still before `_LoadSpells` (`Pet.cpp:118`, and IP's comment at `:1276`). | No. |
| `OnCalculateMaxTalentPointsForLevel` | Twice in the async callback: before `_LoadSpells`, and after it but before `InitLevelupSpellsForLevel` (`Pet.cpp:427`, `:436`, `:2242`). | It can observe the saved book. It does not run again after IP. It is not between the unlearn and the learn. |
| `CanUnlearnSpellSet` / `CanUnlearnSpellDefault` | Only from `InitLevelupSpellsForLevel`, and only when the entry's level is above the pet. | No. IP calls `pet->unlearnSpell` directly. Returning false does not stop a learn; it selects the learn branch. |
| `CanResetTalents` | `Pet::resetTalents` only. | No. |

`OnPlayerLearnSpell`, `OnPlayerCanLearnSpell`, and `OnPlayerForgotSpell` belong to `Player::learnSpell` / player unlearn (`Player.cpp:3428`, `:3443`). **VERIFIED** they are not on `Pet::learnSpell`. The `+600000` trainer spells are player spells; learning one does not call `checkHunterPetSpells`.

`UnitScript` in this tree exposes heal, damage, aura, combat, evade, shapeshift, display, and update hooks (`UnitScript.h`). `addSpell` casts a spell only when it is passive (`Pet.cpp:1872-1873`). An autocastable learn does not apply an aura, so `OnAuraApply` does not mark the autocast bit.

`m_spells` is a public member (`Pet.h:121`). Public visibility is not a hook. Nothing in `ScriptMgr` runs in the gap between `IndividualProgressionSpells.cpp:86` and `:90`. Those two calls are synchronous. `OnPlayerUpdate`, `OnUnitUpdate`, `OnPlayerSave`, and `OnPlayerBeforeLogout` can run later, on some other turn of the world loop. They are not ordered against the 200 ms event, they do not see the pre-unlearn byte at the moment it is discarded, and using them to call `ToggleAutocast` again is the guessed timer the assignment excludes. A save that lands before the event persists the pre-IP book; IP can then dirty it with no second hook until some later save.

**VERIFIED:** no module-owned synchronous hook is source-proven between the rank removal and the rank add. The two calls on lines 83-90 are synchronous. A later event is not that boundary.

## 4. Feasibility

S2, a default-off module that restores the preference, is not approved from these hooks. This branch adds no gameplay C++, no config key, and no SQL. S2 stays blocked pending CS01 and owner direction.

No safe module-owned synchronous hook is source-proven in the unlearn/relearn gap at either pinned core. An edit inside the existing lambda, so IP would copy `active` the way `Pet::addSpell` does, is one possible alternative. The module-only rule does not permit it, and the owner has not approved it. It is described here and was not applied:

1. Keep every current gate, including `isBotAccount`, `VanillaHunterPets`, hunter class, and the TBC tier-5 return.
2. On the `Pet*` already captured by the lambda, before the unlearn loop, look at listed ids the pet knows other than `keepId`.
3. If `keepId` is 0, keep today's removal. Do not learn a spell, and do not invent an OFF rank for an illegal family.
4. If the pet already knows `keepId` and no other listed id is known, do not call `ToggleAutocast`.
5. If exactly one other known id is the same rank chain as `keepId` (`SpellInfo::IsDifferentRankOf`) and both are `IsAutocastable()`, remember that spell's `active` byte and the bar slot index. Call `ToggleAutocast(old, false)` while the old spell is still known, so `m_autospells` drops the stale id that `removeSpell` leaves behind.
6. Then run the existing unlearn and the existing conditional learn.
7. If a new learn happened and a single chain state was captured, apply that byte to `keepId` only, on that same pet, then `PetSpellInitialize`. `ToggleAutocast(keep, true)` does write `ACT_ENABLED` when the id is not yet in `m_autospells` (`Pet.cpp:2260-2271`). `ToggleAutocast(keep, false)` does not write `ACT_DISABLED` unless that id is already in `m_autospells` (`Pet.cpp:2274-2285`). A rank `learnSpell` just added is not (`Pet.cpp:1889`). `CharmInfo::SetSpellAutocast` writes the bar type for that exact id (`CharmInfo.cpp:291-297`) and does not write `PetSpell.active`. So an edit that only calls `ToggleAutocast(keep, captured == ACT_ENABLED)` still gets OFF from the learn default. Explicit OFF has to be stored by writing the captured `ACT_DISABLED` byte on purpose. Matching the default by accident is not the preserve.
8. If more than one unrelated known id would have to donate a state, change nothing about autocast. Do not copy across families, across pets, or onto a rank the player has not trained.
9. Do not add another delay. Do not re-read `GetPet()` after a yield. A separate, still-upstream fix would make `DelayedPetSpellCheck` no-op when the current pet number is not the pet that queued the event.

That description is an IP edit. This module cannot place code inside that lambda, and this task does not. A synchronous module callback with the old spell, the new spell, and a call between `unlearnSpell` and `learnSpell` is not source-proven at either pinned SHA. Section 5 is a different idea: a later save/restore that does not sit in that gap. It is research, **FEASIBLE WITH CAVEATS**, and **NOT TESTED**. It is not S2.

Separately owner-gated alternatives, none of which this branch does:

- A log-only line inside the lambda, printing counts of `ACT_ENABLED` / `ACT_DISABLED` before and after, with no character, pet, or spell id. That can falsify the mechanism, and it is still an IP edit. A module counter on `OnCalculateMaxTalentPointsForLevel` can see only the pre-IP book.
- The existing read-only packet observer on draft #44, run by the owner on a restorable staging copy, comparing an explicit ON and an explicit OFF across summon and across a real legal-rank change. This research did not run it. **NOT TESTED.**
- Leave the preference unrestored until CS01 and the owner direct otherwise. An IP edit is not a required next step of this module. It remains one possible alternative, and only with separate owner approval.

What would falsify the synchronous-hook headline: a `ScriptMgr` call, at either pinned SHA, invoked from `Pet::unlearnSpell`, `Pet::learnSpell`, `Pet::addSpell`, `Pet::removeSpell`, or from the IP lambda, with the pet and both spell ids, before `learnSpell` returns. The citation set is the check. A new core commit that added that hook would reopen that question. `8daffda` does not add it (`PetScript.h` hash matches; `PETHOOK_END` is still the next enumerator). The section 5 save/restore does not falsify the headline. It runs later, on another event, and it was not executed.

## 5. Module-only save/restore alternative

Research only. Nothing in this section is implemented, and no C++ was added for it. The idea is the one in issue #48 comment 6289517104. It was checked against core `a66f1be`, core `8daffda` (`Pet.cpp` is byte-identical; the other cited lines were read at both SHAs where the file is not), and IP `4ff4b5f`. Where the note and the pins disagree, the pins win. Label: **FEASIBLE WITH CAVEATS** / **NOT TESTED**. S2 stays blocked pending CS01 and owner direction.

The idea is not a synchronous hook. It would snapshot autocast from `m_spells` before IP's delayed check, then after that check call `Pet::ToggleAutocast`, `CharmInfo::SetSpellAutocast`, and `owner->PetSpellInitialize()` only where the known rank changed. Explicit OFF has to be kept as rigorously as explicit ON. This write-up does not do that work.

### What the pins support

**VERIFIED.** `m_spells` and `m_autospells` are public (`Pet.h:121-122`). `Pet::isBeingLoaded()` returns `m_loading` (`Pet.h:65`). On the hunter load path, `_LoadSpells` runs inside the async callback (`Pet.cpp:435`) and passes `pet_spell.active` to `addSpell` as `PETSPELL_UNCHANGED` (`Pet.cpp:1567`). `LearnPetPassives`, `InitLevelupSpellsForLevel`, `CleanupActionBar`, and `PetSpellInitialize` all run before `m_loading = false` (`Pet.cpp:438-450`, `:496`). A snapshot taken once `!isBeingLoaded()` sees that post-cleanup book. It is not a raw unread of the column. `CleanupActionBar` can already have overwritten `active` from the bar (`Pet.cpp:2036`). That is the same bar-wins **POTENTIAL ISSUE** as section 1.

**VERIFIED.** `Pet::removeSpell` (`Pet.cpp:1976-2024`) does not mention `m_autospells` and does not assign `.active`. A `PETSPELL_NEW` row is erased (`:1985-1986`). Any other row, including a spell loaded as `PETSPELL_UNCHANGED`, is marked `PETSPELL_REMOVED` (`:1988`) and left in the map with the byte it already had. `Pet::HasSpell` treats that row as unknown (`Pet.cpp:2332-2335`). `addSpell`'s rank loop skips `PETSPELL_REMOVED` (`Pet.cpp:1842-1843`), so the following `learnSpell(keepId)` takes `ACT_DECIDE` and stores `ACT_DISABLED` for an autocastable spell (`Pet.cpp:1810-1813`). The old row's `.active` is still the pre-unlearn byte until a save. That is the REMOVED-entry fallback, for a DB-loaded rank. It is not there for a `PETSPELL_NEW` row, because that row is erased. The note's range `1976-2023` stops one line short of `return true` at `:2024`.

**VERIFIED.** `_SaveSpells` deletes every `pet_spell` row for the pet number, then erases each `PETSPELL_REMOVED` entry from `m_spells` and does not insert it (`Pet.cpp:1576-1591`). `SavePetToDB` returns immediately while `m_loading` (`Pet.cpp:510`). After the flag is clear, a save removes the fallback from memory and from the table. Whether a save runs between IP's check and a later restore is **NOT TESTED**. **POTENTIAL ISSUE:** that save wipes the REMOVED fallback.

**VERIFIED.** The player autocast opcode sets both stores: `Pet::ToggleAutocast(spellInfo, packet.AutocastEnabled)` and then `CharmInfo::SetSpellAutocast(spellInfo, packet.AutocastEnabled)` (`PetHandler.cpp:1003` and `:1007`). `ToggleAutocast` (`Pet.cpp:2247-2286`) returns without writing when the spell is missing or not autocastable. ON inserts the id and sets `ACT_ENABLED` only when the id is absent from `m_autospells` (`:2260-2271`). OFF erases the id and sets `ACT_DISABLED` only when the id is already present (`:2274-2285`). A second call with the same bool does not change `m_autospells` or `.active`. That part is idempotent. `SetSpellAutocast` (`CharmInfo.cpp:291-297`) sets the bar type for a slot whose action equals that exact spell id. It does not search by chain. `Player::PetSpellInitialize` (`Player.cpp:9760-9829`) sends the bar and every non-REMOVED spell's `active` byte (`:9793-9796`). `learnSpell` already calls it when `!m_loading` (`Pet.cpp:1909-1914`), so IP's learn has already sent the default OFF before a later call would send the book again. The functions themselves do not know whether the rank changed. Calling them when the known rank did not change is a separate requirement of the idea, not a property of `ToggleAutocast`.

**VERIFIED, and this corrects the note.** Those three calls do not preserve explicit OFF as rigorously as explicit ON. After the new rank is learned, its id is not in `m_autospells`, because `addSpell` calls `ToggleAutocast` with `active == ACT_ENABLED` (`Pet.cpp:1889`) and the false branch does nothing when the id is absent. `ToggleAutocast(newRank, false)` is then a no-op. It does not store `ACT_DISABLED`. The new row is OFF only because that is the `ACT_DECIDE` default (`Pet.cpp:1812-1813`), and the new bar type is OFF only because `AddSpellToActionBar` used that default (`CharmInfo.cpp:183`). `SetSpellAutocast(newRank, false)` writes the bar again when the id is on the bar. The note's snapshot shape, `{chain first rank -> ACT_ENABLED?}`, is a bool. Applied through `ToggleAutocast`, ON becomes a real `ACT_ENABLED` write and OFF becomes the no-op. A rigorous OFF preserve stores the active byte (`ACT_ENABLED` `0xC1` or `ACT_DISABLED` `0x81`) and writes `ACT_DISABLED` on purpose. Chain identity for that key is `SpellInfo::GetFirstRankSpell` / `SpellMgr::GetFirstSpellInChain` (`CharmInfo.cpp:154`, `:164`). Whether each IP wipe list is one DBC chain is still **UNKNOWN**. **NOT TESTED** in game for ON or for OFF.

**VERIFIED.** `ToggleAutocast(newRank, true)` searches `m_autospells` for the new id only (`Pet.cpp:2258`). It does not remove the old id, and `removeSpell` did not either. Stale old-rank ids remain. That is existing core behaviour. **POTENTIAL ISSUE** for a restore, the same leftover IP already leaves. `PetAI` walks that list (`PetAI.cpp:247`). Whether it casts the stale id is **NOT TESTED**.

**VERIFIED.** `EventProcessor` keeps events in a `std::multimap` keyed by exec time (`EventProcessor.h:93`). `Update` adds `p_time` to `m_time` and then always takes `begin()` while that key is due (`EventProcessor.cpp:43-50`). `CalculateTime(offset)` is `m_time + offset` (`:161`). Equal keys stay in insertion order. Once both events are queued, the smaller timestamp runs first, including when one world tick makes both due. That is an ordering fact about the processor. It is not a proof that a module offset of 100 ms runs before IP.

### Timing claims that do not hold as stated

The note queues one owner-GUID event from the same two hooks, snapshots at `100+200k` ms once `!isBeingLoaded()`, and says that lands before IP's `200+200k` tick because events run in time order. It then restores at least 150 ms after IP, only when the known rank changed, and reads `.active` from the REMOVED row if it is still there.

**POTENTIAL ISSUE: dependence on IP's private 200 ms cadence and `PendingPetSpellCheck`.** The offset and the flag are private to IP. The class is local to `IndividualProgressionSpells.cpp:1252` and is fetched at `:1278`. It is not in `IndividualProgression.h`, so `DataMap::Get` cannot return it to this module. IP's second hook returns only because that flag is already set (`:1278-1280`). A module that hooks both without its own guard queues two events. The `100+200k` formula also needs the module and IP to share a retry count. They do not. The module cannot see IP's `_attempts`.

**POTENTIAL ISSUE: this pet's update does not poll while the load flag is set.** The call chain is the still-loading note in section 2. `m_time` does not move while `EventProcessor::Update` is not called (`EventProcessor.cpp:43`). The note's picture of a sample every 200 ms during `isBeingLoaded()` is not what `Pet::Update` does. **UNKNOWN** whether another caller pumps `pet->m_Events` inside the async callback. **NOT TESTED.**

**POTENTIAL ISSUE: a 10-try give-up leaves no saved byte to restore.** If a fire does happen while the flag is still true, IP stops after ten attempts and runs the check anyway (`IndividualProgressionSpells.cpp:1330-1342`). `_LoadSpells` is earlier in the same callback that clears the flag (`Pet.cpp:435`, `:496`), so a module that also stops has not seen the `pet_spell` book. The note says the snapshot is then empty and the restore does nothing. Doing nothing is the proposed fail-closed choice. An empty map was **NOT TESTED**. This is the same still-loading note as section 2, kept separate from the owner-GUID note, and still pending observation.

**POTENTIAL ISSUE: a pet save between IP and the restore wipes the REMOVED fallback.** `_SaveSpells` does that (`Pet.cpp:1588-1591`). **NOT TESTED** that a save falls in the gap. The in-memory snapshot taken before IP, if it was actually taken, would not depend on that row. The fallback does.

**POTENTIAL ISSUE: stale old-rank ids in `m_autospells`.** Cited above. The named restore does not clear them.

**UNKNOWN: hook registration order between IP and this module.** These pins do not fix the order `ScriptMgr` uses across two loaded modules. Two different `CalculateTime` offsets taken from the same `m_time` are ordered by the timestamps, not by which `OnInitStatsForLevel` ran first. Registration order still decides equal timestamps, and it is **UNKNOWN** whether both modules read the same `m_time`. Nothing here proves the processor is idle between `Pet.cpp:332` and `Pet.cpp:410`. The note's sentence that the snapshot "lands before" IP is not source-proven. **NOT TESTED.**

The note's optional cache is `OnPacketReceive` of `CMSG_PET_SPELL_AUTOCAST`. **Correction:** no pinned `PetScript` or `PlayerScript` hook has that name. The nearest receive hook is `ServerScript::CanPacketReceive(WorldSession*, WorldPacket const&)` (`ServerScript.h:75` at both cores). The handler that reaches the two autocast writes is `WorldSession::HandlePetSpellAutocastOpcode` (`PetHandler.cpp:955`). Whether `CanPacketReceive` observes that packet, and whether a module could cache explicit ON and explicit OFF from it, is **UNKNOWN** and **NOT TESTED**. A module SQL table was correctly left out. It would be owner-gated, and this research does not add one.

### Verdict

**FEASIBLE WITH CAVEATS. NOT TESTED.** The public spell map, the REMOVED row of a DB-loaded rank, and `ToggleAutocast(true)` are real core surfaces. A module could call them without editing IP. They do not run between the unlearn and the learn. They depend on IP's private timer. The named OFF call does not write `ACT_DISABLED`. Explicit OFF has to be preserved as rigorously as explicit ON, and this alternative does not yet show a source path that does so. This is research, not an implementation. S2 stays blocked pending CS01 and owner direction. No gameplay C++, no SQL, and no IP edit follows from this section.

## 6. Base branch

Workflows on `main` at `1f5f317c3991bbac66cc92a7112bbde3c929c232` were searched for `actions/upload-artifact` and `actions/upload`. There are no matches. The draft PR therefore targets `main`. The workflow added here has `contents: read` and does not upload artifacts.

## 7. Local test run

On 2026-10-20, before this branch was pushed:

```text
python3 -m unittest tests/test_a02_s1_hunter_pet_autocast.py -v
python3 scripts/a02_s1_hunter_pet_autocast.py
```

The first push of this branch, at `a029496eb8a9548375a513c3b33163ba563c058a`, reported 18 unit tests (17 ok, 1 skipped without pinned checkouts) and `citations 79 OK`. This docs revision was run the same way on 2026-10-20 before it was pushed: 25 unit tests, 24 ok, 1 skipped without pinned checkouts, and the citation script against raw GitHub reported `citations 129 OK` with the same 26 / 89 / 22 family counts. Those runs pin the lines. They are **NOT TESTED** as gameplay. The workflow on the new head is the run that applies to this text.

## 8. Limits

- **NOT TESTED:** worldserver, client, summon, logout, stable swap, talent purchase, any real `pet_spell` row, and the section 5 save/restore.
- **UNKNOWN:** which listed ids are autocastable in Spell.dbc, whether each wipe list is one `spell_chain`, the owner's bot-account names, and the `ScriptMgr` order between IP and this module.
- **POTENTIAL ISSUE (owner GUID):** the delayed event looks up `GetPet()` by owner. Pending observation. Separate from the still-loading note, and not the ON-to-default-OFF mechanism.
- **POTENTIAL ISSUE (still loading, 10 tries of 200 ms):** the retry and the give-up are in IP's event. Pending observation. Separate from the owner-GUID note. On the ordinary `Pet::Update` path the processor does not run while `m_loading` is set.
- **POTENTIAL ISSUE:** stale `m_autospells` ids, bar-versus-`pet_spell` divergence, Dash's incomplete id list, and bot accounts outside the configured `IndividualProgression.BotAccountsRegex` (the default text is `^RNDBOT.*`; the exclusion must not hardcode it and must not treat all Playerbots as equivalent).
- **FEASIBLE WITH CAVEATS / NOT TESTED:** the section 5 save/restore. Research only. S2 stays blocked pending CS01 and owner direction.
- Source tests and this write-up do not show that a player has lost autocast on the live server. They show that the pinned IP function throws away the byte core would have copied, and that no module-owned synchronous hook is source-proven in that gap.
