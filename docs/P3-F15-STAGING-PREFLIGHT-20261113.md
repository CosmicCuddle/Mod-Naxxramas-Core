# F15 offline staging preflight — 2026-11-13

**Owner:** CosmicCuddle  
**State:** source-only child of F15 operational CLI DRAFT #309.  
**Purpose:** determine whether the evidence needed for safe staging has actually been collected, without probing or changing the server.

## Safety boundary

`scripts/f15_staging_preflight.py` accepts an operator-supplied JSON manifest only.

It does **not**:
- execute PM2, tmux, ps, shell, systemd or filesystem-discovery commands;
- read the owner's live server;
- create directories or logs;
- start, stop, restart, signal or attach to either daemon;
- truncate, rotate, copy or delete files;
- authorize installation or deployment.

Unknown input remains `UNKNOWN`. A manifest setting `authorizations.live_install=true` is treated as a blocker rather than permission.

## Required evidence

The preflight records whether the following have been independently verified:

- Worldserver PM2 process name;
- PM2 manager log, stdout and stderr paths;
- Authserver tmux session, process name and log path;
- the exact owner of overwrite/rotation behavior;
- the safe hook point that must run `snapshot-before-overwrite` before bytes are lost;
- runtime user and log ownership/permission expectations;
- current free space and projected 30-day F15 storage requirement;
- build-version and source-revision fingerprint sources;
- proposed scheduling for `observe-once` and `retain-once`.

All supplied daemon log paths must remain under the configured log root. Capacity is blocked when supplied free bytes are below the supplied 30-day projection.

## Output states

- `BLOCKED`: contradictory or unsafe evidence is present.
- `UNKNOWN`: one or more required facts are not yet verified.
- `READY_FOR_OWNER_REVIEW`: the source preflight has no known blocker and no missing required fact. This is **not** deployment approval.

The next step after `READY_FOR_OWNER_REVIEW` is to prepare backup, rollback and staging instructions for CosmicCuddle's explicit approval.

## Tests

Focused offline tests cover:
1. complete manifest -> owner-review readiness only;
2. missing evidence remains UNKNOWN;
3. log path outside `/root/cosmic_core/logs` blocks;
4. insufficient 30-day capacity blocks;
5. a manifest cannot self-authorize installation;
6. snapshot hook without a verified overwrite owner blocks.

Local Python test result before publication: **6/6 PASS**.

## Custom Modifications Register — F15-STAGING-PREFLIGHT-20261113

| Field | Record |
| --- | --- |
| Intended behaviour | Offline evidence-readiness assessment before any F15 staging. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Parent | DRAFT #309 head `827f5618c991611c483941cabb0ba910fee09180`. |
| Affected paths | `scripts/f15_staging_preflight.py`, `tests/test_f15_staging_preflight.py`, this note. |
| Runtime authority | None; operator-supplied JSON only. |
| Config/SQL/DBC/client | None. |
| Risks | Incorrect operator-supplied evidence can only misclassify readiness; it cannot change the host. |
| Tests | 6/6 focused local PASS; no hosted Actions. |
| Live status | Uninstalled / not invoked on owner host. |
| Rollback | Abandon branch/PR; no live state exists. |
