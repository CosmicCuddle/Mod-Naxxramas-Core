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
  it.entry AS item_id,
  it.name AS item_name,
  it.Flags AS item_flags,
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
  AND q.MinLevel <= 60
  AND ct.maxlevel <= 60
  AND ct.exp = 0
  AND cl.QuestRequired = 1
  AND cl.Reference = 0
  AND cl.MinCount = 1
  AND cl.MaxCount = 1
ORDER BY q.MinLevel, q.ID, ct.entry
LIMIT 100;
```

**Manual/source checks BEFORE accepting a candidate:** confirm Q is genuinely bankable through installed-source `Player::CanBankItem` and normal bank-slot rules; `ITEM_FLAG_MULTI_DROP` is absent, its `follow_loot_rules`, `needs_quest`, template/custom flags and quest constraints are appropriate, and no quest-item-start or class/faction exception changes the predicate. Confirm the creature is genuinely Vanilla/within cap; a direct `cl.QuestRequired=1` hit does **not** prove the mob drops only Q or guarantees a spawn/drop. In the *disposable model only*, isolate a loot object with one non-FFA Q, gold=0 and no other loot; do not mutate actual world loot tables. Record **quest ID, Q item ID, creature ID, source revision and candidate verification** in the existing #109 discussion. Until this is checked, **no specific item is certified**.

Source references: [AzerothCore quest_template](https://www.azerothcore.org/wiki/quest_template), [loot template](https://www.azerothcore.org/wiki/loot_template), [creature_template](https://www.azerothcore.org/wiki/creature_template), [item_template](https://www.azerothcore.org/wiki/item_template), [read-only loot SQL documentation](https://www.azerothcore.org/wiki/useful-sql).

## 3. One controlled disposable fixture

**Fixed setup:** A and B are distinct real-human simulated characters, same eligible group, both within the *loot-reward* range when the corpse is first filled. A is missing one Q and is allowed to receive it. B has the same one-item delivery quest, acquired one Q normally and moved Q into the bank through validated game logic. Thus, *provided the pinned transfer code matches*, `B.q_status.ItemCount=0`, `B.QUEST_STATUS_INCOMPLETE`, `B.GetItemCount(Q,true)=1`. Q in new corpse is shared non-FFA, `Q.is_looted=false`, `unlootedCount=1`, `gold=0`. Save the per-player quest-item cache snapshot before either window opens.

**Minimum cases to run in the existing A04 work lane:**

| Case | Action order | Pinned-source *suspected/broken* witness | Required safe-candidate acceptance |
| --- | --- | --- | --- |
| **T0 control** | A opens → A legally receives Q | Normal success and count decrement | A receives exactly one Q; `unlootedCount` becomes 0; correct notification and release |
| **T1 global flag** | A opens; leaves window open → B with Q still in bank opens only → A clicks original Q row | B's `LootView` may set shared `Q.is_looted=true` without any grant or `unlootedCount--`; A's row remains stale | B's view alone cannot consume A's right; no phantom award; synchronized item/count/row/flags |
| **T2 order reversal** | B with Q still in bank opens first → A opens | Q may become globally hidden despite A's valid need | A can still see and receive Q; no incorrect final corpse cleanup |
| **T3 stale locked row** | Corpse fills with B's Q banked → B retrieves Q bank→bags → B opens | B's cached quest slot persists despite quest objective becoming complete; window can show LOCKED Q row | No false personal award, no misleading actionable Q row or false sparkle, A's legal Q preserved |
| **T4 stock shared entitlement** | Both A and B genuinely need a one-copy Q; vary owner of active loot turn | Pinned stock may permit either eligible human to take Q | **Do not invent new ownership rule**; record under unselected A/B/C owner-policy gate |
| **T5 other entitlements** | Corpse adds independent gold/ordinary/FFA/rolled items; repeat with Master Loot | Sparkle and visible rows may be legitimate despite Q denial | Gold, FFA/MULTI_DROP, rolls, Master Loot and skinning must remain legal and accurately displayed |

For **every case**, record before/after: both quest statuses/objective counts, bank-inclusive and inventory-only Q counts, `Loot::PlayerQuestItems[A/B]`, each `QuestItem::is_looted`, shared `Q.is_looted` and `Q.is_counted`, `unlootedCount`, `Loot::isLooted()`, `hasItemFor(A/B)`, actual `StoreLootItem` recipient/bag/mail outcome, `SMSG_LOOT_RESPONSE` row/slot type, `SMSG_LOOT_REMOVED`, corpse release and each viewer's `UNIT_DYNFLAG_LOOTABLE`. Do **not** infer user-visible client sparkle solely from synthetic unit field values.

**Hard invariants:** opening another player's loot view must never grant/consume A's legal item; the shared count changes only according to actual ownership/award semantics; no duplicated items; both viewer rows and lootable flags correspond to *independent remaining rights*. Do not repair by blindly decrementing `unlootedCount`, marking Q globally looted during packet rendering, changing ordinary Master Loot/roll rules, force-creating personal copies or blanket clearing sparkle.

## 4. Evidence and release/approval gate

1. **CS01 Maintenance:** certify actual bankable Vanilla Q candidate on a matching offline world snapshot; implement **the smallest disposable regression test** in the *existing A04 lane*, and produce failing pinned-source baseline plus passing proposed-candidate evidence. A synthetic model alone does NOT certify installed behavior.
2. **Authoritative H1/H2:** separately reconcile exact owner-reported item/quest, both human quest states, loot method and real award path; an item-aware Core pre-store and viewer-specific row/flag seam may need a separately owner-authorised patch. No owner policy A/B/C is selected yet.
3. **Source/thread safety:** audit exact installed Core/Playerbots/IP/Module, eight map threads, map-local entity lifetime, safe configuration snapshots, restorable backup, default-OFF/reversible behavior and all legal gold/roll/mail/FFA cases. No changes to `acore_world` live SQL or character data without explicit approval.
4. **Unified owner test:** P1 Warlock, P2 Hunter Altbot ammo, **operational** P3 F15 (not synthetic #256 only), and P4 **both** human H1 and H2 must each have credible source-matched testable candidates and a recovery plan. **Only then** request CosmicCuddle's separate permission for one combined in-game/operational staging session. No intentional live crash tests or actual log deletion.

**Reference:** [Maintenance independent ACK of source risk](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4#issuecomment-6545124867); [A04 exact bank-transfer chain](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545098947); [stale locked-row variation](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109#issuecomment-6545166894). The **current owner-installed item database and binary are unverified**, and no SQL was run as part of this document.
