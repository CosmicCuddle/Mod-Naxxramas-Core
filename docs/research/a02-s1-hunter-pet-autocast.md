# A02 S1 — Human Hunter pet autocast persistence

Research only. This document does not implement a fix, does not change Individual Progression, AzerothCore, or Playerbots, and is not an owner decision.

**Headline: NO SAFE MODULE HOOK.** An upstream IP change is indispensable for an atomic preserve of the player's explicit autocast choice. No S2 module code is included.

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

`isBotAccount` is `std::regex_match` of the account name against `IndividualProgression.BotAccountsRegex`, default `^RNDBOT.*` (`IndividualProgression.cpp:351-360`, `:1070`). It is not a Playerbots API call. **VERIFIED** as the gate. **UNKNOWN** whether every non-human account on the owner's server matches that regex. Accounts that do not match are treated as human and are reconciled.

The only caller is `DelayedPetSpellCheck::Execute` (`IndividualProgressionSpells.cpp:1341`). IP's `PetScript` schedules that event from `OnPetAddToWorld` and `OnInitStatsForLevel` (`:1292-1309`), 200 ms out (`:1284-1286`), and its own comment says those hooks run before the async spell load (`:1276`). The event stores the owner GUID, not the pet (`:1315`). On fire it reads `player->GetPet()` again (`:1324`). While `isBeingLoaded()` and the attempt count is below 10, it requeues another 200 ms event (`:1328-1336`). It clears the pending flag before the hunter call (`:1339-1342`), including when the attempt cap is reached and the pet is still loading.

**VERIFIED:** the normal success path runs only after `m_loading` is false, because the retry waits for that. **POTENTIAL ISSUE:** after 10 attempts (about two seconds) it calls `checkHunterPetSpells` even if loading is still true. That race was not executed. If it won, `addSpell` of a saved higher rank can then copy `active` from the rank IP just defaulted to OFF (`Pet.cpp:1855` overwrites the loaded byte). **NOT TESTED.**

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

The delayed event does not close over that `Pet*`. It looks the current pet up again by owner. **POTENTIAL ISSUE** if the event runs on one pet object while `GetPet()` is another. Normal summon refuses to load a second pet while one exists (`Pet.cpp:237`), so the overlap is not the ordinary dismiss-then-summon path. It was **NOT TESTED**.

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

`TogglePetSpellAutoCastAction::Execute` (`PetsAction.cpp:342-395`) walks every known autocastable pet spell, skips a hard-coded denylist (Prowl, one Cower id, Leap, Spell Lock, Devour Magic, Spirit Wolf Leap), and calls `Pet::ToggleAutocast` when the bot policy disagrees. It does not call `SetSpellAutocast`. IP already returns before the lambda for accounts matching the bot regex, so this research's conclusion does not require a Playerbots change. A module that toggled pets of those accounts would fight this action. Non-matching bot accounts are not protected by the regex. **POTENTIAL ISSUE** for oddly named bot accounts. **NOT TESTED** against the owner's account list.

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

**VERIFIED:** no module-usable hook fires atomically between the rank removal and the rank add. **NO SAFE MODULE HOOK.**

## 4. Feasibility

S2, a default-off module that restores the preference, is not available from these hooks. This branch adds no gameplay C++, no config key, and no SQL.

An upstream change inside the existing lambda is the change that would make IP behave like `Pet::addSpell`'s rank copy. It is described here and was not applied:

