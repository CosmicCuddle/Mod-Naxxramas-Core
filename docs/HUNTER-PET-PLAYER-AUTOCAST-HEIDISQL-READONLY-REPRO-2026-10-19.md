# Human Hunter pet autocast — optional read-only HeidiSQL evidence checklist

**Prepared 19 October 2026, NOT executed on a realm.** Use only **after the owner separately approves** a staging investigation. The initial problem is autocast ON/OFF resetting on the same player-controlled Hunter pet, potentially during IP legal-rank reconciliation. This is not an Altbot/Playerbots test.

## Before any later staging test

1. Identify the actual running AzerothCore, Individual Progression and Naxxramas Core revisions privately. CI pinned SHAs are **not** proof of the installed versions.
2. Arrange a **restorable full characters DB backup**, exact Worldserver binary and effective configuration backup on an isolated staging setup; verify restoration **before changing a pet's spells or progression**. This document performs no backup.
3. Select a real player-owned Hunter and one specific existing saved pet from your test copy. Record its **PetNumber** privately and avoid including player/account names, passwords or raw SQL dumps in GitHub.
4. Choose two currently legitimate native-autocastable pet abilities, one manually set **ON**, the other deliberately **OFF**. Never use a spell that IP has not legitimately taught, and do not artificially grant ranks.

## HeidiSQL — read-only comparison of existing `pet_spell`

Select the server's **characters database** in HeidiSQL. Confirm the pet's saved PetNumber from authorized staging records; it is **not** its ephemeral in-world pet GUID. Enter that number in the first statement.

```sql
-- READ ONLY except a local SQL-session variable. Replace 0 with
-- the test pet's saved numeric PetNumber; never use a player GUID.
SET @hunter_test_pet_number := 0;

-- Existing native AzerothCore pet-spell table and native "active" state.
SELECT spell, active
FROM pet_spell
WHERE guid = @hunter_test_pet_number
ORDER BY spell;
```

**The query does not toggle anything.** `SET @hunter_test_pet_number` changes only a local connection variable, not a table. The actual data schema in the pinned Grimfeather core is `pet_spell (guid, spell, active)`; **do not use** a fabricated `character_pet_spell` table. Raw `active` numbers must be compared with observed game UI state and the installed core's `ActiveStates` enum; do not guess what an unfamiliar number represents.

Capture the **spell IDs and their active values**, not the pet or owner name, in a private local note. Changes in an in-memory state are not always immediately written to the database—first ensure the legitimate pet save/logoff happened as part of the approved test.

## Exact differential investigation (staging only)

| Checkpoint | Action on the same saved pet | What to compare |
| --- | --- | --- |
| A | Legitimately save an ON and OFF ability | Native saved spell IDs/active values and in-game UI before reload |
| B | Normal dismiss/re-summon and save without acquiring new IP dummy/training spells | Did either same-rank native spell change state? If yes, **do not** assume rank change was responsible |
| C | Logout/login and save without new rank training | Does the same native rank remain ON/OFF? Note pet number |
| D | In a separately restorable staging scenario, legitimately advance/change IP-allowed pet rank | Compare old legal rank before IP to new legal rank after IP; check whether an old rank is removed and missing keepId is relearned |
| E | Repeat with deliberately OFF as well as ON and another eligible ability | Do not convert default-disabled into evidence of human OFF intent |
| F | Stable swap or genuinely different newly tamed pet | Confirm a new pet does not inherit previous saved-pet choices |

**Important:** The pinned native load sequence is `_LoadSpells` -> `InitLevelupSpellsForLevel`; IP separately runs delayed `checkHunterPetSpells`. A recurrent reset on resummon might involve native family-level rank reinitialization before IP pruning. This is only a source-backed **conditional possibility**: the actual pet's family, learned IDs, progression stage and spell chains decide whether that sequence changes anything.

## Stop conditions

Stop and restore staging if the pet loses a legitimate ability, wrong rank appears, a new pet inherits another pet's settings, the installed core/IP differs from the pinned source and invalidates our assumptions, or the effective module/realm configuration cannot be verified.

Never directly `UPDATE`, `DELETE` or `INSERT` into `pet_spell` as a workaround; a hand-edited row can be overwritten by in-memory pet save, and can conceal the actual root cause. We are testing a behavior, **not repairing characters by SQL**.

Only share a small **redacted** table of `spell` and `active` results plus which checkpoint was tested. Never paste real player identifiers, connection details or entire character tables into public GitHub PR discussions.

## Development decision afterwards

If no rank changes but ON/OFF still resets, investigate core native loading/actionbar behavior first. If IP's remove-then-relearn demonstrably causes the loss, prefer preserving the actual former native active state **inside the same accepted legal-rank transition**, with no new spell grant or sidecar SQL. The pinned public PetScript hooks do not currently prove a reliable atomic module-only handoff. A truly required IP source patch needs separate, explicit owner approval; it is **not** authorised by this diagnostic checklist.

This document is a prepared operator aid. Nothing was read from, connected to or changed on the user's server.
