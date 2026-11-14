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
5. Explicit fatal signal, non-zero exit or signal evidence always defeats the maintenance marker and produces a normal crash incident.
6. A matching transition observed while the marker is only armed is **deferred**: no crash report and no checkpoint advancement occur. If confirmation never arrives, expiration leaves the old checkpoint intact so a later observation classifies the transition normally.
7. A confirmed expected transition advances the checkpoint without incrementing the crash sequence and writes a separate `last-expected-maintenance.json` audit record. It does not enter crash history or raw crash evidence.

## Exact transition contracts

### Worldserver / PM2
- expected STOP: previous identity is live, current identity is non-live, restart counter unchanged;
- expected RESTART: previous and current are live, restart counter advances exactly by one, and pid or uptime identity changes;
- fatal/non-zero/signal classification is never suppressible.

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
- unconfirmed marker never suppresses;
- confirmed exact World restart;
- confirmed World stop;
- fatal/non-zero evidence wins;
- wrong before identity;
- expired marker;
- exact Auth restart/stop;
- wrong operation ID;
- >30 minute window refusal;
- existing marker cannot be silently replaced;
- symlink marker refusal.

Operational integration tests cover:
- baseline → armed expected restart → observation defers with no crash/checkpoint advance → confirmation → same observation is accepted with no crash and marker consumed;
- confirmed expected restart plus SIGSEGV still creates a FATAL_SIGNAL_EXIT crash and does not consume the marker.

## Known remaining recovery gate

The expected transition is intentionally checkpointed **before** marker finalization. This ordering prevents an interruption from consuming the marker and then falsely reporting the already-approved transition as a crash.

Residual case:
- checkpoint advances successfully;
- audit write or marker unlink fails;
- the service state is safe and will not be crash-reported again, but the leftover marker can block a future arm.

Before unattended/live use, add a read-only reconciliation classifier for:
1. checkpoint advanced + matching confirmed marker + matching audit;
2. checkpoint advanced + marker + missing audit;
3. audit present + marker absent;
4. marker/audit operation mismatch;
5. malformed/symlink/insecure marker or audit;
6. expired marker after checkpoint advancement.

Never auto-delete an uncertain marker/audit object.

## Remaining F15 gates

This child does not resolve:
- all-or-nothing pre-overwrite scan/coupling;
- unified retention-intent recovery;
- crash-history bounded atomic locking;
- actual overwrite owner/hook;
- exact installed PM2/tmux topology, paths, runtime user, disk projection and running build/source fingerprint;
- approved scheduler installation;
- live staging/rollback approval.

No host, process, scheduler, log, database, configuration, DBC, client or gameplay state is changed by this candidate.
