# A04/P4 — two-human quest-loot regression: offline fixture selection and minimum pass/fail contract

**Prepared:** 2026-10-31 by Server-Side-Information (policy and source evidence only).  
**Owner:** CosmicCuddle has final gameplay decisions. **Assigned test-harness developer:** Naxx CS03/Claude (explicitly [ACKed/CLAIMED 31 Oct](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6546954986)); **integration/review owner:** CS01 Server-Side-Maintenance.  
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

### Exact five-table historical candidate cross-check (Part 45; executed read-only, 31 Oct)

For this checkpoint Information fetched the **complete underlying Git blobs** (not just short excerpts) of all five relevant public SQL dump files from the SAME pinned `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`, parsed column names and both candidate records, then independently asserted their relationships/fields. **Both historical data-shape checks PASSED; no MySQL connection, server process, source C++ compile, bank move, actual drop or owner DB access occurred.**

| Table | Exact pinned blob SHA |
| --- | --- |
| `quest_template.sql` | `9ebf71c00c7be4be350c614b05797e87effc1557` |
| `quest_template_addon.sql` | `6438787baaf5664becd76afb87a5a61dcd659e84` |
| `item_template.sql` | `a5f561ba1928c4b1d15a18effb73e348f64573ce` |
| `creature_template.sql` | `899a56b0f5d7bac6536a48e038acb23ba8a70812` |
| `creature_loot_template.sql` | `1ae8dc3607c53ee882a9d4cddc55a3942d854030` |

| Historical candidate | Result | Quest prerequisite / objective | Item facts | Direct Vanilla mob drop |
| --- | --- | --- | --- | --- |
| **Primary:** quest **922 Rellian Greenspyre** / Q **5168 Timberling Seed** | **PASS** historical data shape | `PrevQuestID=918`; exactly 1 × 5168 required, no other item/NPC objective counts | Quest class 12; binding 4; `Flags=0`, `flagsCustom=0`; `MaxCount=0`, stackable 20, `StartQuest=0` | Elder Timberling **2030**, `lootid=2030`, `exp=0`, maxlevel 11; Q `Chance=100`, `QuestRequired=1`, `Reference=0`, `GroupId=0`, count 1 |
| **Fallback:** quest **71 Report to Thomas** / Q **735 Rolf and Malakai's Medallions** | **PASS** historical data shape | `PrevQuestID=45`; exactly 1 × 735 required, no other item/NPC objective counts | Quest class 12; binding 4; `Flags=0`, `flagsCustom=0`; `MaxCount=1`, stackable 1, `StartQuest=0` | Murloc Forager **46**, Raider **515**, Streamrunner **735**; all `exp=0` and maxlevel 7–12; direct Q `Chance=40`, `QuestRequired=1`, `Reference=0`, `GroupId=0`, count 1 |

Both also have `QuestType=2`, quest/minimum level within Vanilla, loot `LootMode=1`, and zero remaining required item/NPC objective counts in this exact pinned dataset. Their `Flags=0` excludes the `ITEM_FLAG_MULTI_DROP=0x800` stock FFA path **if the actual loaded template matches**.

**Practical preference:** Start with **922/5168/2030** because its historical 100% direct drop and non-unique stackable item simplify repeated controlled tests; keep **71/735/46-or-515-or-735** as an independently verified public-source fallback, particularly if prerequisite/character selection or bankability makes 922 unsuitable. Do not scatter A04 implementation across two cases. **Neither candidate has been confirmed bankable in an actual game or verified owner snapshot**, even though the pinned `Player::CanBankItem` function has no blanket ban on quest-class items. Prerequisite quest 918 versus 45 must be handled legally; tests need *two human-controlled players*, not necessarily WoW Human-race characters.

**Fastest legitimate next milestone:** CS01 can begin a **purely disposable native Core fixture on this exact pinned historical base data** if appropriate; do not postpone that public-reference baseline solely because the *separate* privately approved owner-offline database comparison is still unavailable. But do not infer actual owner-server readiness, production fix or true client visual behavior until matching installed source/DB, safe reviewer testing and later explicit owner approval. This historical data check certifies only the SQL candidate relationships, not the full A04 H1/H2 remedy.

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

