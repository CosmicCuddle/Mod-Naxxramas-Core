# F15 restart-safe incident checkpoint — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; source/tests only; no live process access or deployment.  
**Parent:** F15 topology normalizer DRAFT #302 head `3c1339ae6007a8afc4aa297fa0138021dfbbdbb1`.

## Purpose

This slice adds durable once-only incident state between the topology evidence
normalizer and the private crash-report renderer.

It still does **not** execute `pm2`, `tmux`, `ps`, inspect `/proc`, read
owner logs, signal/restart daemons or touch `/root/cosmic_core`.

The design solves a concrete operational problem: a polling collector must not
create the same crash report every cycle, and it must not lose an incident if
the report sink fails.

## Semantics

Each service has one private 0600 checkpoint under a trusted 0700 state root.

- First observation establishes a baseline and creates no incident.
- A PM2 restart counter advance or Auth process-identity change is normalized by
  the parent #302 policy.
- The service sequence is incremented only for an actual normalized incident.
- The incident is rendered **before** the checkpoint advances.
- If rendering fails (for example disk-full/permission failure), the checkpoint
  remains on the previous identity and the same incident is retried next poll.
- After a successful render, the new identity + sequence are atomically persisted.
- Re-polling the same identity creates no duplicate report.
- Corrupt, symlinked, non-private or ambiguous checkpoint state fails closed.
- Checkpoint failure does not itself control or restart World/Auth.

Incident IDs are stable monotonic local labels such as:
`worldserver-00000001` and `authserver-00000001`.

## Local disposable evidence

Exact committed source was tested first in a temporary directory:

1. first World observation is baseline only;
2. World restart emits exactly once;
3. successful report advances checkpoint;
4. report failure does **not** consume the World incident;
5. retry after report failure emits the same next incident sequence;
6. first Auth observation is baseline only;
7. Auth disappearance emits exactly once;
8. Auth replacement emits an incident;
9. insecure/corrupt/partial state is refused.

Result: **9/9 local Python tests PASS**. No hosted Actions were used.

## Important remaining gap

This is still not the live collector. The next layer must obtain the actual
read-only evidence:

- Worldserver: real PM2 jlist/status, PM2 manager exit/restart evidence, exact
  stdout/stderr log origins and bounded recent context.
- Authserver: real tmux session/process identity, safe start-time identity and
  existing Auth/native console evidence.
- Build/source fingerprint sources.
- Local/UTC timestamps.
- Safe scheduling/installation model.

Those facts must be verified against the owner's host before deployment. No
intentional live crash/restart is authorized by this source-only slice.

## Custom Modifications Register — F15-INCIDENT-CHECKPOINT-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Persist per-service observation identity and emit each normalized incident once; never consume an incident before report success. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_incident_checkpoint.py`, `tests/test_f15_incident_checkpoint.py`, this note. |
| Parent | #302 head `3c1339ae6007a8afc4aa297fa0138021dfbbdbb1`. |
| Dependencies | Parent topology normalizer + private renderer supplied by caller; POSIX private file permissions/fsync. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Current layer consumes supplied snapshots only; first observation cannot reconstruct incidents that occurred before installation; no multi-host/shared-state support; no live schedule. |
| Tests | 9/9 local disposable Python tests PASS; no hosted Actions/live host tests. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; parent branches and live server remain unchanged. |
