# F15 post-launch lifecycle receipt failure

For CosmicCuddle's proposed PM2 Worldserver / tmux Authserver diagnostics chain,
stacked on PR351. No live services, owner logs, configuration or defaults change.

`Popen` succeeds before `running.json` is published. Previously, a storage error
at that point escaped the wrapper before its wait/capture loop, leaving its
direct child without wrapper observation. Catch expected receipt storage errors
and continue observing the same child. Do not relaunch, signal or kill a child
because of diagnostic storage failure. Existing explicitly enabled launcher
stop forwarding is unchanged.

Continue console collection/final drain independently. If console capture has
no separate error, record `RunningReceiptPersistenceFailure` in the existing
fail-closed exit schema. A console error retains its own type when both fail.
The actual observed child exit remains authoritative; launcher mode propagates
it. Diagnostic-tool mode returns failure even for a clean child with this gap.
The composed report includes the gap and health remains
`REPORT_COMPLETE_WITH_GAPS`. No claim of complete lifecycle capture is made.

Keep incomplete `running.json.pending` evidence untouched. Existing retention
refuses these fail-closed runs; raw source files remain. If the exit receipt also
fails, the existing independent in-memory wait/report recovery path still applies.
No guarantee is made for arbitrary interruption, process death, total storage
failure or recovery of a child whose wait was never observed.

Executable Linux fault-injection tests use finite Python children and temporary
private roots. They demonstrate the exact PR351 failure, continued child wait,
console/archive preservation, partial-receipt retention, composed report and
health gaps, simultaneous sink errors, and launcher/diagnostic CLI status. No
engine or real manager is launched by these new tests. The focused full F15
Linux suite provides the runtime result; Windows syntax checks alone do not.

No migration or new receipt schema is introduced. Rollback reverts this source
child and preserves all raw/partial/exit evidence; older code again abandons
observation on this error. Owner approval is required for any host installation.
