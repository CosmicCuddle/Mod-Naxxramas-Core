# F15 staging backup / rollback plan template — 2026-11-13

**Owner:** CosmicCuddle  
**State:** source-only planning child of F15 DRAFT #318 on the #310 preflight line.  
**Purpose:** define the safety procedure that must exist before any F15 operational tooling is installed, scheduled, or attached to log-overwrite paths.

This document is a **template**, not a deployment plan and not owner approval. Every host-specific field remains UNKNOWN until supported by the current #310/#318 evidence manifest.

## 1. Hard prerequisites

Do not proceed to live staging unless all of the following are true:

- the current #310/#318 preflight result is `READY_FOR_OWNER_REVIEW`;
- exact Worldserver PM2 name and PM2/world log paths are VERIFIED;
- exact Authserver tmux/process/log facts are VERIFIED;
- the real overwrite/rotation owner and pre-overwrite hook point are VERIFIED;
- runtime user and log ownership expectations are VERIFIED;
- current free bytes and projected 30-day F15 storage need are VERIFIED;
- build/source fingerprint sources are VERIFIED;
- proposed observe/retention schedules are recorded;
- the exact target installation paths are known;
- a backup location and rollback procedure have been reviewed;
- CosmicCuddle has explicitly approved the live staging step.

A source build, unit test, or `READY_FOR_OWNER_REVIEW` result is not a substitute for owner approval.

## 2. Production invariants that staging must preserve

- Active logs under `/root/cosmic_core/logs/` must never be deleted by F15.
- Any log that is about to be overwritten/rotated/truncated must be copied first through the approved snapshot path.
- F15 may auto-expire **only F15-owned archive/raw/crash artifacts** older than the approved 30-day policy.
- Existing non-F15 files are never treated as retention-owned merely because they live below the log root.
- Crash reports/raw evidence already captured must not be destroyed during rollback.
- Worldserver/Authserver process topology must not be changed merely to make F15 easier to install.
- No DB, SQL, DBC, client, gameplay or progression state is part of F15 staging.

## 3. Required pre-staging inventory

Before any write to the owner host, record:

| Fact | Required value |
| --- | --- |
| F15 source commit | exact approved commit SHA |
| Installed target files | exact absolute paths |
| Existing files at those paths | present/absent + hashes |
| Runtime user | VERIFIED value |
| Runtime group/ownership expectations | VERIFIED value |
| Log root | VERIFIED absolute path |
| Archive/crash roots | exact F15-owned paths |
| Scheduler mechanism | proposed and owner-approved |
| Worldserver PM2 identity | VERIFIED |
| Authserver tmux/process identity | VERIFIED |
| Free bytes before staging | VERIFIED |
| 30-day projected F15 bytes | VERIFIED |
| Backup root | exact absolute path |
| Rollback owner | named operator/process responsible |

Do not put credentials, tokens, passwords or sensitive environment dumps into the repository.

## 4. Backup plan

The final host-specific plan must:

1. Create a timestamped backup set **before replacing any existing F15 target file**.
2. Preserve path, owner/group and mode metadata for replaced files.
3. Record a cryptographic hash for every backed-up file and every staged replacement.
4. Store backups outside any path that `retain-once` can expire.
5. Never use active World/Auth logs as a backup destination.
6. Never truncate or rotate a log as part of backup preparation.
7. Record whether each target path was originally absent; rollback of a newly-created file means removing only that staged file after schedules/hooks are disabled.
8. Preserve all F15-owned crash/archive evidence created during an approved staging test, even if the staged executable/script is rolled back, unless CosmicCuddle separately approves deletion.

## 5. Proposed staged rollout phases

Each phase requires the previous phase's evidence to be reviewed. Later phases are not implied by approval of an earlier one.

### Phase A — file staging only

Potential future action:
- install the approved F15 files to owner-approved paths;
- preserve exact ownership/mode;
- create required F15-owned directories only if explicitly approved.

Must remain disabled:
- cron/systemd/PM2 schedules;
- automatic retention;
- overwrite hooks;
- process restarts;
- automatic crash observation.

Validation:
- staged files match approved hashes;
- permissions are as planned;
- no daemon state changed;
- no log file content changed.

### Phase B — manual read-only `observe-once`

Potential future action:
- run one approved observation manually.

Expected:
- reads process/topology/log evidence only as designed;
- writes only F15-owned diagnostic/crash artifacts;
- no PM2/tmux process control;
- no active-log mutation.

Rollback:
- disable/remove staged invocation path;
- preserve evidence created by the test.

### Phase C — manual snapshot rehearsal

This phase must **not** overwrite a live log to prove the feature.

Use only an owner-approved disposable/synthetic source file or an already-safe rotation test fixture.

Validate:
- source is copied before the simulated overwrite step;
- archive belongs to F15;
- source bytes/hash match archived bytes;
- failure to snapshot prevents the overwrite path rather than silently losing bytes.

No live rotation/truncation is authorized by this template.

### Phase D — manual `retain-once` rehearsal

Use only F15-owned synthetic/staging artifacts.

Validate:
- younger-than-30-day F15 artifacts remain;
- >30-day F15-owned test artifacts are selected correctly;
- active logs and non-F15 files are never selected;
- crash/raw/archive ownership rules are exact.

Do not test deletion against irreplaceable real evidence.

### Phase E — scheduling / overwrite-hook integration

This is the highest-risk staging phase and requires a separate explicit owner approval after A–D are reviewed.

Before approval, document:
- scheduler entries exactly;
- overwrite hook insertion point exactly;
- failure behavior;
- concurrency/locking behavior;
- disk-full behavior;
- what happens if World/Auth is down;
- how schedules/hooks are disabled immediately.

## 6. Rollback plan

Rollback order must be:

1. Disable any new scheduler entries.
2. Disable the new pre-overwrite hook/integration point.
3. Confirm no F15 process/action remains scheduled or in progress.
4. Restore replaced files from the pre-staging backup, verifying hashes.
5. Remove only files that were proven absent before staging and were created solely by the staged F15 package.
6. Restore original owner/group/mode metadata.
7. Do **not** remove active logs.
8. Do **not** delete F15 archive/crash/raw evidence merely because code was rolled back.
9. Verify Worldserver/Authserver topology matches the pre-staging inventory.
10. Record rollback result and any remaining evidence/manual cleanup requirement.

If rollback cannot prove the original state, stop and escalate rather than improvising.

## 7. Stop conditions

Immediately stop staging and do not advance phases if any of these occur:

- path, process identity, overwrite owner or source revision differs from the reviewed manifest;
- backup hash does not verify;
- free space falls below the reviewed safety margin;
- F15 attempts to select an active/non-owned log for retention;
- snapshot cannot complete before a would-be overwrite;
- unexpected permission/ownership changes are required;
- a command would restart/stop Worldserver or Authserver unexpectedly;
- an UNKNOWN fact appears that affects safety;
- host behavior differs from the approved topology.

## 8. Evidence required after each approved phase

Record:
- exact F15 commit/hash;
- exact command or scheduler entry used;
- exact start/end time;
- files created/modified;
- hashes where applicable;
- disk-space before/after;
- expected versus observed result;
- rollback status;
- unresolved deviations.

Do not claim gameplay/runtime correctness from source tests or a successful staging command.

## 9. Current status

At creation of this template:
- no host evidence has been collected by CS01;
- no host path has been modified;
- no PM2/tmux command has been run;
- no schedule/hook has been installed;
- no log has been copied, rotated, truncated or deleted;
- no production staging approval has been requested by this document.

## 10. Rollback of this source-only template

Abandon/revert this branch/PR. It has no live state.
