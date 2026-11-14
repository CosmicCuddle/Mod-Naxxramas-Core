# F15 owned 30-day retention — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; source/tests only; no live deletion or host deployment.  
**Parent:** F15 pre-overwrite snapshot DRAFT #305 head `86d8fac78ae8e2af1ed8440b9b57d64858a03cd5`.

## Owner rule

- preserve live server logs before approved overwrite/rotation/truncation;
- retain all F15-owned archived server-log copies for **30 days**;
- retain all F15-owned crash reports and crash-history evidence for **30 days**;
- after 30 days, expire only F15-owned archive/crash artifacts;
- never delete, truncate, rename or rotate an active original server log.

The exact boundary is strict: an artifact is retained through the full 30-day
boundary and becomes eligible only when the current UTC time is **later than**
created/observed time + 30 days.

## Snapshot archive retention

`f15_owned_retention_30d.py` recognizes only snapshot pairs created by
`f15_preoverwrite_log_snapshot.py`:

- one `.log` snapshot;
- one strict JSON manifest with kind
  `f15_preoverwrite_log_snapshot`;
- manifest retention_days must equal 30;
- size and SHA-256 must still match before deletion;
- symlink/hardlink/non-private files are refused;
- an fsynced retention intent is written before unlink;
- unknown/foreign JSON is preserved.

The original source path is metadata only and is never an unlink target.

## Crash retention

The crash cleaner recognizes only F15 renderer report names of the form:

`YYYYMMDDTHHMMSSZ-(Worldserver|Authserver)-<incident>.txt`

Unknown/manual files in `Crash Logs/` are preserved.

After an owned report is older than 30 days it may be removed. Only after the
referenced report is gone may its matching structured line be removed from
`Crash-History.txt`. Unknown/manual history lines are retained.

This source slice currently covers the human-readable crash report and
Crash-History index. Raw crash evidence bundles from the future operational
collector must use their own F15-owned manifest format and be added to the same
30-day policy before live deployment. Do not claim raw-bundle retention is
complete until that composition exists.

## Failure behavior

If any owned artifact is missing, tampered, hardlinked, non-private or changes
identity before unlink, retention refuses rather than guessing.

An unfinished `retention-intent.json` blocks further automatic retention for
that root until manually reviewed. Reporting/retention failures must never
restart or kill Worldserver/Authserver.

## Test intent

Focused disposable tests cover:

1. exact 30-day snapshot boundary is retained;
2. snapshot expires after the boundary and source remains byte-identical;
3. tampered snapshot hash refuses deletion;
4. foreign snapshot JSON is preserved;
5. exact 30-day crash boundary is retained;
6. old crash report + matching structured history line expire together;
7. recent crash/history stay;
8. foreign/manual Crash Logs files and unknown history lines stay;
9. unfinished retention intent blocks deletion.

No hosted Actions are requested for this draft.

## Deployment boundary

No production cleanup is authorized by this branch.

Before activation we still need:
- synthetic full-pipeline composition;
- raw evidence bundle ownership/retention format;
- exact production archive paths under `/root/cosmic_core/logs/`;
- current Worldserver/Authserver log/rotation topology verification;
- disk-capacity review;
- rollback/staging plan;
- CosmicCuddle approval.

## Custom Modifications Register — F15-OWNED-RETENTION-30D-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Retain F15-owned archived logs and crash reports/history for 30 days, then expire only verified owned artifacts. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_owned_retention_30d.py`, `tests/test_f15_owned_retention_30d.py`, this note. |
| Parent | #305 head `86d8fac78ae8e2af1ed8440b9b57d64858a03cd5`. |
| Dependencies | F15 snapshot manifest format and F15 renderer crash filename/history format. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Raw crash evidence bundle retention not yet composed; no disk quota policy yet; unknown files intentionally accumulate rather than being guessed/deleted. |
| Tests | Focused disposable tests authored; no hosted Actions/live host test. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; no live file has been deleted. |
