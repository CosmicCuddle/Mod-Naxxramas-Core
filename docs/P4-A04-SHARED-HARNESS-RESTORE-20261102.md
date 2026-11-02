# CosmicCuddle Core P4 — A04 shared test-harness integration correction

**Owner:** CosmicCuddle. **Date:** 2 November 2026. **Status:** DRAFT/unmerged, tests-only, no production code or data.

## Verified hosted failure

The existing combined [Core #284](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/284) has **5 failed workflows**. The F15 PM2 negative-test mismatch was corrected separately in [#285](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/285) (operator CI [41367487421](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41367487421) SUCCESS). The **other four P4-H source harness workflows failed on import before executing loot assertions**:
- [P4-H1 pickup #41365618305](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41365618305), job `125025036033`.
- [P4-H2 sparkle #41365618427](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41365618427), job `125025036420`.
- [P4-H Master Loot #41365618371](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41365618371), job `125025036224`.
- [P4-H interop #41365618203](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41365618203), job `125025035476`.

Each failing log shows **`ModuleNotFoundError: No module named 'build'`** while importing `tests/p4_h*/build_*.py`, which prepend `tests/a04_native` and expect `import build`. The combined source lacked `tests/a04_native/build.py` and its referenced pinned prep/stand-in files even though those exact files exist in original independent [Core #262](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/262). The same workflows' **pinned full Worldserver link jobs** where present were **SUCCESS**, which is only evidence of a native link at that tested SHA, NOT gameplay correctness or harness PASS.

## Exact source preservation / Custom Modifications Register: CORE-P4-A04-HARNESS-RESTORE-20261102

| Field | Record |
| --- | --- |
| Intended behaviour | Restore actual shared A04 native *test fixture* used by P4 H1/H2/Master/interop checks. Nothing may change loot awards, corpse sparkle, master-loot decisions or gameplay. |
| Owning component | CS01 integration test infrastructure, backed by Claude's original [test-only #262](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/262). Original source remains unchanged. |
| Parent and paths | Exact child of [Core #285](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/285) `2f0b20e880a37839dfcb6070f2ad6cd93334ee8d`. Five exact-origin test files under `tests/a04_native/`: `build.py`, `prepare_pinned.py`, `harness_env.h`, `stubs/ConditionMgr.h`, `harness.cpp`; plus two H1/H2 workflow YAML **path-filter-only** amendments, so edits to this shared helper actually trigger their tests. |
| Blob provenance | Exact #262 git blob hashes: `5b43cdb8fb11171c7a6ada80408bf58575c6fbd1`; `15553d57bc4c92ccec477b435c8843a02e93ab9a`; `00dd7a5480aff82ffdf823617fc02e4c8ac64a83`; `dbc8f1ae3942a4c368c91d481db305887086c21a`; and `f9405d608a781965478f1f608a93e97acfcc8219` (harness.cpp). All five fetched and verified **byte-identical**. |
| Runtime and configs | **No runtime C++**, headers in `src/`, SQL, DB, DBC, conf, Playerbots, worldserver, character records or host logs changed. `harness_env.h` is compile-time *test-only*. |
| Risks and limitations | Test harness relies on pinned historical Core `8daffdabe...` and exact blob comparison. May expose additional real P4 regressions once the import runs; a fixed import is not proof the assertions pass. Dynamic tests may require more of #262 harness if future tests import additional modules; do not silently weaken pin, skip checks, or modify original P4 changes. |
| Test status | Existing full Worldserver links on combined #284 have succeeded in some P4 CI jobs; four A04 harness jobs failed **before their assertions**, as above. **This child has NOT independently passed those tests at creation.** Verify exact-head Actions statuses and source/compilation separately; no game or live server tests. |
| Rollback | Close/discard this isolated draft branch to return to #285. No live rollback applies. If ever released with production work, require owner-installed source inventory, native link, staging loot/gameplay, restorable backups and CosmicCuddle's separate approval. |

**Eight-file scoped diff** (latest child adds source-owner original `tests/a04_native/harness.cpp`): two existing H1/H2 workflow path filters, five byte-identical A04 helper/harness files, one register memo. Original #262 harness.cpp blob `f9405d608a781965478f1f608a93e97acfcc8219` was fetched and re-verified identical. First exact [interop run 41417537683](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41417537683) **FAILED only after progressing past the original build import**: 7? seam assertions ran before go_loot compile hit `fatal error: ../a04_native/harness.cpp: No such file or directory`. This additional original test-only dependency is now restored; next exact-head H1/H2/Master/interop results **not yet proven PASS**. No test values changed, bypassed or skipped.

No script executes destructive changes to the owner's server; the fixture copies *pinned public source* into disposable test output in the CI sandbox.


## Evidence checkpoint — exact restored harness (2 Nov 2026)

The [interop run 41417918490](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41417918490) at `3cd1385cd5624b3086aac34a9835020b1574459f` executed **both g++ and clang++ jobs** after all five original A04 fixtures were restored. Both jobs completed `Ran 8 tests ... OK`, **28/28 seam checks** and **15/15 gameobject checks**, with no reported failed checks. The CI step then exited 1 because `.github/workflows/naxx-p4-h-interop-20261101.yml` still matched the outdated literal `CHECKS 13 passed, 0 failed`, while the actual immutable source test defines `GO_CHECKS = 15` and the harness produced `CHECKS 15 passed, 0 failed`. This is an **exact count/CI assertion drift**, NOT a demonstrated gameobject-loot gameplay failure.

In the same combined DRAFT #286, Maintenance updated the workflow's check label and required grep to **15/15**, kept all tests and source behaviors intact, and corrected the original readme's stale gameobject check total. **No tests skipped or weakened**; no P1–P4 runtime C++/SQL/config was changed. The newest exact-head CI result after these changes **is not yet claimed PASS**. The original five helper blobs remain byte-identical to source owner #262; if this child is dropped, return to #285 with no DB or live rollback. Independent owner-host/raid/quest tests are still required before any production approval.

## Subsequent missing regression fixtures and count corrections (2 November 2026)

[Core #286 interop run 41419538088](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41419538088) executed both g++ and clang++: 8/8 Python tests, 28/28 seam checks and 15/15 gameobject checks all succeeded. The subsequent mutant step caught 16/16 source/header mutations (12 CPP and 4 header), but its workflow still expected the obsolete string 15/15, so that job failed on an assertion count mismatch rather than an observed loot regression. The combined branch now requires exact 16/16.

Checking its remaining regression stage identified two Python test drivers omitted from the combined tree: tests/test_a04_native_quest_loot.py (original Core #262) and tests/test_p4_quest_loot_view_guard.py plus the three tests/p4_view_guard source fixtures (original Core #264). All five restored Git blobs are byte-identical to the historical source owners, not modified or reimplemented. Production QuestLootViewGuard CPP/header were already present and remain untouched.

Source-owner test_p4_h_master_loot.py explicitly requires 30 checks (not stale 29), so Master and interop CI must assert 30/30. The H2 21, H1 36, view24 and A04 71 expectations remain unchanged. No skips, disabled tests, production code, SQL, config or live DB/server changes. Exact-head CI and real-world game acceptance still must be verified. Rollback is simply discard this unmerged draft child to return to #285.
