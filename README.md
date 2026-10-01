# mod-naxxramas-core

Custom gameplay module for **AzerothCore WotLK 3.3.5a**, built for the Naxxramas Core project.

The module keeps server-specific gameplay changes in one place, including class changes, racial changes, event overrides, item fixes, PvP systems, mail behaviour, and Playerbot raid preparation.

Some features require matching **DBC edits** on both the server and client. Those changes are documented in [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md).

> **Back up your module directory, databases, configuration, and known-working DBC files before updating the module.** Git history makes module-code changes reversible, but database and DBC changes should still be backed up separately.

## Current patch line

**Naxxramas Core 1.0.6.8.4**

## Current features

### Warrior

#### Rend Flurry (`90054`)

- 1-point Arms talent, Talent ID `3000`.
- 15-second active buff.
- 60-second cooldown.
- Rend affects the primary target and up to **2 additional hostile targets** within **8 yards** of the primary target.
- Additional targets receive the same Rend rank as the original cast.
- Bleed-immune targets receive **Rend Flurry Strike** (`90055`) for **150% weapon damage** instead.
- The replacement strike uses one shared **2-second internal cooldown** via spell `90056`.
- Triggered extra Rends are free and do not recursively spread.

#### Improved Rend Rank 3 (`90057`)

- Extends the original Improved Rend talent to 3 ranks.
- Rank 3 increases Rend bleed damage by **22%**.
- Each valid Rend periodic damage tick has a **3% chance** to generate **25 Rage**.
- Spread Rends created by Rend Flurry can proc independently.

#### Improved Heroic Strike (`12282`)

- Reworked from a 3-point talent to **1 point**.
- Reduces Heroic Strike cost by **5 Rage**.

### Racials

#### Orc — Blood Fury

- Keeps the WotLK offensive Blood Fury bonuses.
- Restores the older **50% healing-received penalty** for **25 seconds**.
- Covers spell IDs `20572`, `33697`, and `33702`.

#### Troll — Berserking (`26297`)

- Keeps the WotLK **20% haste** baseline.
- Restores health-based scaling up to **30% haste** at 10% health or lower.
- The haste amount is snapshotted when Berserking is activated.

#### Blood Elf — Mana Tap / Arcane Torrent

- **Mana Tap** (`28734`) restored as a starting Blood Elf racial.
- **Arcane Torrent** keeps the WotLK 2-second silence while restoring the Mana Tap charge/resource interaction.
- Supports the Mana (`28730`) and Energy (`25046`) Arcane Torrent variants.

#### Forsaken — Touch of the Grave

- **Touch of the Grave** passive: `90052`.
- Health-leech proc: `90053`.
- Uses custom level scaling:
  - Level 1: 5
  - Level 20: 35
  - Level 40: 70
  - Level 60: 150
  - Level 70: 300
  - Level 80: 600
- Includes damage and healing compensation for the server's **Individual Progression** power adjustments.
- World SQL registers the custom spell script/proc behaviour.

#### Forsaken — DBC-based racial work

The project also contains Forsaken changes that depend on matching DBC data:

- **Will of the Forsaken** (`7744`) — custom 5-second Charm/Fear/Sleep immunity implementation with a 120-second cooldown in the current DBC work.
- **Shadow Resistance** (`20579`) — custom **+10 Shadow Resistance** passive.
- **Forsaken Swordsmanship** (`90051`) — +5 Swords and Two-Handed Swords skill.
- Touch of the Grave also requires its matching custom spell rows.

See [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md) before distributing a client patch.

### Events

#### Brewfest — Dark Iron Attack

- Replaces AzerothCore's Dark Iron attack generator with the Naxxramas Core version.
- Dark Iron mole-machine spawning is slowed from AzerothCore's **3-second** repeat to **12 seconds**.
- Other Dark Iron attack-generator behaviour is preserved.

#### Brewfest — sober accessibility option

- Adds a gossip option to **Goldark Snipehunter** and **Glodrak Huntsniper**.
- Allows the player to immediately remove Brewfest drunkenness/fake-inebriation effects.
- The normal Brewfest gossip options remain available.

#### Hallow's End — Shade of the Horseman

- Replaces the event NPC script with the Naxxramas Core version.
- Fire cycle changed from **15 seconds** to **30 seconds**.
- Completion/failure counter threshold changed from **greater than 21** to **greater than 14**.
- Other Shade of the Horseman behaviour is preserved.

