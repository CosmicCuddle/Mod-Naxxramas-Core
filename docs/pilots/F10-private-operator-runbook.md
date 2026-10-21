# F10 Hallow's End — private pilot operator runbook (review draft)

**Scope:** This document accompanies the frozen F10 source candidate, draft PR #77 at `4dc63b3a0df11b35dea7035dae472d6aa947b506` (base `main` at `1f5f317c3991bbac66cc92a7112bbde3c929c232`). The [exact-head Worldserver CI run](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39584426670) passed 1,885/1,885 linked tasks, policy tests and binary symbol checks. CosmicScript02's independent #77 source review passed scope/source only (COMMENTED). **The owner's installed server, database records, binary, configurations and gameplay have NOT been inspected or tested.**

**Draft only. Not a command to deploy.** Each section has a separate permission gate. Do **not** merge PR #77; run `git pull`; switch the installed module to a pilot branch; install SQL; edit an active config; stop/restart servers; or touch live game data based on this document alone. In particular, config defaults OFF do **not** disable database auto-updates.

## A. Read-only facts first (separate owner-approved gate)

The owner prefers the existing `git pull → recompile → Worldserver restart → private in-game test` workflow. Preserve it, but first discover reality instead of guessing paths. The repository README's sample installation path is **not proof** of the owner's installed path.

Start with one short **non-mutating** process listing in MobaXterm (may be shared after review):

```bash
ps -eo pid,ppid,comm | grep -Ei 'worldserver|authserver|pm2|tmux'
```

This displays process names and PIDs, not command lines, passwords or connection strings. If no match, stop and investigate separately. Do not blindly run `pm2 start 0`/`pm2 stop 0`, kill a service, restart authserver, or assume a tmux session owns the Worldserver. PM2 may auto-restart a stopped Worldserver; an unplanned restart can run module SQL before containment. Identify the *actual* supervisor/process/restart policy later through individually reviewed read-only checks. **Never paste PM2 environment dumps or full process command lines**: they may contain credentials.

After verifying the **actual** source directory and receiving permission for the next read-only command, enter it and capture (no local source changes):

```bash
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
git status --short --branch
```

Run those separately for actual Naxxramas Core, AzerothCore/Grimfeather core, Playerbots and Individual Progression directories. Record original branch/commit/dirty files; if *any* uncommitted edits, detached HEAD, mismatched origin, symlink ambiguity or incomplete repo, **STOP** and choose a preservation plan before fetching. Do **not** paste credential-bearing `git remote -v` URLs without redaction. Do not use `git reset --hard` or `git clean`.

Find the *effective* active Worldserver and Playerbots configuration paths, include/override precedence and actual startup executable first, without sharing database connection strings. At the exact pinned sources:
- AzerothCore Worldserver `Updates.EnableDatabases` defaults to **7**; setting **0** suppresses its Auth/Characters/World automatic updater callbacks but not DB connections or normal gameplay writes.
- Playerbots has a **different** DB updater; `Playerbots.Updates.EnableDatabases` defaults to **1** and is not disabled by the core setting. For a separately authorised pilot, BOTH effective values must be **0** before any start.
- Environment keys `AC_UPDATES_ENABLE_DATABASES` and `AC_PLAYERBOTS_UPDATES_ENABLE_DATABASES` may override files. Inspect the effective Worldserver-process environment **without disclosing any other environment variables**. Misparsed/missing config can fall back to updater-ON defaults.
- Do **not** restart authserver as a collateral step; its updater has separate configuration. No startup is safe solely because one file contains a 0.

**Database inspection requires its own owner approval and least-privilege, SELECT-only login.** Discover and confirm actual DB identifiers and engines (World, Characters, Playerbots; Auth if necessary) without sharing passwords. Before relying on the update-history query, inspect each DB's `updates` schema and the installed updater version. Check the *installed* migration-file bytes and hashes against the [15-file Naxx manifest](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/77#issuecomment-6314329884), and separately audit applicable core, IP and Playerbots update files. The mixed legacy event file's **RAW SQL SHA-1** is `315746191db9f1f1091911e9a1671b37a1d14339` (not its Git blob ID `18fa2c1bc9a7a8983e5093f2383142ca16e36691`). Missing/changed DB `updates` history, an unexpected candidate migration, an unverified hash or a required incompatible schema change means **STOP**, not editing `updates` history.

After database identification, the following *examples are SELECT-only* in the verified **World DB** (do not run until separately approved):

