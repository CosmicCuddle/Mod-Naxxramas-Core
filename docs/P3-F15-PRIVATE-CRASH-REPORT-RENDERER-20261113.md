# F15 private detailed crash-report renderer — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated development DRAFT; not installed, not deployed, not connected to PM2/tmux.  
**Parent:** F15 privacy branch at 6b43ed793b13b782091b888f7b26532c207f2d07.

## Purpose

This slice implements only the private report renderer/sink that a later verified
Worldserver PM2 adapter and Authserver tmux adapter may feed.

It does **not** inspect, attach to, launch, signal, stop, restart, or supervise a
real daemon. It does not read owner logs. It does not install anything under
/root.

The intended production destination remains:

    /root/cosmic_core/logs/Crash Logs/

## Behavior

The renderer accepts normalized incident facts and writes:

- one collision-safe timestamped human-readable incident report;
- one append-only Crash-History.txt index entry;
- private directory mode 0700 and report/history mode 0600;
- explicit UNKNOWN for facts not proven;
- bounded recent diagnostic context (32 KiB most-recent bytes);
- narrow secret-value redaction for password/passwd/token/authorization/API key/secret assignments;
- signal number and POSIX signal name when known;
- detailed fields for service, timestamps, classification evidence, PID/PPID,
  supervisor, uptime/start, executable/build/source revision, capture
  completeness/gaps, restart facts, native crash evidence and raw evidence
  reference.

A database error line is deliberately **not** removed merely for containing the
word "database"; useful diagnostics should survive. Only likely secret-value
assignments are redacted.

The renderer does not claim that any nonzero exit is a crash. Without stronger
adapter evidence it classifies only as CLEAN_EXIT, NONZERO_EXIT, SIGNAL_EXIT or
UNKNOWN. A future adapter may supply a more specific classification plus the
evidence supporting it.

## Local disposable evidence

CS01 ran the focused Python test file against the exact source text before the
GitHub commit. Eight tests passed:

1. detailed SIGSEGV report + 0700/0600 permissions + history entry;
2. secret-value redaction while retaining a normal database error;
3. destination collision refusal;
4. insecure 0755 crash directory refusal;
5. incident-id path traversal refusal;
6. ordinary exit code 7 is not guessed to be a signal crash;
7. missing facts render as UNKNOWN;
8. oversized context is bounded to the most recent bytes.

This is local disposable evidence only. No hosted Actions were triggered because
the owner requested Actions storage conservation.

## Next integration slice

The next source work must create a **read-only topology adapter**, not another
launcher:

- Worldserver: consume authentic existing PM2 status/exit/restart/log facts
  without spawning or wrapping another Worldserver.
- Authserver: consume authentic existing tmux/bash/authserver evidence (or the
  currently verified replacement topology) without altering stdin/launch.
- Normalize those facts into this renderer.
- Preserve raw/journal evidence separately and reference it from the report.
- A reporting failure must never kill or restart either daemon.

The actual owner host topology must be verified read-only before staging. No
intentional live crash, restart, service mutation or deployment is authorised by
this development slice.

## Custom Modifications Register — F15-CRASH-REPORT-RENDERER-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Produce detailed private human-readable crash/exit reports plus durable history from normalized evidence. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected files | scripts/f15_crash_report_renderer.py, tests/test_f15_crash_report_renderer.py, this document. |
| Parent/source | 6b43ed793b13b782091b888f7b26532c207f2d07; isolated feature branch. |
| Dependencies | Python 3 POSIX for fcntl/file modes; future PM2/tmux adapter not yet implemented. |
| Config/SQL/DBC/client | None. |
| Risks | Renderer input is only as trustworthy as the future adapter; bounded redaction is not a full secret scanner; Crash-History append and report creation require a trusted private directory. |
| Tests | 8/8 local disposable Python tests PASS before commit; no hosted Actions, native server or live host tests. |
| Live status | DRAFT/uninstalled. No /root files were created by development. |
| Rollback | Abandon isolated branch/PR; parent and live server remain unchanged. |
