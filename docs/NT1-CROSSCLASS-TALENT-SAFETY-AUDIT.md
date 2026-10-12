# NT1 Universal Cross-Class Talent Safety Audit

## Status and scope

**Draft module-only read-only development.** No automated talent repair, offhand exemption, spec switch, equipment manipulation, SQL write, server update or database backup is implemented by this document or the accompanying `repairpreview` change. Existing Alt Bot ordinary Apply stays **blocked if any offhand is equipped or an active pet exists**, irrespective of the new diagnostic result.

The purpose is to examine all classes/specializations consistently **before** planning any destructive reset, including the same class across Vanilla/TBC/WotLK progression. Do not use the new messages as permission to remove existing guards.

### Practical no-code entry point (new in this draft)

```text
.naxxbot talents safetypreview <online-altbotname>
```

Use **safetypreview** to run the ten-class equipment/pet/spec/Talent Completion risk inspection **without any NT1 code**. This is particularly useful for test coverage across all classes and specs before the user has prepared their talent presets. It reports the existing protected-state counts/checksums plus class-wide equipment warnings, not a new talent build.

**Security is strict:** importer enabled; GM or ordinary player with access mode 2/4; real human issuer; existing online non-Random Alt Bot; same-account/direct AI-master relationship for non-GMs; issuing HUMAN character must match the full `AltBotAllowedPlayers` allowlist **even for GMs**. Read-only mode 4 is preferred for normal account testing; mode 2 still exposes the old destructive experimental Apply command.

`safetypreview` intentionally has **no era-specific talent code** and therefore does NOT claim a bot's ranks are Vanilla/TBC/WotLK-legal. Use `repairpreview` with a *valid code for that class and IP era* to inspect explicit active/inactive-spec forbidden talents. Neither command switches specializations, changes pets, moves items or writes SQL.

### Both-spec out-of-era talent scan (new in this draft)

The existing `repairpreview <bot> <NT1-code>` now scans **each owned specialization's talent spell mask separately** using the established `AvailableInEra` server policy. A legal active build does not imply the other specialization is legal. It prints the active-spec count plus each inactive-spec count, with up to six offending Talent.dbc ID/rank/tree/row/column records per inactive spec to avoid huge 3.3.5a chat output.

The inactive scan calls **`Player::HasTalent(spellId, spec)`** for a specifically numbered spec; it does not change the active spec, read inactive glyph values, move equipment or remove pets. This scan is **diagnostic only** and must not be mistaken for a recovery-ready snapshot or approval to apply an NT1 build.

### Existing entry point

`.naxxbot talents repairpreview <online-altbot> <valid-NT1-code>`

- Existing access, actual non-GM Playerbots ownership/master, in-era DBC validation, real human identity, `AltBotAllowedPlayers` character allowlist and no-Random-Bot rules still apply.
- `AccessMode=4` is normal-account read-only mode in the current **merged source**. Existing binaries require the corresponding compilation and Worldserver restart; `AccessMode=2` permits destructive experimental Apply and is **not** the safest testing mode.
- The new `PrintAltBotCrossClassSafetyAudit` runs through existing allowlisted `repairpreview` and the new allowlisted no-code `safetypreview`; both remain read-only.
- This command reads live equipment template IDs/types, current dual-wield/Titan's Grip flags, active pet state, active spec, number of specs, current module `BotTalentCompletion.Enabled` setting and the recognized class.

## AzerothCore source-backed reset facts

Public AzerothCore `Player::resetTalents(bool)` calls `OnPlayerTalentsReset`, may `RemovePet(...PET_SAVE_NOT_IN_SLOT...)`, removes spells and talent auras, resets Titan's Grip and conditionally Dual Wield, then calls `AutoUnequipOffhandIfNeed()`. That latter function may call `RemoveItem`/`StoreItem` **or MAIL the original item** when no bag placement exists. The *actual* offhand item type and main-hand weapon rules matter: simply seeing an offhand item is not sufficient to predict relocation.

