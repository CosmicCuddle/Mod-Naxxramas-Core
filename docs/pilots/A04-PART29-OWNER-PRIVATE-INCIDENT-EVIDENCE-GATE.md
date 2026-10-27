# A04 Part29 — private two-human incident evidence gate (H1 versus H2)

**Prepared only. NOT consent to inspect a server, run SQL, install/configure a module, capture packets, or stage gameplay.** This PUBLIC file is a **blank checklist with no real character, item, quest, NPC, map, guild, host, log or database identifiers**. Store filled-in evidence privately under the owner's approved access policy. Do not commit filled checklists, screenshots, traces or dumps here.

## Why two separate captures are essential

**H1** is an *actual inventory/mail award*: a real human friend apparently obtained quest-related loot someone else expected. A loot window, click, autostore packet, gossip, sparkle or roll window is **not** evidence of a completed award. Normal group loot may legitimately give a shared one-copy item to any independently eligible recipient on their turn or under a relevant loot rule.

**H2** is *sparkle with item denied/unavailable*: the corpse indicator and item eligibility use different checks. A cached per-viewer quest slot can keep the corpse lootable while the current quest item is locked. Only for a narrower shared non-FFA quest item and an **already inconsistent objective counter short / bag count sufficient** can pinned `LootView` serialization potentially mark the shared item looted without decrementing `unlootedCount`; normal `StoreNewItem` and quest acceptance update the tracked counter. Neither path is yet reproduced on the owner's installed binaries.

## Gate 0 — no system access until owner approves separately

1. **Owner written permission and boundary:** identify an authorized *separate nonproduction staging* server/build and which observation/tracing actions are allowed. Do not access World/Auth, private SQL, player sessions, logs or installed configs before this approval.
2. **Backup/restore:** record a recoverable staging binary, config, characters/world data snapshot as applicable, a known-good restart procedure and verified restore method. Do not use production characters for first reproductions.
3. **Installed build identity:** privately record actual AzerothCore, custom Playerbots, Individual Progression, Naxxramas module SHAs/versions, config loaded on *start* and whether each A04 option is effective. CI public pin is not installation proof. Both A04 prototype flags remain default **OFF**; never enable to hunt a bug as a guess.
4. **Two plain controlled human clients:** with informed permission, do separate H1 and H2 reproductions under ordinary configured group loot. Record negative/positive controls and stop on any item loss, duplication, crash, stalled corpse or unexpected live effect.

## Case H1 — friend got the item

Use `yes / no / unknown`, not real private identifiers, in a public discussion. Keep any exact IDs and timestamps in the approved private evidence vault.

| Question | Private observation (not here) |
| --- | --- |
| Did an item actually enter the friend's **bags or mail**? Confirm count before/after, not just a click/roll/window. | ___ |
| Was the friend independently eligible for that item **at the moment of award** (quest stage, objective counters, loot conditions)? | ___ |
| Was the item a *quest bucket* row versus *ordinary item* (possibly usable by a quest)? | ___ |
| Was it a shared one-copy, `MULTI_DROP`/personal, or roll/follow-loot-rules item? | ___ |
| Which group method? Who held the round-robin turn; did its owner close/release first? | ___ |
| Did an error, winner reservation, roll/mail award or alternate Playerbots path occur? | ___ |

**Decision gate:** If the friend was eligible and the observed award is compatible with the documented sharing/turn/roll rule, **do not label it a bug**. If a genuinely ineligible friend received an award, the actual *award route* (not the sparkle) requires a separate native-path/installed-hook audit before designing any correction. Unknown award = not yet an H1 result.

## Case H2 — sparkle, but item unavailable

| Question | Private observation (not here) |
| --- | --- |
| Was it actually sparkling for the denied human? Was the loot window open? | ___ |
| Was the exact **row** `ALLOW`, `LOCKED`, `ROLL_ONGOING`, `HIDDEN`, or unknown? Which actual client/server denial was emitted? | ___ |
| Did that human still need the objective according to **saved quest `ItemCount`** immediately before the window? | ___ |
| Were *their bags already holding enough* of that objective item at that instant? (`GetItemCount(..., true)` includes bank where applicable) | ___ |
| Was the drop a *shared non-FFA one-copy quest bucket* item? Was another eligible human mapped to that exact item? | ___ |
| Did the first viewer open the window before the second? Who released? Was `unlootedCount` still positive, and was the underlying item set `is_looted`? | ___ |
| Were **both separate** effective A04 switches actually ON/OFF in the installed restarted Worldserver (`QuestLootProtection.Enabled` legacy quest-turn versus `RestrictHiddenOrdinarySlots` ordinary slot)? | ___ |

**Decision gate:** Sparkle + LOCKED can be consistent with a cached stock quest row and later recheck. A **specific shared-item side-effect candidate** needs all: quest bucket, shared one-copy/non-FFA, first viewer `ItemCount` short **AND** current inventory count sufficient, another eligible viewer, and ordering/count evidence. **Without these, never classify H2 as that source defect**. An active legacy quest-turn guard for a quest row, or active hidden-ordinary-slot guard for an ordinary row, is a different possible branch; the two switches are independent. Native inventory/roll errors are also different branches.

## Safe pure-function optional triage

`tools/a04/incident_triage.py` accepts **only generic finite-choice categories** in an in-memory `Incident` object; no database, CLI prompt, host, log, network or identifier input and no output file. `assess()` returns *hypothesis codes and missing evidence categories*, not a diagnosis. It never attributes a quest-row denial to the ordinary-slot switch or an ordinary-row denial to the legacy quest-turn switch. `Assessment` always remains `bug_proven=False`, `accepted=False`, `can_enable_a04=False`, `can_change_shared_loot=False`, `write_policy=NO_WRITE` for every combination. No filled incident is ever used in GitHub Actions: tests generate only synthetic values.

**Example for a purely invented scenario** (do not paste owner private identifiers into code or CI):

```python
from tools.a04.incident_triage import Incident, assess
case = Incident(kind="H2", source="creature", bucket="quest",
                shared_one_copy="yes", objective="short", inventory="met",
                sparkle="yes", denied="yes", slot="hidden")
result = assess(case)
assert result.write_policy == "NO_WRITE"
print(result.hypothesis_codes)
```

All `unknown` categories are intentionally acceptable: an incomplete report is a safe incomplete report. Never fabricate missing owner facts, publish sensitive screenshots/IDs into a PUBLIC PR, or use this to authorize staged testing or changing group-loot policy.

## Source/fingerprint provenance and limitations

Public pinned core `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`, `PlayerStorage.cpp` (`isAllowedToLoot`, `_LoadQuestStatus`, `StoreNewItem`), `PlayerQuest.cpp` (`HasQuestForItem`, quest counter updates), `LootMgr.cpp` (`FillQuestLoot`, `hasItemFor`, `LootView`), `LootMgr.h` (`unlootedCount/isLooted`), `Player.cpp` (`StoreLootItem`), `LootHandler.cpp` (`DoLootRelease`). Existing [research DRAFT #179](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/179) at `f328d6e` tested the isolated source/model path. The new evidence-gate tests are separate and **do not rerun native core or prove an installed failure**. Owner observations, custom scripts and exact item/quest metadata may contradict the public hypothesis. Every practical case is **NOT RUN** until separately approved and privately witnessed.