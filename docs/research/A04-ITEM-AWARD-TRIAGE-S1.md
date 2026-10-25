# A04 — Human-friend award evidence triage (S1 synthetic; DO NOT MERGE)

**Purpose.** When a quest-related item seems available to the wrong human party member, avoid mistaking *corpse sparkle*, an ordinary shared loot turn, or an independent `ITEM_FLAG_MULTI_DROP` copy for an invalid successful award. Preserve **normal AzerothCore group loot**; do not create extra personal drops, override the current looter, or make ownership exclusive.

**Scope.** `tests/test_a04_item_award_triage_s1.py` contains a read-only, synthetic **evidence classifier**, not a Worldserver implementation or a validator of real private SQL. All outputs are diagnostic categories and deliberately say `proves_invalid_loot=False` and `permits_runtime_fix=False`. No packet interception, DB connection, character state, addon, or live server execution.

## Input field meanings

| Field | Evidence required / pitfall |
| --- | --- |
| `item_id` | Exact numeric item entry from the affected real pickup; never infer from quest name |
| `source_resolved` | True only for a defensibly resolved generated loot path; a *one-hop* lookup that still points at another reference is **not enough** |
| `needs_quest` | The effective generated row's `QuestRequired` after source resolution; NOT simply “this item is needed by a quest” |
| `friend_has_quest_for_item` | The native `HasQuestForItem(itemId)` result at that moment; having a named quest in the log alone is not necessarily this predicate |
| `ignore_quest_status` | `item_template.flagsCustom & 0x0002` (NOT `FlagsExtra`) |
| `multi_drop` | `item_template.Flags & 0x00000800`; do not confuse with FREE_FOR_ALL group loot method |
| `successful_award` | Actual inventory item receipt vs sparkle/loot display/failed pickup |
| `shared_one_copy_depleted` | Did the same one-copy world drop disappear, or did friend receive an independent copy? The model records this but **cannot** decide it from source flags alone |
| `source_kind` | Current module packet guard is creature-corpse autostore only; chest/roll/master/bot paths need separate proof |

Existing read-only SQL templates: `docs/research/A04-READ-ONLY-ITEM-LOOT-PREFLIGHT.md` (no statements run here). Do not paste a private world database, character names, GUIDs, account details or raw live logs into a public PR. Execute queries on a **read-only clone/account** only if separately approved.

## Interpretation and guardrails

1. Unknown item, custom flags, source or an incomplete reference chain → **NEED_SOURCE_EVIDENCE**. No assumption about eligibility.
2. `QuestRequired=1`, `HasQuestForItem=false`, no custom ignore, and **confirmed** award → **REVIEW_POSSIBLE_AWARD_PATH**. Pinned native `StoreLootItem` is expected to reject under the quest-status predicate, but source path/other module hooks, group turn and actual installed behavior need investigation. This is **not proof of a live bug**.
3. Same fields but only sparkle, missing award data or failed click → **EXPECTED_NATIVE_DENIAL**, not a successful incorrect award.
4. `ITEM_FLAGS_CU_IGNORE_QUEST_STATUS` may explicitly bypass the quest-status requirement; inspect native conditions and other restrictions.
5. `QuestRequired=0` → an **ordinary loot item** that may still be a quest objective. Do not declare it personal or ineligible merely because the friend lacks the quest. Check native group allocation and looter turn.
6. `ITEM_FLAG_MULTI_DROP` → a possible separate per-player copy, not automatically your one-copy drop being stolen.
7. Friend eligible for the item and the drop is a single shared copy → **POTENTIALLY_ELIGIBLE_NEEDS_TURN_EVIDENCE**; this is not inherently a defect.

**Explicit limits:** The classifier does not emulate `LootView`, native group loot permissions, `ConditionMgr`, `isAllowedToLoot`, `LootItem::AllowedForPlayer`, scripts, player inventory mutations, world loot sources, rolls, master loot or a running module. It cannot tell whether any item was actually mis-awarded. Its purpose is to stop an unsafe diagnosis or broad gameplay change before the exact award source has been identified.

## Local-only test

```bash
python3 -m unittest discover -s tests -p 'test_a04_item_award_triage_s1.py' -v
```

The tests use fabricated item entry **7777** and no owner data. A green result is S1 model evidence only, not full C++/Worldserver compilation or game testing. Keep #122 draft and leave #129 and Claude's #132 untouched.