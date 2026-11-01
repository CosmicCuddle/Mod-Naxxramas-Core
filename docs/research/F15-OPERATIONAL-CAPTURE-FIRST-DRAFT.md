# F15 operational capture — first development draft (1 Nov 2026)

**Owner:** CosmicCuddle. **Developer:** CS01 Maintenance. **Status:** DRAFT, unmerged; executable source for review and disposable testing ONLY. No real host, activation, merge or deployment granted.

## Actual operator-facing source

The file scripts/f15_operator_collector.py is a real POSIX command-line program, not the synthetic F15 #249–#261 runner. It accepts explicit, absolute log file paths under one of four labels: Worldserver-out, Worldserver-err, Authserver-out, Authserver-err. It requires the explicit --capture switch. The source files are opened READ-ONLY and must be single-link regular files. No PM2 hook, Auth PTY, tmux launcher, restart service or scheduler is installed.

It starts each previously unseen source at current EOF by default; a separate explicit --include-existing-on-first-poll option allows one-time historical backfill (never rewinds an already established cursor). Thereafter it polls bounded 64-KiB raw-byte segments. It creates private 0700 output folders, SHA-256-named immutable journal records, per-stream UTC-observation-day plain .txt archives, archive digest receipts and a one-process POSIX lock. Changes are fsynced and published atomically. On restart it checks journal continuity, source device/inode and content digests, and refuses source replacement, truncation, suspicious links, foreign output and mutated archives. Original files are never written to or deleted.

**Disposable-only example, using test files—not instructions for CosmicCuddle's host:**

~~~sh
python3 scripts/f15_operator_collector.py --root /tmp/f15-private-disposable \
  --source Worldserver-out=/tmp/f15-fake-world.log \
  --source Authserver-out=/tmp/f15-fake-auth.log \
  --capture --once
~~~

The first poll skips existing bytes; append data to each fake file and poll again to see archives/{label}/{YYYYMMDD}.txt. A long-running process can poll with --capture and --interval, but MUST NOT be installed or operated on real server files before owner-approved deployment review.

## New executable process-exit evidence (development-only)

The separate scripts/f15_process_supervisor.py is an **opt-in real subprocess wrapper**, not a PM2/tmux integration. It requires --execute and an explicit command after --, then starts **one new child program**, captures its stdout/stderr to exclusive private per-run raw files, feeds both streams to the journal collector from the very first byte, and records planned/started/exit evidence on disk with the observed PID and POSIX exit code. It classifies only clean_exit (0), nonzero_exit (positive), or signaled_exit (negative). Neither stderr text nor a nonzero exit is labelled automatically as a proven engine crash.

**Example ONLY using a disposable Python child; DO NOT launch an installed Worldserver/Authserver with this draft:**

~~~sh
python3 scripts/f15_process_supervisor.py \
  --output-root /tmp/f15-fake-child-raw --archive-root /tmp/f15-fake-child-archives \
  --service Worldserver --execute -- python3 -c 'print("synthetic console")'
~~~

Private output and archive roots must be separate and not nested. The wrapper does not attach to a running process, does not restart the child, never issues a kill, and does not install a scheduler. If the supervisor itself is interrupted, the child exit cannot be claimed observed and a review-needed marker is left. It is **not yet production-ready process management**; replacing existing PM2 configuration would require a separate host approval and full lifecycle plan. Tests use only short disposable Python child programs, never real Worldserver/Authserver binaries.

## Crucial incomplete requirements (block rollout)

1. **30-day automatic archive retention is NOT implemented or weakened.** This stage has NO delete/unlink function. A subsequent separately reviewed runtime implementation must use durable, independently justified deletion intent before any allowed archive unlink and must distinguish unexplained missing files from verified deletions. Specifically resolve P3-D and P3-I in original integrated F15 tests. No original/foreign logs may ever be deleted.
2. **Actual exit-code/signal evidence is now implemented ONLY for newly spawned child programs through the explicit supervisor.** There is still NO reliable diagnosis of crashes/stops of existing owner PM2/tmux services, complete Auth PTY, core-dump processing or unattended restart observation. Console output/stderr alone cannot prove a crash.
3. **Automatic log rotation/handoff is NOT implemented.** Inode change or truncate stops capture with explicit refusal, rather than guessing unread history.
4. **Host/data gaps remain:** installed source/PM2/Auth paths, actual log permissions, backup/restore, quota, redaction, crash attribution, same-inode rewrite/rewind, writer races, power-loss durability, filesystem behavior and operator UX. Invalid UTF-8 remains raw and UTC date is observation day, not necessarily event time.

## Development checks and rollback

Run both:

~~~sh
python3 -m unittest discover -s tests -p test_f15_operator_collector.py -v
python3 -m unittest discover -s tests -p test_f15_process_supervisor.py -v
~~~

These tests use disposable TemporaryDirectory sources only. Passing them proves this Python collector's limited capture code, NOT capture of a Worldserver or Authserver, not automatic retention and not a Worldserver binary build.

Rollback: discard the unmerged PR and branch; the owner host was never touched. Before any installation conduct coordinated compatibility checks, original log hash preservation, private backup/restore rehearsal, storage-capacity review and explicit CosmicCuddle approval. Keep experimental features OFF and MapUpdate.Threads=8. All four P1/P2/P3/P4 must be ready together before the owner's gameplay/operational test session.
