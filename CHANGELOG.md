# Changelog

## 1.0.6.8.5 — NT1 Playerbot talent integration (development, Phases 1–2)

- Introduced server-side NT1 base-36 talent decoder and read-only `.naxxbot talents preview <botname> <code>` in Naxxramas Core.
- Staged separately disabled `.naxxbot talents apply` routine to validate a build and current-state snapshot **before** any destructive reset, learn desired ranks, audit exact results and remaining points, and attempt recovery on unexpected failure.
- Added importer-scoped handling of three special off-centre Vanilla/TBC end capstones, without altering normal Playerbots template rules. Prevents the module's optional talent completion feature filling intentional unspent NT1 points during an import.
- Added optional characters SQL `mod_naxxramas_bot_talent_import` table to store successfully applied NT1 codes. **SQL is not installed automatically.** Full persistence through Playerbots randomization is still a development requirement.
- Read-only preview is disabled by default; **applying talents has its own second disabled switch** `NaxxramasCore.BotTalentImport.ApplyEnabled=0`. Not authorized for live deployment before compilation, rollback and maintenance testing; random bots are rejected during this experimental phase.
- **No changes to mod-playerbots, AzerothCore, Individual Progression or MultiBot.** Experimental, not compiled or live-tested; documentation in `docs/PLAYERBOT-NT1-TALENT-IMPORT.md`.
- Classified as **Change Notes 1.0.6.8.5**, not Patch Notes (no DBC edits).


