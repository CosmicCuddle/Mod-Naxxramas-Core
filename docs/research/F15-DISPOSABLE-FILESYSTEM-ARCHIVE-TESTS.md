# F15 follow-up — disposable filesystem archive tests (review-only)

**Safety: test fixture only. Not a deployable archiver. Do not merge into production.**

This branch builds on unchanged [DRAFT #249](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/249) `b39639df00875c52e0e188623867af2b4bf96eda`.

It adds **one synthetic Python filesystem test fixture**, documentation and a dedicated GitHub workflow. Everything is run inside a GitHub-runner-owned `tempfile.TemporaryDirectory`. The fixture constructs all its own fake log files; it offers **no shell entrypoint, no external path argument and no Worldserver/Authserver, PM2, tmux or root access**. No server source, config, SQL, live logs or runtime code is changed.

## What is exercised against real disposable files

- **Initial large source file**: skip historical bytes at first attachment to avoid accidentally duplicating the owner's existing cumulative PM2 history.
- **Subsequent append**: read only new bytes with a limited 4096-byte per-poll budget; after no change, do not append twice.
- **Separate roles/streams**: Worldserver stdout/stderr and Authserver native file simulations do not share a checkpoint.
- **Mutation awareness**: report same-inode truncation and inode replacement; never falsely certify missing old bytes were saved.
- **Content**: arbitrary binary bytes round trip; partial output files are private mode 0600.
- **Sealing and cleanup**: publication into a timestamped final name uses a fake test-owned directory; an existing archive name is not overwritten. 30-day expiry is strict, and only synthetic, registered, verified-inode closed files are removed. Simulated files named `Crash-History.txt`, active source files, unowned or symlink/hardlink replacements remain untouched.
- **Failure cases**: unsupported stream identity, invalid read budget, hardlink/symlink sources, nonfile partial, and failed write preserve the previous checkpoint.

## Known limitations — these prohibit production use

This is a **disposable fixture, not the requested real collector**. It has no persistent checkpoint, streaming line boundaries, multi-logger timestamp/clock provenance, dynamic source detection, buffering across process crashes, reliable daily scheduler, Authserver terminal duplication, PM2 reopen/rotation cooperation, queue/quota/backpressure, free-space reserve, bounded unattended memory use, or authenticated crash signal identity.

The fixture's output file publish and cleanup are designed **only for its unique private temporary directory**. They are not safe against adversarial concurrent directory manipulation or failover on a real server. Production file deletion would require trusted directory handles, locking, nofollow identity checks immediately before operations, authoritative manifest, permission separation and staged testing. Source truncation and file replacement can still lose unseen bytes and must be described honestly.

The existing PM2 logs are ~7.7 GB in the owner's last screenshot. Actual daily archives should preserve future incremental content, with history backfill only by separate explicit choice. The owner's request to stop repeated MobaXterm checks remains in force.

**No owner action is required** to run this off-host GitHub CI. Operational F15 and daily 30-day archives remain **NOT INSTALLED**.

References: [F15 source gate #184](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/184), [initial offline policy #249](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/249), [coordination Issue #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4).
