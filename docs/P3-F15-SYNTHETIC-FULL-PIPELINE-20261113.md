# F15 synthetic full incident pipeline — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; fixture composition only; no live host invocation.  
**Parent:** F15 raw-evidence bundle DRAFT #307 head `c9169e3df988d1bb50ba67c629909f2e13826ed5`.

## Purpose

Compose the F15 source-only layers into one incident path before any host staging:

1. strict read-only evidence probe (#304);
2. topology evidence normalization (#302);
3. restart-safe once-only checkpoint (#303);
4. owned raw evidence bundle + 30-day metadata (#307);
5. detailed private crash report + Crash-History (#301).

The pipeline adds no process-control, restart, signal, rotation, truncation,
database or deployment authority.

## Worldserver fixture path

First PM2 observation establishes a baseline.

A later fixture with an increased PM2 restart counter and an authentic manager
line containing `SIGSEGV` must:

- normalize to `FATAL_SIGNAL_EXIT`;
- carry numeric signal 11 and signal name SIGSEGV;
- allocate incident id `worldserver-00000001`;
- create one raw evidence bundle containing the PM2 jlist snapshot, bounded
  manager excerpt and bounded recent context;
- create one detailed human-readable report under Crash Logs;
- write one Crash-History entry;
- reference the raw evidence bundle from the detailed report;
- advance the checkpoint only after report success;
- create no duplicate report/bundle when the same post-restart state is polled again;\n- if a complete raw bundle exists but report completion failed, reuse that exact first bundle and its stored report input on retry.

## Authserver fixture path

First tmux/process observation establishes a baseline.

A later fixture where the tmux pane still exists but no authserver child exists
must:

- normalize to `PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN`;
- allocate incident id `authserver-00000001`;
- leave exit code and signal UNKNOWN;
- record that tmux remains present;
- create one raw evidence bundle and one detailed report/history entry;
- create no duplicate on the next identical absent-process poll.

This deliberately proves the evidence boundary: an external tmux observer may
know that Authserver disappeared without knowing the kernel wait status. F15
must preserve that distinction.

## Ownership / directory ordering

The composition explicitly establishes the private Crash Logs root before
writing the Raw Evidence child directory. This fixes an interface-order issue
found during composition: raw evidence is created before the final report, so
the parent directory cannot be assumed to exist incidentally.

## Retention relationship

The report/history, raw evidence bundle and pre-overwrite archived server logs
all carry the owner-selected 30-day retention policy in their respective owned
formats. Active original logs are never retention targets.

The synthetic composition does not run retention cleanup itself; retention is
tested/reviewed independently so incident creation cannot silently gain delete
authority.

## Test intent

`tests/test_f15_full_pipeline.py` uses fake PM2/tmux/process sources only.

It covers:
- World PM2 SIGSEGV complete incident path;
- one raw evidence bundle + one report + one history entry;
- raw evidence reference in report;
- no duplicate World emission;
- Auth disappearance with tmux alive and cause UNKNOWN;
- no duplicate Auth emission;
- independent World/Auth incident sequences;\n- report-sink failure after bundle creation leaves the checkpoint unadvanced, then a later retry reuses the first bundle/context/timestamp and completes exactly one report/history entry.

No hosted Actions are requested yet. A single focused milestone run may be
considered only after source review because the owner is conserving Actions
storage.

## Still not proven

- actual owner PM2 process name;
- actual owner tmux session name/current Auth launcher topology;
- exact live stdout/stderr/native log locations;
- permissions/user under which the collector will run;
- pre-overwrite invocation point;
- Worldserver/Authserver real crash behavior;
- disk usage under 30-day retention;
- native coredump/gdb availability;
- installation/scheduling/reboot behavior.

All remain staging gates.

## Custom Modifications Register — F15-SYNTHETIC-FULL-PIPELINE-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Compose read-only evidence, normalization, once-only checkpointing, raw evidence ownership and detailed crash reporting under synthetic fixtures. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_incident_pipeline.py`, `tests/test_f15_full_pipeline.py`, inherited `scripts/f15_raw_evidence_bundle.py` and `scripts/f15_crash_report_renderer.py` retry hardening, this note. |
| Parent | #307 head `c9169e3df988d1bb50ba67c629909f2e13826ed5`. |
| Dependencies | F15 #301–#304, #307 source layers. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Fixture composition is not proof of live topology; pipeline still requires verified installation/scheduling/pre-overwrite hook. |
| Tests | Synthetic fixture tests authored; no live host/Actions. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; no production state changed. |
