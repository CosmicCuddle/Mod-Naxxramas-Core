# F15 crash-window counterexamples — disposable-file source review (30 Oct 2026)

**DRAFT / TEST-ONLY / NONDEPLOYABLE.** This research child builds on [PR #250](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/250), which builds on [policy PR #249](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/249). It changes no World/Auth daemon source or state, Linux service, PM2 module, tmux session, database, configuration or production logs.

## Purpose

PR #249's 38 pure-model checks and PR #250's 29 temporary-file checks passing are **not enough for unattended 30-day archival**. This separate test file proves **ten actual counterexamples** using only disposable files inside test-owned temporary directories. The assertions *pass* because they correctly demonstrate gaps; do **not** interpret a green CI status as fixing these gaps.

### Ten negative-control cases

1. **Worldserver stdout:** after restarting without a durable checkpoint, previously unread bytes can be wrongly skipped as old history.
2. **Worldserver stderr:** the same loss can independently affect the error stream.
3. **Authserver native file:** the same loss occurs for its separate file stream.
4. **Write-before-checkpoint failure:** a crash between publishing an archive append and recording its new offset can cause **duplicate** bytes on retry.
5. **Truncation during an unobserved interval:** unread tail disappears when the source shrinks.
6. **Inode replacement:** the old source's unread tail remains outside the new source and is not recovered by the simplistic follower.
7. **Cross-midnight ingestion:** without a separate actual time scheduler, one partial file can cover multiple days with **no completed timestamped daily archive**.
8. **Retention:** expiry *eligibility* is not an automatic daily cleanup job; the archive remains until a separately implemented caller acts.
9. **Authserver console parity:** reading native `Auth.log` does not magically capture messages present only on its PTY/tmux terminal.
10. **Storage pressure:** a 4096-byte per-poll read limit does not enforce an overall archive-disk quota.

## How this changes release readiness

These are implementation blockers, not excuses to edit the owner's live server. A real archiver design needs an **atomic durable source checkpoint linked to durable archive state**, replay semantics, old-inode tail handling with bounded handles, UTC day segmentation, an authenticated periodic scheduler, crash recovery, disk/quota reserve, and per-daemon logger adapter verification. Production archival and cleanup require race-safe directory-anchored operations, permissions and rollback. A log capture gap must be reported rather than called a successful backup.

**Never** use a `copytruncate` one-liner, blind `pm2 flush`, unreviewed `mv` of active logs, or reroute Worldserver stdin just to pass these tests. Existing evidence shows PM2-managed Worldserver and tmux-managed Authserver with a native Auth.log, but not guaranteed console parity.

## CI contract

A dedicated GitHub Actions job should re-run the previously proven **38 + 29 positive controls** and these **10 additional negative controls**. All file I/O happens in disposable `tempfile.TemporaryDirectory` objects on GitHub runners, not on CosmicCuddle's host. This branch is a review artifact, not an installer or deployable collector. Its success confirms **observability of known gaps**, not that F15 crash/error reporting or 30-day archives are operational.

The owner's request to stop serial terminal commands is preserved. Coordinate implementation and owner approval under [shared Issue #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4) and [F15 master](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6532886167).
