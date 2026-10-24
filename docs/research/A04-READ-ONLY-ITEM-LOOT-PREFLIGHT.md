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

**Read-only SQL convenience note:** `SET @a04_item_id` changes only the local client session variable; it does not modify the world database. If using a server account restricted to `SELECT`, replace `@a04_item_id` with a literal constant and omit `SET`. The query is not meant to be executed with the placeholder 123456 as a real fact.

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
