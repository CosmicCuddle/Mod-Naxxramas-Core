# Independent diagnostic-health receipts

Owner: CosmicCuddle. Source-only child of PR3495a70282913906adf6dfd928d8be7c63845a0b404.

The child's exit status answers a different question from diagnostic health.
After observing exit, the composer attempts an immutable private started receipt,
then report-complete or report-failed receipt. Atomic no-replace publication uses
the existing private renderer sink. A failed health write never replaces child
status; diagnostic CLI mode returns2, launcher mode preserves the child code and
prints a generic warning. No private exception/command/path is serialized.

`python3 scripts/f15_supervised_incident.py health --run-root PRIVATE_RUN`
only reads existing receipts. It returns0 for consistent complete reporting with
complete capture/exit receipt;2 for missing/partial/conflicting/failed/gapped state
or refused input. It never launches, creates missing roots, overwrites receipts,
checks a live PID or claims process liveness. Private regular single-link receipt
reads are descriptor-bound and capped at4096 bytes, refusing symlinks/FIFOs.

These immutable receipts describe the original reporting attempt. A later recover
can finish a report without rewriting its original failed-health history; inspect
recovery outcome/report separately. There is no automatic retry/activation, and
missing receipts under storage failure remain UNKNOWN. Total sink failure cannot
promise durable evidence. Owner monitoring integration remains a future proposal.

Fault tests use finite Python children and private temp files: report failure,
failed health sink, unreadable console preserving original bytes, invalid UTF8,
partial/conflicting receipts, FIFO/oversize refusal and read-only CLI. Full Linux
suite and real PM2/tmux fixtures run together; exact results in PR/review queue.
No production logs/services/DB/config/SQL/DBC/client change. Rollback reverts source
child while preserving existing diagnostic evidence and immutable receipts.
