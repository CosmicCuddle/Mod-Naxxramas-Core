# P1 + P2 — first controlled gameplay test card (NOT AUTHORISED YET)

**31 October 2026 — concise owner-facing reference.** This is an acceptance worksheet, **not** an instruction to pull, recompile, enable configuration, launch a test, or alter character inventory. [Module master status #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) remains authoritative; [Maintenance/Information readiness #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4) owns the installed-source and safety gates.

## What has actually passed

- Historical pinned **full Worldserver compile/link S4** succeeded for the unchanged Warlock P1 C++ + Hunter ammo C++, both without experimental IP grouping ([CI 41119534989](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41119534989)) and with the IP grouping pilot ([CI 41138075456](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41138075456)). The runner was disposable. **Neither is proof of the owner's later-updated installed Core/Playerbots, feature enablement, successful gameplay, or restore-tested backup.**
- Warlock [draft #248](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/248) is default OFF. The owner's **second-stage summoning has previously failed in-game** and has not passed a repair retest. Hunter ammo exists in protected module source, but [issue #31](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/31) has no live acceptance.

## Gate before ANY owner gameplay test

**Maintenance must first** source-match the owner's actual Core, Playerbots, IP, Naxxramas module and other installed modules; inspect effective installed flags/SQL/DBC and preserve local edits; confirm the owner-reported backups can be restored, then obtain explicit separate owner approval for a small test. **Keep `MapUpdate.Threads=8`.**

- P1 must review **two distinct pinned-Core thread-safety concerns**, not claim they crashed: its direct `ConfigMgr::GetOption` under simultaneous reload, and its remote-target `ObjectAccessor::FindPlayer` pointer lookup/dereference. Pinned [Core header](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Globals/ObjectAccessor.h#L76-L80) explicitly warns whole-world lookup is not thread safe; the original Core Meeting Stone branch uses the same lookup, so this is *inherited source concern*, not proven new live defect. [Review handoff](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4#issuecomment-6541799047). **Do not stress-test logouts/cross-map races or live-reload flags as an unreviewed shortcut.**
- P2 `.bot consumables` can also grant **other consumables**, not merely ammo; a pilot may mint items and needs before/after inventory evidence and a character-state rollback.
- **Unrelated holds remain:** HonorOverflow OFF, F14 optional visibility OFF, A04 QuestLootProtection OFF until its eight-thread/H1/H2 review; N-Core pet relay NoWrite/OFF, D18 hard no-go. Functional F15 console archive/crash recorder still not installed.

## P1 Warlock — one approved four-character scenario

| Step | Person / exact observation |
| --- | --- |
| 1. First portal | Four **distinct eligible grouped characters**: Warlock **W**, nearby helpers **A** and **B**, distant target **T**. W casts **698**; W+A+B finish **GO194108 (type18)**. The resulting second portal is expected **GO194097 (type23)**, created by **61993**. Its appearance **is not a pass**. |
| 2. Second portal | A selects **T** and clicks GO194097. Narrow default-off pilot should route this *specific owned portal only* to nontriggered **61994**, **not native 23598**. Preserve T as A's target; record actual 61994/channel result. |
| 3. Final portal | **61994** should produce **GO179944 (type18)**. **A remains channeling**; **different helper B** completes the portal. Historical Core delays final completion **five seconds** before its **7720** path. Do not count an animation, object spawn or immediate B click as success. |
| 4. Arrival | T receives the real summoning request, **accepts**, and **actually arrives** at the intended location. **Only this finishes P1 acceptance.** |

P1 controls (only after safety review): invalid/underlevel/out-of-group/self target must not summon, no duplicate summons, ordinary Vanilla dungeon Meeting Stones remain restricted, TBC/WotLK controls follow their established rules; OFF mode retains the original baseline. [Full source-backed guide](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/test/cs01-p1-warlock-second-stage-pilot-20261030/docs/testing/P1-WARLOCK-SECOND-STAGE-PILOT.md).

## P2 Hunter ammunition — one approved Altbot session

1. Verify **one alive controlled Hunter Altbot** (not a human or rndbot) has a usable bow/crossbow with **Jagged Arrow 11285 selected**, sufficient level and inventory space. Record selected ammo ID and bag count. After *one separately approved* dungeon/raid `.bot consumables` profile, bag count must rise **only by shortfall to configured target**; selection remains **11285**. Fire ranged attacks and verify **real ammo consumption**. A message about supplied ammo is insufficient.
2. Repeat the corresponding positive with **gun + Accurate Slugs 11284**. Check **Doomshot 12654 selected** remains **untouched/skipped**, not replaced or freely duplicated. If ammo selection is 0, a compatible vendor fallback may enter bags but **is not auto-selected**, so firing must not be falsely declared ready.
3. Negative checks: unsupported/broken weapon, non-Altbot, full/insufficient bag space, unsuitable level/era, ordinary cooldown, no repeated bonus beyond target. Other profile grants are recorded separately. **Default `HunterAmmo.Enabled=0`; `AllowSelectedNonVendor=0` stays OFF even during a separately approved basic pilot.** [Detailed Hunter guide](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/docs/part40-to-part41-recovery-20261030/docs/HUNTER-AMMO-BOT-CONSUMABLES.md).

## Minimal evidence and return to safe baseline

Keep a short **private** record: tested source/binary revisions and effective flags; test date; per-step P1 outcome (GO IDs if observable, channel, actual target request and arrival); P2 selected ammo/item counts **before and after**, real shots, skips; unexpected side effects. Do not publish private server/character data in GitHub. A failed checkpoint remains **FAIL/UNVERIFIED** and should be reported separately.

After explicit owner-approved test, return switches to the reviewed default-OFF configuration using a safe restart plan; do not assume disabling the feature removes already-created ammo. Use the verified character backup for inventory rollback if necessary. **No server operation was performed by preparing this page.**