- **Repository migration (2026-10-09):** The optional client addon now lives in its own [NClassicBattlegrounds](https://github.com/CosmicCuddle/N-ClassicBattlegrounds) repository. This Naxxramas Core repository retains server-side queue enforcement and a historical copy of the addon; make future Lua/TOC updates in the standalone repository first. No server code was changed during the migration.

## Unreleased — PvP addon renamed to NClassicBattlegrounds

- Addon is now independently maintained as **NClassicBattlegrounds**, with `NClassicBattlegrounds.lua` and `NClassicBattlegrounds.toc`; in-game display **N Classic Battlegrounds**. Existing `/ncbg` commands remain.
- The previous `addons/NaxxramasClassicBattlegrounds/` folder in this server module is deliberately retained as an archived backup. GitHub standalone repository now uses the shorter `N-ClassicBattlegrounds` name.
- No server-side Battlemaster queue code or compilation requirements changed because of this addon rename.

## Unreleased — PvP addon Arena and Wintergrasp interface restrictions

- Hide the Arena points header and 2v2/3v3/5v5 panels during Vanilla; restore
  them at modern Individual Progression TBC entry (stage 8).
- Hide Wintergrasp timer and icon during Vanilla/TBC; restore from WotLK entry
  (stage 13). Apply even to the Battlemaster dialog where appropriate.
- Preserve the PvP Honor panel and Battlemaster queue controls; no client text
  overlays, DBC edits, SQL updates, or server recompilation required.
- Visual changes are optional and reversible with `/ncbg off`.
- **Unreleased addon update; in-game tests pending.**

## Unreleased — Classic Battlemaster-only Battleground queues

- Added `src/Systems/BattlemasterQueueProgression.cpp` using AzerothCore's server-side pre-queue hook. Vanilla/TBC players must use a nearby Battlemaster NPC; remote queueing unlocks at modern Individual Progression WotLK entry **stage 13**.
- Validates the Battlemaster GUID, NPC flag, interaction distance and Battleground type; checks mixed-progression groups; includes optional GM and Playerbot exemptions matching IP's bot account regex.
- Added `NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled = 0` (default **off** pending testing), `...UnlockStage = 13`, and individual exemption options.
- Optional 3.3.5a addon [NClassicBattlegrounds](https://github.com/CosmicCuddle/N-ClassicBattlegrounds) uses completed hidden progression quests to hide the **Battlegrounds tab next to PvP** before WotLK while preserving PvP information and in-person Battlemaster queue controls. Removed the obstructive bottom message and stopped altering Join buttons.
- Original AzerothCore queueing is restored by disabling the feature; addon `/ncbg off` disables the cosmetic changes only. No DBC/SQL/core/IP/Playerbots source modification.
- Testing and setup details: `docs/CLASSIC-BATTLEMASTER-QUEUES.md`.
- **Committed but not yet compiled or tested in game.**


## Unreleased — Vanilla meeting stone restriction (Individual Progression)

- Added `src/Systems/MeetingStoneProgression.cpp` to block the native meeting-stone summon interaction for players whose own Individual Progression has not entered TBC.
- Meeting stones remain visible and decorative in Vanilla; TBC and WotLK characters retain native AzerothCore summoning, group, target and level checks.
- Clicking a stone in Vanilla explains that summoning stones unlock at The Burning Crusade; the client-side hover tooltip is unchanged.
- Added `NaxxramasCore.MeetingStones.ClassicMode.Enabled = 1` (enabled by default). Set `0` to immediately restore standard WotLK behaviour.
- Uses the Individual Progression public API when available, with a modern hidden-quest fallback if the IP header is not exported.
- The fallback now respects the IP module's enable switch and progression limit, preventing the Vanilla restriction from applying when IP is disabled or treating beyond-limit characters as TBC. Older IP builds without a public header need compatibility testing.
- Module-only C++ and configuration: no new DBC rows, world SQL, client patch, or AzerothCore core modifications.
- **Source committed; compilation and in-game testing pending.**


## Unreleased — Authoritative manual Playerbot talent templates (audit fix)

- Added pre-queued-command template capture for Playerbot `talents spec <name>` and `talents apply <link>` via whisper and party/raid chat (including configured command prefixes and multiple commands).
- The level-appropriate named template, or the exact imported talent link, now limits the initial Playerbots assignment through AzerothCore's pre-learn hook. The original Playerbots routine can walk level-80 templates, but will no longer be allowed to add unintended off-plan ranks for these chat routes.
- Named completion may fill remaining legal points only within the chosen template tree(s); imported custom links stay rank-exact. Impossible plans leave points unused rather than fabricating a different spec.
- Synchronized global per-bot pending state via a mutex. Added ordered intent queue, expiry, and spec/logout cleanup. The mutex is not held while running `LearnTalent`.
- Automated/console/guild bot talent pathways without captured chat-plan context retain the previous conservative completion and expansion-row restrictions. No core, Playerbots, database or DBC modifications.
- **Awaiting compilation and in-game regression tests for this new revision.**


## Unreleased — Level-appropriate Playerbot builds and Wrack safety

- Fixed the completion matcher choosing level-80 premade links ahead of level-60 links. It now uses the closest configured talent link to the bot's own level, preferring the lower level for equal distance.
- Completion choices are limited to the bot's dominant tree and one already-used or planned secondary, rather than allowing arbitrary third-tree filler.
- At level 60, Affliction Warlocks with Wrack and no existing or planned Destruction investment prefer Demonology filler after 31 Affliction points, aiming towards 31/20/0 where the original template permits; no existing talents are removed.
- No upstream Playerbots, AzerothCore or DB/DBC edits. Existing config switch unchanged. Must compile and retest this correction after pulling.


## Unreleased — Optional Playerbot talent completion (test branch)

- Added an opt-in Naxxramas Core PlayerScript that completes remaining **legal talent ranks** after a bot's no-cost respec settles.
- Introduced `NaxxramasCore.BotTalentCompletion.Enabled = 0` (disabled by default pending build/game testing).
- Uses available premade talent templates as a preference where they match the chosen build; falls back to deterministic, conservative rank choices validated by the core.
- Preserves active spec and all existing talent points, avoids combat-time updates and clears pending operations on spec switches and logout.
- No Playerbots source changes; maintains the existing `AiPlayerbot.LimitTalentsExpansion` level-based restrictions and keeps real players untouched.
- Potentially leaves points unspent if no remaining legal rank passes AzerothCore validation; no forced edits or repeated respecs.
- **Not yet verified by compilation or live server testing; do not merge into main until tests pass.**


## Unreleased — Playerbots manual talent limits

- Added a module-owned talent learning guard to enforce `AiPlayerbot.LimitTalentsExpansion = 1` on manually selected premade specs and imported talent links.
- Mirrored Playerbots' existing level thresholds: Vanilla rows 1–6 and middle row 7 through level 60; TBC rows 1–8 and middle row 9 through level 70; all rows from level 71.
- Restricted only the **rows** of the talent tree, not the number of talent points in a tree. Regular player characters remain unaffected.
- No modifications to Playerbots, core, world/characters SQL or DBC files; the safeguard requires recompilation and server restart.
- Note: blocked talents in WotLK premade builds may leave unused points; intelligent redistribution and Individual Progression tier mapping are not part of this initial compatibility fix.


## Naxxramas Core Patch 1.0.6.8.4

### Playerbots — Instance consumables

- Expanded the original Molten Core preparation system into an instance-scoped raid/dungeon consumables framework.
- Reworked the command parser so `.bot consumables` accepts named profiles and any exact level from **1 through 54**.
- Added commands:
  - `.bot consumables 1-54`
  - `.bot consumables mara`
  - `.bot consumables sunken`
  - `.bot consumables brd`
  - `.bot consumables scholo`
  - `.bot consumables stratud`
  - `.bot consumables dm`
  - `.bot consumables lbrs`
  - `.bot consumables ubrs`
  - `.bot consumables mc`
  - `.bot consumables status`
  - `.bot consumables clear`

#### Aura refresh protection

- Added remaining-duration checks before consumable auras are reapplied.
- Normal consumable auras with **more than 10 minutes remaining** are left untouched.
- Normal consumable auras refresh at **10 minutes remaining or less**.
- Buff-food / Well Fed effects use a **5-minute** refresh threshold instead.
- Existing healthy auras are still added to the active tracker for status and cleanup.
- Preparation summaries now report how many aura effects were preserved instead of refreshed.
- Short tactical/timed effects retain their dedicated behaviour.

#### Shared preparation cooldown

- Added one shared **10-minute cooldown** across all consumable preparation commands.
- The cooldown starts only after a profile successfully prepares at least one supported bot.
- `.bot consumables status` and `.bot consumables clear` remain available during the cooldown.
- Invalid locations, unsupported commands, and attempts with no eligible bots do not consume the cooldown.
- Relogging does not clear an active cooldown.
- A party/raid death or wipe resets the cooldown so the group can rebuff after recovering.
- Dead controlling players must resurrect before running another preparation command.
- Status output reports the remaining cooldown while an active profile is tracked.

#### Instance and anti-exploit scope

- Molten Core can only be prepared from inside **Map 409**.
- Bots must also be physically inside the allowed instance/wing before receiving a profile.
- Named shared-map profiles validate the player's physical section:
  - Lower vs Upper Blackrock Spire;
  - Stratholme Undead/Service side;
  - Dire Maul East, West, and North.
- Tracked effects are automatically removed and timed effects cancelled when the controlling player leaves the profile's allowed instance/wing.
- Grouped players can prepare both personally controlled alt/account bots and random Playerbots in the same group/raid.
- Random Playerbots are never processed globally and must be grouped with the player.
- Ungrouped players can only prepare eligible personally controlled alt/account bots already inside the same valid instance scope.

#### Exact level-scaled dungeon preparation

- Added exact-number generic profiles from **1 to 54** rather than fixed 10-level brackets.
- Each bot's effective consumable level is the minimum of:
  - requested command level;
  - the bot's actual level;
  - the dungeon's LFG/target-level cap;
  - level 54.
- Buff progression inherits the strongest previously unlocked option until a better one becomes legal.
- Added role/spec-aware elixir progression for:
  - tanks;
  - Strength melee;
  - Agility melee/hunters;
  - healers;
  - casters.
- Added school-specific caster handling:
  - Shadow Power for Shadow-oriented specs;
  - Frost Power for Frost Mage;
  - Firepower/Greater Firepower for Fire Mage and Destruction Warlock;
  - general Arcane elixirs for Arcane/Elemental/Balance-style casters.
- Added role-appropriate scrolls.
- Scrolls are cleanup-tracked without missing-aura warnings because normal class buffs may replace them.
- Added level-scaled buff food.
- Added level-scaled healing potion stacks and mana potion stacks for mana users.

#### Named dungeon profiles

- **Maraudon** — adds Nature Protection.
- **Sunken Temple** — adds Nature Protection.
- **Blackrock Depths** — adds Fire Protection.
- **Scholomance** — adds Shadow Protection.
- **Stratholme Undead** — adds Shadow Protection and is restricted to the Service/Undead side.
- **Dire Maul** — automatically detects:
  - East: Nature Protection;
  - West: Shadow Protection;
  - North: enhanced endgame inventory support.
- **Lower Blackrock Spire** — standard endgame dungeon package.
- **Upper Blackrock Spire** — restricted to the Upper Spire section and receives a stronger package plus Fire Protection.
- Named dungeon protection effects automatically select the strongest level-valid normal/Greater protection version.
- Dungeon profiles do not create raid class reagents.

#### Molten Core raid preparation

- Keeps the larger class/spec-specific Molten Core profile.
- Applies long-duration consumable effects directly as auras.
- Supplies Vanilla-sized usable inventory consumables rather than later-expansion maximum stacks.
- Automatically supplies **Cache of Mau'ari** when Juju effects require it.
- Supplies sharpening stones or weightstones according to equipped weapon type.
- Supports class/spec weapon oils and Rogue poisons where appropriate.
- Supports Hunter pet consumable preparation when an active pet is available.
- Supports Alliance and Horde controlled bots.
- Warrior Arms uses the Warrior DPS/Fury preparation profile.
- Protection Paladin remains intentionally unsupported by the Molten Core profile.
- Death Knight remains unsupported by Classic profiles.

#### Raid-only class reagents

- Added top-up-only raid reagent preparation.
- Existing quantities are never reduced or replaced; only the missing amount is added.
- Added Vanilla-style targets:
  - Druid: Ironwood Seed ×20; Wild Thornroot ×20.
  - Mage: Rune of Teleportation ×10; Rune of Portals ×10; Arcane Powder ×20; Light Feather ×20.
  - Paladin: Symbol of Kings ×100; Symbol of Divinity ×5.
  - Priest: Sacred Candle ×20; Light Feather ×20.
  - Rogue: Flash Powder ×20; Blinding Powder ×20.
  - Shaman: Ankh ×5; elemental totems ensured; Shiny Fish Scales ×20; Fish Oil ×20.
  - Warlock: Soul Shard reserve ×5.
- Raid reagent top-ups are not used by dungeon or generic level profiles.

#### Vanilla inventory quantities

- Replaced generic WotLK max-stack top-ups with explicit Vanilla-era targets for supplied raid consumables.
- Major healing/mana potions and Limited Invulnerability Potions target stacks of 5.
- Heavy Runecloth Bandages, sharpening/weightstones, and Rogue poisons target stacks of 20.
- Brilliant Wizard/Mana Oil targets one charged oil item.
- Generic dungeon healing/mana potions also target Vanilla stacks of 5.

#### Juju and tracker improvements

- Added timed Juju Flurry handling:
  - application 1 immediately;
  - application 2 at +60 seconds;
  - application 3 at +120 seconds;
  - then stop.
- Juju Flurry no longer creates false missing-buff warnings during its normal downtime.
- Juju Escape is treated as a one-use tactical effect without normal-expiry warnings.
- Timed Juju sequences stop when the profile is cleared or the controlling player leaves the valid instance.
- Short Greater Stoneshield expiries no longer create normal missing-buff warnings.
- Removed conflicting/redundant Warrior Molten Core combinations involving Rumsey Rum Black Label and Elixir of Giants where the stronger selected effects already cover those roles.
- `.bot consumables status` now reports tracked auras and active timed consumable sequences.

### Honor Overflow

- Added configurable conversion of Honor earned above AzerothCore's normal Honor cap into gold.
- Added configurable copper-per-Honor conversion rate.
- Added optional player notifications.
- Added optional Playerbot participation.
- Battleground conversion rewards are awarded immediately.
- Individual Battleground conversion messages are suppressed and replaced by one summary when the Battleground ends or the player leaves early.
- Added handling for players near or already at the gold cap.

Configuration:

```ini
NaxxramasCore.HonorOverflow.Enabled
NaxxramasCore.HonorOverflow.CopperPerHonor
NaxxramasCore.HonorOverflow.Notify
NaxxramasCore.HonorOverflow.IncludeBots
```

### Fortnightly Honor Reset

- Added scheduled Honor resets with a configurable interval, weekday, hour, minute, and anchor date.
- Resets spendable Honor for both online and offline characters.
- Added persistent characters-database state so completed resets survive worldserver restarts.
- A missed scheduled reset can be caught up after the server comes back online.
- Added optional notification for online players when the new Honor cycle begins.
- Added characters-database SQL for the reset tracking table.

Configuration:

```ini
NaxxramasCore.HonorReset.Enabled
NaxxramasCore.HonorReset.IntervalWeeks
NaxxramasCore.HonorReset.DayOfWeek
NaxxramasCore.HonorReset.Hour
NaxxramasCore.HonorReset.Minute
NaxxramasCore.HonorReset.AnchorDate
NaxxramasCore.HonorReset.Notify
```

### Forced PvP zones

- Added forced normal faction PvP in **Silithus** and **Eastern Plaguelands**.
- The player's original manual PvP preference is remembered when entering a forced zone.
- The original preference is restored after leaving.
- Players cannot manually disable PvP while remaining inside a configured forced-PvP zone.
- AzerothCore's normal PvP-off cooldown is used when appropriate after leaving.
- GMs are excluded.
- Added optional Playerbot inclusion and entry notifications.
- Config changes can take effect for players already standing in the affected zones.

Configuration:

```ini
NaxxramasCore.ForcedPvP.Enabled
NaxxramasCore.ForcedPvP.Silithus
NaxxramasCore.ForcedPvP.EasternPlaguelands
NaxxramasCore.ForcedPvP.IncludeBots
NaxxramasCore.ForcedPvP.Notify
```

### Same-account mail

- Restored AzerothCore's configured `MailDeliveryDelay` for normal player mail sent between characters on the same account.
- Same-account mail no longer bypasses the configured delivery delay.
- GM/customer-support mail is excluded.
- Returned mail and COD payments keep their normal behaviour.
- Invalid/self-mail cases are ignored.

### Brewfest

- Added a custom Dark Iron attack generator override.
- Changed Dark Iron mole-machine spawning from AzerothCore's **3-second** repeat to **12 seconds**.
- Preserved the remaining Dark Iron attack-generator behaviour.
- Added an accessibility gossip option to **Goldark Snipehunter** and **Glodrak Huntsniper**.
- The new gossip option immediately removes Brewfest fake-inebriation/drunkenness effects.
- Existing Brewfest gossip options remain available.

### Hallow's End

- Added a custom **Shade of the Horseman** event override.
- Changed the event fire cycle from **15 seconds** to **30 seconds**.
- Changed the completion/failure counter threshold from **greater than 21** to **greater than 14**.
- Preserved the remaining Shade of the Horseman behaviour.

### Forsaken

- Moved **Touch of the Grave** into Naxxramas Core as a registered module script.
- Added custom level scaling for the `90053` health-leech effect:
  - Level 1: 5
  - Level 20: 35
  - Level 40: 70
  - Level 60: 150
  - Level 70: 300
  - Level 80: 600
- Added damage and healing compensation for **Individual Progression** power-adjustment settings.
- Added/updated world SQL registration for the Touch of the Grave spell/proc configuration.
- Removed the need to keep the Touch of the Grave compensation change inside the Individual Progression module itself.

### Items

- Added the **Green Whelp Armor** custom Sleep proc script.
- Restored the server's intended proc level cap so the Sleep proc is allowed when the triggering actor is **level 63 or below**.
- Added world SQL registration for the custom item spell script.

### Module structure and configuration

- Expanded the module into dedicated `Events`, `Items`, `Racials`, and `Systems` source areas.
- Added `conf/mod_naxxramas_core.conf.dist` for configurable Honor and forced-PvP systems.
- Added characters-database SQL support alongside the existing world-database SQL structure.
- Updated the module loader to register all current event, item, racial, PvP, mail, Honor, and Playerbot systems.
- Updated `README.md` to document the current module layout, dependencies, commands, installation/update procedure, and Naxxramas Core **1.0.6.8.4** compatibility.

---

## Naxxramas Core Patch 1.0.6.8.3

### Warrior

- Added Rend Flurry custom Arms talent (`Talent ID 3000`, `Spell ID 90054`).
- Rend Flurry spreads Rend to up to two additional nearby hostile targets.
- Added 150% weapon-damage replacement strike for bleed-immune targets (`90055`).
- Uses a shared 2-second replacement-strike ICD (`90056`).
- Final intended Rend Flurry cooldown changed from 90 seconds to 60 seconds.
- Reworked Improved Heroic Strike from 3 ranks to 1 rank, reducing Heroic Strike cost by 5 Rage.
- Expanded Improved Rend to 3 ranks.
- Added Improved Rend Rank 3 (`90057`) at +22% Rend damage.
- Improved Rend Rank 3 now has a 3% chance per valid Rend periodic tick to generate 25 Rage.
- Added server-side combat-log energize reporting for successful Improved Rend procs.
- Corrected custom Talent ID strategy: Rend Flurry uses Talent ID `3000`, not the earlier experimental `90054` Talent ID.
- Documented mandatory Talent.dbc sort order (`TabID -> TierID -> ColumnIndex`).

### Racials

- Orc Blood Fury retains WotLK offensive bonuses and restores a 50% healing-received penalty for 25 seconds.
- Troll Berserking retains 20% baseline haste and scales up to 30% at low health.
- Blood Elf Mana Tap restored as a starting racial.
- Blood Elf Arcane Torrent retains its WotLK silence while restoring Mana Tap charge/resource interaction.
- Documented Forsaken DBC work including Will of the Forsaken, Shadow Resistance, Forsaken Swordsmanship, and Touch of the Grave.

### Build fixes

- Added `Define.h` before `SpellAuras.h` in the Blood Elf Arcane Torrent and Orc Blood Fury scripts.
- Fixes the compile error: `SpellAuraDefines.h: fatal error: unknown type name 'uint8'`.
- Added `SpellScriptLoader.h` to Troll Berserking and Blood Elf Arcane Torrent so `RegisterSpellScript(...)` is defined during compilation.
- Fixes the Troll compile error: `spell_custom_troll_berserking does not refer to a value`.

### Database / compatibility

- Added world SQL bindings for Rend Flurry and racial scripts.
- Documented existing-character migration risk from obsolete Improved Heroic Strike talent ranks (`12663`, `12664`).
- Added troubleshooting steps for `_LoadTalents` / `ASSERT(talentPos)` crashes.
