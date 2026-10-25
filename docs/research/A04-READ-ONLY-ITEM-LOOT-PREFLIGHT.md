# A04 — Safe read-only item / loot-template preflight (owner data never committed)

**Research-only, not executed against an owner database.** Use this when a *specific* incorrectly looted quest item becomes known. Never paste a private SQL dump, character name, account ID, GUID, or query results containing personal player information into a public GitHub issue. The current diagnosis has **no confirmed item ID or quest ID** from the reported human-friend pickup. The task remains to fix a stock *eligibility violation*, not make all quest-related drops exclusive.

## Public source facts (verified exact pin)

At `Grimfeather/azerothcore-wotlk` commit `8daffdabe9202c228e45d833c9a1d399597a15cd`:

- `src/server/game/Globals/ObjectMgr.cpp` `LoadItemTemplates` selects **`entry`**, **`name`**, **`Flags`**, **`FlagsExtra`**, and **`flagsCustom`** from `item_template`.
- `src/server/game/Entities/Item/ItemTemplate.h`: `ITEM_FLAG_MULTI_DROP = 0x00000800` (**2048**, in the regular `Flags` column); `ITEM_FLAGS_CU_IGNORE_QUEST_STATUS = 0x0002` (in **`flagsCustom`**); `ITEM_FLAGS_CU_FOLLOW_LOOT_RULES = 0x0004` (also in `flagsCustom`). Do **not** misread `FlagsExtra` as `flagsCustom`.
- `src/server/game/Loot/LootMgr.cpp`: `needs_quest` comes from the generated source loot row's `QuestRequired` setting; **`QuestRequired = 0`** means an ordinary shared `loot.items` bucket even if the item happens to be required by a quest. `ITEM_FLAG_MULTI_DROP` controls `freeforall` **independently**. These are two independent bits of evidence.
- Public `data/sql/base/db_world/creature_loot_template.sql` has `Entry`, `Item`, `Reference`, `Chance`, `QuestRequired`, `LootMode`, `GroupId`, `MinCount`, `MaxCount`, `Comment`. `Entry` is a **loot template ID, not necessarily a creature entry**, and `Reference != 0` can route via a separate referenced template; don't assume a matching direct row describes every way a mob drops an item.

## Read-only SQL (Kiera3 / HeidiSQL)

Run against a **read-only clone or SQL account**. Replace `123456` with an actual item ID only when known. Each query is a SELECT; no UPDATE/INSERT/DELETE/DDL is present. The first query is intentionally parameterized by a session variable so it cannot accidentally target every item.

```sql
-- A04: read-only item classification. Replace 123456 with the actual item ID.
SET @a04_item_id := 123456;

SELECT
    entry AS item_id,
    name AS item_name,
    Flags AS flags_raw,
    flagsCustom AS flags_custom_raw,
    (Flags & 2048) <> 0 AS has_individual_multi_drop_flag,
    (flagsCustom & 2) <> 0 AS ignores_quest_status,
    (flagsCustom & 4) <> 0 AS follows_group_loot_rules,
    StartQuest,
    MaxCount
FROM item_template
WHERE entry = @a04_item_id;
```

```sql
-- Direct creature-loot rows for this item. Empty results do not rule out
-- referenced loot templates, GO/chests, spells or script-generated grants.
SELECT Entry AS loot_template_id, Item AS item_id, Reference,
       QuestRequired, Chance, LootMode, GroupId, MinCount, MaxCount, Comment
FROM creature_loot_template
WHERE Item = @a04_item_id
ORDER BY Entry, Reference, GroupId;
```

```sql
-- Direct game-object/chest loot rows. Again, a blank result is not proof
-- the item cannot be awarded through references or other source types.
SELECT Entry AS loot_template_id, Item AS item_id, Reference,
       QuestRequired, Chance, LootMode, GroupId, MinCount, MaxCount, Comment
FROM gameobject_loot_template
WHERE Item = @a04_item_id
ORDER BY Entry, Reference, GroupId;
```

```sql
-- One-level reference-loot evidence for creature and GO templates.
-- Preserve both the outer-row and referenced-row QuestRequired flags:
-- neither alone proves the effective item eligibility of a nested chain.
SELECT 'creature' AS source_kind,
       c.Entry AS source_loot_template_id,
       c.Reference AS referenced_loot_template_id,
       r.Item AS item_id,
       c.QuestRequired AS outer_quest_required,
       r.QuestRequired AS referenced_quest_required,
       r.Reference AS deeper_reference_id,
       c.LootMode AS outer_loot_mode,
       r.LootMode AS referenced_loot_mode
FROM creature_loot_template AS c
JOIN reference_loot_template AS r ON c.Reference = r.Entry
WHERE r.Item = @a04_item_id

UNION ALL

SELECT 'gameobject' AS source_kind,
       g.Entry AS source_loot_template_id,
       g.Reference AS referenced_loot_template_id,
       r.Item AS item_id,
       g.QuestRequired AS outer_quest_required,
       r.QuestRequired AS referenced_quest_required,
       r.Reference AS deeper_reference_id,
       g.LootMode AS outer_loot_mode,
       r.LootMode AS referenced_loot_mode
FROM gameobject_loot_template AS g
JOIN reference_loot_template AS r ON g.Reference = r.Entry
WHERE r.Item = @a04_item_id
ORDER BY source_kind, source_loot_template_id, referenced_loot_template_id;
```


## Source-template lookup after a candidate item ID is known

