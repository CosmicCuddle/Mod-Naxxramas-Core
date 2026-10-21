# F10 Hallow's End — private pilot runbook

**Status: DRAFT. Nothing in this runbook is approved.** Each stage (A–F) needs the server owner's separate explicit approval before that stage starts. Do not inventory a live server, take a backup, change config, fetch, build, bind SQL, restart, or enter the game on the strength of this file.

Source proof is [PR #77](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/77) head `4dc63b3a0df11b35dea7035dae472d6aa947b506` on `pilot/f10-hallows-end-only-source-2026-10-21`. [CI run 39584426670](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39584426670) succeeded: 5/5 `test_f10_event_only_candidate.py` tests, marker `F10_ONE_BUCKET_POLICY_OK`, link `[1885/1885]`, runner-only `worldserver` sha256 `baf7eaf57d38a765a8c202f7b61b5e336407edb5bbfba55d83b09220789760b3`. That binary was not uploaded and is not a distributable build. **In-game behaviour is NOT TESTED.**

`main` is `1f5f317c3991bbac66cc92a7112bbde3c929c232` and does not contain this F10 source. A normal `git pull` on `main` will not install it.

Companion gate: [F10-HallowsEnd-private-acceptance.md](F10-HallowsEnd-private-acceptance.md). Installed paths, database names, credentials, supervisor roles, and live query results are **UNKNOWN** until Stage A fills them in. Use the placeholders below. Redact credentials in every record.

CI pins (the run above, not the owner's install): core `8daffdabe9202c228e45d833c9a1d399597a15cd`, mod-playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c`, mod-individual-progression `4ff4b5fcc1480348f058c632573143e62d4e3a41`.

Dist defaults at this head (`conf/mod_naxxramas_core.conf.dist`), not live values:

| Key | Dist default |
|---|---|
| `NaxxramasCore.HallowsEnd.SoloFire.Enabled` | `0` |
| `NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier` | `3` |
| `NaxxramasCore.HallowsEnd.SoloFire.OneBucket` | `0` |

`Enabled` treats any value other than `1` as `0`. `OneBucket` is experimental and requires `Enabled = 1`.

Creature `23543` registers in C++ as `npc_naxxramas_hallows_end_soh` (`RegisterCreatureAI` on that struct; same name in `data/sql/db-world/2026_09_21_00_event_script_overrides.sql`). Creature `23703` (Brewfest) is `npc_naxxramas_dark_iron_attack_generator` in that same file. The source comment names stock AzerothCore `npc_hallows_end_soh` as the script this module replaces. That comment is not a live reading. `<EXPECTED_OLD_SCRIPTNAME>` comes only from Stage A.

This module has no `db-auth` SQL at this head. It has 12 world and 3 characters migrations. Do not edit those files. A hash change can make the updater apply them again. The only SQL this pilot may later apply is the Stage E template, and only with its own approval.

## Stage A — read-only inventory

No changes. No restart. No `git checkout`, `pull`, or `fetch`. SQL below is a template: run it only after the server owner approves Stage A, against the databases Stage A has already identified by name.

Record every row. Leave **UNKNOWN** rather than guessing.

| Item | Value |
|---|---|
| `<MODULE_DIR>` | UNKNOWN |
| Git remote(s) | UNKNOWN |
| Branch | UNKNOWN |
| Commit | UNKNOWN |
| `git status --porcelain` | UNKNOWN |
| Symlinks inside the module and server tree | UNKNOWN |
| Core SHA (installed) | UNKNOWN |
| Playerbots SHA (installed) | UNKNOWN |
| Individual Progression SHA (installed) | UNKNOWN |
| Other installed modules and SHAs | UNKNOWN |
| Build directory | UNKNOWN |
| Owner's build command | UNKNOWN |
| `worldserver` binary path | UNKNOWN |
| Active `worldserver.conf` path | UNKNOWN |
| Active `mod_naxxramas_core.conf` path | UNKNOWN |
| Active `playerbots.conf` path | UNKNOWN |
| Effective `Updates.EnableDatabases` | UNKNOWN |
| Effective `Playerbots.Updates.EnableDatabases` | UNKNOWN |
| `AC_UPDATES_ENABLE_DATABASES` | UNKNOWN (value only; redact the rest of the environment) |
| `AC_PLAYERBOTS_UPDATES_ENABLE_DATABASES` | UNKNOWN |
| Which file or env wins for each updater flag | UNKNOWN |
| `<AUTH_DB>` `<WORLD_DB>` `<CHARACTERS_DB>` `<PLAYERBOTS_DB>` | UNKNOWN |
| `updates` rows for the 15 module files (name, hash, state) | UNKNOWN |
| Pending or hash-mismatched updates | UNKNOWN |
| `creature_template` ScriptName 23543 / 23703 / 23686 / 23537 | UNKNOWN |
| `spell_script_names` for 42339 / 42348 | UNKNOWN |
| tmux session(s), including whether `worldserver` exists | UNKNOWN |
| PM2 list (index, name, script, cwd, restart policy) | UNKNOWN |
| Which supervisor actually owns worldserver | UNKNOWN |
| Watchdog / auto-restart | UNKNOWN |
| Log path and uptime | UNKNOWN |
| authserver process (record only) | UNKNOWN |

Historical note only: the owner has used tmux session `worldserver` and PM2 index `0` (`pm2 stop 0` / `pm2 start 0`). Current roles are **UNKNOWN**. Do not treat index 0 or that session name as the worldserver.

Manifest for **this commit only** (raw file SHA-1, the updater hash). Compare to the installed `updates` tables. Do not rewrite history to force a match. A missing name is a STOP, and a matching hash under a different name is also a STOP (the updater can treat a renamed file as already applied).

| DB | File | Raw SHA-1 |
|---|---|---|
| characters | `2026_09_24_00_honor_reset.sql` | `d4c07bec79ccd143d3b0a5e452d0e3a819788282` |
| characters | `2026_10_08_00_arcane_momentum.sql` | `0c21e8c55b1a154360a3bc24a3322e4de0b0fd84` |
| characters | `2026_10_10_00_bot_talent_import.sql` | `7a19a342e90a03444556ace75d91a1b26b29c24b` |
| world | `2026_09_19_00_mod_custom_class_spell.sql` | `45bc5b7233232957216a47b61c813c4ea42d089a` |
| world | `2026_09_20_00_orc_blood_fury.sql` | `d539ae59ebda68ec6111897e3f77c3966252418f` |
| world | `2026_09_20_01_troll_berserking.sql` | `b135152f7c0cc196206b04f5e05c50bef76384b6` |
| world | `2026_09_20_02_blood_elf_mana_tap.sql` | `5385f5f4a39036c5a2d3db28c9589e281f9ccdac` |
| world | `2026_09_20_03_blood_elf_arcane_torrent.sql` | `8143812623b9a43dec1594dca65765ee555a5bbb` |
| world | `2026_09_21_00_event_script_overrides.sql` | `315746191db9f1f1091911e9a1671b37a1d14339` |
| world | `2026_09_21_01_touch_of_the_grave.sql` | `fca7c2c07dde2f1480046c26364f282784fe731d` |
| world | `2026_09_24_00_item_spell_overrides.sql` | `0da079c4ede250f8d39092e9e57323142ebbfd6c` |
| world | `2026_09_29_00_brewfest_sober_gossip.sql` | `6be3e0b77d0376467e10b83d236b49629505e0cc` |
| world | `2026_10_07_00_shaman_rockbiter.sql` | `ab73acd4824d2119a174a73f4dbc7c398366abd1` |
| world | `2026_10_08_00_arcane_momentum.sql` | `d1af947fdaddc9daf6dab9637f1fe54416a13413` |
| world | `2026_10_09_00_monthly_elemental_invasions.sql` | `ad5b4dae2955da5fcf9c8c1b7b74d4642f1a42a1` |

Confirm the installed `updates` columns before trusting this. When comparing textual hexadecimal hashes, normalise upper-/lower-case; **a case mismatch alone is not a different SHA-1**. This only applies to case, not to missing/renamed rows, unexpected state, changed bytes or another mismatch. These 15 files are not the core, Playerbots, or Individual Progression migration inventory. List those directories too. Individual Progression's `data/sql` tree still has to be accounted for before any start.

```sql
-- TEMPLATE - DO NOT RUN without separate owner approval.
-- Stage A, read-only. Repeat on <WORLD_DB> and <CHARACTERS_DB>.
-- Add <PLAYERBOTS_DB> for that module's own updates table (not these 15 names).
SELECT name, hash, state
FROM updates
WHERE name IN (
    '2026_09_24_00_honor_reset.sql',
    '2026_10_08_00_arcane_momentum.sql',
    '2026_10_10_00_bot_talent_import.sql',
    '2026_09_19_00_mod_custom_class_spell.sql',
    '2026_09_20_00_orc_blood_fury.sql',
    '2026_09_20_01_troll_berserking.sql',
    '2026_09_20_02_blood_elf_mana_tap.sql',
    '2026_09_20_03_blood_elf_arcane_torrent.sql',
    '2026_09_21_00_event_script_overrides.sql',
    '2026_09_21_01_touch_of_the_grave.sql',
    '2026_09_24_00_item_spell_overrides.sql',
    '2026_09_29_00_brewfest_sober_gossip.sql',
    '2026_10_07_00_shaman_rockbiter.sql',
    '2026_10_08_00_arcane_momentum.sql',
    '2026_10_09_00_monthly_elemental_invasions.sql'
)
OR hash IN (
    'd4c07bec79ccd143d3b0a5e452d0e3a819788282',
    '0c21e8c55b1a154360a3bc24a3322e4de0b0fd84',
    '7a19a342e90a03444556ace75d91a1b26b29c24b',
    '45bc5b7233232957216a47b61c813c4ea42d089a',
    'd539ae59ebda68ec6111897e3f77c3966252418f',
    'b135152f7c0cc196206b04f5e05c50bef76384b6',
    '5385f5f4a39036c5a2d3db28c9589e281f9ccdac',
    '8143812623b9a43dec1594dca65765ee555a5bbb',
    '315746191db9f1f1091911e9a1671b37a1d14339',
    'fca7c2c07dde2f1480046c26364f282784fe731d',
    '0da079c4ede250f8d39092e9e57323142ebbfd6c',
    '6be3e0b77d0376467e10b83d236b49629505e0cc',
    'ab73acd4824d2119a174a73f4dbc7c398366abd1',
    'd1af947fdaddc9daf6dab9637f1fe54416a13413',
    'ad5b4dae2955da5fcf9c8c1b7b74d4642f1a42a1'
);
```

```sql
-- TEMPLATE - DO NOT RUN without separate owner approval.
-- Stage A, read-only, <WORLD_DB> only.
SELECT entry, ScriptName
FROM creature_template
WHERE entry IN (23543, 23686, 23537, 23703);

SELECT spell_id, ScriptName
FROM spell_script_names
WHERE spell_id IN (42339, 42348);
```

`spell_naxxramas_hallows_end_one_bucket` is a C++ `AllSpellScript` in the module binary. Do not insert a `spell_script_names` row for it.

## Stage B — backups

Requires its own approval, after Stage A. **STOP** if any backup or the isolated restore check fails. Do not continue to C.

1. Copy the original worldserver binary. Record size and sha256.
2. Record the module checkout: remote, branch, commit, and a clean worktree. Keep a copy of that tree, or a ref that can recreate it exactly.
3. Byte-copy the three active conf files from Stage A (`worldserver.conf`, `mod_naxxramas_core.conf`, `playerbots.conf`) **and every active config include, launcher/supervisor definition, environment override source and other local setting that controls the Worldserver executable or updater masks**. Preserve ownership/modes and record size and sha256 of the protected copies. Without these, returning to the original updater/restart behaviour may be impossible even if the three named files were saved.
4. First inspect the database storage engines and agree a **consistent** backup plan. A `--single-transaction` dump is appropriate only for a properly managed transactional snapshot: it does not by itself guarantee consistency for nontransactional tables or across independently changing databases. Account for concurrent writes, cross-database dependencies, and any required coordinated quiescence/snapshot. For the verified compatible engine/backup tool, dump `<WORLD_DB>`, `<CHARACTERS_DB>`, `<PLAYERBOTS_DB>` and `<AUTH_DB>` if a dependency may touch auth or that remains UNKNOWN. Include **`--events --routines --triggers`** so scheduled SQL events are not silently omitted. Put credentials in a mode-`0600` option file; never put passwords in the command line, GitHub or screenshots. Record each dump's size and sha256.
5. Restore every dump into an **isolated** scratch instance whose database names are not the live ones. Re-run the Stage A SELECTs on the scratch world DB and confirm the same ScriptName values. Confirm dump sha256 before and after copy.

```bash
# Illustrative only. Finalise after Stage A. Do not run from this document.
sha256sum <WORLDSERVER_BIN>
cp -a <WORLDSERVER_BIN> <BACKUP_DIR>/worldserver.bin
cp -a <WORLD_CONF> <MODULE_CONF> <PLAYERBOTS_CONF> <BACKUP_DIR>/
# option file (mode 0600), not the command line:
# [client]
# user=<DB_USER>
# password=<DB_PASSWORD>
# host=<DB_HOST>
mysqldump --defaults-extra-file=<CREDENTIALS_OPTION_FILE> \
  --single-transaction --events --routines --triggers \
  --result-file=<BACKUP_DIR>/<WORLD_DB>.sql \
  <WORLD_DB>
sha256sum <BACKUP_DIR>/<WORLD_DB>.sql
# Repeat for <CHARACTERS_DB>, <PLAYERBOTS_DB>, and <AUTH_DB> when required.
# Also copy active included conf files and the actual service/launcher/override
# definitions identified in Stage A; these paths cannot be guessed here.
# mariadb-dump accepts the same flags. Restore only into a scratch instance.
```

## Stage C — updater containment (pilot worldserver only)

Requires its own approval, after a verified Stage B. Target the pilot worldserver process only.

Effective values that the next worldserver start will see:

- `Updates.EnableDatabases = 0`
- `Playerbots.Updates.EnableDatabases = 0`

Playerbots has its own updater. At mod-playerbots `037c014` `src/Script/Playerbots.cpp`, `OnModuleDatabasesLoading()` reads `Playerbots.Updates.EnableDatabases` (dist default `1`) and can `Populate` / `Update` the Playerbots database while the core mask is `0`. `AC_UPDATES_ENABLE_DATABASES` and `AC_PLAYERBOTS_UPDATES_ENABLE_DATABASES` override the files. Record the Stage A originals, then make both **effective** values `0`, including the environment of the supervised process.

This is not read-only database mode. Gameplay still writes. It is not a promise that the schema already matches the binary.

Do not restart authserver. If Stage A found any other installed module with its own updater, **STOP**. A bounded source scan found no third updater hook in Individual Progression `4ff4b5fcc1480348f058c632573143e62d4e3a41` or this module at `4dc63b3`. Other installed modules and revisions are UNKNOWN.

Do not leave a window where a watchdog can start worldserver on the new tree before both flags are `0`. If the restart policy is UNKNOWN, **STOP** before any stop, start, or live config edit.

## Stage D — install on a temporary local branch

Requires its own approval. Default route: no merge.

`git pull` on local `main` will not deliver F10 (`main` is `1f5f317`). Do not run `git pull origin pilot/f10-hallows-end-only-source-2026-10-21` while on local `main`. That can merge the candidate into the working main branch.

After Stage A shows a clean worktree, and after C is in effect for the process that is about to start:

1. In `<MODULE_DIR>`, fetch the named pilot branch from the remote Stage A recorded. Do not assume the remote name.
2. Require the fetched commit to be exactly `4dc63b3a0df11b35dea7035dae472d6aa947b506`. Any other hash: **STOP**.
3. Create a temporary local branch at that commit, named so it cannot be mistaken for main (example: `pilot-f10-local`).
4. **Determine what the Stage A build command actually does before running it.** Some familiar AzerothCore commands (including wrappers) can both COMPILE **and INSTALL** into the live launcher directory, potentially replacing `worldserver`, configuration distributions or other installed files while the old Worldserver is still running. If the command can install, restart, stop a service or edit live destinations, **do not run it as-is in Stage D**. Under a separate owner-approved build plan, perform **build only** in a verified build tree, with no install step or side-effecting wrapper; alternatively choose a verified separate isolated staging prefix that cannot affect the active installation. Leave every copy/install into the live launcher path to step 6 **after the exact Worldserver is stopped and auto-restart inhibited**. Do not substitute the CI CMake line. The CI binary is runner-only. **A successful compile does not prove which binary the installed supervisor starts.** Record the candidate built binary's exact path and SHA-256, the active service executable path and its preserved known-good backup; separately approve any required later copy/install of the candidate executable and permissions.
5. **Do not start or restart Worldserver during Stage D.** Before ANY future executable replacement, optional Stage E SQL change, or pilot startup, use the verified supervisor under a **separately authorised maintenance window** to stop the original Worldserver and inhibit automatic restart. Confirm it is actually stopped. If the process cannot be safely stopped or auto-restart cannot be controlled, **STOP** and do not stage the executable or write SQL. Do not `kill` by guess, use an unconfirmed PM2 index or tmux session, or restart authserver.
6. Under separate installation permission and with the service verifiably stopped, stage the exact newly built binary where the real Worldserver launcher will load it, preserving original ownership, mode and known-good binary; then verify staged SHA-256 equals the candidate build hash. **Do not stage the binary until the Stage A–C checks and restore rehearsal have passed.** The Stage A 23543 binding decision must be resolved in Stage E before the first pilot startup.

```bash
# Illustrative only. Finalise names after Stage A. Do not run from this document.
# Forbidden while on local main:
#   git pull origin pilot/f10-hallows-end-only-source-2026-10-21
git -C <MODULE_DIR> status --porcelain
git -C <MODULE_DIR> fetch <REMOTE> pilot/f10-hallows-end-only-source-2026-10-21
git -C <MODULE_DIR> rev-parse FETCH_HEAD
# must print 4dc63b3a0df11b35dea7035dae472d6aa947b506
# do not switch if FETCH_HEAD differs, is ambiguous, or SHA verification fails
git -C <MODULE_DIR> switch -c pilot-f10-local 4dc63b3a0df11b35dea7035dae472d6aa947b506
git -C <MODULE_DIR> rev-parse HEAD
# then ONLY a separately reviewed build-only command with NO live install side effects;
# no copy/install into the live launcher until the verified Worldserver is stopped;
# no start/restart until Stage E is resolved
```

Alternative, only if the server owner separately approves a real merge of PR #77: a later `git pull` on `main` can deliver F10. That merge is not approved by this runbook. Both routes still need stages A–C and the same start gate.

## Stage E — conditional 23543 binding

Requires its own approval. Skip this stage when Stage A already shows `23543` ScriptName = `npc_naxxramas_hallows_end_soh`. **If a SQL change is needed, it is prohibited while the current live Worldserver is still running**: require the Stage D identified Worldserver to be fully stopped with automatic restart safely inhibited, and verify the World/Characters/Playerbots backup and isolated restore first. No SQL is authorised merely by stopping the process.

Run it only when Stage A shows a different **non-NULL** ScriptName. Put that exact verified value in `<EXPECTED_OLD_SCRIPTNAME>` with correct SQL quoting/escaping. If the SELECT failed, the value is **NULL**, quoting is uncertain or the existing binding is ambiguous, **STOP** and prepare a separately reviewed guarded NULL-safe design instead of copying the example. Do not execute `2026_09_21_00_event_script_overrides.sql` and do not edit it. That file also updates Brewfest `23703`.

Affected rows must be exactly 1. Any other count: `ROLLBACK` and **STOP**. The default last statement below is `ROLLBACK`. Change it to `COMMIT` only after the count is 1 and the server owner has approved the commit. Do not touch `23703`.

```sql
-- TEMPLATE - DO NOT RUN without separate owner approval.
-- Stage E, <WORLD_DB> only. One row. Does not mention entry 23703.
START TRANSACTION;
UPDATE creature_template
SET ScriptName = 'npc_naxxramas_hallows_end_soh'
WHERE entry = 23543
  AND ScriptName = '<EXPECTED_OLD_SCRIPTNAME>';
SELECT ROW_COUNT() AS affected_rows;
-- Required: affected_rows = 1. Otherwise leave the ROLLBACK in place and STOP.
ROLLBACK;
-- COMMIT;
```

Compensating template (rollback of this stage only):

```sql
-- TEMPLATE - DO NOT RUN without separate owner approval.
-- Reverse of Stage E. Same <EXPECTED_OLD_SCRIPTNAME> recorded before the forward update.
START TRANSACTION;
UPDATE creature_template
SET ScriptName = '<EXPECTED_OLD_SCRIPTNAME>'
WHERE entry = 23543
  AND ScriptName = 'npc_naxxramas_hallows_end_soh';
SELECT ROW_COUNT() AS affected_rows;
-- Required: affected_rows = 1. Otherwise leave the ROLLBACK in place and STOP.
ROLLBACK;
-- COMMIT;
```

### First pilot startup — only AFTER the Stage E decision

Stage E must be recorded as **SKIPPED because 23543 was already correctly bound**, or **COMPLETED with a separately approved, verified one-row transaction** before any pilot Worldserver startup or Hallow's End gameplay. If a required binding fix is unapproved or fails, **STOP**; do not start with a known missing binding and expect the current process to reload a changed ScriptName automatically.

Only after Stages A–E and a **separate startup/restart authorisation**, ensure the exact identified Worldserver supervisor cannot restart unexpectedly, confirm the real launcher is configured to start the newly staged and SHA-256-verified pilot binary (not the old path or a second uncontrolled process), verify both effective automatic updater flags remain `0` (including environment overrides), and perform the planned controlled Worldserver start. Keep both optional Hallow's End features OFF initially. Do not restart authserver. Verify startup logs show no core or Playerbots updater populate/update; any activity or missing required schema means **STOP** and follow the separately approved rollback. Gameplay and optional feature activation still require Stage F approval.

## Stage F — private acceptance

Requires its own approval. Turn F10 switches on only for this stage, in the conf file the pilot worldserver actually loads. Leave `PeriodMultiplier` at the recorded original (dist default `3`) unless the server owner approves another value in 2–8.

- Solo-pace cases: `NaxxramasCore.HallowsEnd.SoloFire.Enabled = 1`, `OneBucket = 0`.
- One-bucket positive case **(b)** and its fail-closed negative conditions in **(c)**: use `Enabled = 1` and `NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 1` for the comparison, then explicitly test each flag OFF one at a time. Record the effective flags for each run; otherwise a negative case could pass trivially with the whole feature disabled.
- **Do not assume editing a file instantly changes the running module.** For each test configuration, first establish how this installed Worldserver reads or reloads these keys; verify the effective value in the actual process before interpreting gameplay. If a restart is required, it is another **separately owner-approved controlled restart**, with both updater masks and executable identity rechecked first. Never casually restart to switch test cases.

Record PASS, FAIL, or NOT RUN for each case, with a one-line note. **The difference to test is the module's extra full-size one-bucket shortcut, not the existence of stock 42339→42348.** In the pinned core, stock splash `42348` can remove all auras from a small (amount ≤2) normal fire, and lowers a full-size amount 3 to 1. Confirm actual in-game spell timing; do not treat these source-model results as already observed.

| Case | What to do | Result |
|---|---|---|
| (a) | One real human plus bots. Solo pace. Bots do not count as the nearby player. | |
| (b) | One real human. Normal fire `23686`, full-size aura `42074`, bucket spell `42339` on that fire. | |
| (c) | Negative module conditions: bot caster; two real humans; training fire `23537`; never-Shade-ignited or foreign fire; overlapping Shades; optional flags OFF. Verify **no extra module one-bucket removal**. On suitable full-size normal fire amount 3, expect only the stock bucket reduction toward amount 1 when module conditions fail, subject to live timing. Small fires may already be extinguished by stock splash; training and other targets must follow their own stock paths, not necessarily retain every aura. | |
| (d) | Compare OneBucket ON versus OFF baseline: stock splash `42348` remains present, **no new unintended unrelated-aura effects** beyond stock `RemoveAllAuras()` on small fires, and no regression to quest credit (source quests `12135`, `12139`, `11131`, `11219`). Do not claim all unrelated auras always remain. | |
| (e) | Event finish, event failure, and cleanup. | |

**Roll back immediately** on any crash, any unexpected SQL applied at start or during play, wrong quest credit, or any change to Brewfest `23703`.

## STOP

Stop and do not improvise when any of these are true:

- Fetched or checked-out module commit is not `4dc63b3a0df11b35dea7035dae472d6aa947b506`.
- Installed core, Playerbots, or IP SHA is not the set the server owner accepted from Stage A.
- Worktree is dirty, or symlinks make the built tree differ from the recorded checkout.
- Effective updater config or either `AC_*` override is UNKNOWN.
- Any of the 15 history rows is missing, hash-mismatched, or not in the realm's already-applied state.
- Any other pending module, core, IP, or Playerbots update would run on start.
- `23703`, `23686`, `23537`, `42339`, or `42348` bindings differ from the Stage A record later, or Stage A could not read them.
- Another installed module has its own updater.
- The worldserver supervisor or its auto-restart policy is UNKNOWN.
- The existing compile/build command's **install behaviour or live side effects are UNKNOWN**, or it would run an installation, overwrite a real launcher binary or restart a service before the separately approved Stage D stop/install gate.
- The Worldserver is still running when any optional Stage E SQL write or candidate binary replacement is proposed, or the runtime executable path/staged hash has not been verified.
- A backup or the isolated restore check failed.
- The startup log shows any updater populate/update activity.

## Rollback

Use the supervisor and paths recorded in A and B. Do not restart authserver.

1. **Stop Worldserver through the verified supervisor and prevent automatic restarts** under the separately authorised plan. Confirm it is stopped before any rollback file operation. Do not restart authserver.
2. Keep BOTH updater settings **effective at `0`**, accounting for environment overrides, while the stopped server's binary and module tree are being restored. Record the F10 switches to return OFF (`Enabled = 0`, `OneBucket = 0`; original `PeriodMultiplier`) without restoring an old updater-ON configuration prematurely.
3. Restore the exact known-good Worldserver binary and module checkout (branch, commit, permissions and any preserved local edits), while the startup gate remains closed. Keep the temporary pilot branch available until known-good operation has been verified; **do not delete it early**.
4. Reverse entry `23543` only if Stage E committed, using the separately authorised compensating SQL template and recorded `<EXPECTED_OLD_SCRIPTNAME>`; otherwise leave the original row untouched.
5. Restore a database only if the incident assessment makes it necessary, the isolated restore has succeeded, and the server owner separately approves the live restore. A broad restore can overwrite legitimate gameplay progress since the backup.
6. **Before restoring any original active `.conf` byte-copies, included config files, launcher/supervisor settings or previous updater environment values**, review pending migrations and the supervisor's restart behaviour. Such an original file or override may itself re-enable automatic World/Playerbots SQL updates. Only after this review is approved may the original configuration bytes and the **verified prior effective values** be restored together under a controlled, stopped Worldserver. If previous values are unsafe, keep the Worldserver stopped and both effective masks contained at `0`, with the original file copies retained safely in backup; arrange a separate approved normal-operation plan. Never silently reset to dist defaults `7` or `1`.
7. Start Worldserver through the verified supervisor **only when** backup restoration, database binding, effective updater configuration and the pending-migrations gate are all safe and separately approved. Otherwise leave it stopped rather than risking an automatic migration.
8. Re-run the approved Stage A SELECTs and compare 23543, Brewfest `23703`, normal `23686`, training `23537`, stock `42339`/`42348`, and update history to the pre-pilot record (with the documented Stage E reverse if used). Confirm no unexpected updater apply. Only after this verification and separate owner consent may the temporary local pilot branch be removed.

## Evidence record

| Field | Value |
|---|---|
| Date (UTC) | |
| Operator | |
| the server owner approval recorded for stages | |
| Module commit before / pilot commit | |
| Core / Playerbots / IP SHAs | |
| Backup dir, sizes, sha256 | |
| Scratch restore result | |
| Effective updater values before / during / after | |
| 23543 before / after (Stage E skipped: yes/no) | |
| 23703 before / after (must match) | |
| (a) (b) (c) (d) (e) | |
| Rollback taken | |
| Left the realm on which commit and which binary sha256 | |
