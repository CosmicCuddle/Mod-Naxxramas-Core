# Five-feature integrated candidate — owner smoke-test and rollback preflight

**Scope:** prospective five-feature [integration draft #66](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/66), pinned candidate `146fad73a82729c5cde88e531f59725dff04ee24`. This document is an **S5/S6 plan only**, not proof that #66 passed its full Worldserver link, not installation instructions to execute now, and not approval for gameplay changes. Review the **actual final exact head** again if any source changes.

**Responsibility:** CosmicScript01 technical review, CosmicScript02 independent peer review. The owner's plan is **one comprehensive module upgrade**, not a silent partial deployment.

## Proof ladder — do not skip stages

| Stage | Evidence required | What it does NOT prove |
| --- | --- | --- |
| S1/S2 | Exact pinned C++ source contracts and model tests, defaults/readers checked | Live Pet, loot, quest, aura or event behaviour |
| S3 | Independent review of the exact source head; all known blockers documented | Full compilation or deployed compatibility |
| S4 | One complete pinned actual `worldserver` build **and link**, with all feature-specific executable/library markers and final SHA-256 at the SAME head | Successful server startup, world database binding, actual operator dependency versions or gameplay |
| S5 | Owner separately approves a backed-up deployment and opt-in test scope *after* matching their installed dependency SHAs and verifying scripts/SQL with read-only queries | All edge cases or production confidence |
| S6 | Individual feature pilot results, negative cases and rollback verified in the owner's environment, with independent exact-head review | Automatic merger or broad publication |

**Known exact evidence:** source tests passed on #65; #61 linked but **failed** two now-invalid contiguous literal grep predicates. #66 exact `146fad73a82729c5cde88e531f59725dff04ee24` now **COMPLETED PASS** full pinned Worldserver compile/link 1,887 Ninja tasks and 13/13 actual reader/source linked feature checks, [CI #39434876269](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39434876269). Do not retroactively mark #58, #59 or #61 CI green. Pinned #66 compilation is **NOT** owner-installed runtime acceptance. This smoke-plan CI cannot replace #66.

## Step 0 — mandatory owner approval and backups (NOT authorised yet)

1. Record the actual checked-out `git rev-parse HEAD` of AzerothCore, Playerbots, Individual Progression and Mod-Naxxramas-Core **on the owner's server**, including uncommitted local edits and configuration deviations. Pinned GitHub CI SHA checks do **not** prove installed SHA compatibility.
2. Obtain **separate owner permission** for a specific exact source candidate, complete Worldserver upgrade, config values, restart, SQL migration plan, test characters and fallback. A draft/green CI or this document is not permission.
3. Before any migration, save tested backups of **world, characters and auth** database as relevant, worldserver executable, module source, config and locally modified SQL/DBC. Verify the backups can be restored. Keep DBC/client archives backed up even when this candidate has no DBC delta.
4. Prepare a written rollback: stop Worldserver, restore prior known-good binary/module/config, **restore database from owner-verified backup if any SQL changed**; only use narrowly scoped migration-specific rollback where audited. Do not assume a Git revert undoes character/database writes.

## Step 1 — read-only installed database preflight (do not execute until owner approval)

The module registers `npc_naxxramas_hallows_end_soh` for Shade NPC 23543. The repository already contains `data/sql/db-world/2026_09_21_00_event_script_overrides.sql`; it **updates `creature_template.ScriptName` for entry 23543**. A successful binary symbol does **not** prove this row in the installed world DB has the correct value. NPC 23686 is the normal fire trigger and should retain its stock script. No SQL statements in this document mutate state.

```sql
-- Read-only; run against a verified acore_world selection ONLY after approval.
SELECT `entry`, `ScriptName`
FROM `creature_template`
WHERE `entry` IN (23543, 23686);

-- Read-only: the Eastern Plaguelands zone handler is a SEPARATE MANUAL bind.
SELECT `TypeId`, `ScriptName`
FROM `outdoorpvp_template`
WHERE `TypeId` = 6;
```

**EP is not automatically installed by a successful executable link.** The optional forward `docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql` is deliberately outside the module's auto-updater path and requires a **separate owner-approved** migration after backup. The narrowly scoped `docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql` only rebinds rows it installed; it is NOT universal DB restoration. The owner must approve any change after reviewing actual current row values.

### Automatic character-database SQL hazard (new A02 exploratory cache is **NOT** included in #66)

**P0 owner-approval gate:** At pinned Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd`, `src/server/database/Updater/UpdateFetcher.cpp:157-185` scans module subdirectories of `data/sql/` and includes every directory whose name contains the lowercase DB token. `DBUpdater.cpp:194-199` returns `characters` for the Character database. Thus any optional `data/sql/db-characters/*.sql` containing a hunter-autocast cache `CREATE TABLE` can be **automatically applied** when character DB updates are enabled. A header comment reading "DO NOT APPLY" does **not** prevent this discovery. The current owner-approved request is for a **draft design only**, not automatic SQL installation.

Before incorporating a future A02 cache PR, require its standalone SQL to live **outside** the module auto-updater tree, under a dedicated manual owner-approved `docs/install` path. Verify a restorable character-DB backup, the actual existing schema, and explicit permission before ever applying it. Do not accept a proposed cache indexed only by `owner_guid + pet_number` without proving safe lifetime identity: core `Pet::_SaveSpells` explicitly says pet numbers can be recycled. Do not accept separate unchecked `DELETE` and `INSERT` cache writes as atomic preservation. **Read-only negative source tests** in this PR reject any `mod_naxxramas_hunter_pet_autocast` SQL found inside an auto-discoverable module `data/sql` character directory; they do not execute SQL.

## Step 2 — initial config and dependency checks (before enabling anything)

In the candidate module's `conf/mod_naxxramas_core.conf.dist`, the following **optional** gameplay changes are 0: `NaxxramasCore.BotConsumables.HunterAmmo.Enabled`, `NaxxramasCore.QuestLootProtection.Enabled`, `NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled`, and `NaxxramasCore.HallowsEnd.SoloFire.Enabled`. F10 multiplier defaults to **3** but has no effect while F10 Enabled is 0. Existing unrelated defaults (Honor, Forced PvP, etc.) must not be globally reset to zero; preserve the owner's working configuration. EP handler is controlled through its SQL `outdoorpvp_template` binding rather than one of those four flags.

The five candidates are:
- Hunter Ammo bot provisioning (existing raid-consumables system): verify ammo matches equipped weapon, profession/bag/inventory boundaries and safe repeat on restock.
- Quest Loot Protection: packet-based, narrow `CMSG_AUTOSTORE_LOOT_ITEM` gate for a grouped eligible creature quest item; reject unauthorised pickup without breaking ordinary loot.
- Eastern Plaguelands tower lock and announcement: handler is a distinct **optional manual DB script binding**, verify existing worldstate/lock expiration, faction messaging and untouched stock EP before any binding.
- Molten Core Greater Fire Protection **one-shot**: verify aura refresh does not repeat every update, and ordinary protection/consumable behaviour remains unchanged while disabled.
- Hallow's End Shade SoloFire: with explicit owner opt-in and actual seasonal/event availability, verify one real player with bots, two real players, no real player, inactive event, config multiplier, fire spread and normal cancellation. **One-bucket extinguish is NOT implemented** in #66, because upstream trigger 23686 retains its stock `SPELL_WATER_SPLASH=42348` rule. Do not mark bucket instant-response complete.

## Step 3 — one-feature-at-a-time supervised smoke runs (LATER)

For each candidate, preserve a **before** state and an **after** observation (screenshots/log timestamps and exact settings), verify that disabled behaviour matches stock first, then enable **only that single approved optional flag or binding** in a controlled operator window. Stop and roll back if behaviour differs. Verify both expected result and a negative case (different class, different loot owner, normal MC encounter, multiple real players, off stage/season). Record the disabled-restored state after each test. No character, item, inventory, pet or SQL modification should be silently performed by the test plan itself.

A green source/S4 result may justify **requesting** owner permission to begin S5, but cannot imply that permission exists.

## Known OPEN/BLOCKED features OUTSIDE this five-feature S4 candidate

- **A01 Golemagg melee run-out/run-in:** source read-only action audit/probe is draft and opt-in; no safe action-level public movement veto proven. No fix.
- **A02 human Hunter pet autocast ON/OFF persistence:** #60 intentionally aborts all ON restores without authoritative accepted-choice signal. #67 source survey confirms polling a buffered packet cannot prove explicit OFF acceptance. No functional fix.
- **A03 NT1 changed-build Altbot Apply:** core direct learning may partially commit; reset may mutate/mail offhand gear. Existing changed-build path rejects on safety grounds. No gear-inert functional Apply.
- **F10 bucket one-hit:** stock Shade fire NPC 23686 handles splash via reduce-by-two, not unconditional extinction. Separate optional hook feasibility investigation; not included.

Never present S4 acceptance as *complete module release acceptance* while those requirements remain open. **No owner action is requested by this draft.**

## Operator signoff record template (fill only during later authorised S5/S6)

| Gate | Actual value / evidence | Result |
| --- | --- | --- |
| Owner approval for named commit and backup | Unrecorded | NOT STARTED |
| Installed core / PB / IP / module SHAs | Unknown | BLOCKED |
| Exact-head all-five S4 Worldserver binary | #66 head `146fad7`, [CI #39434876269](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39434876269): 1,887 Ninja units; 13/13 markers; SHA-256 `04f5f7467ace71f31947415b83ed65f87ee999d83a93962278d8adbcfce9388d` | PASS for pinned build only |
| World/character/auth backup and restore check | Not attempted | BLOCKED |
| Shade script row 23543 and trigger 23686 SELECT | Not executed | BLOCKED |
| EP handler TypeId 6 SELECT / approved bind | Not executed | BLOCKED |
| Four optional config flags disabled at baseline | Candidate source yes, operator config unknown | NOT TESTED |
| Five feature pilots and negative checks | No owner in-game session | NOT TESTED |
| Rollback rehearsal and owner final acceptance | No owner test/release | BLOCKED |

[Master development tracker #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) · [CosmicScript coordination #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48). No deployment, merge, world SQL execution or live-server access is implied.
