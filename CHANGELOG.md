# Changelog

## Naxxramas Core Patch 1.0.6.8.4

### Playerbots — Molten Core raid consumables

- Added the first automated Playerbot raid-consumables profile for **Molten Core**.
- Added player commands:
  - `.bot consumables mc`
  - `.bot consumables status`
  - `.bot consumables clear`
- Molten Core preparation applies class/spec-appropriate long-duration consumable effects directly as auras.
- Usable inventory consumables are topped up to one native maximum stack rather than being applied as permanent effects.
- Automatically supplies **Cache of Mau'ari** when Juju effects require it.
- Supplies weapon consumables according to equipped weapon type, including sharpening stones and weightstones.
- Supports class/spec weapon consumables such as caster oils and Rogue poisons where appropriate.
- Supports Hunter pet consumable preparation when an active pet is available.
- Supports Alliance and Horde controlled bots.
- When the controlling player is grouped/raiding, only controlled bots in the same group are prepared.
- When the controlling player is not grouped, controlled bots currently in the world are eligible.
- Added consumable-aura tracking and missing/expired buff warnings.
- Rerunning the Molten Core command refreshes the tracked preparation set.
- Added status reporting for prepared bots, applied auras, supplied items, supplied Cache of Mau'ari items, skipped pet buffs, unsupported bots, and failures.
- Warrior Arms intentionally uses the Warrior DPS/Fury preparation profile.
- Added Greater Stoneshield handling for tank-oriented profiles.
- Added Dense Weightstone handling for blunt Warrior weapons.
- Current intentional exclusions:
  - Protection Paladin has no automatic Classic Molten Core profile yet.
  - Death Knight has no Molten Core profile because the class did not exist in Vanilla.
- Registered the new system through `NaxxramasCore_loader.cpp`.

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
