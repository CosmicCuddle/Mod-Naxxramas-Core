# Troubleshooting

## `_LoadTalents` assertion / `ASSERT(talentPos)`

AzerothCore loads saved talent spell IDs from `character_talent`. If a saved spell is no longer present as a valid rank in the current `Talent.dbc`, login can fail at `_LoadTalents`.

This is especially relevant after changing Improved Heroic Strike from 3 ranks to 1 rank.

Old Improved Heroic Strike talent spell IDs:

```text
12282 - Rank 1
12663 - Rank 2
12664 - Rank 3
```

The new tree only keeps `12282`.

### Find affected characters

Run this against the characters database:

```sql
SELECT
    ct.guid,
    c.name,
    ct.spell,
    ct.specMask
FROM character_talent AS ct
LEFT JOIN characters AS c
    ON c.guid = ct.guid
WHERE ct.spell IN (12663, 12664)
ORDER BY ct.guid;
```

### Back up before changing anything

```sql
CREATE TABLE IF NOT EXISTS character_talent_backup_10683
LIKE character_talent;

INSERT IGNORE INTO character_talent_backup_10683
SELECT *
FROM character_talent
WHERE spell IN (12282, 12663, 12664);
```

### Full talent wipe for one offline character

If a specific character must have all talents removed, stop the worldserver first and use the character GUID:

```sql
DELETE FROM character_talent
WHERE guid = YOUR_CHARACTER_GUID;
```

Verify:

```sql
SELECT *
FROM character_talent
WHERE guid = YOUR_CHARACTER_GUID;
```

A normal offline `.reset talents CharacterName` command sets an at-login reset flag, but a character with an invalid saved talent can crash during `_LoadTalents` before the at-login reset is processed. Directly cleaning the invalid `character_talent` rows avoids that problem.

## Arms tree appears completely blank

Check `Talent.dbc` ordering. Custom Talent ID `3000` must be physically placed according to:

```text
TabID -> TierID -> ColumnIndex
```

Do not append it at the end of the DBC.

## Rend Flurry shows the wrong cooldown

Check `Spell.dbc` row `90054` on both client and server:

```text
RecoveryTime = 60000
```

If it is still `90000`, the cooldown will remain 1.5 minutes.

## Improved Rend tooltip still says 1%

The server C++ proc is currently set to:

```cpp
roll_chance_i(3)
```

Update the client/server `Spell.dbc` description for `90057` so it says **3%** as well.
