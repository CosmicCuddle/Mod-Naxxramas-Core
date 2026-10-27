# Part28 — owner-authorised three-feature gameplay acceptance

**PREPARATION ONLY · NOT PERMISSION TO INSTALL, RUN, ENABLE, MERGE OR DEPLOY.**

This short operator worksheet is for **GFPP 120 seconds**, **F12 physical Scarlet Monastery exits**, and **F13 Vanilla-stage Atiesh exterior landing**. All three already exist together in the **protected, unmerged draft PR #160**, exact `a7523ebb823169edc969d971d00aa293119f2f05`. Its [full pinned integrated Worldserver source/native + link workflow](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40229204745) is **COMPLETED SUCCESS**. This is **source/build proof only**; the owner's installed core, custom Playerbots, Individual Progression, DBC, live SQL rows, map geometry and config have not been verified.

**Do not treat this worksheet as approval.** The owner must separately approve the exact binary/source combination, staged server or maintenance window, which flags may be changed, backup and restore process, and individual gameplay trials. Never try it directly on a live realm or silently merge #160. Keep `MapUpdate.Threads=8`; do not modify core, Playerbots, IP, database, DBC or client files as part of this plan. Default state is **OFF**.

## Gate 0 — complete before any runtime testing

- [ ] **Written owner approval:** exact staging host/build and features authorised; confirm this is not the production service and no private data will enter the PUBLIC repository.
- [ ] **Installed-source compatibility:** privately record exact installed AzerothCore, custom Playerbots and IP revisions, enabled modules, module build and config. The public CI pins are not the installed versions. Resolve any incompatible code or data first.
- [ ] **Restorable rollback:** create and verify recoverable snapshots of the staging binary, original module config and all deployment-dependent data. Record how to recover the prior binary/config; test the restore procedure before any staging change. Back up affected characters/world data under an approved private policy if the test environment shares mutable state.
- [ ] **Controlled state:** only individually approved opt-ins; all unrelated module switches remain OFF. Changes to F12/F13 startup-snapshot settings require an approved **restart**, not `.reload config`. Start with one feature and one eligible human/bot. No CLI automation, host commands or SQL steps are granted by this document.
- [ ] **Evidence:** keep screenshots/timestamps, current build identity, config state and character facts **private**. Report only pass/fail and a non-identifying symptom summary to PUBLIC GitHub.

## Gate 1 — GFPP one-time 120-second refresh

Source: #160 keeps #120 `NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled = 0` until separately approved.

- [ ] In a **permitted staged** Molten Core case with one genuinely eligible grouped/controlled bot, enable ONLY this setting with the owner-approved restart or configuration method. Issue the normal `.bot consumables mc` command and confirm Greater Fire Protection was **actually applied/preserved**. Start a stopwatch at that success, not at login.
- [ ] Before ~120 seconds: observe **no** one-shot refresh. At the first eligible processing tick **at/after 120 seconds**, observe **one** refresh attempt. Record actual timestamp and aura remaining time. It is update-tick scheduled, not a guarantee of execution exactly at the wall-clock millisecond.
- [ ] Continue beyond ~240 seconds with the **same command invocation**: no second one-shot refresh. A fresh command, if approved, is a **new** eligible sequence.
- [ ] Repeat the negative case using a bot that leaves the party/instance or dies before its deadline: no delayed or redirected reattempt after return, and no change to Juju Flurry's independent behavior.
- [ ] Return this one-shot switch to **OFF** using the documented safe rollback and confirm ordinary baseline behavior.

**Pass only if:** one intended attempt at first eligible >=120-second update, no premature/second repeat, and excluded bots are not targeted. A unit timer passing CI is not a stopwatch result.

## Gate 2 — F12 Scarlet Cathedral and Armory door exits

Settings are restart-only: `NaxxramasCore.ScarletExits.Enabled`, `UseVanillaDoorTargets` and `RouteDungeonFinderExits`. Default: master OFF; vanilla door targets ON; Dungeon Finder reroute OFF.

- [ ] With feature **OFF** and permission, document baseline normal entrance/exit behavior in each wing, including orientation and whether there are private trigger or map overrides.
- [ ] With **only** `ScarletExits.Enabled=1` in an approved staging restart, enter **Cathedral** through outside area trigger 610, exit through 604. Observe arrival **outside Cathedral's own door** and verify no immediate bounce into the dungeon. Repeat **Armory** outside entrance 612, exit 606, outside its own door.
- [ ] Confirm the Graveyard and Library entrances/exits were **not changed**. Check normal groups and an approved Dungeon Finder comparison: `RouteDungeonFinderExits=0` leaves Dungeon Finder behavior stock.
- [ ] In a safe negative case (missing/unsafe owner-side trigger row, already on destination map, denied native eligibility), the module must **not** send a character to an unsafe hard-coded point. Record stock fallback or a clear fail-closed outcome; no forced teleport workaround.
- [ ] Return master flag OFF through a restart, confirming baseline.

**Pass only if:** 610↔604 and 612↔606 lead to their correct physical wing doors with safe landing/facing, while unrelated/dungeon-finder routes retain agreed stock behavior. Numeric geometry in public source is not proof of live map height.

## Gate 3 — F13 Atiesh Vanilla exterior arrival

Setting: `NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled=0` by default, applied on startup only.

- [ ] Verify privately that the installed Individual Progression header/era logic matches the staged build, the normal Atiesh portal object/template is as expected, and the exterior Karazhan return/exit row **4436** is valid. This is *not* permission to change those rows.
- [ ] With explicit approval, enable the flag for a **Vanilla-stage human character** and use the actual **Atiesh portal game object** (not a direct bot `28147` cast). Confirm character arrives **outside the main Karazhan gate**, with safe height/facing, and is not taken inside the instance.
- [ ] Check a non-Vanilla stage character, a GM and an unrelated portal object: each must retain **stock** behavior. For a group-owned portal test the owner/party restriction without bypassing it.
- [ ] Verify an invalid/missing exterior destination or refused teleport **fails closed** with no inside-cast fallback; do not deliberately corrupt live rows or put a character in an unsafe location.
- [ ] Restore the setting to OFF through a staged restart and confirm stock behavior.

**Pass only if:** Vanilla eligible GO use arrives outside; later-stage/GM/nonmatching cases stay stock; failures do not fall back inside. A direct spell cast deliberately bypasses this module hook, so it is **not** a valid positive trial.

## Gate 4 — record and stop

| Feature | Owner test result | Exact staged build/restart privately recorded? | Rollback privately verified? |
| --- | --- | --- | --- |
| GFPP 120 seconds | NOT RUN | No | No |
| F12 Cathedral and Armory | NOT RUN | No | No |
| F13 Atiesh Vanilla exterior | NOT RUN | No | No |

If any required observation fails or owner-installed source differs from the approved candidate, **stop that feature**, keep it OFF and return to source diagnosis rather than silently altering data, loot, maps or progression.

**Not included / still blockers:** A02 genuine human Hunter manual autocast choices plus synchronized SelfBot/rank/pet-birth proofs; A04 **two separate** reported human quest-loot symptoms; F15 automatic crash + warning/error reporting for both Worldserver and Authserver; and F14 optional `/who` (OFF). The *combined five-gameplay-feature release* remains **0/5 owner-accepted** until the separate conditions are actually verified and explicitly signed off. Nothing in this public worksheet requests private item, quest, loot, NPC, SQL, account, host or IP relationship details.
