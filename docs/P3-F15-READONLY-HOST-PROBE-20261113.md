# F15 strict read-only host probe — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; source/tests only; no live host invocation performed.  
**Parent:** F15 incident checkpoint DRAFT #303 head `137db146b56dc66202ecef62ba78af741a9bcb0d`.

## Purpose

This slice defines the first host-facing evidence probe, but keeps it strictly
read-only and dependency-injectable for testing.

It exposes no start, stop, restart, kill, signal, attach, write-config or service
management operation.

## Allowed evidence reads

### Worldserver / PM2
The probe may execute only:

`pm2 jlist`

It requires exactly one named process and extracts:
PID, PM2 id, status, restart count, unstable restart count, uptime/start values,
exit code and PM2 stdout/stderr log paths.

### Authserver / tmux
The probe may execute only:

- `tmux display-message -p -t <session> "#{pane_pid}"`
- `ps -eo pid=,ppid=,comm=,args=`

It then walks only the returned process tree and requires exactly one
`authserver` descendant. The process start identity is read from the standard
read-only `/proc/<pid>/stat` start-time field.

A live tmux pane with zero authserver descendants returns an explicit absent Auth identity so disappearance can be reported; multiple descendants remain ambiguous and fail closed.

### Log context
A bounded helper can read only the last <=32 KiB of an explicitly selected
regular file with no symlink following. This is intended for PM2 stdout/stderr
or an explicitly verified Auth native log in a later composition layer.

## Local disposable evidence

The exact source was tested using a fake command runner and temporary files:

1. exact `pm2 jlist` command only;
2. expected PM2 fields extracted;
3. duplicate PM2 process refused;
4. tmux pane -> bash -> authserver tree resolved;
5. /proc start ticks parsed;
6. multiple authserver descendants refused;
7. tmux failure refused with no fallback mutation;
8. bounded regular-file tail works and symlink tail is refused;
9. invalid process names execute no commands.

Focused suite result: **9/9 PASS** (the combined assertions above are grouped
into nine unittest cases). No hosted Actions were used.

## Security boundary

The default runner uses an argv list, never a shell. Environment is reduced to
PATH. stdin is DEVNULL. Output is bounded. All process/service names are
validated before command execution.

This does **not** prove that the owner's current PM2 process name, tmux session
name, log paths, user/permissions or /proc topology match the recorded
historical facts. Those must be verified read-only before installation.

## Next integration slice

Compose:

`read-only probe -> topology normalizer (#302) -> incident checkpoint (#303) -> private renderer (#301)`

with fake fixtures first. After that source-only composition is proven, live
read-only staging on the owner host requires explicit approval. No intentional
crash/restart is needed for initial staging; baseline observation and synthetic
fixture replay can be used first.

## Custom Modifications Register — F15-READONLY-HOST-PROBE-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Obtain PM2/tmux/process/log evidence through a minimal strict read-only interface. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_readonly_host_probe.py`, `tests/test_f15_readonly_host_probe.py`, this note. |
| Parent | #303 head `137db146b56dc66202ecef62ba78af741a9bcb0d`. |
| Dependencies | PM2 CLI, tmux, ps and Linux /proc only when later run on host. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Actual process/session names and log origins remain unverified; polling can miss transient states; auth external observation still cannot recover kernel wait status. |
| Tests | 8/8 local disposable unittest cases PASS; no live host/Actions. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; no live-state change exists. |