These additional **read-only, one-reference-hop** searches map a candidate item to the *creature template* or *chest/fishing-hole gameobject template* that references its loot template. The first four queries identify item and loot rows, but a `creature_loot_template.Entry` is **not necessarily** a `creature_template.entry`. Pinned `CreatureData.h` has `CreatureTemplate::lootid`; pinned `GameObjectData.h` has `GameObjectTemplate::chest.lootId` at data index **1**, and `fishinghole.lootId` also at index **1**. This is template-level identification, **not proof** a specific player killed or opened that source. Both queries deliberately exclude further nested references, scripts, spells, skinning, pickpocketing and other award routes.

```sql
-- Creature template -> creature loot template; direct or one reference hop.
-- A repeated source can have multiple matching loot rows; keep every row.
SELECT c.entry AS creature_entry, c.name AS creature_name,
       c.lootid AS creature_loot_template_id,
       l.Entry AS matched_outer_loot_template_id,
       l.Item AS direct_item_id, l.QuestRequired AS outer_quest_required,
       l.Reference AS reference_id,
       r.Item AS referenced_item_id, r.QuestRequired AS referenced_quest_required,
       r.Reference AS deeper_reference_id
FROM creature_template AS c
JOIN creature_loot_template AS l ON c.lootid = l.Entry
LEFT JOIN reference_loot_template AS r ON l.Reference = r.Entry
WHERE l.Item = @a04_item_id OR r.Item = @a04_item_id
ORDER BY c.entry, l.Entry, l.Item, r.Item;
```

```sql
-- Chest type=3 and fishing-hole type=25 use Data1 as their GO loot ID.
-- DO NOT join Data1 for other GO types: it has a different meaning.
SELECT g.entry AS gameobject_entry, g.name AS gameobject_name,
       g.type AS gameobject_type, g.Data1 AS go_loot_template_id,
       l.Entry AS matched_outer_loot_template_id,
       l.Item AS direct_item_id, l.QuestRequired AS outer_quest_required,
       l.Reference AS reference_id,
       r.Item AS referenced_item_id, r.QuestRequired AS referenced_quest_required,
       r.Reference AS deeper_reference_id
FROM gameobject_template AS g
JOIN gameobject_loot_template AS l ON g.Data1 = l.Entry
LEFT JOIN reference_loot_template AS r ON l.Reference = r.Entry
WHERE g.type IN (3, 25)
  AND (l.Item = @a04_item_id OR r.Item = @a04_item_id)
ORDER BY g.entry, l.Entry, l.Item, r.Item;
```

**Interpretation limits:** `QuestRequired` on outer and referenced rows is *raw evidence*, not a calculated effective entitlement; the source item may be obtained through a different route as well. In the GO query, the `Data1` interpretation is constrained to **chest/fishing-hole types**; do not treat generic GO Data1 as a loot pointer. An absent result does not disprove the owner's incident. These are templates, not character loot logs or an instrumented reproduction. Query only on a read-only copy/account and do not commit any private outputs.

**Reference limitation:** The query covers **one reference hop** only. A result with `deeper_reference_id != 0` signals another reference to investigate separately; a blank result does **not** prove that nested references, scripts, spells or other loot sources are absent. `outer_quest_required` and `referenced_quest_required` are raw table columns, not a proven resolved runtime rule. Public `reference_loot_template` DDL at the same pin confirms `Entry`, `Item`, `Reference`, `QuestRequired`, and `LootMode`. Do not commit owner world-row results.

**Read-only SQL convenience note:** `SET @a04_item_id` changes only the local client session variable; it does not modify the world database. If using a server account restricted to `SELECT`, replace `@a04_item_id` with a literal constant and omit `SET`. The query is not meant to be executed with the placeholder 123456 as a real fact.

All six query examples are SELECT-only after the optional session-local parameter declaration. Run only when an actual item ID is identified, on a backed-up read-only database or clone.

## Decision matrix after results exist

| Evidence | Stock interpretation | Next check |
| --- | --- | --- |
| Direct `QuestRequired=1`, viewer lacks quest, no ignore status | Native `AllowedForPlayer` should reject at inventory award | Prove actual wrong recipient; inspect other add-item/award handlers |
| `QuestRequired=0`, non-MULTI_DROP | Ordinary shared item, even if relevant to a quest | Establish group method and actual turn; don't invent personal ownership |
| `Flags & 2048 != 0` | Native per-player FFA rights; no loss of other's entitled copy | Trace `PlayerFFAItems` membership and per-player `is_looted` |
| `flagsCustom & 2 != 0` | Pinned source can bypass quest-status gating | Distinguish custom intentional data from unexpected acceptance |
| `flagsCustom & 4 != 0` | Item follows special native group rules | Do not apply ordinary non-special hidden-slot prototype |
| No matching direct source row | **Unknown**: reference-template / GO / other route | Track actual source GUID/type and loot-template/reference chain read-only |

The key remaining evidence is a **specific player-versus-friend pickup**: item ID, quest objective, the creature/GO source, whether both characters actually had that quest active, group loot mode, and whether the alleged wrong player really received an inventory item. Do not request personal names or raw private data. A successful **synthetic test or Worldserver link** cannot establish that the owner's reported client behaviour violated native rules.

## Guardrails

1. Never run write queries or import/migrate tables just for this investigation.
2. Retain original server/database backups; after identifying candidate item rows, preserve the exact old values for rollback.
3. Do not implement personal quest copies, owner-reservation or hard-coded quest item lists.
4. Do not claim this preflight proves the cause until source data and a controlled human-to-human reproduction agree.
5. Any candidate live change remains blocked pending Grok reciprocal review, exact-head native/pinned Worldserver link, and owner-approved backed-up staged test.