### Items

#### Green Whelp Armor

- Restores the server's custom Sleep proc restriction.
- The Sleep proc is allowed when the triggering actor is **level 63 or below**.

### Server systems

#### Honor Overflow

When a player earns Honor after reaching AzerothCore's configured Honor cap:

- Excess Honor can be converted into gold.
- The conversion rate is configurable in `mod_naxxramas_core.conf`.
- Battleground conversion rewards are awarded immediately.
- Battleground spam is suppressed and replaced with one summary when the Battleground ends or the player leaves.
- Playerbot participation can be enabled or disabled separately.
- Gold-cap handling prevents invalid over-cap rewards.

Main settings:

```ini
NaxxramasCore.HonorOverflow.Enabled
NaxxramasCore.HonorOverflow.CopperPerHonor
NaxxramasCore.HonorOverflow.Notify
NaxxramasCore.HonorOverflow.IncludeBots
```

#### Fortnightly Honor Reset

- Automatically resets spendable Honor on a configurable schedule.
- Resets both **online and offline** characters.
- Stores the last completed reset in the characters database.
- Survives server restarts and catches up a missed scheduled reset.
- Reset interval, weekday, time, anchor date, and player notification are configurable.

Main settings:

```ini
NaxxramasCore.HonorReset.Enabled
NaxxramasCore.HonorReset.IntervalWeeks
NaxxramasCore.HonorReset.DayOfWeek
NaxxramasCore.HonorReset.Hour
NaxxramasCore.HonorReset.Minute
NaxxramasCore.HonorReset.AnchorDate
NaxxramasCore.HonorReset.Notify
```

The module includes the required characters-database SQL table under `data/sql/db-characters/`.

#### Forced PvP zones

- Forces normal faction PvP throughout:
  - **Silithus**
  - **Eastern Plaguelands**
- Remembers whether the player had manually enabled PvP before entering.
- Restores the player's original PvP preference after leaving.
- Prevents players from disabling PvP while still inside a forced zone.
- GMs are not forced into PvP.
- Playerbot inclusion and entry notifications are configurable.

Main settings:

```ini
NaxxramasCore.ForcedPvP.Enabled
NaxxramasCore.ForcedPvP.Silithus
NaxxramasCore.ForcedPvP.EasternPlaguelands
NaxxramasCore.ForcedPvP.IncludeBots
NaxxramasCore.ForcedPvP.Notify
```

#### Same-account alt mail delay

- Restores AzerothCore's configured `MailDeliveryDelay` for player mail sent between characters on the **same account**.
- Normal player-to-player mail rules remain unchanged.
- GM/customer-support mail, returned mail, COD payments, invalid mail, and self-mail are excluded.

### Playerbot raid consumables

The module contains a Playerbot raid-preparation system. The first profile is **Molten Core**.

Commands available to normal players:

```text
.bot consumables mc
.bot consumables status
.bot consumables clear
```

#### `.bot consumables mc`

Prepares supported controlled bots for Molten Core.

- If the player is in a group/raid, only controlled bots in that same group are prepared.
- If the player is not grouped, controlled bots currently in the world are eligible.
- Applies long-duration consumable effects directly as auras.
- Refreshes tracked consumable auras when the command is rerun.
- Tops usable inventory consumables up to one native maximum stack.
- Supplies **Cache of Mau'ari** when Juju effects require it.
- Supplies sharpening stones or weightstones according to equipped weapon type.
- Supplies class/spec-appropriate weapon oils or Rogue poisons where required.
- Supports Hunter pet consumable preparation when an active pet is present.
- Supports both Alliance and Horde bots.
- Tracks applied raid-consumable auras and warns the controlling player when tracked buffs disappear or expire.

Supported Vanilla classes/spec families include:

- Warrior — Protection and DPS; Arms uses the Warrior DPS profile.
- Paladin — Holy and Retribution.
- Hunter.
- Rogue.
- Priest — healing and Shadow.
- Shaman — Restoration, Elemental, and Enhancement.
- Mage — including Frost-specific consumable handling.
- Warlock.
- Druid — Restoration, Balance, Feral tank, and Feral DPS.

Current intentional exclusions:

- **Protection Paladin** — no automatic Classic Molten Core profile yet.
- **Death Knight** — no Molten Core profile because the class did not exist in Vanilla.

#### `.bot consumables status`

Shows the active tracked consumable profile and reports missing tracked auras.

