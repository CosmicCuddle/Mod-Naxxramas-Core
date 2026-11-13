# F15 PM2/tmux topology evidence normalizer — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT, pure source/tests only, not installed or connected to live processes.  
**Parent:** F15 private crash renderer DRAFT #301 at 45a22cfd0583a48e325808faa91a21aa0d47e1c4.

## Purpose

This slice normalizes already-supplied process-manager evidence into incident facts
that the private crash renderer can later consume.

It deliberately does **not** execute pm2, tmux, ps, read /proc, tail live logs,
attach to a process, launch a daemon, signal a daemon, restart a daemon or touch
/root. A later separately reviewed collector may obtain those inputs read-only.

## Worldserver / PM2 model

Input is two PM2 jlist-compatible snapshots plus an optional bounded PM2 manager
text excerpt.

A reportable event exists when the named process's restart_time increases.
The normalizer:

- refuses a restart counter moving backwards;
- requires exactly one matching named PM2 process;
- preserves PID/replacement PID, status, restart counters, uptime fields and
  PM2 exit_code when available;
- optionally parses the standard manager line shape:
  App [name:id] exited with code [N] via signal [SIGNAL];
- labels SIGSEGV/SIGABRT/SIGBUS/SIGFPE/SIGILL as FATAL_SIGNAL_EXIT only when
  that signal evidence is actually supplied;
- labels a nonzero exit as NONZERO_EXIT;
- labels other supplied signals as SIGNAL_EXIT_CAUSE_UNPROVEN;
- otherwise records PM2_RESTART_OBSERVED rather than guessing a crash.

## Authserver / tmux model

The current recorded topology is tmux -> bash -> authserver. tmux does not by
itself provide wait-status evidence to an external observer.

The pure model therefore compares process identity using PID + process start
ticks. If the identity disappears or changes between samples, it emits:

    PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN

It records whether the tmux session was still observed and whether a replacement
Authserver identity appeared. It intentionally does not invent exit code or
signal facts.

This means the first operational version can still create a useful detailed
incident report if Authserver disappears, while clearly saying that the exact
kernel exit cause is UNKNOWN. Stronger Auth exit/signal provenance would require
a separately approved launcher/wrapper or another authoritative manager source.

## Local disposable evidence

CS01 ran the exact pure source before commit:

- no PM2 restart => no incident;
- PM2 restart + SIGSEGV manager evidence => FATAL_SIGNAL_EXIT;
- PM2 restart + exit 7 => NONZERO_EXIT;
- PM2 restart without stronger evidence => PM2_RESTART_OBSERVED;
- wrong PM2 name refused;
- backward restart counter refused;
- unchanged Auth PID/start identity => no incident;
- vanished Auth process => cause UNKNOWN;
- replacement Auth process => cause UNKNOWN.

Result: **9/9 local tests PASS**. No hosted Actions were used.

## Next slice

The next implementation must be a narrowly read-only collector that obtains the
real current facts and feeds this normalizer + #301 renderer:

1. Worldserver: exact PM2 process name, jlist/status source, PM2 manager-log
   provenance and current stdout/stderr log origins.
2. Authserver: exact tmux session/process identity, safe process discovery,
   existing native Auth.log/console provenance and whether tmux remains after an
   Authserver exit.
3. Persistent previous-snapshot/checkpoint state so restarts are detected once,
   not repeatedly.
4. Bounded recent log context and source/build fingerprints.
5. No report/collector failure may stop or restart either daemon.

Actual host inspection/staging requires separate owner approval. No intentional
live crash or service mutation is authorised here.

## Custom Modifications Register — F15-TOPOLOGY-EVIDENCE-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Normalize PM2 restart/exit evidence and externally observed Auth process identity changes without guessing unknown causes. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | scripts/f15_topology_evidence.py, tests/test_f15_topology_evidence.py, this document. |
| Parent | #301 head 45a22cfd0583a48e325808faa91a21aa0d47e1c4. |
| Dependencies | PM2 jlist-compatible values when later supplied; Auth PID/start identity when later supplied. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Polling can miss intermediate states; PM2 manager text may be incomplete; external tmux observation cannot recover Auth wait status; real source names/paths still unverified. |
| Tests | 9/9 local disposable Python tests PASS; no hosted Actions/live processes. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; #301 and live server remain untouched. |
