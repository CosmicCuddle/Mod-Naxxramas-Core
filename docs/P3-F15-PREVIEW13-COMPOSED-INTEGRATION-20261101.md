# CosmicCuddle — P3 F15 13-case retention-preview integration

**Date:** 1 November 2026. **Owner:** CosmicCuddle. **Status:** DRAFT / unmerged / not installed. No production logs, original raw streams, server processes or schedules accessed or altered.

## Why this child exists

The combined [Naxx Core source DRAFT #283](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/283) exact `16314bf0a958266742ed9ce68598645d8cfcd173` inherited the old **9-case** F15 collector-owned archive preview from [#280](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/280). Information's [current independent DRAFT #277](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/277) `e3d38e6583e7ef54205a330c123c095fac939e1c` provides an improved **read-only 13-case** preview, distinct from the Core CS03 **copy-only completed supervisor raw archive** source [#281](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/281).

## Custom Modifications Register — CORE-F15-PREVIEW13-INTEGRATION-20261101

| Field | Exact record |
| --- | --- |
| Intended behaviour | Preview, only after explicit `--preview`, expiry of **collector-owned** pre-existing UTC-day archives with the same safe 30-day cutoff and validated journal/receipts. No deletion, PM2/tmux, World/Auth launch or supervised original raw stream archival. |
| Owning component / source | Core F15 Python scripts; original source of this preview owned by Information's isolated #277, integrated into CS01 child of #283 without editing either parent branch. |
| File changes | Replace `scripts/f15_retention_preview.py`, `tests/test_f15_retention_preview.py`, `docs/research/F15-RETENTION-PREVIEW.md` with **identical Git blobs from #277**. Add one isolated preview CI workflow and this integration memo. No C++/SQL/DB/config/DBC/owner-host changes. |
| Exact source refs | #277 preview script `05903eb336b044fa868127f9faacb25de1fbed6c`; 13-test fixture `1ca4473ac7760c0de7004bc1e3954c4e72a52e60`; memo `b0d02215873f89e3c88943f75cbef111429559a4`. |
| CI exception and fix | Current #277 isolated workflow blob `e2916bef470c667eb03d8ba6017011c114c69da5` contains an **actual malformed/unclosed 13-case `grep -Eq` line at L36** with duplicated embedded AST step, plus a stray L60 path fragment. **Do not copy that broken workflow unchanged.** The isolated CI child retains three intended steps (syntax, exact 13 count/OK, no-delete AST) and fixes that command/step structure. Push branch filter updated to this integration branch; PR path trigger remains. Source owner notified in #277 thread. |
| Security / regressions | Existing private 0700 path and ancestor checks, cooperative lock, record/archive label equality and allowlist, symlink/hardlink receipt tests, generic path-free refusal, no-delete/process AST guard. Information authored 13 disposable tests; successful hosted/local execution on this integrated SHA is **not yet claimed**. |
| Remaining risks | Core parent collector PM2 replacement fixture remains independently unresolved, and no actual owner source/installed module data, 30-day raw-log auto-retention/backup or functional crash tests are verified. Existing source-race and path ownership limitations remain; separate CS03 refusal privacy fix on #281 still outstanding. |
| Test plan | Run exact-head isolated preview 13-case test and AST, then inherited full F15 suites, then full pinned combined Worldserver link; stage collector & supervisor logs on approved private disposable fixtures; preserve originals and refuse unknown/malformed structures. No real server files used in CI. |
| Dependencies | Existing `f15_operator_collector.py` and `f15_archive_retention.py` as inherited in #283, Python 3 POSIX flock. Does not modify the combined P1 Warlock, P2 Hunter ammo, P4 loot, IP or Character Services source. |
| Rollback | Drop this isolated child to return to #283 and the exact old 9-case preview, **not** a live-data rollback. For any future release, establish restorable host backups and explicit owner approval independently. |
| Live status / approval | **NOT INSTALLED / NOT ACTIVE.** CosmicCuddle has not authorised merging this child, enabling data manipulation, deleting logs, changing processes or deploying. |

**No claim:** A passing static/isolated CI suite would not prove the real World/Auth crash/console capture or one-session P1–P4 gameplay acceptance. The automated test is not owner-staging evidence.
