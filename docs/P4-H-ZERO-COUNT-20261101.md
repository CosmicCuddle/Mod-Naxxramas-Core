# Master Loot P4-H: malformed zero-count quest item guard

## Why this exists
The original `GiveQuestSlot` in default-OFF P4-H #272 checks the leader's personal `QuestItem::is_looted` and shared `LootItem::is_looted`, but not `LootItem::count`. A deliberately malformed row with count **0** and both flags false would proceed to `CanStoreNewItem` and potentially inventory/counter/notification paths. **It has NOT been demonstrated that normal AzerothCore corpse or chest loot generation can create this state or that the owner's server has experienced it.** It is defensive, not a confirmed live exploit.

## Changed behavior (only on malformed rows)
The separate CS01 DRAFT guard returns `Result::AlreadyLooted` before attempting an inventory transfer if `item.count == 0`. The existing per-viewer slot mapping, flags, normal positive-stack award order, other error outcomes, handler hook pass-through, bot behavior, and Master Loot configuration are unchanged. Both corpse and GameObject/chest paths call the same header helper. The Core owns the earlier Master Loot authorization checks.

## Executable negative fixtures
- `tests/p4_h_master_loot/master_loot_harness.cpp`: uses original pinned loot bodies, sets 0 stack AFTER opening a real populated corpse; checks both personal/shared unlooted flags, no received item, unchanged count, no removal notification, unchanged `unlootedCount`. Expected harness check count rises from 29 to **30**.
- `tests/p4_h_interop/go_loot_harness.cpp`: same inconsistent state in a group-rules chest with actual personal list; checks fixture and refusal state in **two new assertions** (GO count 13 → **15**).
- Existing stock-vs-module mutants updated with the new guarded source line; new zero-guard-deletion mutant included in both original P4-H and interop test lists to prove the new negative fixtures detect its absence.
- `tests/test_p4_h_zero_count_source.py`: portable source contract that checks the count test precedes inventory and state writes, fixtures exist and the feature remains OFF.
- Existing pinned A04 native harnesses still require actual pinned Core data. They have **not** been run locally in this Maintenance session; hosted checks must demonstrate success on this exact HEAD.

## Custom modification register entry
**Key:** NAXX-CS01-P4H-ZERO-COUNT-20261101. **Owner:** CS01 Maintenance (Claude is on break). **Branch:** `maintenance/cs01-p4h-zero-count-20261101`, stacked on combined P1–P4/H1/H2/GO test DRAFT #275 at `0fe049975166e614633bce9e5c77b9f8b686dc54`. **Files:** `src/Systems/MasterLootQuestGive.h`, pinned Master Loot/GO harnesses, mutant lists, source test, CI workflow and this record. **Dependencies:** default-OFF `NaxxramasCore.MasterLootQuestGive.Enabled = 0`, pinned Core/Playerbots/IP versions, correct loot permissions and quest-slot presentation, unchanged config/DBC/SQL. **Risks:** the malformed state is hypothetical; stricter refusal might differ from stock behavior for abnormal custom loot scripts. **Source tested:** modification made, static checks; **native/CI/gameplay:** unverified until exact HEAD evidence. **Deployed:** NO. **Rollback:** revert only this stacked PR, keep P4-H #272/#273/#275 and all historical/custom default-OFF functions; no data migrations required. **Approval:** owner production approval required, including staged multi-human corpse/chest Master Loot tests and rollback confirmation.

No live owner process, database, client, configuration, archive, quest status, money or loot was changed.
