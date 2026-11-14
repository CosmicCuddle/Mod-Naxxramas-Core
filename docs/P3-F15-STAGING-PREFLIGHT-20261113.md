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

## Evidence envelope

Every required fact is supplied as an explicit evidence envelope:

```json
{
  "status": "VERIFIED",
  "value": "worldserver",
  "source": "operator-read-only evidence reference"
}
```

Host facts must be `VERIFIED` and must carry non-empty provenance. A plain string such as `"verified"` is not evidence and is rejected as malformed.

The two scheduling fields may be either `PROPOSED` or `VERIFIED`, because they describe the staging plan rather than already-observed host state.

`UNKNOWN` remains unresolved and cannot produce `READY_FOR_OWNER_REVIEW`.

## Required evidence

The preflight requires:

- Worldserver PM2 process name;
- PM2 manager log, stdout and stderr paths;
- Authserver tmux session, process name and log path;
- the exact owner of overwrite/rotation behavior;
- the safe hook point that must run `snapshot-before-overwrite` before bytes are lost;
- runtime user and log ownership/permission expectations;
- current free space and projected 30-day F15 storage requirement;
- build-version and source-revision fingerprint sources;
- proposed scheduling for `observe-once` and `retain-once`.

All daemon log paths must be absolute normalized POSIX **strict descendants** of the owner-approved F15 root `/root/cosmic_core/logs`; the manifest cannot broaden or redefine that trust boundary. Capacity values must be genuine non-negative integers; booleans are explicitly rejected even though Python normally treats them as integers. Capacity is blocked when supplied free bytes are below the supplied 30-day projection.

## Output states

- `BLOCKED`: malformed, contradictory or unsafe evidence is present.
- `UNKNOWN`: one or more required facts are absent or not yet verified.
- `READY_FOR_OWNER_REVIEW`: the source preflight has no known blocker and no missing required fact. This is **not** deployment approval.

The next step after `READY_FOR_OWNER_REVIEW` is still to prepare backup, rollback and staging instructions for CosmicCuddle's explicit approval.

## Tests

Focused offline tests now cover the original provenance/type/capacity/path/authorization cases plus:
- canonical versus noncanonical daemon paths;
- the shipped all-UNKNOWN example;
- `log_root="/"` cannot broaden the trust boundary;
- an alternate root remains blocked absent a separate owner decision;
- a daemon log path equal to the root directory is rejected;
- valid strict descendants remain accepted;
- embedded NUL bytes are rejected because lexical PurePosixPath normalization alone accepts them but operating-system file APIs cannot use them.

The prior 13/13 result belongs to an older head. The current branch contains **20 focused test methods**, but a full exact-head run is **not claimed** in this environment. No hosted Actions were requested.

## Custom Modifications Register — F15-STAGING-PREFLIGHT-20261113

| Field | Record |
| --- | --- |
| Intended behaviour | Offline evidence-readiness assessment before any F15 staging. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Parent | DRAFT #309 head `827f5618c991611c483941cabb0ba910fee09180`. |
| Affected paths | `scripts/f15_staging_preflight.py`, `tests/test_f15_staging_preflight.py`, this note. |
| Runtime authority | None; operator-supplied JSON only. |
| Config/SQL/DBC/client | None. |
| Risks | Incorrect operator evidence cannot change the host; malformed/unproven evidence now blocks or remains UNKNOWN rather than becoming review-ready. |
| Tests | 20 focused test methods committed; current exact-head execution UNKNOWN here. Prior 13/13 result applies only to an older head; no hosted Actions. |
| Live status | Uninstalled / not invoked on owner host. |
| Rollback | Abandon branch/PR; no live state exists. |
