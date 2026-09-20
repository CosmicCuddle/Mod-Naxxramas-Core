# mod-naxxramas-core

Custom gameplay module for **AzerothCore WotLK 3.3.5a**, built for the Naxxramas Core project.

The module groups class changes, racial changes, and server-specific gameplay scripts in one place. Some features also require matching **DBC edits** on both the server and client; those changes are documented in [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md).

## Current features

### Warrior

- **Rend Flurry** (`90054`)
  - 1-point Arms talent, Talent ID `3000`.
  - 15-second active buff.
  - Final intended cooldown: **60 seconds**.
  - Rend affects the primary target and up to **2 additional hostile targets** within **8 yards** of the primary target.
  - Additional targets receive the same Rend rank as the original cast.
  - Bleed-immune targets receive **Rend Flurry Strike** (`90055`) for **150% weapon damage** instead.
  - The replacement strike uses one shared **2-second internal cooldown** via spell `90056`.
  - Triggered extra Rends are free and do not recursively spread.

- **Improved Rend Rank 3** (`90057`)
  - Extends the original Improved Rend talent to 3 ranks.
  - Rank 3 increases Rend bleed damage by **22%**.
  - Each valid Rend periodic damage tick has a **3% chance** to generate **25 Rage**.
  - Spread Rends created by Rend Flurry can proc independently.

- **Improved Heroic Strike** (`12282`)
  - Reworked from a 3-point talent to **1 point**.
  - Reduces Heroic Strike cost by **5 Rage**.

### Orc

- **Blood Fury**
  - Keeps the WotLK offensive Blood Fury bonuses.
  - Restores the older **50% healing-received penalty** for **25 seconds**.
  - Covers spell IDs `20572`, `33697`, and `33702`.

### Troll

- **Berserking** (`26297`)
  - Keeps the WotLK **20% haste** baseline.
  - Restores health-based scaling up to **30% haste** at 10% health or lower.
  - The haste amount is snapshotted when Berserking is activated.

### Blood Elf

- **Mana Tap** (`28734`) restored as a starting Blood Elf racial.
- **Arcane Torrent** keeps the WotLK 2-second silence while restoring the Mana Tap charge/resource interaction.
- Supports the Mana (`28730`) and Energy (`25046`) Arcane Torrent variants.

### Forsaken / DBC-based racial work

The current project also contains DBC-side Forsaken changes that are not implemented as C++ scripts in this module archive. They include:

- **Will of the Forsaken** (`7744`) — custom 5-second Charm/Fear/Sleep immunity implementation with a 120-second cooldown in the current DBC work.
- **Shadow Resistance** (`20579`) — custom **+10 Shadow Resistance** passive.
- **Forsaken Swordsmanship** (`90051`) — +5 Swords and Two-Handed Swords skill.
- **Touch of the Grave** (`90052` / `90053`) — custom Forsaken passive/proc pair.

See the DBC documentation before distributing a client patch.

## Installation

> **Back up your module directory, databases, and known-working DBC files before installing or updating.**

1. Place this repository in your AzerothCore modules directory:

   ```text
   /root/azerothcore-wotlk/modules/mod-naxxramas-core/
   ```

2. Apply the required DBC edits documented in [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md).

3. Ensure the edited DBC files are present in both the server data files and the client patch.

4. Re-run CMake if required by your build setup, then compile AzerothCore normally.

5. Start `worldserver`. The SQL files under `data/sql/db-world/` are intended to be applied through AzerothCore's module SQL update system.

## Module layout

```text
mod-naxxramas-core/
├── data/
│   └── sql/
│       └── db-world/
├── docs/
├── src/
│   ├── Class/
│   │   └── Warrior/
│   │       ├── WarriorImprovedRend.cpp
│   │       └── WarriorRendFlurry.cpp
│   ├── Racials/
│   │   ├── BloodElf/
│   │   │   └── BloodElfArcaneTorrent.cpp
│   │   ├── Orc/
│   │   │   └── OrcBloodFury.cpp
│   │   └── Troll/
│   │       └── TrollBerserking.cpp
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

See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) before deploying the talent changes to an existing character database.

## Compatibility

- AzerothCore WotLK 3.3.5a
- Naxxramas Core patch line: **1.0.6.8.3**
- Requires matching server/client DBC data for DBC-dependent features.

## DBC files used by the current Warrior/racial work

- `Spell.dbc`
- `Talent.dbc`
- `SkillLineAbility.dbc`

Raw DBC files are intentionally excluded from this repository by `.gitignore`. Keep binary client data in your own patch/build distribution and document the required rows here instead.