1. Keep every current gate, including `isBotAccount`, `VanillaHunterPets`, hunter class, and the TBC tier-5 return.
2. On the `Pet*` already captured by the lambda, before the unlearn loop, look at listed ids the pet knows other than `keepId`.
3. If `keepId` is 0, keep today's removal. Do not learn a spell, and do not invent an OFF rank for an illegal family.
4. If the pet already knows `keepId` and no other listed id is known, do not call `ToggleAutocast`.
5. If exactly one other known id is the same rank chain as `keepId` (`SpellInfo::IsDifferentRankOf`) and both are `IsAutocastable()`, remember that spell's `active` byte and the bar slot index. Call `ToggleAutocast(old, false)` while the old spell is still known, so `m_autospells` drops the stale id that `removeSpell` leaves behind.
6. Then run the existing unlearn and the existing conditional learn.
7. If a new learn happened and a single chain state was captured, apply that byte to `keepId` only, on that same pet: `ToggleAutocast(keep, captured == ACT_ENABLED)` and `CharmInfo::SetSpellAutocast` for the same bool, then `PetSpellInitialize`. `ACT_DISABLED` must be applied on purpose. Matching the default by accident is not the preserve.
8. If more than one unrelated known id would have to donate a state, change nothing about autocast. Do not copy across families, across pets, or onto a rank the player has not trained.
9. Do not add another delay. Do not re-read `GetPet()` after a yield. A separate, still-upstream fix would make `DelayedPetSpellCheck` no-op when the current pet number is not the pet that queued the event.

That is an IP edit. This module cannot place code inside that lambda. A core hook with the old spell, the new spell, and a synchronous callback between `unlearnSpell` and `learnSpell` does not exist at either pinned SHA, so a module-only S2 would be inventing the hook.

Owner-gated alternatives, none of which this branch does:

- A log-only line inside the lambda, printing counts of `ACT_ENABLED` / `ACT_DISABLED` before and after, with no character, pet, or spell id. That is the smallest instrument that can falsify the mechanism, and it is still an IP edit. A module counter on `OnCalculateMaxTalentPointsForLevel` can see only the pre-IP book.
- The existing read-only packet observer on draft #44, run by the owner on a restorable staging copy, comparing an explicit ON and an explicit OFF across summon and across a real legal-rank change. This research did not run it. **NOT TESTED.**
- Doing nothing until the owner accepts an IP change. That is the source-safe module position.

What would falsify the headline: a `ScriptMgr` call, at either pinned SHA, invoked from `Pet::unlearnSpell`, `Pet::learnSpell`, `Pet::addSpell`, `Pet::removeSpell`, or from the IP lambda, with the pet and both spell ids, before `learnSpell` returns. The citation set is the check. A new core commit that added that hook would reopen S2. `8daffda` does not add it (`PetScript.h` hash matches; `PETHOOK_END` is still the next enumerator).

## 5. Base branch

Workflows on `main` at `1f5f317c3991bbac66cc92a7112bbde3c929c232` were searched for `actions/upload-artifact` and `actions/upload`. There are no matches. The draft PR therefore targets `main`. The workflow added here has `contents: read` and does not upload artifacts.

## 6. Local test run

On 2026-10-20, before this branch was pushed:

```text
python3 -m unittest tests/test_a02_s1_hunter_pet_autocast.py -v
python3 scripts/a02_s1_hunter_pet_autocast.py
```

The unit run was 18 tests, 17 ok, 1 skipped when the pinned checkouts were not in the environment. A second unit run with `A02_CORE_OLD`, `A02_CORE_NEW`, `A02_IP`, and `A02_PLAYERBOTS` pointing at the four pinned checkouts included the citation test and passed. The citation script, fetching raw GitHub rather than the local trees, reported `citations 79 OK` and the 26 / 89 / 22 family counts. That script run is **VERIFIED** for the line pins. It is **NOT TESTED** as gameplay.

## 7. Limits

- **NOT TESTED:** worldserver, client, summon, logout, stable swap, talent purchase, and any real `pet_spell` row.
- **UNKNOWN:** which listed ids are autocastable in Spell.dbc, whether each wipe list is one `spell_chain`, and the owner's bot-account names.
- **POTENTIAL ISSUE:** stale `m_autospells` ids, bar-versus-`pet_spell` divergence, the 10-attempt early check, the owner-GUID event, Dash's incomplete id list, and bot accounts outside `^RNDBOT.*`.
- Source tests and this write-up do not show that a player has lost autocast on the live server. They show that the pinned IP function throws away the byte core would have copied, and that no module hook can catch it.
