# A04 S2 candidate — ordinary corpse loot hidden-slot guard (NOT approved fix)

**Author:** CS01, during CS03's owner-reported break. **Owner contract:** keep *normal WoW/AzerothCore loot* intact; diagnose and fix an item a group member was *not actually entitled* to receive. A real human friend has collected unexpected quest-related items. The owner did **not** authorise changing round-robin rules, creating extra quest items, choosing a named recipient or rewriting drop tables.

**Review-only, default OFF, isolated draft.** This is a narrow defense for one **source-backed candidate discrepancy**, **not evidence of the observed human-friend pickup**. There is no run-time reproduction yet. Do not merge, install, package, enable, or declare this a complete A04 fix. Preserve the separate, docs-only #122 S1 trace, and have CS02/Grok independently review this exact head after primary A02 and F12/F13 work.

## Source argument at pinned versions

- **Core** Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`. `LootView::operator<<` (`LootMgr.cpp`, approximately 995–1100) does not show normal non-FFA, unconditional item slots to an out-of-turn viewer in round-robin. In `GROUP_LOOT` and `NEED_BEFORE_GREED`, non-holder under-threshold ordinary slots are also hidden.
- `Player::StoreLootItem` (`Player.cpp` 13860–13960) resolves the requested item and validates `AllowedForPlayer`, blocking, roll winner and inventory capacity before a grant, but does **not generally repeat the exact ordinary-item round-robin visibility constraint** for the decoded autostore slot.
- `QuestLootProtection.cpp` previously returned true early for all `requestedSlot < loot.items.size()`. A forged or stale `CMSG_AUTOSTORE_LOOT_ITEM` for a hidden ordinary slot can potentially reach `StoreLootItem`. A normal client sending such a slot, and whether the owner's specific item was ordinary versus quest bucket, remain UNKNOWN.
- A true `QuestRequired=1` item already goes through `LootItem::AllowedForPlayer` with `HasQuestForItem` unless a template custom ignore-quest-status flag applies. A `QuestRequired=0` item can be legitimately shared, even when used by a quest; this candidate **does not make it personal loot**.

## Proposed opt-in rule

Only in the **existing, enabled, creature-corpse** `CMSG_AUTOSTORE_LOOT_ITEM` hook, and only for a normal `loot.items` slot:

- New suboption `NaxxramasCore.QuestLootProtection.RestrictHiddenOrdinarySlots = 0`; missing key also means OFF. Existing `QuestLootProtection.Enabled=0` master stays OFF. When either is OFF, there is no change.
- `RoundRobin` with an active, different looter -> deny a hidden **unblocked, ordinary, unconditional, non-FFA, non-winner, non-special** item request.
- `GroupLoot` / `NeedBeforeGreed` -> additionally require `is_underthreshold`; higher-quality visible/rolled items stay native.
- The turn owner must still be present and grouped, in world and on the **same live map and instance**. If departed/missing, fail open. This is deliberately more conservative than the native viewer hide when the turn is stale.
- Released turn, own turn, unrecognized slot, disabled setting, master/FFA loot mode, personal `ITEM_FLAG_MULTI_DROP`, conditional items, roll winners/blocked items, special follow-loot-rules, other loot sources, and quest-specific slots are **left to native**. No new owner entitlement calculation is used.
- Refusal is a single `LOOT_ERROR_LOCKED` packet and skipping that autostore opcode; no item counts, inventory, loot flags or `roundRobinPlayer` are changed. Debug stays separately OFF.

The pure `QuestLootNormalSlotPolicy.h` decision is native-testable without a running worldserver. The actual server hook in `QuestLootProtection.cpp` gathers current facts and applies it only after existing creature/range/group/method guards.

**Important limitation:** This is intended to reject only an *invisible* ordinary item slot request, not arbitrary human group quest pickup. It will **not solve an unintended quest item erroneously flagged as ordinary and still visible to an eligible turn-holder**, nor a Playerbot direct award/GO/master/roll bypass. It cannot be called the first full functional fix without item-level evidence tying it to the reported complaint.

## Verification and go/no-go

1. Validate `tests/quest_loot_normal_slot_policy.cpp` with C++17 and C++20, warnings as errors, and `tests/test_a04_native_hidden_slot_contract.py` on **exact SHA** (pure policy/source test, NOT server link).
2. Independent review against the pinned core of all loot-view cases and hook ordering, particularly Master Loot, unchanged ordinary legitimate award, released holder, owner offline, `ITEM_FLAG_MULTI_DROP`, `follow_loot_rules`, and group threshold values.
3. Full **pinned Worldserver compile/link and symbol check** using disposable GitHub runners. Confirm missing new config key leaves all behavior unchanged. The native test alone cannot prove C++ hook integration or ABI.
4. Investigate the actual reported quest/item/creature-or-GO, `QuestRequired`, custom quest ignore flag, conditions, item template, method and turn-holder (read-only). If the observed award is otherwise stock-valid, do not silently block it. If it is an invalid quest-specific pickup or a different award path, revise the solution accordingly.
5. Complete owner-approved, backed-up two-human controlled staging test, then all bot and multi-map regressions. No live test or server changes in this draft.

**Known test limitations:** The pure model does not exercise AzerothCore's live slot mapping, group state, `AllowedForPlayer`, map threads, actual packets or saved inventory. Current module has no global ownership state. Tests are review evidence, not S4/owner gameplay acceptance.

## Rollback and capacity

Both switches default 0. No SQL or DBC changes and no item-generation modifications. The branch is independent of Claude's frozen #125/#127/#128 and Grok's #126. The 50/50 CS01/CS02 temporary work allocation remains until the owner reports Claude's return. The first candidate for **owner in-game** testing still requires actual A04 and A02 functional fixes plus F12 **physical** Cathedral/Armory portals, F13 Atiesh outdoors and #120 P0+B10, with reviewed fully linked CI, explicit owner permission and backups.
