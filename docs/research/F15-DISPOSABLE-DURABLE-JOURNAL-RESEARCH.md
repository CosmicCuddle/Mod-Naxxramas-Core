# F15 — disposable crash-safe journal research, **not a production collector**

**Status: DRAFT, offline fixture only, no installation or deployment.**

This is an isolated child of [negative-control PR #251](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/251), which in turn inherits [#250](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/250) and [#249](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/249). Only **one test helper, one test file, this documentation and a dedicated CI workflow** are added. The runtime AzerothCore module, IP, Playerbots, server configuration, database, SQL, DBC and all live log files remain untouched.

## Why the preceding green tests are inadequate

The 10 negative controls in PR #251 demonstrate that, even though a test archiver copies appended bytes, a recorder restart can lose unread lines or write the same lines twice when it crashes at an unlucky moment.

The new GitHub-runner fixture explores a small **durable checkpoint and immutable segment publication protocol** as an alternative to an unsafe in-place append:

1. On initial attachment, write a persisted source inode/offset baseline; **never automatically copy gigabytes of historical PM2 output**.
2. On each poll read a bounded, newly appended byte span. Write it to a uniquely named immutable segment file in a runner-only directory, `fsync`, then atomically publish that segment.
3. Only after publishing the segment, update a checksummed manifest containing the source inode and new committed offset using an atomic rename and directory sync.
4. If a crash occurs after publishing but before manifest commit, on restart verify the contiguous segment and **recover** the checkpoint without appending the same bytes a second time. If a crash occurs after committing, the persisted offset prevents duplication.
5. Detect changes to source inode or shrinkage and **warn** when an unseen tail might be lost. No claim of recovering missing old bytes.
6. Keep Worldserver stdout, Worldserver stderr and Authserver's native test stream independently identified.

The new test injection supports before-segment-publication, after-segment-publication and after-checkpoint failure points. All synthetic inputs/outputs are created within an internal `tempfile.TemporaryDirectory` on GitHub runners. Existing negative controls still prove the old simpler fixture has its known bugs; they are not rewritten or silenced.

## Limitations preventing real server use

**This code is placed under `tests/` and is NOT suitable for execution on the owner's host.** It is not a daemon, not a collector, and contains no public command-line entrypoint, live paths, service controls, SQL or scheduler.

The following gaps remain before a production implementation could be reviewed:

- Atomicity in this fixture assumes a trusted, **single-writer, disposable Linux directory**. It is not hardened against malicious concurrent directory changes, symlink/permission races, fsync/rename portability differences, partial disk failure, physical reboot, or a crash midway through manifest temp-file creation.
- Published segment identity needs stronger full hashes and authenticated manifests; the current demo uses truncated hashes and fixed path conventions, with no locked multi-writer coordination.
- No owner-process stderr/stdout/PTY adapter, native logger feature parity, PM2 rotation cooperation, old-inode tail recovery, periodic midnight sealing, compressed text archives, 30-day actual retention scheduler, disk quota/free-space floor, deduplication across live service incarnations, or durability of stdout messages that the producer never flushed.
- A **source that changes in-place without shrinking**, such as a same-inode rewrite at identical size, is not detected by inode-and-size alone.
- Never use this fixture as a replacement for a production incident monitor; it cannot distinguish an intentional server shutdown from a fatal signal or generate F15 crash diagnoses.

This is a narrowly scoped, reproducible test toward solving one major failure mode, not completion of F15. Preserve the owner's request for **no further serial host commands**, and obtain owner approval plus backups and staged test/rollback plan before any future server integration.

### Acceptance gate

Run **38 policy tests + 29 disposable-file positive tests + 10 known-gap negative controls + 20 new journal recovery tests** in a hosted GitHub Action at the exact branch head. All must complete without skips. The negative controls passing means the *older* fixture's shortcomings are still visible, while the new 20 demonstrate a narrowly improved journal design. No gameplay or live-server test is claimed.
