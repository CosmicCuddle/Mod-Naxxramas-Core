# P4 H1 + H2 + original Core locked quest slot: test-only bridge, 7 November 2026

**Owner:** CosmicCuddle. **Maintainer:** Server-Side-Maintenance. **Purpose:** protect the established human-to-human quest-item denial and legitimate corpse loot while checking the meaning of a *visible but LOCKED* item row. **Exact source base:** owner Naxx [integrated DRAFT #292](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/292) `51d0611476358286505aed3ca806ea250f644f66`, with existing owner H0/H1/H2 source **unchanged**. Legacy original-Core harness pinned to Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`, already used for historical A04/P4 H1 and H2 test fixtures. Does **not** substitute for owner Core2 native link or 3.3.5a gameplay.

## Why one combined check adds value

- P4 H1 `QuestLootPickupAuthorization.h::SlotVisibleInServerView` is a **slot visibility** gate. Its serializer consumes the item slot type byte but deliberately does not treat all `LOOT_SLOT_TYPE_LOCKED` rows as forbidden. It defers final award eligibility to the original Core `Player::StoreLootItem`. A locked quest row can thus be visible and pass H1's *visibility* test without being awarded.
- P4 H2 `QuestLootSparkleGuard.h::ViewOffersSomething` treats a **locked QUEST row** as not actionable. It intentionally keeps sparkles on **locked normal Master Loot rows**, ordinary loot, valid normal quest rows and gold. Blanket-rejecting all LOCKED rows would break established Master Loot behaviour.
- P4 H0's `HideOwnSatisfiedQuestRows` preserves exact viewer-specific quest flags during these passive views. Interleaved checks must not consume a shared quest item or prevent the rightful owner from collecting it.
- Existing [P4 issue #109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109) records an OWNER-OBSERVED real-gameplay H2 failure on quest 855 (false corpse sparkle for human B after normal loot removed, even after out-of-range reentry), while the other player's actual quest pickup was denied and legitimate normal loot/owner quest pickup succeeded. The fixture uses **different pinned quest item 5168 / quest 922**, *not* quest855's exact installed loot table or user session. It is a focused engine contract, not proof the previously observed H2 symptom has been repaired on the owner's machine.

## What the actual C++ fixture executes

`tests/p4_h_locked_slot_bridge.cpp` includes the **unchanged** native original P4-H1 helper harness and the **actual two Naxx headers**; it links the original pinned extracted `LootView`, `Player::StoreLootItem` and quest/item-state bodies with existing fixture stubs. All checks execute in one process in the following sequence:

1. **T3 locked quest row:** B was eligible when corpse was built, then brought a previously banked seed into inventory and completed the objective. Original Core LootView displays a **LOCKED** quest row; H1 view gate may return true because the row is *visible*. H2 must suppress sparkle when B can take nothing; original Core StoreLootItem must still refuse B. Neither passive check may consume the shared item.
2. **Owner remains eligible:** A sees an `ALLOW_LOOT` quest row, H1 and H2 preserve visibility/sparkle, original Core awards the item to A. This protects the user's previously verified rightful quest loot.
3. **Normal locked Master Loot:** B sees a locked **normal** Master Loot row; H1 must still classify the slot as visible, and H2 must keep the normal-loot sparkle as stock. We do not grant a manual pickup or override Master Loot rules.
4. **Ordinary loot and gold:** A's normal loot remains visible, sparkles, and can be awarded by original StoreLootItem; gold still triggers sparkle. No blanket corpse denial.

The new `tests/test_p4_h1_h2_locked_slot_bridge.py` source and executable verifier expects exactly **18** named cross-system C++ checks, not a changed source implementation. The GitHub workflow compiles/runs the fixture under **GCC and Clang C++20** against the **exact pinned original public Core** (sparse checkout, no private credentials), and asserts exactly FOUR new paths: this document, C++/Python tests and CI. All runtime `src/`, config, SQL/DBC and installed client remain unchanged. **Do not report GREEN until both actual Actions jobs pass.**

## Limits, dependencies and future tests

- This is **not** an actual client packet, installed Core2/PB6 build, live game or quest855 SQL verification. Only a cross-guard native extracted-original-body simulation, with existing fixture stubs; it cannot establish real client visual invalidation or owned corpse phasing.
- `ITEM_FLAGS_CU_IGNORE_QUEST_STATUS`, Master Loot transfer packets and `follow_loot_rules` are separate Core award exceptions: their intended user-specific rights must be reviewed before any future global deny change. The test intentionally avoids changing any of those policy paths.
- H1, H2, H0 and P4 protection distributed defaults remain **OFF**. Their cross-module actual installed configuration, WotLK loot flags and host variant are unverified. Owner gameplay acceptance F01–F20 and real two-human quest855 remain outstanding.
- Any future behavioural patch must be proposed on its **own** owning source branch, avoid other developers' P4/H1/H2 work, preserve quest 855 successful rightful award, Master Loot, FFA/MULTI_DROP, roll, normal loot and corpse state, compile the five owner forks, and obtain CosmicCuddle's review, backup/rollback plan and offline test approval. This review-only DRAFT makes no production policy decision or fix.

**Rollback:** reject this test-only branch/DRAFT; no runtime/DB/host modifications, and the pinned Naxx owner #292 source remains exactly unchanged.
