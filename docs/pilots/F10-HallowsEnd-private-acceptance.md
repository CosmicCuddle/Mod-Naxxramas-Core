# F10 Hallow's End — isolated source candidate and operator gate

Status: **DRAFT / SOURCE-ONLY / NOT INSTALLABLE YET** (21 October 2026). Owner approved Hallow's End **priority**, not execution. Reviewed donor: [frozen PR #74](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/74) `c06f9983d02a999ed77d805b3af6644f1e9e5dd5`. Do not merge or run on a realm from this draft.

## Actual source scope

This branch starts from `main` `1f5f317c3991bbac66cc92a7112bbde3c929c232`, not from the five-feature staging branch. It replaces only `src/Events/HallowsEndShadeOfTheHorseman.cpp`, adds `src/Events/HallowsEndSoloFire.h`, `src/Events/HallowsEndSoloFireConfig.cpp`, three OFF-by-default `conf/mod_naxxramas_core.conf.dist` event keys, and adds F10-local tests / ephemeral CI / this gate. The three runtime C++ blobs are byte-for-byte the previously reviewed six-feature donor. Existing module loader remains unchanged. No Golemagg, Hunter, talents, quest loot, EP towers, MC consumables, core, Playerbots or IP runtime changes are proposed in this draft. Main's pre-existing systems are *still in the module*; do not misrepresent the whole module as event-only.

## Hard SQL/updater blocker: do not install even with settings OFF

Existing tracked `data/sql/db-world/2026_09_21_00_event_script_overrides.sql` contains **BOTH** Brewfest `creature_template.entry=23703` and Hallow's End Shade `entry=23543` mutations. This file is intentionally **unchanged** here to preserve historical migration hashes. Grimfeather's auto-updater can discover module world SQL, so a pull/restart may apply unrelated changes even when event settings are OFF. Other module world migrations also exist. Do **NOT** copy/restart a checkout or apply this file until complete world-updater containment and update-history inspection are approved and independently validated. Never solve this by editing the historical migration in place: a changed hash could cause reapplication. Actual owner updater settings, source SHAs and DB bindings are unknown.

## Ordered operator approval gates (NO action taken)

1. **Separate owner permission for read-only server/DB preflight.** Identify installed core/Playerbots/IP/module Git SHAs, active module path and World DB updater settings. Review **all** module `data/sql/db-world` filenames against DB update history; verify server-start behavior before any pull/restart. Determine Hallow's End event end on this private realm.
2. **Separately approved verified backups** of module source, active configurations, world DB, and any affected data. Prove restoration on a safe isolated copy; record original 23543, 23703 and related script bindings before any mutation.
3. **Only after approval to READ world DB**, consider these SELECT statements in the verified world schema (do not run now):

   ```sql
   SELECT entry, ScriptName FROM creature_template WHERE entry IN (23543, 23686, 23537, 23703);
   SELECT spell_id, ScriptName FROM spell_script_names WHERE spell_id IN (42339, 42348);
   SELECT name, hash, state FROM updates WHERE name = '2026_09_21_00_event_script_overrides.sql';
   ```

   The updates schema and relevant module state must be verified before trusting the third query. Confirm event 23543 is bound to `npc_naxxramas_hallows_end_soh`; ensure no changes to Brewfest 23703, normal fire 23686, training fire 23537, and stock 42339 script binding. If any value differs, stop and draft a separately reviewed, minimal row-specific change with an **exact old-value guard**, affected-row check, backup, and matching rollback. NO mixed migration execution.
4. **Separate permission for deployment / SQL if unavoidable / config activation / restart**, each with preflight evidence. Stage the source tree with the module updater safely contained; activate only `NaxxramasCore.HallowsEnd.SoloFire.Enabled = 1` and, for a deliberate one-bucket test, `NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 1`; period multiplier defaults to 3. Preserve a known-good binary and config. Do NOT enable unrelated draft features.
5. **Separate owner-approved private in-game acceptance** of solo real human, human+Playerbots, bot throwing bucket, two real players, unowned/training fire, missing 42132 ignition, overlapping living Shades, normal 42348 splash/other aura and child fire, quest credit and failure/cleanup. Actual 42348 missile speed, effect ordering and stock `RemoveAllAuras` impact remain unproven. If unintended aura, quest-credit or fire behavior occurs: stop testing, disable both flags, return to the known-good binary/config, restore DB only under the approved rollback protocol, and verify original 23543/23703 binding.

## Required independent verdict

CosmicScript02: review this exact source head and confirm that this branch contains only event source changes relative to `main`; verify unchanged donor blobs, no incidental five-feature additions, three OFF defaults, stock splash, no training-fire/child/unrelated-aura side effects, and the SQL updater STOP gate. If real source-level 42339→42348 ordering demonstrates a defect, submit a minimal fix on a *separate* draft for reciprocal review. CI link proves compile, not startup/gameplay.

Completion requires source CI PASS, cross-review, explicit updater isolation evidence, reviewed reversible test/rollback, separate owner approvals, and owner-confirmed in-game acceptance. All other roadmap tasks remain parked in [Issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28).
