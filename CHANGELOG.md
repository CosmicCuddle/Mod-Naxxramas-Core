# Changelog

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

### Database / compatibility

- Added world SQL bindings for Rend Flurry and racial scripts.
- Documented existing-character migration risk from obsolete Improved Heroic Strike talent ranks (`12663`, `12664`).
- Added troubleshooting steps for `_LoadTalents` / `ASSERT(talentPos)` crashes.
