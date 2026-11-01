# P3 F15: supervised raw console-log storage age audit (read-only)

**Purpose:** report Worldserver and Authserver console backup capacity without claiming that automatic 30-day archive retention also deletes the supervised raw `stdout.raw` / `stderr.raw` streams. The existing F15 retention intentionally keeps raw files and durable supervisor receipts; this is a remaining bounded-disk risk, NOT a regression from this draft. CosmicCuddle controls any future deletion policy.

## Executable code

- `scripts/f15_supervised_storage_audit.py --output-root <private-existing-raw-root> --archive-root <private-existing-archive-root>` reads **only** existing supervised private filesystem metadata and the original `start.json`, `exit.json` and collector `origin.json` receipts. Unlike the existing `private_dir` helper, the new root validation does **not** create missing directories. No service is started or contacted.
- It checks run-id syntax, exact source/archive run identity, strict receipt schema, source paths, Worldserver/Authserver names, archive-origin dev/inode, raw file privacy (0600), regular-file type and single link count. Symlinks/hardlinks or inconsistent identities are refused; unclassified or unfinished runs are retained as unfinished.
- It returns numeric `raw_bytes`, `completed_runs`, `unfinished_runs`, observed subprocess `clean_exit/nonzero_exit/signaled_exit` counts, and raw bytes in **completed runs with an exit older than 30 days** (UTC). It never prints content from logs, character names, private file paths, server tokens or log lines. A subprocess exit code or signal is an observation **not conclusive proof of an AzerothCore engine crash**.
- This CLI has **no deletion function, rotation, archive expiration, process management, PM2/tmux attachment, cron/timer, remote host action or background agent**. Even when it reports old files, `deletions: 0` is guaranteed by source design. The separate F15 archive retention continues unchanged and retains its explicit `--retention-30d` approval gate.
- This does not solve long-term raw-log disk capacity. Actual raw cleanup requires separately approved archival-integrity proofs, owner backup policy, dry-run/purge controls and operator-tested host paths. Do not add deletion by simply changing this audit.

## Synthetic tests and verification levels

`tests/test_f15_supervised_storage_audit.py` runs only temporary Python child processes through the existing F15 supervisor, never Worldserver/Authserver. Cases include separate World/Auth metrics, clean/nonzero observed exits, no log-content disclosure, no source mutation, day29 vs day31 age, unfinished runs, symlink and hardlink refusal, forged capture receipt and no auto-created directories. New source-only CI checks Python syntax and AST for absent destructive/copy/create calls.

Tests are **committed DRAFT**, not claimed HOSTED PASS before exact SHA jobs run. No actual owner host/source log, archival durability or overnight retention tested. If the pinned historical supervisor API changes, this script must be updated and re-tested before owner staging.

## Custom Modifications Register — NAXX-CS01-P3-RAW-STORAGE-AUDIT

- **Owner:** CS01 Maintenance temporarily covers Claude's P3 work while Claude is away. **Status:** independent reviewable DRAFT, OFF (not invoked automatically), NOT merged or deployed.
- **Source baseline:** combined [P1–P4/H1/H2/P4-H DRAFT #273](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/273) HEAD `090e2fb6f89c695f616411561d2fb2fb5f8f46c2`. Neither Claude's #263 P3 collector nor the combined P1/P2/P4 runtime scripts are rewritten.
- **Files:** new `scripts/f15_supervised_storage_audit.py`, `tests/test_f15_supervised_storage_audit.py`, dedicated workflow and this record.
- **Dependencies:** Python 3, existing F15 `f15_process_supervisor.py`, strict `f15_supervised_retention.py` receipt shapes, `f15_operator_collector.Refused`, owner-controlled 0700/0600 private directories and separate Worldserver/Authserver naming.
- **Risks:** report only counts raw supervised **subprocess** output, not PM2/tmux or original installed host logs; raw files are intentionally NOT removed; untrusted files cause refusal; host may use different binary/process launch configuration and paths. Counts of older files are a capacity-warning, never an automatic deletion schedule. No changes to MapUpdate.Threads=8.
- **Tests:** syntax/unit tests require hosted execution; staging World/Auth crash capture and actual owner host remain unverified. **Rollback:** revert only this additive draft and its scheduled invocation (none is created); original F15 sources and retention remain intact.
- **Owner approval required:** before installing the script or any future raw-log deletion/rotation, PM2/tmux reconfiguration, actual service launches, backups/restores or production changes.