`Player::ActivateSpec` is a separate, **state-modifying** function. It can remove pets, unsummon controlled entities/totems, save/load different action bars, remove and restore talent/glyph auras, alter power/forms and invoke offhand compatibility again. NEVER switch a bot's spec just to read the inactive glyph IDs or prove safety.

Sources:
- [AzerothCore Player.cpp — talent reset / spec switch / offhand control](https://github.com/azerothcore/azerothcore-wotlk/blob/master/src/server/game/Entities/Player/Player.cpp)
- [AzerothCore Player.h — active-spec glyph getter](https://github.com/azerothcore/azerothcore-wotlk/blob/master/src/server/game/Entities/Player/Player.h)
- [Naxxramas Core BotTalentCompletion hook](../src/Systems/BotTalentCompletion.cpp)
- [Current NT1 source](../src/Systems/BotTalentImport.cpp)

**Important:** this follows the public AzerothCore master source observed during design, not a byte-for-byte assertion about the administrator's running core revision or Playerbots fork. It must still be checked against that exact build.

## Read-only offhand classification — diagnostic, not exception

| Observed situation | Diagnostic | Effect on Apply |
| --- | --- | --- |
| No offhand | Empty; state outside equipment still unknown | Existing checks continue; does NOT imply safe |
| Template unavailable | Unknown; fail-closed | Existing occupied-offhand block unchanged |
| Main hand polearm, staff or fishing pole | Potential forced unequip | Occupied-offhand block unchanged |
| Offhand weapon and current Dual Wield absent | Potential forced unequip | Occupied-offhand block unchanged |
| Offhand weapon and spell 674 not learned | Dual Wield may disappear at reset | Occupied-offhand block unchanged |
| Two-handed offhand or a 2H main without Titan's Grip | Potential forced unequip | Occupied-offhand block unchanged |
| Offhand weapon with current matching abilities | Talent-dependent state not guaranteed after reset | Occupied-offhand block unchanged |
| Ordinary caster focus or shield with compatible 1H main | No *currently observed* core removal trigger | Occupied-offhand block unchanged; hooks not proven safe |

This is deliberately **not** a complete simulation of a talent reset. The core and Playerbots scripts can have additional hooks and effects. A green-looking classification is not a green light.

## Ten-class and spec audit matrix

| Class | Specs to test | Primary risks to examine |
| --- | --- | --- |
| Warrior | Arms / Fury / Protection | Titan's Grip loss, 2H offhand, shield/weapon transitions, stance/passive spell effects |
| Paladin | Holy / Protection / Retribution | Caster shield versus 2H weapon, Righteous Fury and other talent-linked auras |
| Hunter | Beast Mastery / Marksmanship / Survival | Current/stabled pet, exotic-pet eligibility, pet spell/talent state, possible dual wield |
| Rogue | Assassination / Combat / Subtlety | Dual-wielded original items, talent spells, temporary effects |
| Priest | Discipline / Holy / Shadow | Caster orb/book or shield, talent-derived effects, temporary summons |
| Death Knight | Blood / Frost / Unholy | Frost dual wield vs 2H, ghoul state, WotLK-era/level restrictions |
| Shaman | Elemental / Enhancement / Restoration | Enhancement talent-granted Dual Wield, shield/focus offhands, totems/summons |
| Mage | Arcane / Fire / Frost | Water Elemental and summoned state, caster orb/books, temporary spell effects |
| Warlock | Affliction / Demonology / Destruction | Felguard/demon state, stabled/temporarily unsummoned pets, reagent return, glyphs |
| Druid | Balance / Feral / Restoration | Shapeshift/form-linked talent passives, caster offhands, summoned entities |

The report prints the **class-specific review category** for the current bot. It does NOT yet infer the bot's actual tree/role or prove that all listed hazards are present. That will require additional DBC-aware testing.

### Cross-cutting checks required for EVERY class

1. Original item-instance GUIDs AND bag/slot coordinates; no replacement item, silent mail, bank change, destruction or duplication.
2. Both specializations' talent rank-spell IDs and spell records; active and inactive glyphs from **offline DB**, not a live spec switch.
3. Pets including temporarily unsummoned/stabled entries; active `GetPet()` being null does **not** prove no pet state.
4. Cast/talent-granted spells, passive/triggered auras, glyph effects, shapeshift state and relevant summon/reagent state.
5. Action bars and abilities after **separate**, expressly approved, disposal-only spec-switch scenarios, not as a diagnostic side effect.
6. Interactions with `NaxxramasCore.BotTalentCompletion.Enabled = 1` and other Playerbots respec/maintenance hooks; check no undesired subsequent talent fill or overwrite.
7. Individual Progression tier, target class/level/era and possible TBC/Vanilla DBC row exceptions.
8. Full **consistent** characters DB backup plus an **isolated tested restore**, before *any* destructive experiment. A checksum, dry-run preview or Python test is not a restore.

## Regression strategy

Initial offline/source CI:
- Ten recognized class cases plus unknown-class fail-closed wording.
- Synthetic examples for 1H+caster focus, 1H+shield, staff+offhand, lost dual wield, 2H offhand and empty offhand.
- No mutating calls in the new helper.
- Original active-pet/offhand `CheckApplyReadiness` denial must remain present.
- Mode 3 (GM read-only) and mode 4 (owned-player read-only) Apply denials preserved.
- Reporter only called after existing Alt Bot human identity, access and allowlist checks; no new command.
- Both-spec summary and active-only glyph caveats remain unchanged.

**These tests inspect source/contracts and synthetic examples only. They do not compile C++ or prove the user's installed AzerothCore fork is compatible.**

Future *approved* test build:
- Verify compiler APIs on exact local AzerothCore/Playerbots/IP version.
- Exercise only `repairpreview` in normal-player Mode 4 with safe disposable test bots from every class, one scenario at a time.
- Verify the new report does not consume/rearrange items, activate specs, cast spells or save character DB.
- Independently audit/restore database snapshots before ever testing destructive resets. The currently implemented normal Alt Bot Apply still rejects occupied offhands or active pets.

### Rollback and operator guidance

This source is on a **draft** branch and is not merged or installed. No immediate recompilation or config edits are required just to discuss the design. If eventually approved, the owner can back up the active source/config and binaries, merge/recompile only after CI+review, run read-only commands, and roll back to the known prior Git revision if necessary. A source rollback never reverses gameplay changes made by other systems.


## 12 October 2026 — second source/API review (still draft)

Public AzerothCore `master` interfaces were checked for `Item::GetTemplate() const`, `Player::GetItemByPos(bag,slot) const`, `Player::HasTalent(spell,spec) const`, `Player::GetSpecsCount()`, `Player::GetActiveSpec()`, `Player::GetGlyph()`, `Player::GetQuestStatus() const`, `Unit::CanDualWield() const`, `Player::CanTitanGrip() const`, `Player::HasSpell() const` and formatted `ChatHandler::PSendSysMessage`. These signatures support the current code shape; **the administrator's exact AzerothCore/Playerbots/IP checkout SHA is still unknown, and no compiler/game execution has validated it**.

The audit now falls back to the non-null class label `unknown` instead of passing an unsupported class as a null pointer to formatted output. When equipped item's template is unavailable, the report includes main/offhand **item entry IDs**, while remaining fail-closed. No equipment state is changed.

`safetypreview` also reports the **issuing HUMAN character's** effective Individual Progression era and capped stage, using the same hidden rewarded quest policy as `CheckPlayerProgressionEra`. If IP is disabled, output explicitly retains bot-level restrictions. It does **not** validate an NT1 build, determine a bot's era-legal talents, grant Apply, or create a permission. Stage/era are context for a human reviewer; no spec change or inactive glyph access occurs.

Additional source/synthetic regressions cover the shared capped IP stage, access-check ordering, missing mainhand, unknown templates and unknown class. The spell-674 dual-wield check stays **conservative**, not a promise that abilities survive reset. The original offhand/pet blockers, modes 3/4, and protected-state limitations remain.

**Pending:** inspect exact deployed AzerothCore, Playerbots and IP revisions, run current GitHub source CI, then arrange a single approved C++ build and in-game **read-only** diagnostic pass. No tests here establish full DB restore or safe gear/spec recovery.
