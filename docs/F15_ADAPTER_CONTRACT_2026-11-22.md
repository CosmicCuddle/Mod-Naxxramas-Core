# F15 future service-manager adapter contract

Owner: CosmicCuddle. Source only; no installation is authorized by this document.
The existing PM2 Worldserver and tmux Authserver topology is not changed here.

## Opt-in execution and stop ownership

Use supervise with --execute and explicit argv. --launcher-mode forwards TERM/INT
only to the direct owned child; never external PIDs or process groups. Commands
must remain foreground and must not daemonize or replace themselves with a shell
that hides the actual server. stdin is closed; console interaction is not supported.

--stop-timeout is optional, finite 0.1..300 seconds, requires launcher mode, and
starts when the first stop request is forwarded. Repeated requests do not reset
it. On expiry, poll again: a reaped child is not killed. An unreaped owned child
receives SIGKILL at most once; the outcome and report explicitly mark escalation.
The poll cadence and capture I/O can delay forwarding/escalation. This is not a
hard real-time deadline. Descendants are not controlled. No timeout means no forced
escalation. Manager deadlines must leave room for stop grace, capture and reporting;
no host-specific values are approved here.

## Status and evidence

Launcher status is child code or 128+signal, even after expected post-exit report
failure. Diagnostic mode returns2 for failed diagnostics. A clean child can return0
with a warning on stderr; diagnostic health must therefore be monitored separately.
Exit-receipt failure attempts the independent bundle/report sink and marks evidence
as recovered from memory. Simultaneous storage/wrapper failure can lose evidence.
Completed verified bundles support recover without relaunch. Pending/incomplete or
altered evidence requires inspection; never overwrite it to make retries succeed.

## Future installation prerequisites

Verify exact foreground binaries, actual PM2/tmux launch and stop behavior, manager
restart policy, executable/build fingerprints, private paths, free space and log
ownership. Preserve existing server arguments/environment and custom features.
PM2 restart policy must not turn a clean shutdown into a restart loop. tmux session
presence alone does not prove Authserver health. Test actual server shutdown and
restart in an owner-approved disposable staging environment before production.

The designated Crash Logs and inherited 30-day owned-evidence retention stay in
force. Never use retention to delete active/foreign logs. Prepare verified backup
of exact manager/launcher/config files, an owner-reviewed change plan and rollback.
Production installation requires CosmicCuddle approval. Rollback disables new
hooks first, restores exact prior launch configuration and preserves diagnostic
evidence. No config/SQL/DBC/client or live service change occurred in this work.
