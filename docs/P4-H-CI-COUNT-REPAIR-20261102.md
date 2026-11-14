# P4-H1/H2/Master exact CI assertion drift repair — 2 November 2026

**Owner:** CosmicCuddle. **Component:** Mod-Naxxramas-Core P4-H2 corpse sparkle and Master Loot quest give, inherited default OFF. **Type:** CI workflow assertions and documentation ONLY. Source parent #286 `edbed1937ab9312cbef24309845595cdb2ccf8fe` remains unchanged.

## Evidence

- [Core #286 Master Loot run 41420617819](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41420617819): actual Worldserver link **SUCCESS**; both GCC/Clang model jobs failed only because `mutants.py` reliably caught **10/10** known mutations while workflow asserted stale `9/9`. The full test model still reported `CHECKS 30 passed, 0 failed`, source contract six tests OK. Fix exact expected mutation count to 10; do not remove the mutant check or weaken the implementation.
- [Core #286 H2 run 41420617754](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41420617754): actual Worldserver link **SUCCESS**; both GCC/Clang models emitted `Ran 8 tests` / `OK`, and `CHECKS 21 passed, 0 failed`, while workflow expected six tests. Fix exact expected count to eight; retain 21-case assertion and all original source tests.

## Change and release boundary

Only `.github/workflows/naxx-p4-h-master-loot-20261101.yml` and `.github/workflows/naxx-p4-h2-sparkle-20261101.yml` are modified. No `src/`, config, SQL, scripts, initial source snapshots, test fixtures or on-disk player data. New exact-head CI must pass independently; historic successful native builds are not gameplay validation. P4 systems remain default OFF until stage/host testing, backups and CosmicCuddle approval.

**Rollback:** discard this test-only child to return the unchanged Core #286 source. No production operation or player data edit.