```sql
SELECT entry, ScriptName
FROM creature_template
WHERE entry IN (23543, 23686, 23537, 23703);

SELECT spell_id, ScriptName
FROM spell_script_names
WHERE spell_id IN (42339, 42348);

SELECT name, hash, state
FROM updates
WHERE name = '2026_09_21_00_event_script_overrides.sql';
```

Expected Shade entry 23543 binding: `npc_naxxramas_hallows_end_soh`; original values for *every* entry must be recorded, especially Brewfest 23703 and training fire 23537. The stock 42339 bucket/spell hooks must match the pinned source and runtime setup; do not guess if data differs. The 23543 and 23703 updates coexist in the **same old SQL file**. Do not edit or blindly execute that file, and do not overwrite unrelated world rows.

## B. Backup and isolated restore (separate owner-approved write gate)

**This section is a design for backup approval, not executable actions yet.** After A, record the actual verified paths and service process, backup target, file ownership, disk capacity, schemas and DB storage engines, plus a separate protected storage location. Before an installed checkout/rebuild:
1. Preserve **full current source/worktree including untracked local files**, the original Git SHAs/branches and the exact currently used Worldserver binary (plus executable permissions, ownership, and service startup path); include any compiled module artefacts as appropriate.
2. Preserve byte-for-byte copies of the **effective** `worldserver.conf`, `mod_naxxramas_core.conf`, `playerbots.conf`, their include files and any relevant launcher/supervisor settings; do not disclose passwords.
3. Back up all potentially affected databases: **World**, **Characters**, **Playerbots** and **Auth** where a discovered update path, restart or rollback dependency requires it. Choose a compatible `mariadb-dump`/`mysqldump` strategy for the **observed engine** (a `--single-transaction` dump is not a full transactional guarantee for nontransactional tables). Use protected credentials, no password on the command line, protected backup storage, no repo uploads.
4. Record sizes and SHA-256 for every backup and a matching timestamp/manifest; test **complete isolated restoration** to a disposable, disconnected DB/server before touching the real installation. A dump command exit code or hash alone does NOT prove restorability.
5. Explicitly confirm who/what can restart the Worldserver automatically and how the already running service will remain safe through a future approved deployment window.

**STOP** if backup/restore cannot be independently validated, if credentials/DB engine/path is uncertain, if the user would lose uncommitted edits, or if the pilot could be restarted automatically with unverified updater settings.

## C. Exact Git and build plan (requires separate permission after A and B)

**Do not `git pull` on local `main` and expect F10**: the reviewed F10 code is *only* on draft branch `pilot/f10-hallows-end-only-source-2026-10-21` at exact SHA `4dc63b3a0df11b35dea7035dae472d6aa947b506`; the tracked `main` SHA is `1f5f317c3991bbac66cc92a7112bbde3c929c232` as of this runbook. Pulling that remote pilot branch *while on main* could merge it into a local branch unexpectedly. Do not merge PR #77 into remote `main` before a separate owner decision.

For an **approved** no-merge private pilot: after a clean worktree and backups, identify/verify the actual remote, fetch the named pilot branch without merging, verify fetched full SHA **exactly**, and switch to a **new, unmistakably named temporary local pilot branch** at that SHA. Stage/compile with the owner's confirmed core/PB/IP versions and existing CMake/build/install procedure. Do not replace the known-good binary or active configs until A/B and the separate owner deployment/restart approvals are complete. Never copy runner binary SHA-256 `baf7eaf...` as though it were the owner's reproducible compiled binary: it identifies CI's *ephemeral* runner build only.

The three F10 config keys in PR #77's distribution file (not necessarily in the owner's active file) are:
```ini
NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0
NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier = 3
NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 0
```
No active config change is implied. Use **effective** core and PB updater settings, with all environment overrides checked; both updater controls must stay 0 only for the separately reviewed isolated pilot. If missing requisite migrations break startup, **STOP**, do not casually re-enable automatic updates. Keep Authserver untouched. Preserve prior config for rollback; restoring updater-ON settings to an unchanged old binary may still run outstanding migrations, so restoration itself requires risk review.

## D. Conditional row-23543 fix (NOT APPROVED and normally unnecessary)

Only if the separately approved read-only query proves 23543 is **not** `npc_naxxramas_hallows_end_soh`, propose a *new* explicit owner-reviewed one-row update with verified old value, matching reverse action, full DB backup, an isolated rehearsal and a transaction/affected-row expectation. **Never run the mixed 23543+23703 historical file** or alter `updates` history merely to make the test work.

