# DBC changes

This module is not completely standalone. Several features rely on matching WotLK 3.3.5a DBC edits.

Always back up the original rows **and** the complete known-working DBC files before editing them. The server and client must use matching data.

## Final intended Warrior rows

### Spell.dbc

#### 12282 — Improved Heroic Strike

Key final behavior:

```text
Effect[0]           = 6
EffectAura[0]       = 107   (SPELL_AURA_ADD_FLAT_MODIFIER)
EffectMiscValue[0]  = 14    (SPELLMOD_COST)
EffectBasePoints[0] = -51   (effective -50 internal = -5 displayed Rage)
```

Description:

```text
Reduces the cost of your Heroic Strike ability by $/10;s1 rage points.
```

#### 90054 — Rend Flurry

Key final values:

```text
ID                   = 90054
RecoveryTime         = 60000
CategoryRecoveryTime = 0
DurationIndex        = 8
PowerType            = 1
ManaCost             = 0
StartRecoveryCategory = 0
StartRecoveryTime     = 0
Effect[0]            = 6
EffectAura[0]        = 4
SpellClassSet        = 4
SpellIconID          = 2751
```

Final intended cooldown: **60,000 ms = 60 seconds**.

> Release check: an earlier working DBC used `RecoveryTime = 90000`. Make sure the release DBC is changed to `60000` before packaging.

#### 90055 — Rend Flurry Strike

```text
Effect[0]           = 31
EffectBasePoints[0] = 149
```

The raw base points value `149` produces **150% weapon damage**.

#### 90056 — Rend Flurry Internal Cooldown

```text
DurationIndex = 39
```

This is the **2-second** shared replacement-strike internal cooldown aura.

#### 90057 — Improved Rend Rank 3

```text
EffectBasePoints[0] = 21
```

The raw value `21` produces the intended **+22% Rend damage**.

Final description should state:

```text
Increases the bleed damage done by your Rend ability by 22%. In addition, each periodic damage tick from Rend has a 3% chance to generate 25 rage.
```

The 3% proc itself is implemented server-side in `WarriorImprovedRend.cpp`.

> Release check: the currently uploaded DBC copy still contains the older `1%` wording. Update the text to `3%` before packaging the final client DBC.

## Talent.dbc

### 124 — Improved Heroic Strike

```text
SpellRank_1 = 12282
SpellRank_2 = 0
SpellRank_3 = 0
```

### 127 — Improved Rend

```text
SpellRank_1 = 12286
SpellRank_2 = 12658
SpellRank_3 = 90057
SpellRank_4-9 = 0
```

### 3000 — Rend Flurry

```text
ID              = 3000
TabID           = 161
TierID          = 3
ColumnIndex     = 3
SpellRank_1     = 90054
SpellRank_2-9   = 0
PrereqTalent_1  = 121
PrereqTalent_2  = 0
PrereqTalent_3  = 0
PrereqRank_1    = 2
PrereqRank_2    = 0
PrereqRank_3    = 0
Flags           = 1
RequiredSpellID = 0
CategoryMask_1  = 0
CategoryMask_2  = 0
```

`PrereqRank_1 = 2` is zero-based and therefore requires **Deep Wounds 3/3**.

### Critical Talent.dbc ordering requirement

The WotLK client requires Talent records to be ordered by:

```text
TabID -> TierID -> ColumnIndex
```

Do not simply append Talent ID `3000` to the end of the file. Incorrect ordering can make the entire Arms tree appear blank.

Also, do **not** restore the earlier experimental Talent ID `90054`. The final talent is:

```text
Talent ID = 3000
Spell ID  = 90054
```

## SkillLineAbility.dbc

### 90054 — Rend Flurry

```text
ID            = 90054
SkillLine     = 26
Spell         = 90054
RaceMask      = 0
ClassMask     = 1
AcquireMethod = 1
```

`SkillLine = 26` is Arms and `ClassMask = 1` is Warrior.

## Current racial DBC work

### 7744 — Will of the Forsaken

The current custom Spell.dbc data uses:

```text
RecoveryTime  = 120000
DurationIndex = 28
Effect[0-2]   = APPLY_AURA
Aura[0-2]     = mechanic immunity
Misc values   = Charm / Fear / Sleep mechanics
```

The current English description is:

```text
Provides immunity to Charm, Fear and Sleep while active. May also be used while already afflicted by Charm, Fear or Sleep. Lasts 5 sec.
```

### 20579 — Shadow Resistance

The current custom row is a flat Shadow Resistance passive:

```text
Effect[0]           = APPLY_AURA
EffectBasePoints[0] = 9
EffectAura[0]       = 22
EffectMiscValue[0]  = 32
```

Raw base points `9` gives **+10 Shadow Resistance**.

### 90050 — Ancestral Macecraft

```text
Skill with Maces and Two-Handed Maces increased by 5.
```

### 90051 — Forsaken Swordsmanship

```text
Skill with Swords and Two-Handed Swords increased by 5.
```

### 90052 / 90053 — Touch of the Grave

`90052` is the racial passive/proc aura and has a **5% proc chance** in the current DBC work. It triggers `90053`.

The current description for `90052` states that attacks and damaging spells can drain the target, dealing Shadow damage and healing the caster for the same amount, with a 15-second internal limitation described in the tooltip.

## Backup checklist

Known rows to preserve for this patch line:

```text
Spell.dbc
7744  - Will of the Forsaken
20579 - Shadow Resistance
12282 - Improved Heroic Strike
90050 - Ancestral Macecraft
90051 - Forsaken Swordsmanship
90052 - Touch of the Grave passive
90053 - Touch of the Grave proc
90054 - Rend Flurry
90055 - Rend Flurry Strike
90056 - Rend Flurry Internal Cooldown
90057 - Improved Rend Rank 3

Talent.dbc
124  - Improved Heroic Strike
127  - Improved Rend
3000 - Rend Flurry

SkillLineAbility.dbc
90054 - Rend Flurry
```
