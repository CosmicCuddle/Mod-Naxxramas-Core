# A04 — Human-to-human quest-loot functional S2 entry gate (review only)

**Status:** source-backed implementation readiness checklist, **NOT a selected loot policy**, not a functional fix. Owner reports a second **human** actually receiving a quest-related item, not just a glowing corpse. This file changes no C++, SQL, DBC, configuration, test executable, item or live state. Do not merge this draft. CS01 owns A04 and integration; peer review remains mandatory.

## Exact-source foundation (24 Oct 2026)

- Module main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`: `src/Systems/QuestLootProtection.cpp`, unchanged by this S1 branch; default `QuestLootProtection.Enabled = false`.
- Current `CanPacketReceive` sees only a human session's `CMSG_AUTOSTORE_LOOT_ITEM`, and checks creature/vehicle **corpse** loot, three group methods and **viewer-specific quest slots**. It deliberately permits the request when the *clicking human is the round-robin holder*, when the holder was released, when the relevant item is in regular `loot.items`, for game objects/chests or non-corpse sources, and on various owner ineligibility paths.
- Denial is `SendLootError(sourceGuid, LOOT_ERROR_LOCKED)` and `return false`, **independent of Debug**. No permitted path logs in this module. A visible row or sparkle is not proof of a successful server award.
- [#117](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/117) traces the actual `StoreLootItem` and alternative award paths at Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`; [#122](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/122) adds HF-01–HF-07 present-behaviour synthetic observations. Neither provides functional S2.

## Why a policy decision is essential

| Owner choice | Prevents friend taking the *single* item on the friend's valid turn? | Loot count | Implementation / constraint |
| --- | --- | --- | --- |
| **A: keep existing rotating turn with a stronger click guard** | **No**. A friend who holds the turn and meets the quest requirement may still take the shared copy. | Stock one copy | Smallest policy change; **insufficient alone** if that is the owner's unwanted case. |
| **B: separate personal copies for eligible players** | **Yes** for covered eligible drops, since the friend uses their own copy. | More items than stock when multiple eligible players | Needs loot-generation policy, not a packet-only denial; must preserve existing `MULTI_DROP` and `unlootedCount` semantics. |
| **C: reserve the one shared copy for a named eligible player** | **Yes**, while that chosen owner remains eligible and the award path is guarded. | Stock one copy | Needs deterministic claimant selection + departure, completion, grouping, relog and fallback rules; a round-robin holder is **not** necessarily the named quest owner. |

**Decision still unmade.** Do not silently pick A/B/C, duplicate loot, or assign ownership from group leader, first click, player GUID, or loot turn without owner approval. If multiple humans both legitimately need one quest item, no system can infer which person the owner intended without an explicit rule. Also decide whether ordinary `loot.items` items that happen to serve a quest, and game-object/chest drops, are in scope: the existing guard skips both categories.

## Read-only proof before choosing S2

1. Identify one *replaceable / staging* reproduction: quest ID, item ID, creature or GO entry, source type, `QuestRequired` on the loot-template row and normal vs quest bucket; do not share private SQL dumps or player GUIDs publicly.
2. Confirm whether the friend's item was an independent `ITEM_FLAG_MULTI_DROP` personal copy or a depletion of the **same** one-copy `LootItem`. Separate view/visibility/click and actual inventory award evidence.
3. Confirm **running** module binary and loaded `QuestLootProtection.Enabled`, loot method and the active `roundRobinPlayer` turn. A distributed config example cannot prove runtime status; an absent Debug log proves neither permit nor bypass.
4. Select the desired **one-copy named-owner vs personal-copy** rule and exact eligible-source scope. A is insufficient for the known eligible-friend-turn case. If C, define owner selection and stale-owner fallback. If B, define quantity and source exclusions.
5. Independently source-review the proposed S2 hook against current pinned core/IP/Playerbots APIs, confirm it is module-owned, default OFF, thread/instance safe, and fail-open to native for out-of-scope sources. Get native tests and fully linked Worldserver before staging.

## Required candidate regression cases (not run)

- **P01:** two real humans, both need one-copy creature quest line; friend holds turn and receives it under *current* code. New expectation depends on B/C owner choice.
- **P02:** current owner holds turn and still needs quest; friend's non-owner click is refused without deleting item, closing window, losing coins or denying unrelated slots.
- **P03:** release of loot turn while both still need the item; claimant/remaining copy obey chosen fallback, never stuck forever.
- **P04:** designated claimant disconnected, departed group/map/instance, died or no longer needs item: no permanent unlootable corpse or improper award.
- **P05:** `QuestRequired=0` normal `loot.items` item needed for a quest: separate explicit inclusion/exclusion rule; do not call it a quest-slot row.
- **P06:** already-personal `ITEM_FLAG_MULTI_DROP` quest and ordinary item buckets: both humans retain exactly their stock personal rights; do not mint a second copy.
- **P07:** chest/other GO, skinning and pickpocket: native behaviour unless expressly included after additional source validation.
- **P08:** GROUP_LOOT, ROUND_ROBIN, NEED_BEFORE_GREED, MASTER_LOOT and FREE_FOR_ALL: check each separately, including rolls/master awards which bypass the human autostore hook.
- **P09:** Playerbot/Altbot award path bypass of `CanPacketReceive`: identify separately; do not claim a human-only fix protects bots.
- **P10:** feature master OFF and unsupported source/packet: exact native parity; no synthetic copy or denial.
- **P11:** a friend without a relevant quest never gains an item through this module; confirm native conditions still apply.
- **P12:** one allowed pickup modifies exactly the intended loot counters and views; refused pickup modifies none.
- **P13:** parallel map threads, two separate instances, group change during corpse lifetime and owner unavailable: no process-global entitlement cache or cross-instance stale ownership.
- **P14:** addon UI sparkle/loot row and actual bag award recorded independently; deny-only debugging not mistaken for permit logs.
- **P15:** after one pickup, no unexpected double-count, duplicate pickup, container side effect or crash; no irreversible in-game testing without owner's backup and restore plan.

Treat `HF-01..HF-07` as **observations of the old implementation**, not newly passing S2 expectations. P01–P15 are design gates, not executed tests. A green Python model does not mean S2 C++ or an owner-installed build passed.

## First-build integration / safety gate

The first owner-approved test candidate must contain *actual functional* A04 **plus** A02 Hunter autocast, F12 Scarlet *normal physical entrance/exit*, F13 Atiesh outside Karazhan, and existing review-only #120 P0+B10. Keep isolated drafts, no protected-branch merge, unapproved SQL/DBC/core/IP/Playerbots modification, binary upload, release, or live install. Review exact branch heads, all switches/defaults, linked pinned Worldserver, reciprocal peer findings, and preserve the owner's Playerbots published SHA `e88cc4099e69f35126b28942a412ca702d20453b` **with two local uncommitted modifications** and their eight-thread map setup. Owner approval, restorable backups and rollback precede staging.

**Owner decision needed for actual S2:** one-copy named owner (**C**) versus separate eligible personal copies (**B**), plus scope for normal-item quest collections/chests. Document the choice; do not silently infer it from a complaint that a friend could click or take the item.
