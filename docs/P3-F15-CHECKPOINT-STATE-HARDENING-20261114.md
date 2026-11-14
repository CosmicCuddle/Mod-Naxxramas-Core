# F15 checkpoint/state hardening — 2026-11-14

**Owner:** CosmicCuddle  
**State:** source-only child of DRAFT #309.  
**Parent:** `827f5618c991611c483941cabb0ba910fee09180`.

## Purpose

Close two restart-safety/state-machine defects found during CS01 review without adding process-control, scheduling, retention, log-overwrite, SQL, DBC, client or gameplay authority.

## Changes

### Checkpoint transaction

- serialize each service's complete read/normalize/render/commit transaction with a private persistent `flock` file;
- replace the fixed `<checkpoint>.pending` filename with unique private temporary files;
- fsync the temporary file before atomic replacement and fsync the parent directory after replacement;
- stale temp files from a killed writer do not block later commits;
- insecure/non-regular/multi-link lock files fail closed.

### Worldserver lifecycle normalization

- a live PM2 identity becoming stopped/non-live is an incident even when `restart_time` is unchanged;
- a live identity replacement with the same restart counter is retained as cause-unknown evidence rather than silently committed;
- stopped/absent -> live is treated as recovery/start rather than a second crash when at most one restart is observed;
- multiple restart attempts while previously non-live remain incident evidence;
- existing fatal-signal/non-zero/restart classifications remain for restart-counter advances.

### Authserver lifecycle normalization

- present -> absent remains one disappearance incident;
- present A -> present B remains one replacement/disappearance incident;
- absent -> present is a recovery/start transition and advances the checkpoint without a false crash;
- a baseline established while Auth is absent can later recover cleanly;
- partial/invalid pid/start identities still fail closed.

## Focused evidence

Branch source files were fetched back from GitHub after commit and copied exactly into a local isolated Python check.

Verified locally:
- both changed Python source files compile;
- World same-counter live -> stopped classification;
- World same-counter live identity replacement classification;
- stopped -> live recovery suppression;
- Auth absent -> present recovery;
- stale legacy fixed pending file does not wedge a later commit;
- Auth present -> absent -> present advances without refusal;
- two concurrent observers of the same World restart emit one incident and advance sequence once.

This is Python/source evidence only. It is **not** a Worldserver/Authserver native build, installed-host test, PM2/tmux live observation, or production proof.

## Remaining F15 gates

This child does not resolve:
- approved-maintenance expected STOP/RESTART markers;
- all-or-nothing pre-overwrite scan/coupling;
- unified retention-intent recovery;
- crash-history bound/atomic locking;
- real overwrite owner/hook;
- exact installed topology/paths/runtime user/capacity/build fingerprint;
- scheduling;
- owner-approved staging.

## Rollback

Abandon/revert this child branch. It has no host state and changes no live process, configuration, database or log.
