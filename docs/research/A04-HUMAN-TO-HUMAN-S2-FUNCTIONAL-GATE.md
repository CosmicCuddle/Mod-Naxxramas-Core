# A04 — Human-to-human quest-loot functional S2 entry gate (review only)

**Status:** source-backed implementation readiness checklist, **NOT a selected loot policy**, not a functional fix. Owner reports a second **human** actually receiving a quest-related item, not just a glowing corpse. This file changes no C++, SQL, DBC, configuration, test executable, item or live state. Do not merge this draft. CS01 owns A04 and integration; peer review remains mandatory.

## Exact-source foundation (24 Oct 2026)

- Module main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`: `src/Systems/QuestLootProtection.cpp`, unchanged by this S1 branch; default `QuestLootProtection.Enabled = false`.
- Current `CanPacketReceive` sees only a human session's `CMSG_AUTOSTORE_LOOT_ITEM`, and checks creature/vehicle **corpse** loot, three group methods and **viewer-specific quest slots**. It deliberately permits the request when the *clicking human is the round-robin holder*, when the holder was released, when the relevant item is in regular `loot.items`, for game objects/chests or non-corpse sources, and on various owner ineligibility paths.
- Denial is `SendLootError(sourceGuid, LOOT_ERROR_LOCKED)` and `return false`, **independent of Debug**. No permitted path logs in this module. A visible row or sparkle is not proof of a successful server award.
- [#117](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/117) traces the actual `StoreLootItem` and alternative award paths at Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`; [#122](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/122) adds HF-01–HF-07 present-behaviour synthetic observations. Neither provides functional S2.

## Owner-approved requirement — stock WoW quest-loot parity (supersedes A/B/C discussion)

**Owner clarified:** keep the **normal WoW/AzerothCore group-loot system** and correct only the bug that lets a grouped player access or actually receive quest drops they **should not be eligible to take under normal rules**. Do not change drop counts, rotate/assign loot turns differently, create personal copies, or reserve a legitimate shared item to a newly invented owner. **Do not ask the owner to choose A/B/C** as a condition of diagnosing the bug; those old proposals remain historically documented in #117 and are not approved.

**Correct distinctions:**

- **Invalid pickup:** the other group member is not eligible under native quest/loot rules, but can see or collect the item; this is the suspected actual defect and requires a concrete source-backed fix to item visibility and/or **inventory award**, not cosmetic sparkle alone.
- **Valid shared pickup:** two players legitimately qualify for the same shared one-copy item, and the current holder takes it according to normal group-loot rules. This is **not by itself proof of a defect**, even if another player wanted the item.
- **Personal multi-drop:** `ITEM_FLAG_MULTI_DROP` grants independent copies; the friend taking their own copy cannot be described as consuming yours.
- **Ordinary quest-related drops:** an item needed by a quest can still come from regular `loot.items` (`QuestRequired=0`) and remain stock shared loot. Do not automatically convert every quest-related item into a personal quest slot.
- **Sources and award paths:** creature corpse, chest/game object, rolls, master loot, human autoloot and Playerbot direct packet paths must be classified independently; not all pass the module's present packet hook.

The existing `QuestLootProtection.cpp` guard is **not evidence** that the owner's running configuration is correct, nor that native `AllowedForPlayer` / `HasQuestForItem` was bypassed in the reported incident. Compare actual quest + item + source/loot method evidence against pinned AzerothCore award and visibility logic before claiming a production defect. No functional fix is written or authorised here.

## Read-only reproduction and proof before S2

1. Identify one *replaceable / staging* reproduction: quest ID, item ID, creature or GO entry, source type, `QuestRequired` on the loot-template row and normal vs quest bucket; do not share private SQL dumps or player GUIDs publicly.
2. Confirm whether the friend's item was an independent `ITEM_FLAG_MULTI_DROP` personal copy or a depletion of the **same** one-copy `LootItem`. Separate view/visibility/click and actual inventory award evidence.
3. Confirm **running** module binary and loaded `QuestLootProtection.Enabled`, loot method and the active `roundRobinPlayer` turn. A distributed config example cannot prove runtime status; an absent Debug log proves neither permit nor bypass.
4. Prove the expected **native eligibility** for that exact quest + item + loot method + source, distinguishing an illegitimate recipient from a legitimate shared-loot turn. Record whether the displayed loot row, sent slot or actual inventory award violated native rules. Keep stock item counts and owner/turn semantics; there is **no B/C policy choice**.
5. Independently source-review the proposed S2 hook against current pinned core/IP/Playerbots APIs, confirm it is module-owned, default OFF, thread/instance safe, and fail-open to native for out-of-scope sources. Get native tests and fully linked Worldserver before staging.

## Required candidate regression cases (not run)

- **P01:** two real humans who both need a genuinely shared one-copy creature quest item: the eligible loot-turn holder's award stays **normal WoW behaviour**, with no invented owner, extra copy or unjustified denial.
- **P02:** current owner holds turn and still needs quest; friend's non-owner click is refused without deleting item, closing window, losing coins or denying unrelated slots.
- **P03:** release of loot turn while both still need a shared item: existing stock round-robin release/fallback stays unchanged; no new reserved-claimant policy.
- **P04:** previous round-robin holder disconnected, departed group/map/instance, died or no longer needs item: stock rules release/permit as normal, without making corpses permanently unlootable.
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

**S2 entry gate now:** identify the concrete **illegitimate** quest-item visibility/pickup/award behaviour under existing WoW rules, then propose the smallest module-owned, default-OFF correction and native tests. **No B/C loot-policy redesign is requested or approved**. When a reported award matches stock rules, report that transparently rather than changing the economy.