#### `.bot consumables clear`

Removes the consumable auras tracked by this system and clears its tracking state.

## Dependencies and integrations

### AzerothCore

Designed for **AzerothCore WotLK 3.3.5a**.

### Playerbots

`src/Systems/BotRaidConsumables.cpp` uses Playerbot APIs directly. The current module build therefore expects the server's Playerbots module/code to be available when this system is compiled.

Honor Overflow and Forced PvP also contain Playerbot-aware behaviour.

### Individual Progression

Touch of the Grave reads the Individual Progression configuration when calculating its damage/healing compensation. This prevents the custom racial from being unintentionally double-scaled by progression power adjustments.

### DBC files

Current class/racial work can require matching edits to:

- `Spell.dbc`
- `Talent.dbc`
- `SkillLineAbility.dbc`

Raw DBC files are intentionally excluded from this repository by `.gitignore`. Keep binary client data in the server/client patch distribution and document required rows in [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md).

## Installation / updating

1. **Back up first.**
   - Existing `mod-naxxramas-core` directory.
   - World and characters databases.
   - Current module configuration.
   - Known-working server/client DBC files.

2. Place or update this repository in the AzerothCore modules directory:

   ```text
   /root/azerothcore-wotlk/modules/mod-naxxramas-core/
   ```

3. Review [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md) and apply any required DBC edits.

4. Ensure edited DBC files are present in both:
   - the server data files;
   - the client patch.

5. Review `conf/mod_naxxramas_core.conf.dist` and keep your installed module configuration in sync with any new settings.

6. Re-run CMake when required by the build setup, then compile AzerothCore normally.

7. Start `worldserver`.
   - SQL under `data/sql/db-world/` is for the world database.
   - SQL under `data/sql/db-characters/` is for the characters database.

8. Check the worldserver startup log for module/SQL errors before allowing players back onto the server.

## Module layout

```text
mod-naxxramas-core/
├── conf/
│   └── mod_naxxramas_core.conf.dist
├── data/
│   └── sql/
│       ├── db-characters/
│       │   └── 2026_09_24_00_honor_reset.sql
│       └── db-world/
│           ├── class/racial spell bindings
│           ├── event overrides
│           ├── Touch of the Grave
│           ├── Green Whelp Armor
│           └── Brewfest sober gossip
├── docs/
│   ├── DBC-CHANGES.md
│   └── TROUBLESHOOTING.md
├── src/
│   ├── Class/
│   │   └── Warrior/
│   │       ├── WarriorImprovedRend.cpp
│   │       └── WarriorRendFlurry.cpp
│   ├── Events/
│   │   ├── BrewfestDarkIronAttack.cpp
│   │   ├── BrewfestSober.cpp
│   │   └── HallowsEndShadeOfTheHorseman.cpp
│   ├── Items/
│   │   └── GreenWhelpArmor.cpp
│   ├── Racials/
│   │   ├── BloodElf/
│   │   │   └── BloodElfArcaneTorrent.cpp
│   │   ├── Forsaken/
│   │   │   └── TouchOfTheGrave.cpp
│   │   ├── Orc/
│   │   │   └── OrcBloodFury.cpp
│   │   └── Troll/
│   │       └── TrollBerserking.cpp
│   ├── Systems/
│   │   ├── AltMailDelay.cpp
│   │   ├── BotRaidConsumables.cpp
│   │   ├── ForcedPvP.cpp
│   │   ├── HonorOverflow.cpp
│   │   └── HonorReset.cpp
│   └── NaxxramasCore_loader.cpp
├── .gitignore
├── CHANGELOG.md
└── README.md
```

## Important talent migration note

Changing talent ranks can leave old characters or Playerbots with obsolete spell IDs in `character_talent`.

For the Improved Heroic Strike rework, the old ranks were:

```text
12282 - Rank 1
12663 - Rank 2
12664 - Rank 3
```

The new talent only uses `12282`. A character that still has `12663` or `12664` saved can fail during `_LoadTalents` because those spell IDs are no longer valid talent positions in the new `Talent.dbc`.

See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) before deploying talent changes to an existing character database.

## Compatibility

- AzerothCore WotLK 3.3.5a
- Naxxramas Core patch line: **1.0.6.8.4**
- Current Playerbot raid-consumables code expects Playerbots support.
- Touch of the Grave contains Individual Progression compensation.
- DBC-dependent features require matching server/client DBC data.
