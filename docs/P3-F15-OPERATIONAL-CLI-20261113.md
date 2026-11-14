# F15 operational CLI — source-only staging candidate — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; not installed/scheduled; no live host invocation.  
**Parent:** F15 synthetic full pipeline DRAFT #308 head `de72dacba130d9d562e1b922103947cbdd477d3d`.

## Purpose

Provide one narrow operator surface for the source-proven F15 components without
giving the tool authority to control Worldserver/Authserver.

The CLI exposes exactly three modes:

1. `observe-once`
2. `snapshot-before-overwrite`
3. `retain-once`

There is no start, stop, restart, kill, signal, attach, reload-server, log
truncate or DB operation.

## Production path defaults

Source defaults are aligned to the owner requirement:

- live log root: `/root/cosmic_core/logs/`
- crash reports: `/root/cosmic_core/logs/Crash Logs/`
- raw crash evidence: `/root/cosmic_core/logs/Crash Logs/Raw Evidence/`
- archived pre-overwrite logs: `/root/cosmic_core/logs/Archived Logs/`
- observer checkpoint state: `/root/cosmic_core/logs/.f15-state/`

These locations are fixed production trust boundaries for the CLI and do not
create/change anything until an operator invokes a mode. The CLI exposes no
state/crash/log/archive root override. Tests and source-level composition may
inject temporary roots only through the Python function APIs.

## observe-once

Inputs may identify:
- Worldserver PM2 process name;
- PM2 manager log path;
- Authserver tmux session name;
- Authserver native/console log path;
- build/version and source revision strings.

Worldserver behavior:
- one real `pm2 jlist` observation is made;
- that exact observation is replayed internally into the composed pipeline so
  detection does not perform a second race-prone PM2 sample;
- PM2 stdout/stderr paths from the snapshot are accepted only when they resolve beneath the approved live log root and contain no symlink component, then tailed read-only and bounded;
- PM2 manager log is subject to the same approved-root/symlink rule and tailed read-only, bounded;
- log-tail failures become explicit unavailable context rather than process
  control.

Authserver behavior:
- uses the strict tmux/process-tree read-only probe;
- optional Auth log tail is bounded and must resolve beneath the same approved live log root with no symlink component;
- disappearance under live tmux is reportable with cause UNKNOWN.

Output to stdout is only a compact JSON incident summary; raw log content is not
printed there.

## snapshot-before-overwrite

This mode snapshots direct regular files from the selected live log root into a
private archive directory which must be a direct child of that log root.

It never truncates, rotates, renames or deletes source logs.

**Critical deployment rule:** this mode must be invoked by the actual
pre-start/pre-rotation/pre-overwrite owner before destructive overwrite occurs.
Running it later cannot recover bytes already lost.

The exact current PM2/Auth/core logging behavior must therefore be verified
before wiring this command into production.

## retain-once

Runs only the reviewed owned-retention functions:

- pre-overwrite archived log snapshots;
- raw crash evidence bundles;
- detailed crash reports;
- matching structured Crash-History entries.

Only verified F15-owned artifacts older than the full 30-day boundary qualify.
Active original logs remain outside retention authority.

## Source test intent

Focused tests cover:

1. World observe baseline then PM2 SIGSEGV restart using fake command runner;
2. source stdout/stderr remain unchanged by observation;
3. no-target observe refuses before command execution;
4. pre-overwrite snapshots leave active logs unchanged;
5. archive destination must be a direct child of log root;
6. 31-day owned archive/raw-evidence/crash artifacts expire together;
7. active source log survives retention unchanged;
8. parser exposes exactly the three approved modes;
9. PM2/Auth/manager log sources outside the approved log root are refused;
10. final or parent-component symlink log sources are refused;
11. no operational mode exposes state/crash/log/archive root overrides that could broaden the production trust boundary.

No hosted Actions are requested yet.

## Installation/staging gate

Before any live use, Maintenance must verify read-only:

- exact PM2 Worldserver name;
- exact PM2 manager/out/err log paths;
- exact Authserver tmux/session/process topology;
- exact Auth log path;
- current logger overwrite/rotation/truncate behavior;
- user/permissions;
- available disk space for 30 days;
- source/build fingerprint source;
- desired scheduling mechanism for `observe-once` and `retain-once`;
- exact safe hook point for `snapshot-before-overwrite`.

Then prepare backup/rollback and request CosmicCuddle approval before installing
or scheduling anything.

Initial live staging does **not** require intentionally crashing either daemon.
It can establish a baseline, replay synthetic fixtures outside production state,
and verify directory/permission behavior first.

## Custom Modifications Register — F15-OPERATIONAL-CLI-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Expose separated read-only observation, pre-overwrite copy, and owned 30-day retention operations. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_operational_cli.py`, `tests/test_f15_operational_cli.py`, this note. |
| Parent | #308 head `de72dacba130d9d562e1b922103947cbdd477d3d`. |
| Dependencies | F15 #301–#308 and #305–#307 source layers; PM2/tmux/ps/Linux /proc only when staged. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Not yet scheduled; exact live topology/overwrite owner unknown; one-shot observation interval not selected; disk-capacity gate pending. Runtime observation now refuses configured log sources outside the approved root or through symlink components. |
| Tests | Focused source tests authored; no live host/hosted Actions test. |
| Live status | DRAFT/uninstalled. |
| Rollback | Do not install/schedule; abandon branch/PR. No live state change exists. |
