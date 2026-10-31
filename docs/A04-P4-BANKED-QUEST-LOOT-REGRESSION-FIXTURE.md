# A04/P4 — two-human quest-loot regression: offline fixture selection and minimum pass/fail contract

**Prepared:** 2026-10-31 by Server-Side-Information (policy and source evidence only).  
**Owner:** CosmicCuddle has final gameplay decisions. **Implement/test owner:** CS01 Server-Side-Maintenance.  
**Status:** DRAFT acceptance worksheet. **NOT executed, NOT a resolved gameplay bug or approval for Core/database modifications.**  
**Existing authority:** [A04 Issue #109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109), [four-priority coordination #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4), [original gameplay policy A/B/C (none selected)](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/117).

## 1. Why this is the next useful test

Historical `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` can count a single *shared* non-FFA quest item Q once when the corpse is created, yet **globally mark it looted when a different player's loot window is opened** without a pickup/count decrement. A legitimate first player can retain a stale row; another path renders a stale locked row. These conditional source chains have been [independently reviewed by Maintenance](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4#issuecomment-6545124867), **not reproduced on the installed owner binary**, and do not establish the root of reported H1 actual wrong-human award or H2 corpse sparkle.

**Stop condition:** Do not expand A04 research into new branches before capturing an actual fail-before/fix-after *disposable/source-matched* test of this one reproducible case. Preserve existing policy and award code until the owner's stronger shared-quest entitlement choice and an item-aware pre-award/viewer seam are approved.

## 2. Identify candidate Vanilla Q from a read-only copy of the world database

This SELECT-only query is for **CS01 on an OFFLINE/snapshot world database**, after checking the actual schema. It is **not a command for CosmicCuddle to execute on live `acore_world`**. AzerothCore public reference schemas provide `quest_template.RequiredItemId1/RequiredItemCount1`, `creature_loot_template.Entry/Item/QuestRequired/MinCount/MaxCount`, `creature_template.lootid/exp/maxlevel` and `item_template.entry/name/Flags/FlagsExtra`. The query intentionally scans **direct** mob loot and only the first required-item slot: initial simple candidate search, **not** a complete loot-source inventory. A zero-row result means broaden offline search, **not** invent a quest/item ID.

```sql
-- READ-ONLY CANDIDATE DISCOVERY ON A VERIFIED OFFLINE WORLD DB COPY ONLY.
-- Do not edit quest, loot or item rows to satisfy this fixture.
SELECT
  q.ID AS quest_id,
  q.LogTitle AS quest_title,
  q.MinLevel AS quest_min_level,
  q.QuestLevel AS quest_level,
  it.entry AS item_id,
  it.name AS item_name,
  it.Flags AS item_flags,
  it.bonding AS item_bonding,
  it.maxcount AS item_maxcount,
  it.FlagsExtra AS item_flags_extra,
  ct.entry AS creature_id,
  ct.name AS creature_name,
  ct.maxlevel AS creature_max_level,
  cl.Chance AS drop_chance,
  cl.GroupId AS loot_group_id
FROM quest_template AS q
JOIN item_template AS it
  ON it.entry = q.RequiredItemId1
JOIN creature_loot_template AS cl
  ON cl.Item = it.entry
JOIN creature_template AS ct
  ON ct.lootid = cl.Entry
WHERE q.RequiredItemId1 <> 0
  AND q.RequiredItemCount1 = 1
  AND q.RequiredItemCount2 = 0
  AND q.RequiredItemCount3 = 0
  AND q.RequiredItemCount4 = 0
  AND q.RequiredItemCount5 = 0
  AND q.RequiredItemCount6 = 0
  AND q.RequiredNpcOrGoCount1 = 0
  AND q.RequiredNpcOrGoCount2 = 0
  AND q.RequiredNpcOrGoCount3 = 0
  AND q.RequiredNpcOrGoCount4 = 0
  AND q.QuestType = 2
  AND q.QuestLevel BETWEEN 1 AND 60
  AND q.MinLevel <= 60
  AND ct.maxlevel <= 60
  AND ct.exp = 0
  AND (it.Flags & 2048) = 0  -- exclude ITEM_FLAG_MULTI_DROP in pinned 3.3.5a Core
  AND cl.QuestRequired = 1
  AND cl.Chance = 100
  AND cl.GroupId = 0
  AND cl.Reference = 0
  AND cl.MinCount = 1
  AND cl.MaxCount = 1
ORDER BY q.MinLevel, q.ID, ct.entry
LIMIT 100;
```

### Verified historical candidate from pinned Grimfeather world SQL (not live `acore_world`)

I independently read the **actual MySQL dump blobs** in `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` (2026-06-01 dump timestamp), not just the public AzerothCore wiki, and cross-joined **all four** historical tables by parsing their `INSERT` rows. **Recommended first candidate (only on an offline copy with source-match):**

| Field | Exact historical dump value |
| --- | --- |
| Quest | **922 — Rellian Greenspyre**, quest level 7, minimum level 4, `QuestType=2`, `RequiredItemId1=5168`, `RequiredItemCount1=1`, no other required-item or NPC/GO objective counts |
| Required item Q | **5168 — Timberling Seed**, `class=12` Quest, `bonding=4` Quest, `Flags=0`, `FlagsExtra=0`, `flagsCustom=0`, `maxcount=0`, `stackable=20` |
| Creature | **2030 — Elder Timberling**, historical levels 10–11, `exp=0`, `lootid=2030` |
| Direct loot row | `creature_loot_template.Entry=2030, Item=5168, Reference=0, Chance=100, QuestRequired=1, GroupId=0, LootMode=1, MinCount=1, MaxCount=1` |

**Why this selection is safer:** I first found quest **176 — Wanted: Hogger** / item **1931 — Huge Gnoll Claw** / creature **448 — Hogger**, with a 100% direct quest drop, but its item `Flags=2048`. The pinned [`ItemTemplate.h` defines `ITEM_FLAG_MULTI_DROP = 0x00000800`](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Item/ItemTemplate.h#L158), so **Hogger's claw is invalid for our non-FFA shared-item regression**. Timberling Seed has `Flags=0` and avoids that trap. The SELECT above now explicitly filters this bit, enabled `QuestType=2`, quest level 1–60, direct **100%** nongrouped drop, and outputs useful bankability-related item fields. The historical dump yielded a candidate when these predicates were applied; **the exact SELECT has not been executed in MySQL or against any private server database**.

Pinned evidence files: [quest_template.sql](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/data/sql/base/db_world/quest_template.sql), [item_template.sql](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/data/sql/base/db_world/item_template.sql), [creature_template.sql](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/data/sql/base/db_world/creature_template.sql), and [creature_loot_template.sql](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/data/sql/base/db_world/creature_loot_template.sql).

**Remaining essential checks:** First prove the candidate exists unchanged in the owner's *approved offline* world snapshot, can be accepted by two actual eligible characters, is permitted by `Player::CanBankItem` in the exact deployed Core, and yields `LootItem::freeforall=false`. Quest-item `bonding=4` and `Flags=0` **do not alone prove bankability**. The creature's original loot template or coins may include other rewards—**the zero-gold, single-Q fixture is an isolated disposable model, not a claim about the live Elder Timberling loot table**. Never edit the live quest or loot database to force the test.

**Manual/source checks BEFORE accepting a candidate:** confirm Q is genuinely bankable through installed-source `Player::CanBankItem` and normal bank-slot rules; `ITEM_FLAG_MULTI_DROP` is absent, its `follow_loot_rules`, `needs_quest`, template/custom flags and quest constraints are appropriate, and no quest-item-start or class/faction exception changes the predicate. Confirm the creature is genuinely Vanilla/within cap; a direct `cl.QuestRequired=1` hit does **not** prove the mob drops only Q or guarantees a spawn/drop. In the *disposable model only*, isolate a loot object with one non-FFA Q, gold=0 and no other loot; do not mutate actual world loot tables. Record **quest ID, Q item ID, creature ID, source revision and candidate verification** in the existing #109 discussion. Until this is checked, **no specific item is certified**.

Source references: [AzerothCore quest_template](https://www.azerothcore.org/wiki/quest_template), [loot template](https://www.azerothcore.org/wiki/loot_template), [creature_template](https://www.azerothcore.org/wiki/creature_template), [item_template](https://www.azerothcore.org/wiki/item_template), [read-only loot SQL documentation](https://www.azerothcore.org/wiki/useful-sql).

## 3. One controlled disposable fixture

**Fixed setup:** A and B are distinct real-human simulated characters, same eligible group, both within the *loot-reward* range when the corpse is first filled. A is missing one Q and is allowed to receive it. B has the same one-item delivery quest, acquired one Q normally and moved Q into the bank through validated game logic. Thus, *provided the pinned transfer code matches*, `B.q_status.ItemCount=0`, `B.QUEST_STATUS_INCOMPLETE`, `B.GetItemCount(Q,true)=1`. Q in new corpse is shared non-FFA, `Q.is_looted=false`, `unlootedCount=1`, `gold=0`. Save the per-player quest-item cache snapshot before either window opens.

**Minimum cases to run in the existing A04 work lane:** T0–T4 and T6 cover the principal **one-required-item Q**; T5 is a **separate, optional RequiredItemCount=2 accounting test** needing a second legally verifiable quest/item. Do **not** delay the principal historical quest 922 / item 5168 candidate merely because a T5 item is not yet known.

| Case | Action order | Pinned-source *suspected/broken* witness | Required safe-candidate acceptance |
| --- | --- | --- | --- |
| **T0 control** | A opens → A legally receives Q | Normal success and count decrement | A receives exactly one Q; `unlootedCount` becomes 0; correct notification and release |
| **T1 global flag** | A opens; leaves window open → B with Q still in bank opens only → A clicks original Q row | B's `LootView` may set shared `Q.is_looted=true` without any grant or `unlootedCount--`; A's row remains stale | B's view alone cannot consume A's right; no phantom award; synchronized item/count/row/flags |
| **T2 order reversal** | B with Q still in bank opens first → A opens | Q may become globally hidden despite A's valid need | A can still see and receive Q; no incorrect final corpse cleanup |
| **T3 stale locked row** | Corpse fills with B's Q banked → B retrieves Q bank→bags → B opens | B's cached quest slot persists despite quest objective becoming complete; window can show LOCKED Q row | No false personal award, no misleading actionable Q row or false sparkle, A's legal Q preserved |
| **T4 stock shared entitlement** | Both A and B genuinely need a one-copy Q; vary owner of active loot turn | Pinned stock may permit either eligible human to take Q | **Do not invent new ownership rule**; record under unselected A/B/C owner-policy gate |
| **T5 optional: partial banking via whole-slot move** | With a *different*, legally bankable RequiredItemCount=2 Q, B has two **separate bag slots, Q×1 each**, objective 2, empty bank slot; move one **entire** Q×1 slot bag→bank using **`SwapItem`**, leaving Q×1 in other bag slot | Pinned `SwapItem` calls `RemoveItem → BankItem → ItemRemovedQuestCheck` and may double-subtract the post-move bag count (bag=1, bank=1, persisted objective=0); a **partial split from one Q×2 stack via `SplitItem` is NOT the same path** | Validate legal two-slot setup, actual executed branch, bag=1/bank-inclusive=2, quest counter consistency, eligible per-viewer Q rights; if not legally reproducible, mark T5 not runnable rather than rewriting DB/item flags |
| **T6 other entitlements** | Corpse adds independent gold/ordinary/FFA/rolled items; repeat with Master Loot | Sparkle and visible rows may be legitimate despite Q denial | Gold, FFA/MULTI_DROP, rolls, Master Loot and skinning must remain legal and accurately displayed |

For **every case**, record before/after: both quest statuses/objective counts, bank-inclusive and inventory-only Q counts, `Loot::PlayerQuestItems[A/B]`, each `QuestItem::is_looted`, shared `Q.is_looted` and `Q.is_counted`, `unlootedCount`, `Loot::isLooted()`, `hasItemFor(A/B)`, actual `StoreLootItem` recipient/bag/mail outcome, `SMSG_LOOT_RESPONSE` row/slot type, `SMSG_LOOT_REMOVED`, corpse release and each viewer's `UNIT_DYNFLAG_LOOTABLE`. Do **not** infer user-visible client sparkle solely from synthetic unit field values.

**Hard invariants:** opening another player's loot view must never grant/consume A's legal item; the shared count changes only according to actual ownership/award semantics; no duplicated items; both viewer rows and lootable flags correspond to *independent remaining rights*. Do not repair by blindly decrementing `unlootedCount`, marking Q globally looted during packet rendering, changing ordinary Master Loot/roll rules, force-creating personal copies or blanket clearing sparkle.


### Source-verified bank movement and fixture separation (Part 45 correction)

The historical pinned [`Player::CanBankItem`](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/PlayerStorage.cpp#L2110-L2295) performs item ownership, quota and destination-capacity checks; this body shows **no blanket prohibition solely because item Class=QUEST/bonding=QUEST**. It **does not prove** actual Timberling Seed 5168 bankability, since item state, unique count, permissions, exact template and installed custom rules remain unverified. An actual accepted legal bag→bank operation remains required.

**Critical source-route distinction:** historical [`Player::SwapItem` L3735–3768](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/PlayerStorage.cpp#L3735-L3768) takes a **whole occupied bag slot** into an empty bank slot, then runs `ItemRemovedQuestCheck` *after* removal/banking. By contrast [`Player::SplitItem` L3525–3637](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/PlayerStorage.cpp#L3525-L3637) can clone part of Q×2 into bank without a direct `ItemRemovedQuestCheck` call in that branch. Thus a single Q×2 **split** cannot stand in for T5's specifically demonstrated **whole-slot** path. [Maintenance's independent correction](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545597203) explains how to keep the controls distinct.

**Recommended fastest safe dependency order:** Use the historical **quest 922 / item 5168 / creature 2030** only as a *candidate for T0–T3* on a disposable pinned Core + historical world-table snapshot, if bankability and legal quest conditions are positively confirmed. This does **not** require or authorise querying the owner production DB. Match the owner's privately preserved installed World/character database and source **later**, before any inference that their server behaves identically. T4 policy and T5 optional accounting remain independent; the mandatory H1/H2 gameplay symptoms still need direct verified fixes and owner authorization. No guaranteed test day or false certification.

## 4. Evidence and release/approval gate

1. **CS01 Maintenance:** certify actual bankable Vanilla Q candidate on a matching offline world snapshot; implement **the smallest disposable regression test** in the *existing A04 lane*, and produce failing pinned-source baseline plus passing proposed-candidate evidence. A synthetic model alone does NOT certify installed behavior.
2. **Authoritative H1/H2:** separately reconcile exact owner-reported item/quest, both human quest states, loot method and real award path; an item-aware Core pre-store and viewer-specific row/flag seam may need a separately owner-authorised patch. No owner policy A/B/C is selected yet.
3. **Source/thread safety:** audit exact installed Core/Playerbots/IP/Module, eight map threads, map-local entity lifetime, safe configuration snapshots, restorable backup, default-OFF/reversible behavior and all legal gold/roll/mail/FFA cases. No changes to `acore_world` live SQL or character data without explicit approval.
4. **Unified owner test:** P1 Warlock, P2 Hunter Altbot ammo, **operational** P3 F15 (not synthetic #256 only), and P4 **both** human H1 and H2 must each have credible source-matched testable candidates and a recovery plan. **Only then** request CosmicCuddle's separate permission for one combined in-game/operational staging session. No intentional live crash tests or actual log deletion.

**Reference:** [Maintenance independent ACK of source risk](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4#issuecomment-6545124867); [A04 exact bank-transfer chain](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545098947); [stale locked-row variation](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545166894). The **current owner-installed item database and binary are unverified**, and no SQL was run as part of this document.
