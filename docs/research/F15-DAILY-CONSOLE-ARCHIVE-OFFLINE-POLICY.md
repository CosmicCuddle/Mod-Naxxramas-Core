# F15 — Daily console archive: isolated offline policy test (30 October 2026)

**Status: DRAFT / REVIEW ONLY / NOT OPERATIONAL. Never run this as a host collector.**

This branch adds one pure Python model, 38 synthetic regressions, a dedicated GitHub Actions test and this memo. **No AzerothCore, IP, Playerbots, module runtime, SQL, DBC, config, PM2, systemd, tmux, Authserver or Worldserver files are changed.** Do not merge, install, schedule, delete, or apply logger settings without separate owner review and approval.

## Owner-approved functional goal

Each day, preserve the available console output as **separate, timestamped readable text archives** for Worldserver and Authserver. The owner should be able to read the previous day's logs the following day. Prune **only tool-owned, completed console archives strictly older than 30 elapsed 24-hour days**, not the open log, independent `Crash-History.txt`, crash reports, unrelated files or database backups.

Real source discovery (owner's read-only screenshots, 30 October):
- Worldserver is PM2-managed in fork mode and has separate cumulative stdout/stderr PM2 sinks (~7.7 GB combined). They were actively updated; no dated archives in that folder.
- Authserver is tmux → bash → Authserver. Its terminal stdout/stderr go to a PTY, while a different native `Auth.log` is open as FD3. The on-disk file and open FD have the same inode, but a previous-day mtime. Native file and console have **unverified parity**.
- Root filesystem had approximately 84 GB available at check time. Never assume 30 days of unbounded logs will fit. The observed installed paths belong in the **private host runbook**, not copied into public CI test fixtures.
- Existing [F15 source audit #184](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/184) warns of stdout/stderr severity ambiguity, asynchronous tail loss, and possible overwrite on restart.

## What this branch actually tests

1. UTC (timezone-offset aware) safe archive **filename formatting only**, separate stream and session/incarnation tag.
2. A **metadata-only** candidate set for 30-day expiry. Exactly 30 days old stays; 30 days + one second becomes eligible. Open/unowned/symlink/nonregular/multilink/unknown-inode/duplicate-name/malformed-name files are never proposed for pruning. A manifest's close timestamp must match the filename.
3. A **pure byte-range model** for one source inode: startup without an approved historical backfill skips existing multi-GiB bytes; future growth only proposes the new span; inode replacement or truncation emits a visible data-loss warning; no change produces no copy.

## What this branch does NOT do

- **No file I/O at all:** it does not collect, copy, append, rotate, flush, rename, chmod, unlink, delete, schedule or archive any file, including in tests.
- No durable stream checkpoints, atomic daily rollover, line framing, overlap prevention, safe follow of live PM2 writer, Authserver PTY capture, crash signals, report publishing, concurrent archive writers, protected free-space floor, or multi-day time gaps.
- Metadata alone is **not sufficient to delete a real file safely**; production code must anchor operations to trusted directory file descriptors, verify manifest/writer ownership, hold correct locks, reject symlinks/hardlinks, recheck inode identity immediately before deletion, preserve failed archive windows and record cleanup.
- No automatic recovery of legacy PM2 history (first attachment deliberately skips existing bytes until the owner separately chooses a controlled backfill); no guarantee against missed source writes during restart/rotation; no preexisting lost messages recreated.
- No actual Worldserver/Authserver launch or gameplay testing. The existing F15 operational R0 gate remains open.

## Next development gate

After independent review, decide the supported **actual collector** for PM2 stdout/stderr and Authserver native file/PTY without changing Worldserver stdin, then build and test a separate disposable **real file-I/O** archiver against synthetic files with restarts, concurrent appends, permission races, disk quotas and day boundaries. Only after consent may the owner consider a backed-up staged install, daemon integration, and 30-day pruning of newly created owned archives. No command is required from the owner for this offline CI stage.

The combined Warlock/Hunter/A04 native Worldserver CI is a separate test and must not be represented as evidence that F15 operational monitoring works.

Authoritative cross-project coordination: [Issue #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4); owner retention requirement in [module master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6532886167).
