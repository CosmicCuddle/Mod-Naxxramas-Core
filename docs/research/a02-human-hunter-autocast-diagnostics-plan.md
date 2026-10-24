# A02 diagnostics plan — human Hunter pet autocast (read-only)

**Status:** documentation of a later, owner-authorized capture. No C++, no SQL file, no DBC, no config, no workflow, and no edit to AzerothCore, Individual Progression, Playerbots, or the integration branch. Nothing here was run on a worldserver, a client, or a characters database. This note does not authorize those captures and does not implement the observer from [PR #103](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/103).

**Author:** CosmicScript02. **Requested by:** CosmicScript01 in [#48 comment 6385255481](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6385255481), after the S1 scoped pass on [#121 comment 6384977431](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/121#issuecomment-6384977431). **Parent trace:** [`docs/research/a02-human-hunter-autocast-s1.md`](a02-human-hunter-autocast-s1.md) at `528af648c0fd5988b5919ea0eec305c2346d69c5`. **Bite/Claw question:** [PR #103](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/103), head `ec73fc77b33e185e46e7684a03a3cecd7bad770c`. [#69](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/69) stays blocked. Do not revive that cache and do not apply `docs/install/manual_hunter_pet_autocast_cache.sql`.

## Labels

| Label | Meaning in this note |
| --- | --- |
| VERIFIED | Read at the pinned SHA and cited `file:line`. |
| VERIFIED preserved | The cited path does not write a new autocast byte for that spell. This is not an in-game pass. |
| POTENTIAL ISSUE | The cited source can remove or replace the spell. It is not proven that a real character hits that branch. |
| UNKNOWN | Not determined from the pinned source. |
| NOT TESTED | No worldserver, no client, no characters DB, no summon, relog, dismiss, stable click, or level-up. |

A label is not a gameplay result. In-game behaviour is NOT TESTED.

## Pins re-read for this plan

| Role | Repository | Full SHA |
| --- | --- | --- |
| Grimfeather AzerothCore | `Grimfeather/azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| Grimfeather IP | `Grimfeather/mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` |
| Playerbots | `mod-playerbots/mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |

Playerbots was not re-walked. The S1 note already records its `ToggleAutocast` writer, including forced OFF for spell 1742. A bot is not a subject of the matrix below. Leave that code alone.

`ActiveStates` at core `src/server/game/Entities/Unit/CharmInfo.h:59-66`: `ACT_PASSIVE = 0x01` (decimal 1), `ACT_DISABLED = 0x81` (decimal 129), `ACT_ENABLED = 0xC1` (decimal 193), `ACT_DECIDE = 0x00`. Explicit OFF means the player path stored `ACT_DISABLED`. Explicit ON means `ACT_ENABLED`. `PetSpellState` at `src/server/game/Entities/Pet/PetDefines.h:56-62`: `PETSPELL_REMOVED = 3`. That state is memory only. `_SaveSpells` does not write it.

## 1. What a later capture is allowed to look at

Three stores already exist. This note does not query them.

| Asked name | What the pin actually has | Citation |
| --- | --- | --- |
| `character_pet_spell` / `character_pet_spells` | No statement in `CharacterDatabase.cpp` uses that name. A failed lookup of that name is not a spell removal. | VERIFIED absent. The pet spell statements are the rows below. |
| Pet spell row | `pet_spell` columns `guid`, `spell`, `active`. `guid` is the pet number, not the player guid. | `CHAR_SEL_PET_SPELL` `CharacterDatabase.cpp:575`; insert ` :581`; delete-all ` :578`. |
| Pet bar | `character_pet.abdata`, one string of `type action` pairs for action-bar indexes 0 through 9 (20 tokens). | `CHAR_REP_CHAR_PET` `CharacterDatabase.cpp:590`; writer `Pet::GenerateActionBarData` `Pet.cpp:2541-2551`; token-count check `CharmInfo.cpp:253-254`. |
| Which Bite/Claw dummy the hunter owns | IP calls `player->HasSpell` on the dummy id (`IndividualProgressionSpells.cpp:96`). Those ids are player spells. The existing player-spell read is `character_spell` (`spell`, `specMask`) at `CharacterDatabase.cpp:78`. | `Player::HasSpell` itself was not opened. If a `character_spell` row and the client spellbook disagree, the `HasSpell` result is UNKNOWN. |

`abdata` type is the decimal `ActiveStates` value. A cleared chain slot from `RemoveSpellFromActionBar` is type `129` and action `0` (`CharmInfo.cpp:221`). A later load that still finds a spell id the pet no longer knows sets that slot to type `1` and action `0` (`Pet::CleanupActionBar` `Pet.cpp:2033-2034`).

### When a row is the post-check row

`checkHunterPetSpells` does not call `SavePetToDB`. `Pet::ToggleAutocast` does not either. `SavePetToDB` returns immediately while `m_loading` (`Pet.cpp:510`). A read taken before the next successful save still shows the previous save. That mismatch is the expected lag, not a falsifier.

| Action | What it saves, and when IP runs | Citation |
| --- | --- | --- |
| Manual autocast click | No save. Memory and the client bar change. The row changes on the next successful save. | `HandlePetSetAction` `PetHandler.cpp:801`, `:819`, `:834`. `HandlePetSpellAutocastOpcode` `PetHandler.cpp:1003`. Neither function calls `SavePetToDB`. |
| Dismiss | Saves the pet that is still out, then unsummons it. That save is the pre-load state. | `Spell::EffectDismissPet` `SpellEffects.cpp:4773-4784` calls `Remove(PET_SAVE_NOT_IN_SLOT)`. `Player::RemovePet` saves at `Player.cpp:9367`. |
| Call Pet while that pet is already out | No load, no spell write, no IP pass. The live pet is moved near the player. | `Spell::EffectSummonPet` `SpellEffects.cpp:3406-3441`. |
| Call Pet when nothing is out | Loads the current or unslotted hunter pet, which schedules IP. On success the pet object is added inside `LoadPetFromDB`, and `SummonPet` then returns null (`Player.cpp:9212`). A failed load with entry 0 also returns null (`:9216-9219`). The client pet frame, not that return value, shows which one happened. | `SpellEffects.cpp:3452` passes `SUMMON_PET`. `Player.cpp:9186`. `GetLoadPetInfo` for entry 0 is `Pet.cpp:203-210`. `Pet::LoadPetFromDB` sets `m_loading` at `:218`, calls `InitStatsForLevel` at `:332`, and `map->AddToMap` at `:410`. |
| Logout / relog | Logout save writes whatever memory is current (`PlayerStorage.cpp:7303-7305`). Login loads that pet (`CharacterHandler.cpp:1103`, `Player::LoadPet` `PlayerStorage.cpp:6388-6395`) and the load schedules IP again. | A row read while the character is offline, before the next login, is the logout save only. |
| Stable swap | The pet put away is saved by `RemovePet` before the other pet loads. IP does not run on a despawned pet. The pet taken out is a different pet number and does get the load path. | `HandleStableSwapPet` `NPCHandler.cpp:646-757`, `RemovePet` at `:703`, `LoadPetFromDB` at `:731`. Slot swap of that pet number is `Pet.cpp:375-387`. |
| Pet level-up | No save in `GivePetLevel`. Native level-up spells run immediately. IP is scheduled from `InitStatsForLevel` and runs about 200 ms later, longer if the pet is still loading. | `Pet.cpp:948-961`. Scheduler `IndividualProgressionSpells.cpp:1304-1306` and `:1348-1362`. |

The IP event is queued from `OnPetAddToWorld` (`:1312-1317`) and `OnInitStatsForLevel` (`:1320-1329`). A per-pet flag stops the second of those two hooks from queueing a second event (`:1296-1300`). The body calls `checkHunterPetSpells` once the pet is not loading, or after 10 attempts (`:1350-1362`). On the normal load path `_LoadSpells`, `InitLevelupSpellsForLevel`, and `CleanupActionBar` run in the async callback (`Pet.cpp:435-446`) and `m_loading` becomes false at `:496`, before that IP body.

**Read rule.** For a resummon, the dismiss save is too early. Log out, or dismiss again, only after the pet has been back out long enough for the delayed check, and read that later save. For a pure toggle, log out without an intervening load and read while offline. Login, wait, log out, and read again for the post-IP save. Two reads are required wherever the question is "toggle, or removal."

### What the server log can and cannot show

VERIFIED: the success path of `checkHunterPetSpells`, `Pet::learnSpell`, `Pet::unlearnSpell`, `Pet::removeSpell`, and `Pet::ToggleAutocast` has no `LOG_*` line that names the spell id or the autocast byte. The unlearn packet in `unlearnSpell` is commented out (`Pet.cpp:1963-1968`). `learnSpell` sends `PetLearnedSpell` and `PetSpellInitialize` only when `!m_loading` (`Pet.cpp:1909-1914`). `removeSpell` sends `PetSpellInitialize` when the bar clear runs and `!m_loading` (`Pet.cpp:2015-2020`).

Lines that do exist, and do not settle the three questions:

- `HandlePetSetAction` logs `LOG_DEBUG("network.opcode", "HandlePetSetAction. CMSG_PET_SET_ACTION")` (`PetHandler.cpp:698`). No spell id. Whether that logger is enabled on a live server is UNKNOWN.
- `Player::RemovePet` logs entry, save mode, and the reagent flag (`Player.cpp:9314`). No spell id.
- The load callback logs `LOG_DEBUG("entities.pet", "New Pet has {}")` with the GUID (`Pet.cpp:448`). No spell id.
- The IP comment at `IndividualProgressionSpells.cpp:1296-1297` mentions doubled unlearn/learn chat messages as the reason for the pending flag. Those functions do not `LOG_` that text. The client string is UNKNOWN. NOT TESTED.

Silence is not proof the branch ran. A line that names spell 1742 or a Bite/Claw id is outside the functions above until the line is quoted and identified. The #103 observer, which would log spell id, `active`, spell state, bar type, and `isBeingLoaded`, is not implemented here and must not `SELECT` these tables. A later owner-authorized read of the rows is a person reading them, not a module query.

## 2. How the three questions differ in source

### (a) Growl manual OFF — VERIFIED preserved, NOT TESTED

`checkHunterPetSpells` contains no Growl string and passes no Growl id to `unlearnSpell` or `learnSpell`. VERIFIED by reading `IndividualProgressionSpells.cpp` at `dd96f2b`. No Growl spell id is claimed. DBC was not opened. The capture records whichever spell id is on the Growl button and in `pet_spell` before the action. That id is UNKNOWN until then.

If that id is already known and not `PETSPELL_REMOVED`, `Pet::addSpell` returns false and does not change `active` (`Pet.cpp:1800-1803`). If core `InitLevelupSpellsForLevel` (`Pet.cpp:1920-1934`) learns a higher rank of a spell still in `m_spells`, `addSpell` copies `active`, including `ACT_DISABLED` (`Pet.cpp:1850-1860`). An accepted OFF click stores `ACT_DISABLED` only when the id was in `m_autospells` (`Pet.cpp:2274-2284`) and sets the bar when the bar action is that spell (`PetHandler.cpp:815-819` and `:834`, or `SetSpellAutocast` `CharmInfo.cpp:291-300`).

### (b) Cower 1742 — removal, not a toggle — POTENTIAL ISSUE, NOT TESTED

A toggle leaves the spell id in the book. `ToggleAutocast(false)` sets `active = ACT_DISABLED` and does not remove the id (`Pet.cpp:2274-2284`). The row after a later save still has that `spell` value.

The live Cower call is not a toggle. Serpent, Moth, Chimaera, and Silithid call `reconcile({ 1742 }, {})` at `IndividualProgressionSpells.cpp:445`, `:453`, `:460`, and `:467`. `keepId` stays 0 because the dummy list is empty (`:93-100`). If `pet->HasSpell(1742)` (`:105`, and `HasSpell` is false for `PETSPELL_REMOVED` at `Pet.cpp:2332-2335`), the call is `unlearnSpell(1742, false, true)` (`:106`). `learnSpell` is not called (`:109-110`). `removeSpell` marks a loaded spell `PETSPELL_REMOVED` (`Pet.cpp:1985-1988`). Because `clear_ab` is true and `learn_prev` is false, `RemoveSpellFromActionBar` sets the matching chain slot to action `0`, type `ACT_DISABLED` (`Pet.cpp:2012-2013`, `CharmInfo.cpp:211-224`). `_SaveSpells` then skips `PETSPELL_REMOVED` and does not insert 1742 (`Pet.cpp:1588-1592`).

After the save that follows that pass, the removal signature is: no `pet_spell` row for 1742, and the client no longer has a 1742 button. A row that remains, with `active` changed from 193 to 129, is a toggle. That result falsifies removal for that pet. Higher ids in the commented list (`1753`, `1754`, `1755`, `1756`, `16697`, `27048` at `:129`) are not in the live wipe list. Whether those ids share a DBC chain with 1742 was not read. UNKNOWN. The row for 1742 does not depend on that chain. The bar slot does.

Wolf and the other families whose `// Cower` line is a comment do not call this unlearn. Wolf's comment is `:128-129`. Cat's is `:145-146`. VERIFIED: those lines do not unlearn. A Wolf that loses 1742 falsifies "only the four live calls."

`reconcile` runs only if the gates at `:58-68` pass: player in world, `VanillaHunterPets`, the account-name bot test is false, class hunter, and `hasPassedProgression(..., PROGRESSION_TBC_TIER_5)` is false. The family test is `familyEntry->Name[0]` compared with the English literal, including `"Serpent"` (`:89-90`, `:440`). Installed config, the account regex, the character's progression, and whether DBC index 0 is that English string were not read. UNKNOWN. A no-change result while a gate fails does not confirm preservation.

### (c) Bite/Claw rank overwrite — mechanism VERIFIED, who hits it UNKNOWN, NOT TESTED

This is the open question from PR #103 head `ec73fc7`. Two different `reconcile` shapes are easy to misread as one.

`keepId` is the highest dummy id in the second list that `player->HasSpell` owns, minus 600000. The loop walks that list backwards (`IndividualProgressionSpells.cpp:94-100`). Every other id in the first list that the pet knows is unlearned with `clear_ab` true (`:103-106`). If `keepId` is non-zero and the pet does not know it, `learnSpell(keepId)` (`:109-110`). `learnSpell` stores `ACT_DISABLED` for a new autocastable spell (`Pet.cpp:1810-1813`). The old rank is already `PETSPELL_REMOVED`, so the native copy at `Pet.cpp:1855` does not see it (`:1841-1843`). Explicit ON on the old rank therefore becomes OFF on `keepId`. Explicit OFF stays numerically OFF because that is the learn default. The old OFF byte is not copied. A later row of `active = 129` cannot tell those two histories apart.

If the pet already knows only `keepId`, the unlearn loop skips that id and `learnSpell` is not called. Both ON and OFF stay as saved. VERIFIED for that code. Whether any real hunter is in that state is UNKNOWN.

**Use these calls for the overwrite question:**

- Wolf Bite, non-empty dummy list, `:117`. Wipe ids `17253, 17255, 17256, 17257, 17258, 17259, 17260, 17261, 27050`. Dummies `617253, 617255, 617256, 617257, 617258, 617259, 617260, 617261, 627050`. The last dummy is tested first. Examples of the subtraction at `:98`: `627050 - 600000 = 27050`, `617253 - 600000 = 17253`. If the hunter knows none of those dummies, `keepId` stays 0 and every known wipe id is removed with no replacement. That is removal, not the #103 overwrite.
- Cat Claw, non-empty dummy list, `:137`. Same wipe ids as Wolf Claw. The dummy list at that line starts at `616827` and ends at `627049`. Example of the subtraction at `:98`: `627049 - 600000 = 27049`, `616827 - 600000 = 16827`. Same empty-dummy warning if the hunter knows none of those dummies.

**Do not use these calls as the overwrite question.** An empty dummy list never learns:

- Wolf Claw `:120` unlearns every listed Claw rank and learns nothing. POTENTIAL ISSUE, same shape as Cower 1742, for the whole list. NOT TESTED.
- Serpent Bite `:442` and Chimaera Bite `:457` are the same empty-dummy removal of the Bite list. Silithid Claw `:464` is the same for Claw.

Level-up can show both mechanisms in one action. `GivePetLevel` calls `InitStatsForLevel` and then `InitLevelupSpellsForLevel` (`Pet.cpp:959-960`). The native learn copies `active` if the new rank is higher than a rank still in `m_spells` (`:1855`). About 200 ms later, IP can unlearn that rank and `learnSpell(keepId)` as `ACT_DISABLED` when `keepId` is a different id. One client glance cannot separate those two moments. NOT TESTED which frame a client shows.

## 3. Shared setup for every case

Record these before the action. If one of them fails, the IP expectation is "no spell change," and that result does not answer the question.

- One human hunter. Not a Playerbot, and the account name must not take the return at `IndividualProgressionSpells.cpp:61-62`. The installed regex was not read. UNKNOWN.
- IP enabled, and `VanillaHunterPets` true, or the case is the negative case. Source default of that flag was not re-opened here. Installed value UNKNOWN.
- The character has not passed `PROGRESSION_TBC_TIER_5` (`:67-68`), unless the case is that negative.
- The pet is already that hunter's hunter pet, and `CreatureFamilyEntry::Name[0]` is the family string named in the case. The DBC string was not read. UNKNOWN. Record creature entry and family id so a later reader can check the string.
- Baseline: the manual toggle is done, then a save completes, and `pet_spell.active` and the parsed `abdata` type for that spell id are the same byte. The toggle opcodes do not save. A crash before the baseline save can drop an in-memory OFF. UNKNOWN how often. Do not start a case from a mismatched pair.
- Do not apply #69 SQL. Do not add a module. Do not call `ToggleAutocast` from a module.

Client capture for every case: the pet action bar, whether the spell button is present, and whether the autocast glow is on or off. Row capture: `pet_spell.spell` and `pet_spell.active` for that pet number, plus `character_pet.abdata`, read at the time the case names. Log capture: the worldserver log from a few seconds before the action until the post-check save. Expected log from the cited functions: no spell-id line. Quote anything that does name the id.

## 4. Observed-input matrix

Decimal `129` is `ACT_DISABLED`. Decimal `193` is `ACT_ENABLED`. "Post-check save" means a logout or a later dismiss after the pet has been out through the delayed IP pass, not the dismiss that started a resummon.

### Growl — manual OFF

The Growl id is whatever baseline `pet_spell` row and bar button the player treats as Growl. Family for these rows is Wolf, so the commented Cower line cannot remove 1742 in the same pass.

| Case | Setup | Action | Expected after the stated read | Label | What would falsify it |
| --- | --- | --- | --- | --- | --- |
| G1 | Wolf. Growl id known. Manual OFF. Baseline row `active` 129 and `abdata` type 129, action = that id. | Dismiss, then Call Pet with the pet not already out. Wait until the pet is back. Log out and read the new save. | Same spell id. `active` 129. Bar button present, glow off. `abdata` type 129 and action = that id. IP never names the id (`checkHunterPetSpells` has no Growl string). An already-known rank is left alone (`Pet.cpp:1800-1803`). | VERIFIED preserved in source. NOT TESTED. | That id is absent, or `active` is 193, or the glow is on, while the gates in section 2 held and the baseline pair was 129/129. A read of the dismiss save, before the post-check logout, still showing 129 does not count either way. |
| G2 | Same baseline. | Log out, read while offline, log in, wait, log out, read again. | Both reads: same id, `active` 129, glow off. The login load schedules IP (`CharacterHandler.cpp:1103`, `Pet.cpp:332`) and that pass still does not name Growl. | VERIFIED preserved in source. NOT TESTED. | The second read drops the id or stores 193. The first read is the toggle/save only (`PlayerStorage.cpp:7303-7305`). |
| G3 | Two pets. This Wolf is the one with Growl OFF at 129. The other pet is a different pet number. | Stable-swap this Wolf away. Read both pet numbers. Later swap this Wolf back out, wait, then take the post-check save. | While stabled, this pet number keeps the saved 129. IP does not run on it despawned (`NPCHandler.cpp:703` saves, then `:731` loads the other number). After it is loaded again, G1's expectation applies to this number only. | VERIFIED preserved in source. NOT TESTED. | This pet number's Growl id changes while it stayed despawned, or the two numbers share rows. They do not (`CharacterDatabase.cpp:575`). |
| G4 | Same Wolf, Growl OFF at 129, pet stays out. | Give the pet a level. Look at the bar immediately, and again after more than a second. Read `pet_spell` only after a later logout. | `GivePetLevel` does not save (`Pet.cpp:948-961`). If core teaches a higher rank, that rank's `active` is the copied 129 (`Pet.cpp:1855`). IP still does not name Growl. The post-check save has the new id at 129 if a rank-up happened, otherwise the old id at 129. | VERIFIED preserved in source for the copy and for IP's silence. Which rank a level-up row contains is UNKNOWN. NOT TESTED. | The rank present after the second look has `active` 193 when the pre-level rank was 129, or the id vanishes with no higher rank stored at 129. |
| G5 | Same baseline, pet already out. | Press Call Pet. Do not dismiss. | No reload and no IP pass (`SpellEffects.cpp:3406-3441`). Button and byte stay as they were. No new save is required. | VERIFIED from that early return. NOT TESTED. | The spell id or `active` changes when this was the only action. Using G5 as the "IP re-learn" action is the wrong setup. |

### Cower 1742 — removal versus a toggle

| Case | Setup | Action | Expected after the stated read | Label | What would falsify it |
| --- | --- | --- | --- | --- | --- |
| C1 | Serpent. Pet knows 1742. Manual OFF, baseline `active` 129, bar type 129, action 1742. Record any of `1753, 1754, 1755, 1756, 16697, 27048` that are also known. | Log out and read while offline (toggle snapshot). Log in, wait, log out, read again (post-IP snapshot). | Offline read: row 1742 still present, `active` 129, button present, glow off. That is the toggle (`Pet.cpp:2274-2284`, save `PlayerStorage.cpp:7303-7305`). Post-IP read: no row for 1742, no replacement id, button gone. That is `reconcile({ 1742 }, {})` at `:445`, then `_SaveSpells` dropping `PETSPELL_REMOVED` (`Pet.cpp:1588-1592`). A higher id that was known and is not in the live wipe list is still present. | POTENTIAL ISSUE. The unlearn is VERIFIED source for a pet that passes the gates and `HasSpell(1742)`. NOT TESTED. | Post-IP row for 1742 still present. If that row is 129 or 193, the spell was not removed. A remaining row whose only change is `active` is a toggle, which is the other outcome. A new spell id appearing as a replacement falsifies "no `learnSpell`" (`:109-110`). |
| C2 | Serpent. 1742 known. Manual ON, baseline `active` 193 and bar type 193. | Same two logouts as C1. | Offline read: row present, `active` 193, glow on. Post-IP read: row absent, button gone, not a 1742 button with glow off. Removal does not depend on the old byte (`unlearnSpell(1742, false, true)` at `:106`). | POTENTIAL ISSUE. NOT TESTED. | Post-IP row remains with `active` 129. That is a toggle from ON to OFF, and it falsifies removal. A remaining row at 193 falsifies that the unlearn ran. |
| C3 | Repeat C1's setup and the two logouts on Moth, then Chimaera, then Silithid. | Same. | Same bytes as C1. Live calls `:453`, `:460`, `:467`. | POTENTIAL ISSUE. NOT TESTED. | Same falsifier as C1, per family. One family keeping 1742 while another loses it means that family's gate or `Name[0]` did not take the live call. UNKNOWN until the family string is known. |
| C4 | Wolf, or Cat. 1742 known. Manual OFF at 129. | Same two logouts. | Both reads: row 1742 present, `active` 129, button present, glow off. The `reconcile` line is a comment (`:128-129` Wolf, `:145-146` Cat). | VERIFIED preserved in source for those comments. NOT TESTED. | Post-IP row for 1742 is absent. That would falsify "the comment does not unlearn." |
| C5 | Serpent that does not know 1742. | Resummon and a post-check save. | Still no row. `HasSpell` is false, so `:105` does not unlearn. | VERIFIED no-op for an absent id. NOT TESTED. | This case cannot prove the live call ran. Do not treat an absent row here as a removal result. |
| C6 | Serpent, 1742 known, OFF at 129, pet stays out. | Click the autocast control off again, or on then off. Do not dismiss, relog, stable, or level. Then log out once and read while offline. | Row remains, `active` 129, button remains. No IP pass ran. The offline row is the toggle signature to put beside C1's second read. | VERIFIED from the toggle and from the absence of a save inside the opcode. NOT TESTED. | The offline row is already gone. The click path does not delete `pet_spell` rows (`Pet.cpp:2247-2286`). |

### Bite/Claw — the #103 overwrite, and the empty-dummy trap

Before B1–B4, record which Wolf Bite dummies the hunter actually has, from the client spellbook, and as supporting rows from `character_spell` (`CharacterDatabase.cpp:78`). `keepId` is the highest owned dummy minus 600000 (`IndividualProgressionSpells.cpp:94-100`, list at `:117`). If the spellbook and the row disagree, `keepId` is UNKNOWN and the case does not run.

| Case | Setup | Action | Expected after the stated read | Label | What would falsify it |
| --- | --- | --- | --- | --- | --- |
| B0 | Wolf. Hunter knows none of the Bite dummies at `:117`. Pet knows one or more of the wipe ids. Autocast either byte. | Dismiss, Call Pet while not already out, wait, post-check save. Also repeat the two-logout relog. | Every listed Bite id is absent. No new Bite id. `keepId` stayed 0, so `:109` did not learn. This is removal of the chain, not a rank overwrite. | POTENTIAL ISSUE. VERIFIED source when `HasSpell` is false for every dummy. Whether this hunter knows a dummy is UNKNOWN. NOT TESTED. | Any wipe id remains, or a Bite id that was not already known appears. Do not file this row as the #103 overwrite. |
| B1 | Wolf. Hunter knows at least one dummy. Pet knows a wipe id that is not `keepId`, and does not know `keepId`. That known rank is manual ON at 193, baseline saved. | Resummon as in B0, then the post-check save. Repeat with relog's second logout. | Old id absent. `keepId` present. `keepId.active` is 129. Bar shows `keepId`, glow off. Explicit ON became the learn default (`Pet.cpp:1810-1813`) because the old rank was `PETSPELL_REMOVED` before the copy (`:1841-1843`, `:1855`). | VERIFIED source for that branch. Who has this setup is UNKNOWN. NOT TESTED. | `keepId.active` is 193, or the old id remains, or `keepId` was not learned. 193 on `keepId` would mean the native copy or an ON write ran, which this IP order does not do. |
| B2 | Same as B1, except the old rank is manual OFF at 129. | Same resummon and the same relog. | Same result as B1: old id gone, `keepId` at 129, glow off. The byte matches B1, so this capture does not show that the old OFF was copied. | VERIFIED source that the record is discarded. The visible OFF is also the learn default. NOT TESTED. | Old id remains, or `keepId` is absent. A result of 129 does not falsify "the copy was skipped," because 129 is the default. That limit is the #103 observation gap. |
| B3 | Wolf. Pet already has only `keepId` and no other wipe id. That rank is ON at 193. | Resummon, relog, and a stable swap that loads this pet. Post-check save of this pet number. | `keepId` remains. `active` stays 193. Glow stays on. The unlearn skips `id == keepId` (`:105`) and `learnSpell` is not called (`:109`). | VERIFIED source. Whether the pet is in this state is UNKNOWN. NOT TESTED. | `active` becomes 129, or the id changes, while the gates held. That would falsify "already only the legal rank leaves the byte alone." |
| B4 | Same as B3, OFF at 129. | Same three load actions. | `keepId` remains at 129. Glow off. | VERIFIED preserved in source for this state. NOT TESTED. | `active` becomes 193, or the id changes. |
| B5 | Cat, not Wolf. Same four setups as B0–B4, using the Claw list and dummies at `:137`. | Same actions as the matching B row. | Same expected bytes, with Claw ids in place of Bite ids. | VERIFIED source for Cat's non-empty dummy list. NOT TESTED. | Same falsifiers as B0–B4. A Wolf must not be used for this Claw overwrite row. |
| B6 | Wolf. Pet knows one or more Claw ids from the list at `:120`. Any autocast byte. | Resummon and the post-check save. | Every listed Claw id absent. Nothing learned. The dummy list is empty. This is not the #103 overwrite. | POTENTIAL ISSUE. VERIFIED source for that empty list. NOT TESTED. | A listed Claw id remains, or a new Claw id appears. Filing B6 as "ON became OFF" is the wrong reading: the id should be gone. |
| B7 | The B1 setup, pet stays out, one level that can teach a Bite rank. | Look at the bar at the level-up moment and again after more than a second. Read rows only on a later logout. | `GivePetLevel` does not save (`Pet.cpp:959-960`). The first look can still show the native copy of 193 on a higher rank (`Pet.cpp:1855`). The second look, after the 200 ms IP event (`IndividualProgressionSpells.cpp:1304-1306`), is B1's result when that new rank is not `keepId`: `keepId` at 129. The logout row matches the second look, not the first. | Two-step order is VERIFIED source. Which frame the client shows is NOT TESTED. One sample is ambiguous. | The logout row still has the old rank at 193 when `keepId` was a different id and the gates held. Or the second look is already `keepId` at 193. |
| B8 | Two pet numbers. The loaded-out pet is the B1 Wolf. The pet put away is any other hunter pet. | Stable swap. Read both numbers after the swap save. Load the B1 Wolf, wait, then take its post-check save. | The pet put away keeps the rows written at `RemovePet` (`NPCHandler.cpp:703`, `Player.cpp:9367`). It is not re-learned while despawned. The B1 Wolf, once loaded (`:731`), follows B1 on its own number only. | VERIFIED split of the two pet numbers. NOT TESTED. | The stabled number changes before it is loaded again, or the loaded number's result is written onto the stabled number. |

Stable, relog, and resummon are the same IP entry once a pet is loaded: `InitStatsForLevel` schedules the check (`Pet.cpp:332`, `IndividualProgressionSpells.cpp:1320-1329`). Level-up adds the immediate native learn in B7. Call Pet while the pet is already out is G5, not an IP trigger.

## 5. How to read a capture

- Button still there, glow off, row present at 129: toggle or preserved OFF. This is the Growl expectation, the commented-Cower expectation, and the "already only `keepId`" expectation. It is also the offline snapshot in C1, before IP runs.
- Button gone, row absent, no new id: removal. This is the post-IP expectation for Cower 1742 on the four families, for Wolf Claw, and for Bite when the hunter owns no dummy.
- Old id gone, `keepId` present at 129, glow off, and the old rank had been 193: the #103 overwrite of an explicit ON. Source mechanism VERIFIED. A real pet hitting it is UNKNOWN until this capture exists.
- `keepId` at 129 after an old OFF: agrees with the overwrite and also agrees with "the learn default." It does not prove the old choice was copied. B2 cannot close that gap.
- Client changed, row not yet changed: the save has not happened. Read again after the post-check save.
- No spell-id line in the server log: expected from the cited functions. It neither confirms nor falsifies.
- Querying `character_pet_spell` and getting no row: wrong table. Not a removal.

No row in this matrix was captured. In-game behaviour is NOT TESTED. Running the matrix needs a separate owner authorization. This note is not that authorization.

## 6. What this plan does not do

- It does not revive PR #69 or apply `docs/install/manual_hunter_pet_autocast_cache.sql`.
- It does not add a module, a log line, a `ToggleAutocast`, a `learnSpell`, or a `SELECT`.
- It does not edit Playerbots, Individual Progression, AzerothCore, or the #120 integration branch.
- It does not decide whether a module may persist Bite/Claw. #103 still has no safe module writer. Functional persistence of a spell IP replaces stays blocked.
- It does not treat Growl's source result as an in-game pass.

## Workflow note

Re-read on this branch before the commit that adds this file. No file under `.github/workflows/` contains `upload-artifact` or `actions/upload-artifact`. Every `pull_request` trigger has a `paths` list. None of those paths is `docs/research/` or this filename. Every `push` trigger is limited to a different branch name than `cs02/a02-human-hunter-autocast-s1-20261024`. `workflow_dispatch` does not run because a commit was pushed. A push whose only changes are this file and the pointer in the S1 note does not match those filters, so it does not start a job that builds or uploads a binary. NOT TESTED as a GitHub Actions run until that push is observed. This file does not add or edit a workflow.
