# F15 operational capture — first development draft (1 Nov 2026)

**Owner:** CosmicCuddle. **Developer:** CS01 Maintenance. **Status:** DRAFT, unmerged; executable source for review and disposable testing ONLY. No real host, activation, merge or deployment granted.

## Actual operator-facing source

The file scripts/f15_operator_collector.py is a real POSIX command-line program, not the synthetic F15 #249–#261 runner. It accepts explicit, absolute log file paths under one of four labels: Worldserver-out, Worldserver-err, Authserver-out, Authserver-err. It requires the explicit --capture switch. The source files are opened READ-ONLY and must be single-link regular files. No PM2 hook, Auth PTY, tmux launcher, restart service or scheduler is installed.

It starts each previously unseen source at current EOF by default; a separate explicit --include-existing-on-first-poll option allows one-time historical backfill (never rewinds an already established cursor). Thereafter it polls bounded 64-KiB raw-byte segments. It creates private 0700 output folders, SHA-256-named immutable journal records, per-stream UTC-observation-day plain .txt archives, archive digest receipts and a one-process POSIX lock. Changes are fsynced and published atomically. On restart it checks journal continuity, source device/inode and content digests, and refuses source replacement, truncation, suspicious links, foreign output and mutated archives. Original source files are never written to or deleted. **Experimental 30-day deletion of collector-owned archived data** is now implemented behind a separate, disabled-by-default --retention-30d switch; see below.

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

**Repeated child launch fix:** each invocation now creates a distinct archival collector root at `<archive-root>/runs/<run-id>`; the per-run root is recorded in the run's private `start.json` and observed `exit.json`. This avoids falsely reusing the earlier child's log inode/origin cursor on a second Worldserver/Authserver launch. Prior per-run raw output and archive files remain untouched and independently reconstructable. The operator must plan retention and backups for *each per-run collector root*; this draft does not automatically enumerate child run roots, schedule their expiry, or claim that PM2 launches are supervised. The added disposable regression launches two successive fake Worldserver children and checks both complete, distinct archives.

## Crucial incomplete requirements (block rollout)

1. **30-day archive + raw-journal expiry is IMPLEMENTED IN DEVELOPMENT, but not production approved.** Explicit --retention-30d triggers validation of chronological, contiguous journal days and matching original archive and receipt bytes, then durable intent publication before removing a collector-owned day archive, receipt and raw journal prefix. It changes the replay origin cursor only after these removals, saves an audit record, and refuses all subsequent capture/retention if an intent is interrupted. Unexpected missing archived bytes FAIL CLOSED, never 'expired' by age. Exact 30-day cutoff is end of UTC observation day PLUS 30x24 hours. No symlink/hardlink/nonregular file is willingly removed. **Retention is OFF by default**, and no original log is targeted for deletion. IMPORTANT: not yet proven safe against all same-UID workspace writers, filesystem rename/unlink races, operator interference, arbitrary power loss or long-running resource exhaustion; P3-D/P3-I threat review and native operations testing are still required before enabling on any owner host.
2. **Actual exit-code/signal evidence is now implemented ONLY for newly spawned child programs through the explicit supervisor.** There is still NO reliable diagnosis of crashes/stops of existing owner PM2/tmux services, complete Auth PTY, core-dump processing or unattended restart observation. Console output/stderr alone cannot prove a crash.
3. **Automatic log rotation/handoff is NOT implemented.** Inode change or truncate stops capture with explicit refusal, rather than guessing unread history.
4. **Host/data gaps remain:** installed source/PM2/Auth paths, actual log permissions, backup/restore, quota, redaction, crash attribution, same-inode rewrite/rewind, writer races, power-loss durability, filesystem behavior and operator UX. Invalid UTF-8 remains raw and UTC date is observation day, not necessarily event time.

## Development checks and rollback

Run all three suites:

~~~sh
python3 -m unittest discover -s tests -p test_f15_operator_collector.py -v
python3 -m unittest discover -s tests -p test_f15_archive_retention.py -v
python3 -m unittest discover -s tests -p test_f15_process_supervisor.py -v
~~~

