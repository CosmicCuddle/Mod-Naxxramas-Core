# F15 — read-only World PM2/Auth native source admission (review draft)

**Owner:** CosmicCuddle. **Project:** Server-Side-Maintenance (CS01).
**Source parent:** [F15 synthetic integrated DRAFT #256](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/256) at `dcf09ec570575feec82c4afc1ca1c0806e99d617` (stacked on the existing #249–#252 chain).
**State:** Independent test-only stacked DRAFT, unmerged. Not installed or executed on the owner's server.

## Purpose

Before designing an actual input adapter for F15, fail closed if the claimed sources do not match the **three distinct, explicit, consented inputs**:

1. Worldserver PM2 stdout log (from an already obtained PM2 process-list JSON snapshot).
2. Worldserver PM2 stderr log (same process, but a different file).
3. Authserver **native file** explicitly identified by the operator; this is NOT the Auth tmux console/PTY.

`tests/f15_source_admission.py` is a **callable-only, non-installed, read-only admission/provenance helper**. No default source paths, no shell subprocess, no automatic PM2 calls, no CLI, no log contents or filenames in returned metadata, no writes/deletion/copy, no remote or owner-host access. It does not package, redirect or attach to either daemon. It requires a caller to supply an operator-approved PM2 JSON snapshot, exact World process name and executable basename, exact Auth native pathname and *both separately approved source-directory roots*.

For each source, the helper validates path components with directory-relative `O_DIRECTORY | O_NOFOLLOW`, opens the final file `O_RDONLY | O_NOFOLLOW | O_NONBLOCK`, and obtains only `fstat` metadata; it rejects symlink parents/final files, non-regular files, hardlinks, source paths outside explicit roots, incorrect PM2 executable/status, duplicate process records, and physical inode aliases across all three streams. It closes the descriptors. Returned samples contain stream label, device/inode, byte size and modification/change times only.

`compare_sample` can report an **observed** growth, truncation, replacement/rotation or changed metadata with unchanged size. It NEVER claims complete capture or recovered unread rotated tails. A same-size rewrite with artificially restored timestamps or a truncate/regrow between samples can remain invisible. No attested origin or secure identity is inferred from untrusted PM2 JSON.

## Executed test evidence and limitations

Local test run on isolated temporary fixture files: `python3 -I -B -m unittest discover -s tests -p test_f15_source_admission.py -v` (from repo checkout); the source/test files were also run in an equivalent local flat directory. **15/15 passed** in that local test before GitHub submission. At initial DRAFT HEAD `e1f1b6a` the dedicated new admission CI job succeeded but inherited #256 frozen five-file assertion failed mechanically because the child has new paths. The branch-only inherited job's frozen step was then restricted to the original Claude #256 branch, preserving the actual inherited regression tasks; **check the updated exact-head hosted CI before claiming resolution**.

Tests cover ordinary metadata-only success; missing/duplicate PM2 process, stopped status, unexpected executable, duplicate out/err or Auth inode, symlink parent/file, hardlink, outside-approved-root and prefix confusion, directory source, observed source growth/truncation/same-size rewrite, and no source mutations. All test input files are disposable fixtures.

**Still absolutely NOT operational:** this helper does not read or stream log bytes, checkpoint/journal them, combine with #256's synthetic `IntegratedRunner`, preserve 30-day archives, perform UTC sealing, capture Auth PTY, cooperate with actual PM2 rotation, distinguish crash from stop, handle real quota/fsync/old-inode tails, or eliminate check-then-unlink races. No live owner path or effective PM2 fields have been verified. An actual single-authority collector is future work and requires separate review and owner approval. This slice cannot satisfy the P3 operational acceptance gate by itself.

## Review/rollback

Changed paths (four added, one CI-only inherited guard adjustment): `tests/f15_source_admission.py`, `tests/test_f15_source_admission.py`, this memo, `.github/workflows/naxx-f15-source-admission-20261031.yml`, and the **existing #256 workflow** `.github/workflows/naxx-f15-integrated-disposable-20261031.yml`. The inherited change scopes ONLY the frozen five-file assertion to Claude's original #256 PR branch; the inherited 101 + 54 + 14 synthetic regression tasks are still invoked for this child branch. The dedicated child workflow independently asserts the inherited file is byte-identical to original #256 except for that exact conditional. Original Claude branch is untouched. No existing #249–#256 Python/C++ source, tests or docs, no `src/`, `conf/`, `data/`, `tools/`, SQL, PM2, tmux, Worldserver, Authserver, host files or production state. To roll back this unmerged proposal, drop its isolated review branch/PR. The owner four-priority P1/P2/P3/P4 coordinated-testing gate and 8 map threads remain unchanged.

Before any proposed host test: collect **owner-consented, minimal redacted metadata only**, verify actual log file names/effective permissions and process state securely, match installed commits/config and restored backups, decide Auth native-vs-PTY parity and PM2 rotated-tail lifecycle, and request owner approval. Never post raw PM2 environment dumps, absolute confidential host paths, log bodies or credentials to GitHub.
