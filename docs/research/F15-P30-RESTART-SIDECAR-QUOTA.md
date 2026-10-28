# F15 P30 — bounded S3 restart sidecars (offline only)

**Status:** DRAFT and offline. Nothing is installed or enabled. F15 remains **BLOCKED_AT_R0 / NOT OPERATIONAL** for both Worldserver and Authserver, for crashes and for WARN/ERROR alike. This change touches no daemon, log, root path, service, config or database.

**Base:** #185 `ce8c85ec9ee6ed61bd44b4ef92d6737c03fd0b1e`, which descends from #141 `656e108` and #177 `7a94963`. Assigned in #48 6467467057 (P1).

## Problem (from the #177 review, comment 6467422929)

`RestartSidecarStore.publish_restart` wrote one immutable `restart-<incident>-<id>.txt` per caller-supplied `attempt`, with no admission check. In a disposable probe, one capped crash accepted **1,500** sidecars, and every publish rescanned the growing directory, taking about 151 s in total. The #177 caps and the #181 4,096-entry scan ceiling did not cover this path.

## Change

- **`offline_restart.py`:** new `_admit_restart_locked`. It runs inside the existing verified directory and legacy lock, **after** the duplicate check (an identical replay still returns `False`, and a conflicting one still raises `FileExistsError`) and **before** any temp write. One bounded scan counts:
  - sidecars of this incident (fixture cap **8**);
  - sidecars of the same daemon, mapped through the finalized incident's service (fixture cap **128**);
  - **all** `restart-*.txt` names, including malformed, orphaned or symlinked ones (fixture cap **256**);
  - bytes, against the **one** `MAX_TOTAL_REPORT_BYTES` budget shared with finalized crash and error reports.

  At any limit it raises `OverflowError` and increments the in-memory, saturating `capacity` counter. Nothing is deleted, renamed or overwritten.
- **`offline_store.py`:** the report admission also counts `restart-*.txt` bytes, so both directions share the byte budget. Sizes come from `lstat`, so symlinks are never followed.
- **No format change:** the S2/S3/S4 file formats and names are unchanged. An invalid `attempt` is still refused by `RestartObservation.checked()`.

All four ceilings are **test fixtures**, not an owner retention or service-level policy. A refusal is an untrusted local diagnostic; it does not identify a real World or Auth event.

## Tests

`tests/test_f15_restart_sidecar_quota_p30.py` has 16 tests, all on disposable temp directories:
- the 8/9 boundary;
- 1,500 distinct attempts leave exactly 8 sidecars, well inside the bounded-time limit;
- a duplicate at the cap is idempotent, and a conflicting replay still conflicts;
- invalid attempts write nothing;
- a refusal leaves every file byte-identical;
- world vs auth lane fairness;
- malformed, symlinked and foreign names consume the quota, and the symlink target is untouched;
- the shared byte budget works in both directions;
- concurrent distinct and identical publishers in separate processes;
- ENOSPC before link leaves no sidecar or temp file;
- EIO on index rebuild keeps the final sidecar and crash, and recovery works afterwards;
- a crowded directory fails closed;
- a lock file owned by another uid fails closed (review item A11);
- quota lane validation for both admissions (review item A13).

Locally, 14 must-fail mutants were all caught, including removing the admission call, which restores the original bug.

## Not solved here

These remain open: writer authenticity (anything running as the same uid can write), forged `verified` flags, the real World/Auth producer and its binding, path ownership under `/root`, reconciling the format with #171, retention or overflow-event policy, and every owner R0 fact.
