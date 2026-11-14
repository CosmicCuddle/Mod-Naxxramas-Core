# F15 pre-overwrite batch hardening — 2026-11-14

**Owner:** CosmicCuddle  
**State:** source-only child of DRAFT #309.  
**Parent:** `827f5618c991611c483941cabb0ba910fee09180`.

## Purpose

Guarantee that a directory-level “copy logs before overwrite” attempt does not publish successful snapshot pairs for early files before a later source fails validation.

This candidate does **not** own or perform the destructive overwrite. A future overwrite owner must treat any non-success from this helper as a hard stop.

## Batch contract

For `snapshot_log_directory`:

1. the archive must be a direct child of the selected log root;
2. a private archive lock serializes scan → preparation → publication;
3. the complete direct log root is pre-scanned with `lstat` before snapshot data is created;
4. `Crash Logs`, `Archived Logs`, `.f15-state` and ordinary nested directories are never recursively copied;
5. excluded F15 names must themselves be real directories;
6. symlinks, hardlinks, FIFOs/devices/sockets/other non-regular entries and over-bound sources fail closed;
7. every eligible regular file is opened no-follow and must still match its pre-scan fingerprint;
8. all copies and manifests are first written as unique private hidden pending files and fsynced;
9. every source is revalidated as a complete set after preparation;
10. only after all preparation/revalidation succeeds are final `.log` + `.json` pairs published and the archive directory fsynced.

A source changing while another source is copied invalidates the batch before final publication.

## Interruption semantics

Preparation failure may leave hidden pending evidence for review but leaves no final snapshot pairs.

Publication is not a multi-file filesystem transaction. If the process or filesystem fails during the final publication loop, partial final evidence may remain. The operation raises/fails and **must never be interpreted as successful preservation**. A future overwrite owner must be coupled so it does not proceed on this failure.

The helper cannot stop active log writers. The eventual overwrite owner must also ensure that bytes cannot be appended after a successful snapshot return and before the destructive overwrite. That coupling remains a separate staging gate.

## Retention compatibility

The existing 30-day archive retention recognizes owned snapshots only through final `*.json` manifests of kind `f15_preoverwrite_log_snapshot`.

This child’s:
- `.f15-snapshot.lock`;
- hidden `*.pending.<unique>` data;
- hidden `*.pending.<unique>` manifests

do not match that ownership scan and are preserved as foreign/incomplete evidence. They are not silently deleted by normal snapshot retention.

## Tests added

Focused tests cover:
- ordinary two-log batch success;
- non-recursion of nested directories and F15 directories;
- root/source/excluded-name symlinks;
- FIFO and hardlink refusal before final publication;
- excluded F15 name with wrong object type;
- second-source preparation failure with no final pair;
- source drift after pre-scan;
- early source drift while later source is prepared;
- source mutation during copy;
- partial `os.write`;
- deterministic collision refusal;
- concurrent identical snapshots serialized by the archive lock;
- insecure archive lock;
- publication interruption propagating failure;
- archive-root containment;
- insecure archive permissions;
- naive timestamps.

These tests are committed but **not claimed executed on an exact checked-out branch in this environment**. No hosted Actions were requested.

## Custom Modifications Register — F15-PREOVERWRITE-BATCH-HARDENING-20261114

- **Owner:** CosmicCuddle.
- **Owning component:** Mod-Naxxramas-Core F15 operational tooling.
- **Intended behaviour:** all eligible direct active logs must pass a complete pre-scan and copy/revalidation phase before final snapshot pairs are published; any failure blocks the future overwrite owner.
- **Parent/source reference:** DRAFT #309 exact head `827f5618c991611c483941cabb0ba910fee09180`.
- **Affected files:** `scripts/f15_preoverwrite_log_snapshot.py`, `tests/test_f15_preoverwrite_log_snapshot.py`, this document.
- **Config/SQL/DBC/client dependencies:** none.
- **Operational dependency:** actual overwrite/rotation owner is still UNKNOWN and must later be wired so snapshot failure prevents overwrite.
- **Known risks:** active writers can append after helper success unless the overwrite owner supplies a safe quiescent/cutover point; interrupted publication can leave partial evidence requiring review; hidden pending evidence is intentionally not auto-deleted.
- **Tests:** focused source tests added; exact-head execution remains UNKNOWN here; no hosted Actions.
- **Live status:** DRAFT only; uninstalled and not invoked on owner host.
- **Rollback:** abandon/revert this child branch. No live state exists.
