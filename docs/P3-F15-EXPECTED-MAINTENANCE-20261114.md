# F15 expected-maintenance discrimination — 2026-11-14

**Owner:** CosmicCuddle  
**State:** source-only DRAFT child of F15 checkpoint/state hardening.  
**Parent:** `cce9c7b132f5940e012387b69423360cd75a0827`.

## Purpose

Prevent approved Worldserver/Authserver maintenance stops or restarts from being recorded as unexpected crash incidents, without giving F15 any authority to stop, restart or signal a process.

## Safety model

Expected maintenance is deliberately two-phase:

1. **Arm:** an external, separately approved maintenance owner arms one service-specific operation ID and transition (`stop` or `restart`) for at most 30 minutes.
2. The marker binds itself to the **existing durable F15 checkpoint identity**. The caller cannot supply an invented before-state.
3. **Confirm:** after the real maintenance owner reports successful completion, it confirms the same operation ID.
4. F15 observes the post-state and accepts it as expected only when the service, before identity, transition shape, bounded time and confirmation all match.
5. Explicit fatal signal or non-zero exit always defeats the maintenance marker. Unknown/destructive signals such as `SIGKILL` also remain unexpected. Only clean operator termination signals `SIGINT`/`SIGTERM` may accompany an otherwise exact confirmed World maintenance transition.
6. A matching transition observed while the marker is only armed is **deferred**: no crash report and no checkpoint advancement occur. If confirmation never arrives, expiration leaves the old checkpoint intact so a later observation classifies the transition normally.
7. A confirmed expected transition advances the checkpoint without incrementing the crash sequence and writes a separate `last-expected-maintenance.json` audit record. It does not enter crash history or raw crash evidence.

## Exact transition contracts

### Worldserver / PM2
- expected STOP: previous identity is live, current identity is non-live, restart counter unchanged;
- expected RESTART: previous and current are live, restart counter advances exactly by one, and pid or uptime identity changes;
- fatal/non-zero evidence is never suppressible; `SIGKILL`/unknown signals remain unexpected; `SIGINT`/`SIGTERM` may match only an otherwise exact confirmed maintenance transition.

### Authserver / tmux
- expected STOP: previous pid/start identity exists and current identity is absent;
- expected RESTART: previous and current pid/start identities exist and differ;
- because tmux observation has no authoritative child wait status, an Auth transition is suppressible only after the separate maintenance owner confirms the operation ID.

## Operational authority boundary

This child does **not** expose an `arm`, `confirm`, `stop` or `restart` CLI command. The existing operational CLI still exposes only:
- `observe-once`;
- `snapshot-before-overwrite`;
- `retain-once`.

A future approved maintenance/launcher owner must call the arm/confirm primitive around its own already-authorized process-control action. F15 itself remains diagnostic.

## Evidence added

Source tests cover:
- unconfirmed exact transition is not accepted as confirmed maintenance and integration defers it without checkpoint advance;
- confirmed exact World restart;
- confirmed World stop;
- fatal/non-zero evidence wins;
- wrong before identity;
- expired marker;
- exact Auth restart/stop;
- wrong operation ID;
- >30 minute window refusal;
- existing marker cannot be silently replaced;
- symlink marker refusal for administrative access while observation treats it as no suppression authority;
- confirmation retry idempotency with a different retry timestamp;
- clean SIGINT/SIGTERM exact transition acceptance;
- SIGKILL/fatal/nonzero rejection;
- invalid marker/audit recovery classification;
- standalone marker consume API absence.

Operational integration tests cover:
- baseline → armed expected restart → observation defers with no crash/checkpoint advance → confirmation → same observation is accepted with no crash and marker finalized;
- confirmed expected restart plus SIGSEGV still creates a FATAL_SIGNAL_EXIT crash and does not finalize the marker;
- invalid/symlink marker still permits normal unexpected-restart reporting and remains for recovery review;
- clean SIGTERM exact confirmed restart is accepted without crash history;
- SIGKILL during a confirmed maintenance window remains an unexpected signal incident;
- checkpoint advanced + audit-write failure leaves a classified stale confirmed marker and no duplicate crash on retry;
- checkpoint + audit advanced + marker-unlink failure leaves a classified matching stale marker/audit and no duplicate crash on retry.

## Known remaining recovery gate

The expected transition is intentionally checkpointed **before** marker finalization. This ordering prevents an interruption from consuming the marker and then falsely reporting the already-approved transition as a crash.

Residual cases are intentionally fail-closed/reviewable:
- checkpoint advances successfully but audit write fails;
- checkpoint and audit advance but marker unlink fails;
- malformed/insecure marker or audit state remains present for recovery review.
The service transition is not crash-reported again once the checkpoint has advanced, but stale/invalid maintenance state can block a future arm until an operator reviews it.

A read-only reconciliation classifier is now included. It distinguishes:
1. clean checkpoint/no marker/no audit;
2. audit-only clean;
3. checkpoint advanced + stale confirmed marker + missing audit;
4. marker/audit mismatch;
5. marker + matching audit, including stale-after-advance;
6. invalid/missing checkpoint;
7. invalid/unsafe marker;
8. invalid/unsafe audit.

It performs **no cleanup**. Before unattended/live use, define an owner-reviewed recovery procedure for each classified state. Never auto-delete an uncertain marker/audit object.

## Remaining F15 gates

This child does not resolve:
- all-or-nothing pre-overwrite scan/coupling;
- unified retention-intent recovery;
- crash-history bounded atomic locking;
- actual overwrite owner/hook;
- exact installed PM2/tmux topology, paths, runtime user, disk projection and running build/source fingerprint;
- approved scheduler installation;
- owner-reviewed recovery actions for reconciliation states;
- live staging/rollback approval.

No host, process, scheduler, log, database, configuration, DBC, client or gameplay state is changed by this candidate.