These tests use disposable TemporaryDirectory sources only. Passing them proves this Python collector's limited capture code, NOT capture of a Worldserver or Authserver, not automatic retention and not a Worldserver binary build.

Rollback: discard the unmerged PR and branch; the owner host was never touched. Before any installation conduct coordinated compatibility checks, original log hash preservation, private backup/restore rehearsal, storage-capacity review and explicit CosmicCuddle approval. Keep experimental features OFF and MapUpdate.Threads=8. All four P1/P2/P3/P4 must be ready together before the owner's gameplay/operational test session.

## Retention failure/review contract

Automatic expiry is deliberately opt-in. A private owner-only retention-intent.json is written and fsynced BEFORE any archive/receipt/journal unlink. If a power interruption or simulated exception occurs before the full operation completes, the intent remains and future collector polls fail closed rather than claim an expired archive. An operator must investigate; this draft intentionally has NO automatic intent-clear command. A separate retained metadata receipt under retention-history tracks a completed removal. Old raw journal segments are removed with the expired archive rather than silently retained forever. A later active-day journal remains contiguous after updating origin.start. The code intentionally stops if original archive/receipt is absent or differs from reconstructed journal, even after it becomes old. These guarantees are conditional on the private 0700 workspace and current test assumptions; see unresolved same-UID race/power-loss limits above. This is NOT an approved destructive service setting.

## Existing PM2 read-only observer — new development-only code (1 November 2026)

`scripts/f15_pm2_observer.py` is an **actual opt-in source implementation** for the PM2-hosted part of the owner's request. Unlike the new-child supervisor, it does **not** spawn, stop, kill, restart, signal or reconfigure Worldserver/Authserver. An explicit `--observe` lets it execute PM2's read-only `jlist` query for **one exact process name**, select the named service's out/err regular log paths, and use the existing private collector to capture bytes written *after* first admission. Explicit `--include-existing-on-first-poll` allows backfill, and `--retention-30d` independently opts into experimental owned-archive expiry. No default log deletion and no original PM2 source deletion.

It persists **only selected fields** (service, PM2 name, PID, status, two source paths) in a private observer state, plus an event when the selected PID/status/path changes. A PID change is deliberately classified `unclassified_process_change`; PM2 JSON alone does not prove engine crash, exit code/signal or stack trace. Raw PM2 JSON (which may contain environment values or secrets) is **never written to the archive**. Duplicate app names, ambiguous fields, missing paths, untrusted links, duplicate inodes, modified records, unknown prior root and source replacement fail closed. The same private root must not be reused for different app identities.

**Disposable demonstration only (not permission to attach to CosmicCuddle's running server):**

~~~sh
python3 scripts/f15_pm2_observer.py \
  --root /tmp/f15-disposable-pm2-private --pm2-name fake-world \
  --service Worldserver --observe --once
~~~

This only works when a deliberately controlled fake PM2 listing supplies **existing regular out and err files**. It cannot create console log files that PM2/tmux never saved. The CLI does not install an unattended service/scheduler; real PM2 names, source paths, permissions, Authserver hosting mode and process control are still unknown.

**Critical remaining gap:** PM2 log *rotation*, truncate or inode swap still deliberately refuses capture until reviewed. This is a safe failure, **not seamless automatic rotation**; the old rotated inode's unread tail could be unavailable by the next poll. Native/tmux Authserver (when not PM2-managed), independent process exit attribution, disk quota/redaction, full restart/rotation integration and safe unattended retention remain blocked for production. Do not enable on the owner host until those are resolved, an actual inventory and backup/restore drill succeed, and CosmicCuddle approves.

New disposable suite (uses fake JSON and temporary log files only):

~~~sh
python3 -m unittest discover -s tests -p test_f15_pm2_observer.py -v
~~~

This adds tests for exact app-name matching, default-OFF gating, private redacted state, append-only capture, PID changes without false crash claims, symlink/inode rotation refusal and invalid log paths. It does not exercise a real PM2 instance or actual Worldserver/Authserver; the exact-head hosted CI result must be checked separately.
