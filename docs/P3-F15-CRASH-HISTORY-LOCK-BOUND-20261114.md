# F15 Crash-History lock/bound hardening — 2026-11-14

**Owner:** CosmicCuddle  
**State:** source-only child of DRAFT #309.  
**Parent:** `827f5618c991611c483941cabb0ba910fee09180`.

## Purpose

Make crash-history publication bounded and idempotent under retry/concurrency without rewriting an already-published crash report.

## Renderer contract

- `Crash-History.txt` has an explicit 8 MiB ceiling.
- A persistent private sidecar `Crash-History.txt.lock` supplies the stable exclusive `flock` domain across history-file replacement.
- While holding that sidecar lock, one opened history fd covers validation, duplicate inspection and append.
- Both lock and history objects must remain private regular single-link files; the lock must remain empty.
- History is read with bounded `pread`, not unbounded `Path.read_text()`.
- Existing history must end on a complete newline and be valid UTF-8.
- Exact physical history lines are compared; a single existing exact line is idempotent, more than one is refused.
- A new append is refused if it would cross the ceiling.
- Partial `os.write` is completed explicitly; append is fsynced.
- History fields are normalized to one physical line so embedded tabs/newlines cannot defeat retry matching.
- Symlink, hardlink, insecure-mode, malformed/incomplete and non-UTF-8 history fail closed.
- Concurrent first publication uses create-or-validate for the private crash directory and exact report file; a concurrent exact report creation is verified rather than treated as a different incident.

## Repairable publication

A detailed report may already exist if a prior attempt failed before Crash-History append. `ensure_report()` verifies the report byte-for-byte and then repairs the missing history line under the history lock.

History refusal does not rewrite or modify an existing report.

## Tests added

Focused tests cover:
- sidecar-lock symlink, insecure/non-empty and hardlink refusal;
- ordinary report/history private publication;
- retry idempotency;
- report-only partial publication repair;
- concurrent history repair;
- concurrent first report creation;
- embedded newline/tab normalization;
- existing oversized history;
- append crossing the configured bound;
- history symlink, insecure mode and hardlink;
- incomplete trailing line;
- non-UTF-8 history;
- duplicate exact lines;
- partial `os.write`;
- existing renderer redaction, path, collision and bounded-context cases.

Tests are committed but **not claimed executed on an exact local checkout in this environment**. No hosted Actions were requested.

## Remaining composition gate

The 30-day retention helper currently rewrites `Crash-History.txt` through its own atomic replacement path and does not yet acquire `Crash-History.txt.lock`. Unattended retention therefore remains blocked until retention/recovery hardening uses this **same persistent sidecar lock** around history read/rewrite/replace. Locking the replaceable history inode itself would be insufficient because a waiter could append to the old inode after rename.

## Custom Modifications Register — F15-CRASH-HISTORY-LOCK-BOUND-20261114

- **Owner:** CosmicCuddle.
- **Owning component:** Mod-Naxxramas-Core F15 crash-report renderer.
- **Intended behaviour:** bounded, private, exact-once crash-history indexing under retries/concurrency.
- **Parent/source ref:** DRAFT #309 exact head `827f5618c991611c483941cabb0ba910fee09180`.
- **Affected files:** `scripts/f15_crash_report_renderer.py`, `tests/test_f15_crash_report_renderer.py`, this document.
- **Dependencies:** future retention history rewrite must acquire the exact same `Crash-History.txt.lock` sidecar before reading/replacing history; compatible-but-separate inode locks are not sufficient.
- **Known risks:** reaching the history bound stops incident publication/checkpoint advancement until operator review; this is deliberate fail-closed behaviour. This child does not rotate/truncate history.
- **Tests:** focused tests added; exact-head execution UNKNOWN here; no hosted Actions.
- **Live status:** DRAFT only, not installed or invoked on owner host.
- **Rollback:** abandon/revert this child branch; no live state exists.
