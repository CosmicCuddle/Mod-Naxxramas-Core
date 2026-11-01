# CosmicCuddle — F15 raw-log archive + private-supervisor test composition

**Date:** 1 November 2026. **Owner:** CosmicCuddle. **Status:** isolated development DRAFT; unmerged, not installed or scheduled. No production log/host operation is authorised.

## Exact source and reason

- **Parent:** [Core #281](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/281) exact review-fix head `796cc817343fdbad7b61ff3885f961d51bfe4cdc`, itself child of [combined P1–P4 + P3 tooling #280](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/280) `deebd7b68d2966ede6dc80a8da92d1351e4cb7eb`. #281 introduces **opt-in, copy-only** completed Worldserver/Authserver supervisor raw-stream archive, with source receipts, SHA-256 manifest, private staged atomic publish, idempotent re-verification and a default read-only dry-run. It **never removes or truncates an original raw file**.
- **Second source:** reviewed one-file [Core #282](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/282) at `7afe457ef10f0440196c29a18c886f5db27cf544` corrects a synthetic unfinished-run fixture to create the same private 0700 run/capture directories as the real supervisor. Source path `tests/test_f15_supervised_retention.py` was copied with its **exact Git blob SHA** `3fde1ce724e9b69d9def842afd9b49d0924855db`. There is **no change** to private-mode enforcement or to actual retention logic.
- **CI composition:** the existing `.github/workflows/f15-raw-archive-20261101.yml` now includes the inherited supervised retention suite (previously skipped due to the defective fixture) plus the raw-archive 20-test suite, 13 mutant negatives, storage audit and child-process supervisor tests; its five-path frozen source check is conditional on the original Claude #281 source branch, not this legitimate child. The existing `.github/workflows/naxx-p4-h-master-loot-20261101.yml` gains **only PR paths** for the archive script, tests, fixture and archive workflow, triggering the combined pinned native Worldserver link.
- **No edited runtime path in this child:** `scripts/f15_raw_archive.py`, `f15_supervised_retention.py`, the F15 collector, Naxx P1 Warlock/P2 Hunter/P4 quest loot C++, default flags, SQL, DBC and client files remain byte-identical to their reviewed parent #281.

## Custom Modifications Register — NAXX-P3-F15-RAW-ARCHIVE-COMPOSED-20261101

| Field | Description |
| --- | --- |
| Intended behaviour | Verify F15 completed-run, no-original-deletion raw archive and existing 30-day **collector-owned** archive retention while independently testing that unfinished raw runs stay untouched. |
| Owning code and refs | #281 source archiver, #282 exact fixture, this child of #281 with only two inherited GitHub Actions workflow edits and new memo. Original branches and PRs remain untouched. |
| Dependencies | POSIX private 0700 run/capture/archive directories; full pinned historical Core+Playerbots+IP Worldserver workflow; available disk for copied raw streams, POSIX rename/fsync. Actual owner process manager, original raw stream paths and current dependencies are UNVERIFIED. |
| Risks and limits | Archive is **copy-only** and requires explicit owner-selected completed run; it is NOT a scheduler or original raw-log 30-day retention. Source checks, SHA-256 and single-link mode checks do not guarantee same-UID concurrent adversarial replacement protection. No engine-crash inference from process exit. |
| Tests | Claude reported **20 local tests + 13 mutants** on the original #281 update. The new composed HEAD requires **new hosted CI and disposable reruns**, including inherited unfinished-run 0700 fixture and pinned full native Worldserver link. No actual owner-host, native/gameplay or installed-version acceptance claimed. |
| Live status and rollback | DRAFT only. Revert/discard this child to restore #281; other independent parent #280/#282 sources remain. No files deleted, archives created on owner host, migration, setting changes or installation. |
| Operator gates | Verify real installed World/Auth capture configuration and backup restores first. Separate owner approval required before executing any archive copy on live logs, any scheduler, or any deletion/retention policy for original raw streams. |

## Acceptance checklist

- [ ] Exact HEAD GitHub archive CI finishes: 20/20 synthetic archive cases, 13/13 mutants, complete F15 retention/collector/supervisor/audit tests. No claim from queued status.
- [ ] Exact HEAD pinned Worldserver link completes without accidentally launching World/Auth. Historical Core/Playerbots pins do not establish compatibility with the owner's installed versions.
- [ ] Validate all source, date, privacy and copy-only boundaries on disposable paths with umask 022 and 077; compare source hashes and new archive manifests.
- [ ] Inspect owner-installed server topology and back up source/data before any approved real-host dry-run. Protect existing P1/P2/P4 custom gameplay.
- [ ] Obtain explicit CosmicCuddle approval separately for any staging/install, owner logs, automated 30-day raw retention or destructive cleanup.
