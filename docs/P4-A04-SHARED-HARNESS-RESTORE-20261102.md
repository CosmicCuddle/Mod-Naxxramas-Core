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
| Parent and paths | Exact child of [Core #285](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/285) `2f0b20e880a37839dfcb6070f2ad6cd93334ee8d`. Four exact-origin test files under `tests/a04_native/`: `build.py`, `prepare_pinned.py`, `harness_env.h`, `stubs/ConditionMgr.h`; plus two H1/H2 workflow YAML **path-filter-only** amendments, so edits to this shared helper actually trigger their tests. |
| Blob provenance | Exact #262 git blob hashes: `5b43cdb8fb11171c7a6ada80408bf58575c6fbd1`; `15553d57bc4c92ccec477b435c8843a02e93ab9a`; `00dd7a5480aff82ffdf823617fc02e4c8ac64a83`; `dbc8f1ae3942a4c368c91d481db305887086c21a`. All four were fetched **and verified byte-identical** after the integration copy. |
| Runtime and configs | **No runtime C++**, headers in `src/`, SQL, DB, DBC, conf, Playerbots, worldserver, character records or host logs changed. `harness_env.h` is compile-time *test-only*. |
| Risks and limitations | Test harness relies on pinned historical Core `8daffdabe...` and exact blob comparison. May expose additional real P4 regressions once the import runs; a fixed import is not proof the assertions pass. Dynamic tests may require more of #262 harness if future tests import additional modules; do not silently weaken pin, skip checks, or modify original P4 changes. |
| Test status | Existing full Worldserver links on combined #284 have succeeded in some P4 CI jobs; four A04 harness jobs failed **before their assertions**, as above. **This child has NOT independently passed those tests at creation.** Verify exact-head Actions statuses and source/compilation separately; no game or live server tests. |
| Rollback | Close/discard this isolated draft branch to return to #285. No live rollback applies. If ever released with production work, require owner-installed source inventory, native link, staging loot/gameplay, restorable backups and CosmicCuddle's separate approval. |

**Seven-file scoped diff (exact child HEAD `483c09e44bae1222f42ae45620519b420f907933`):** two existing workflow path filters, four verified identical A04 helpers, one register memo. Four new hosted H1/H2/Master/interop tests were triggered, queued/pending at the time of update; **not PASS**. No new source test values, skipping or unpinned edits.

No script executes destructive changes to the owner's server; the fixture copies *pinned public source* into disposable test output in the CI sandbox.
