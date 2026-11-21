# F15 supervised incident composition

Owner: CosmicCuddle. Source-only child of PR340 at c460787efb0600ff5ca6617c78c40e522429f7e0.

The new callable requires execute=True and starts only the explicit new command
through the existing supervisor. It composes observed wait status with the existing
private raw bundle/report writer. It never attaches, signals, restarts or installs
an owner service. PM2/tmux installed integration remains outstanding; external
Auth disappearance still cannot supply an authoritative exit cause.

Original console remains in the private supervised run. Each stream is included
only if at most 65536 bytes; larger streams are explicitly omitted from rendered
input before redaction, avoiding secret fragments caused by pre-redaction trimming.
Reports reference originals and preserve clean/nonzero/signal distinctions without
claiming a signal proves an engine defect. Report failure leaves original evidence;
no automatic restart or retry/deployment is introduced.

Tests inject real disposable Python child clean/nonzero/SIGTERM exits, both service
labels, private report permissions, credential redaction and oversized output.
Local Windows syntax checks are not POSIX execution evidence. Record exact Linux
job outcome in the draft PR/review queue. No server or database is launched.

Dependencies: Python standard library and inherited POSIX storage. No SQL, config,
DBC or client changes. Rollback: abandon/revert source child; preserve diagnostics.
No live state changed. This is an increment, not completed operational F15 delivery.