### Claimed native-source fixture — preserve precise evidence boundaries (31 October)

[Developer Naxx CS03/Claude explicitly claimed this exact existing task](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6546954986), proposed a dedicated new branch `claude/cs03-a04-native-quest-loot-20261031`, only **new tests/docs/CI paths**, and reported a local g++ 13 header-compile feasibility probe. **No hosted complete harness results, source-executed T0–T3 witness, full Core runtime, actual bank move or gameplay are verified by this claim.** CS01 remains reviewer/integration owner; do not substitute separate IP CS03-IP.

The proposed harness will extract original pinned C++ function bodies with verified blob/body hashes and real loot structure layouts; its collaborators (Player inventory, bank, conditions, group, World/Client send path) are **stubbed**. Record evidence distinctly as **real extracted Core function execution under synthetic collaborators**. Neither a successful compilation of headers nor running extracted bodies authenticates `CanBankItem`, `SwapItem`, `Player::SendLoot` or the actual owner's database/source.

**Independent exact-source safeguards sent [in the existing assignment thread](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6547060325):**

- T1/T2 require **B with active quest922, incomplete saved objective 0/1 and existing Q5168 ×1 bank-inclusive**, not an unrelated friend with no active quest. At corpse generation both A and B must be in loot-reward range and their `Loot::PlayerQuestItems` maps created. With `showInLoot` omitted, B's `HasQuestForItem` can report true; when `&showInLoot` is passed by `LootView`, B's same source check returns false with `showInLoot=false` because `GetItemCount(Q,true)=1`. Only that conditional reaches B viewer-local plus shared non-FFA `is_looted` mutation. This makes **B VIEW-only no-award** a different state than H1 actual wrong-person receipt.
- Historical `Player::StoreLootItem` returns a **non-null `LootItem*` even if `CanStoreNewItem` rejected a full bag or a constraint**; the pointer is not an award receipt. Record separate `InventoryResult`, calls to `StoreNewItem`/`SendNewItem`, successful actual inventory delta, `Q.is_looted`, quest-slot flags and `unlootedCount`. [Pinned `Player.cpp` L13861–13961](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L13861-L13961).
- A `LootView` packet/flag inconsistent with `unlootedCount` is at most an **H2 source-level candidate**. Without executing `Player::SendLoot` and per-player `UNIT_DYNFLAG_LOOTABLE` updates plus real clients, it cannot certify observed corpse sparkle. Without real `Item`/`Bag`/banking it cannot certify genuine legal item 5168 bankability.

## 4. Evidence and release/approval gate

1. **Naxx CS03/Claude (claimed):** build and independently prove the **smallest extracted pinned-source C++ harness** using original function bodies and pinned header layouts, not a hand-reimplemented logic model; record T0–T3, intentional historical failing baseline and must-fail mutant controls. **CS01 Maintenance:** review it, certify true bankability later in a source-matched environment, and own future integration/fix decisions. Neither fixture-stub bank state nor an extracted body is a real Player inventory or installed Worldserver test.
2. **Authoritative H1/H2:** separately reconcile exact owner-reported item/quest, both human quest states, loot method and real award path; an item-aware Core pre-store and viewer-specific row/flag seam may need a separately owner-authorised patch. No owner policy A/B/C is selected yet.
3. **Source/thread safety:** audit exact installed Core/Playerbots/IP/Module, eight map threads, map-local entity lifetime, safe configuration snapshots, restorable backup, default-OFF/reversible behavior and all legal gold/roll/mail/FFA cases. No changes to `acore_world` live SQL or character data without explicit approval.
4. **Unified owner test:** P1 Warlock, P2 Hunter Altbot ammo, **operational** P3 F15 (not synthetic #256 only), and P4 **both** human H1 and H2 must each have credible source-matched testable candidates and a recovery plan. **Only then** request CosmicCuddle's separate permission for one combined in-game/operational staging session. No intentional live crash tests or actual log deletion.

**Reference:** [Maintenance independent ACK of source risk](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4#issuecomment-6545124867); [A04 exact bank-transfer chain](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545098947); [stale locked-row variation](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545166894). The **current owner-installed item database and binary are unverified**, and no SQL was run as part of this document.