**SQL TEMPLATE — NOT runnable until manually replaced, reviewed and separately authorised:**
```sql
-- The reviewer must replace the placeholder with the exact SELECT-observed
-- previous ScriptName and handle SQL quoting/NULL correctly.
START TRANSACTION;
UPDATE creature_template
SET ScriptName = 'npc_naxxramas_hallows_end_soh'
WHERE entry = 23543 AND ScriptName = '<VERIFIED_OLD_SCRIPTNAME>';
-- Confirm ROW_COUNT() = 1; if not, ROLLBACK and STOP.
-- COMMIT is permitted only after an explicit approved change-window check.
```

**Rollback template (separately reviewed, not automatically applied):**
```sql
START TRANSACTION;
UPDATE creature_template
SET ScriptName = '<VERIFIED_OLD_SCRIPTNAME>'
WHERE entry = 23543
  AND ScriptName = 'npc_naxxramas_hallows_end_soh';
-- Confirm ROW_COUNT() = 1; otherwise ROLLBACK / STOP.
```

If no row change is required, **no SQL is proposed**. Never touch Brewfest 23703, training fire 23537, normal trigger 23686, or global stock 42339/42348 registrations merely to simplify the pilot.

## E. Private gameplay acceptance (separate owner approval; not yet performed)

First record baseline with **both** optional F10 flags OFF (if an owner-approved safe event test is possible). Then deliberately enable only the agreed F10 flags under the separately approved restart procedure, keeping unrelated draft features OFF. Record the event schedule/time remaining on the actual private realm; do not infer its end date from retail.

| Case | Observation required |
|---|---|
| Solo pacing | Exactly one real human and one or more Playerbots: bots are excluded from the solo population count; note the visible wave timing/pacing |
| Normal bucket | Genuine Shade-ignited entry **23686** bearing aura **42074**, including amount 3: one accepted real-player bucket spell **42339/effect 0** extinguishes targeted 42074 |
| Negative casters | Bot-cast bucket, two real humans, solo flag OFF, OneBucket OFF: no module-only fast extinguish |
| Negative targets | Training entry **23537**, never-Shade-ignited/foreign/child fires, absent 42074: untouched by custom removal |
| Owner overlap | Two living owning Shades / no valid Shade / Shade Reset: one-bucket policy refuses incorrect owner census |
| Stock splash | **42348** spell timing, stock small-fire `RemoveAllAuras` impact and unrelated auras; compare with baseline, do not claim the module can undo stock behaviour |
| Event lifecycle | Success/failure, cleanup/reset, quest credit and Brewfest/other game-event scripts retain expected behaviour |

Capture only screenshots/log excerpts without account credentials, private player data or connection strings. If a regression occurs, **STOP**, turn off F10 under the approved procedure, and use F after owner rollback consent.

## F. Rollback and verified return to normal (separate approval)

Follow the **actual preflight-recorded** original branch/commit, module worktree, binary, config copies, file permissions and service/supervisor plan. Restore only the explicitly impacted databases from tested backups if the approved incident assessment requires it; broad DB restore can destroy legitimate gameplay progress since backup. Verify the original 23543/23703/23537/23686 script bindings, stock 42339 registrations and DB update history before any further startup. Do not automatically restore `Updates.EnableDatabases=7` or `Playerbots.Updates.EnableDatabases=1` just because these are defaults: restore the **owner's verified original effective values** only after pending migration safety has been reviewed and approved. Recheck Worldserver logs for errors and confirm known-good behaviour. Any uncertainty => leave the realm stopped for further review rather than risk hidden writes.

## Approval ledger

| Gate | Evidence needed | Current state |
|---|---|---|
| S4 source | Exact #77 head CI, source review | **PASS** (source only) |
| S5A read-only installed inventory | Owner explicitly permits inspection; installed path/SHAs/config/supervisor/DB query results | **NOT PERFORMED** |
| S5B backup+isolated restoration | Separate owner consent, protected files/dumps, restore proof | **NOT PERFORMED** |
| S5C installation/recompile/config/SQL/restart | Separate owner consent for each proposed action with S5A/B evidence | **NOT APPROVED** |
| S6 private gameplay | Separate owner consent and completed matrix, user acceptance | **NOT PERFORMED** |

Everything above is a **reviewed-pilot proposal**, not authorization to merge, run SQL/DBC, restart, modify a live config, stage source, or touch the user's account/characters/bots. The unrelated A01/A02/A03 module roadmap remains paused, not abandoned.
