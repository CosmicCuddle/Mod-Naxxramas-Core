# CosmicCuddle — P3 F15 PM2 observer privacy + deterministic rotation regression

**Date:** 2 November 2026. **Owner:** CosmicCuddle. **Status:** DRAFT, source not installed, no live PM2/World/Auth accessed.

## Purpose and source-level issue

On the inherited combined source [Core #284](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/284) exact parent `4aacde23284dd2b45c1ca09b09abb5c165a7a101`, the **CS01-owned** F15 PM2 observer branch has two bounded issues:

1. `scripts/f15_pm2_observer.py::main` catches `Refused`, `OSError` and `ValueError` but appends `str(exc)` to stderr. Python `FileNotFoundError` can include the private log path by default; validation messages may also carry owner paths. Fix only the error surface: emit one generic fail-closed message with the same exit code 2. No change to `observe_once`, `pm2 jlist`, start/stop permissions, raw collection or any file writing.
2. In `tests/test_f15_pm2_observer.py::test_rotation_and_symlinks_refuse_without_source_deletion`, the test unlinks then recreates a synthetic source path. If the filesystem immediately recycles its previous inode, the underlying legitimate `dev/ino` identity check can see no difference and the test is flaky. Keep an open read-only FD to the old unlinked inode until after the new file is checked; assert the replacement has a distinct inode and that the observed collector refuses. This does **not** change its production policy for rotation/truncation.

## Custom Modifications Register — CORE-P3-F15-PM2-PRIVACY-20261102

| Field | Record |
| --- | --- |
| Intended behaviour | Preserve existing opt-in observer and raw original log safety; prevent owner-private filesystem path disclosure in CLI error output; make replacement-inode source regression deterministic |
| Owning component | CS01 Maintenance's F15 PM2 observer, distinct from Core CS03's original `f15_raw_archive.py` privacy fix in [Core #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143) |
| Changed source | `scripts/f15_pm2_observer.py` only in one CLI `except` output; no collection logic changed |
| Changed tests | `tests/test_f15_pm2_observer.py`: opened prior file FD through replacement, asserts different inode; new test mocks three path-bearing exception classes and asserts nonzero exit, silent stdout, private stderr, no created root and original sources unchanged |
| Dependency | Python 3 + POSIX `os.fstat` / `st_ino`; inherited Core F15 `f15_operator_collector.py` and existing `f15_archive_retention.py`; original Core #284 P1/P2/P3/P4 implementation unchanged |
| Source ref | Child of exact #284 head `4aacde23284dd2b45c1ca09b09abb5c165a7a101`; do not rewrite parent or Claude #281 |
| Test status | Test authored but **not executed locally or in hosted CI at the time of this entry**. Exact-head disposable operator CI and full F15 suites required before any claim of PASS; a test pass is not a World/Auth launch or live rotation result |
| Live status | No owner-host test, config/DB/SQL/DBC, server process, live logs, cron, raw deletion or production install performed |
| Risks / limits | No automatic rotation-follow support: legitimate replacements remain refused to prevent silent loss until an independently approved handoff design exists. A generic error may require secure private diagnostic triage instead of printing paths. All other F15 runner/scheduler/retention and installed module compatibility requirements remain open |
| Rollback | Drop this isolated child to return to #284 and existing PM2 observer; no live data rollback applies. Any future release needs restorable owner backups and approval |

## Safe validation

- Run `python3 -m unittest discover -s tests -p test_f15_pm2_observer.py -v` against disposable fake PM2 JSON and temp files.
- Confirm strict rejection when prior inode held open and replaced, including symlink/duplicate-source tests.
- Force `FileNotFoundError`, `Refused`, `ValueError` with private paths at CLI boundary; check return 2, generic stderr, zero stdout, no leaked path/source bytes.
- Run inherited F15 operator, collector, retention, supervisor, 13-case preview, and raw-copy suites plus pinned historical Core/PB Worldserver link; check exact code SHA and keep independent test scopes distinct.
- Before any owner-staging, verify actual installed PM2/tmux process/output paths and approvals, plus real World/Auth rotations, crash classification, daily archive 30-day retention and restore.
- **Never** launch/restart/kill an owner server, touch actual logs, delete raw files, enable experimental retention or merge/deploy without CosmicCuddle's separate approval.
