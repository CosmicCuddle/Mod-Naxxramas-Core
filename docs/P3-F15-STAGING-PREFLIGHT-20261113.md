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

All daemon log paths must be absolute normalized POSIX paths under the configured log root. Capacity values must be genuine non-negative integers; booleans are explicitly rejected even though Python normally treats them as integers. Capacity is blocked when supplied free bytes are below the supplied 30-day projection.

## Output states

- `BLOCKED`: malformed, contradictory or unsafe evidence is present.
- `UNKNOWN`: one or more required facts are absent or not yet verified.
- `READY_FOR_OWNER_REVIEW`: the source preflight has no known blocker and no missing required fact. This is **not** deployment approval.

The next step after `READY_FOR_OWNER_REVIEW` is still to prepare backup, rollback and staging instructions for CosmicCuddle's explicit approval.

## Tests

Focused offline tests cover:

1. complete provenance-bearing manifest -> owner-review readiness only;
2. plain strings cannot masquerade as verified evidence;
3. missing evidence provenance blocks;
4. a host fact marked only `PROPOSED` remains unresolved;
5. boolean capacity values block;
6. negative capacity blocks;
7. insufficient 30-day capacity blocks;
8. log paths outside `/root/cosmic_core/logs` block;
9. relative daemon log paths block;
10. explicit UNKNOWN stays UNKNOWN;
11. a manifest cannot self-authorize installation;
12. malformed authorization structure blocks.\n13. the shipped example manifest itself remains UNKNOWN with every required fact unresolved.

Local Python result after the evidence hardening: **13/13 PASS**.

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
| Tests | 13/13 focused local PASS after provenance/type/path hardening; no hosted Actions. |
| Live status | Uninstalled / not invoked on owner host. |
| Rollback | Abandon branch/PR; no live state exists. |
