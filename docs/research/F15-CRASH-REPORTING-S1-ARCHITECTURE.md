# F15 S1 — external crash reporting: evidence and architecture contract

**Status:** DRAFT / S1 peer-review corrections, research only; no executable monitor,
changes to host services, server, SQL, DBC, configuration, or restart logic.
This revision incorporates CS01/CS03 source reviews and CS02's disposable GDB/launcher
probe (review of `f68fa1f`). The owner's actual launcher and fresh final-head
independent review remain pending.

- [Master F15 requirements](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6366816579)
- [F15 coordination and three-developer assignments](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6366834172)
- **Source pinned for public-startup study:** AzerothCore
  `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`.
- **Installation / supervisor / effective GDB state: UNKNOWN.** Do not choose
  systemd, PM2, tmux, screen, shell loop or debug flags based on this document.
- Never deliberately crash the actual Worldserver/Authserver for acceptance.

## 1. What the pinned public source actually establishes

`apps/startup-scripts/README.md` documents `run-engine`,
`simple-restarter`, `starter` and `service-manager.sh` with optional
GDB, configurable LOGS_PATH / CRASHES_PATH, and alternative PM2/systemd and
tmux/screen setups. This does NOT establish that the owner is running them.

In `src/simple-restarter` lines 50–94, the wrapper:
1. launches `starter` and records its **wrapper exit status**;
2. notes runtime and total restart count;
3. stops after six rapid runs (each under 10 seconds);
4. exits after a clean (0) status;
5. otherwise sleeps three seconds before restarting.

Preserve this loop guard, normal-exit semantics and any real installed
equivalent. Pinned `World.h` defines **0 normal stop, 1 error, 2 intended
restart**. Code 2 is NOT a crash when the planned restart is independently
confirmed; do not classify *every* nonzero wrapper status as a crash. A later
crash during a planned shutdown is still possible and must not be suppressed.
**Verified disposable-probe hazard (CS02, no owner server):** the pinned
`starter` script with `GDB_ENABLED=1` and an empty GDB-file input returned **0
for every tested child result** (exit 0, 1, 2, SIGABRT, SIGSEGV). Its trailing
`rm -f "$GDB_TEMP_FILE"` masks the GDB status. The generated GDB `--batch`
script returned **1** for ordinary exits 0/1/2 (because backtrace commands
find no stack) and **0** for SIGABRT/SIGSEGV (after capturing their signal).
The GDB return code is neither the inferior's exit code nor a safe crash
classifier. The pinned `simple-restarter` reads the masked `starter` status:
under this tested GDB setup it would interpret every case as clean and stop
instead of distinguishing a crash, error, or planned restart. With
`GDB_ENABLED=0`, the disposable `starter` returned the original child codes
0, 1, 2, 134 and 139 respectively; that is NOT evidence about the owner's
unknown launcher or options. **No restart/monitor implementation can rely on
this wrapper status for crash counting without an independently validated
actual-child event source and preservation of restart behaviour.**
The six-crash live loop was not exercised. This is design evidence only;
no assumed fix or installed GDB/launcher choice is authorised.

`src/starter` (around lines 216–294) can run GDB and produce
`gdb-<timestamp>.txt` in the configured crashes path; this is an optional
technical attachment, **not** the complete distinct-event reporting feature.

`src/run-engine` chooses the wrapper vs one-shot starter and sets default
crash/log directories. That path is unrelated to the owner's required path
until explicitly configured.

## 2. First actual-host discovery — strictly read-only

Before deciding any implementation or installing a service, establish:
- real launch command and supervisor **for each** Worldserver and Authserver;
- who owns the supervisor and server binaries, and effective restart policy;
- wrapper vs real child PID and stable invocation/boot identity;
- clean admin stop/restart markers (zero and nonzero policies vary);
- whether stdout/stderr/server errors persist before the crash, and where;
- whether GDB, core dumps, debugging symbols, journal messages and OOM
  evidence are present; symbolized stacks require compatible exact builds;
- current file permissions and user/group ownership **without changing
  `/root` ACL or making game processes root**.

A future authorised review can ask for redacted startup/service details,
but not passwords, tokens, private logs or a live crash demonstration.
If the actual launcher is not an AzerothCore startup script, replace the
assumptions below with its verified exit-event interface.

## 3. Event and classification model

An **incident** is the verified unexpected end of one actual server process
invocation. A **notice** is evidence from journal/coredump/GDB/launcher/etc.
Several notices for the same death must create **one** incident, not several.

Provisional canonical identity (subject to actual supervisor verification):
`host + boot_id + service_instance + supervisor_invocation_id + actual_PID +
verified_process_start_identity`. The **exit observation time is evidence,
NOT an identity/dedup discriminator**: GDB, journal and wrappers can report
the same event at different times. Construct a stable name-derived incident ID
(e.g. UUIDv5) **only from a verified canonical key**; never issue a new random
UUID each time a collector or reporter restarts. If identity cannot be
verified, retain the notice as uncorrelated/pending with explicit uncertainty,
not an invented unique crash. Do not dedup distinct invocations solely by
PID, timestamp or service name.

Conservative classifications:

| Evidence | Action | Cause label |
| --- | --- | --- |
| Verified death by SIGSEGV / SIGABRT | Record once | Observed signal, not assumed underlying bug |
| Verified exit 1 / unexpected actual child nonzero termination | Record once if not planned | Observed code; underlying cause may remain unknown |
| Confirmed intended Worldserver exit 2 / planned restart | No crash record | Preserve administrative restart, but do not ignore a later proven fatal teardown |
| SIGINT/SIGTERM graceful normal stop with corroboration | No crash record | Preserve normal shutdown |
| Verified kernel OOM-kill referring to that PID/invocation | Record once | OOM evidence; do not guess which module allocated memory |
| GDB stack only with uncertain final process exit | Correlate; do not create unproven duplicate | Diagnostic trace, confidence stated |
| Normal planned stop or intentional administrative restart | No crash record | Preserves established planned-stop semantics |
| Error burst with process still running | Separate rate-limited warning only | Does **not** increment crash count |
| Hang without verified death | Optional separate warning, after review | Not a crash |
| Freeze detector logs `forcing a crash`, then an actual fatal termination is verified | Record once | On pinned non-Windows core the `ABORT` macro invokes `Acore::Abort`, **sleeps about 10 seconds**, then `Crash()` performs a null-pointer store, ordinarily SIGSEGV (not assumed SIGABRT). Correlate the freeze log with the later verified death using one process-invocation identity; do not create two incidents because the timestamps differ. The original hang cause may remain unknown |
| `auth.uptime.EndTime IS NULL` without process/supervisor corroboration | Retain unfinished-session evidence; do not automatically count | Process may still be running or may have crashed during teardown |
| Shutdown/restart status unavailable | Fail closed on cause; preserve evidence | Unknown; report only when unexpected death verified |

**Mandatory wording where cause unproven:**
`Crash cause: Unknown — further investigation required`.

Record as distinct fields: `Observed termination`, `Confirmed cause
(if known)`, `Possible explanations (not proven)`, and `Missing evidence`.
Never label Playerbots, IP or Naxx as causal from an incidental stack frame.

## 4. Crash report contract

Destination **exactly**:
`/root/cosmic_core/logs/Crash Logs/`
including the space and capital letters. Only create on approved installation.

Each unique finalized crash produces one `.txt` file such as
`worldserver-crash-start-2026-10-23T22-10-11Z-<stable-incident-id>.txt`
or `authserver-crash-...`, with `O_CREAT|O_EXCL`-equivalent
collision protection (an example, not implemented). The filename's human-
readable UTC time is the **verified canonical process START time** from
the incident identity, not the independently observed CRASH time. The actual
observed termination time(s), including their UTC offsets and sources, belong
in the report body. Two collectors of one invocation MUST compute exactly
the same final filename regardless of when each noticed its death. Publish
under the same cross-process incident lock, refuse an existing finalized
incident ID (including a matching `-<stable-incident-id>.txt` filename),
and only then use atomic no-clobber publication. Never convert an unknown
canonical start timestamp into an invented incident identity.
UTF-8 text and predictable CRLF-compatible formatting for Notepad.

Proposed fields, each marked available/unknown:
- `Report schema version` and stable incident ID;
- local time, numeric timezone offset, configured timezone identifier
  if verified, and UTC timestamp;
- Worldserver/Authserver, actual server PID, optional wrapper PID and
  launch/invocation identity;
- exact executable path and captured Git build/revision if reliably available;
- observed signal/exit status, supervisor classification, explicit root-cause
  confidence, error messages (bounded/redacted), thread/backtrace when present;
- journal/OOM/coredump references and hashes where useful, not unauthorised
  copying of sensitive unrestricted dumps;
- crash capture/reporter failure status, plus observed automatic restart result.

**Keep finalized incident files immutable.** If confirmed restart evidence
arrives later, publish a small, separately no-clobber-protected sidecar under
the **same incident ID** and atomically rebuild `Crash-History.txt` from both.
Never rewrite or append to the original incident file; never count a restart
sidecar as a new crash. If no restart outcome is observed, say `Not verified`.
A sidecar itself must have deterministic identity, bounded content and a
validated finalization marker so reader recovery never counts partial data.

Security: owner-only directory, safe `umask 077`/mode, no secrets or unbounded
`journalctl`/environment dumps; allowlisted log lines with credential
redaction, strict byte/time limits and no symbolic-link traversal (`O_NOFOLLOW`
where supported). Refuse symlinked or group/world-writable parent directories.
`/root` is commonly root-only: investigate whether a constrained, independent
privileged broker is necessary for the **owner-requested output path**, but
do not grant game processes root or broad directory access to make logging work.
Treat all evidence and arguments as untrusted; never interpolate raw log text
into shell commands. Log publication failure separately without affecting
Worldserver/Authserver or their restart system.

## 5. Durable incident storage and Crash-History.txt

**Individual completed files are authoritative**; `Crash-History.txt`
is a derived index, rebuilt by scanning and validating finalized individual
reports. Its entries include incident ID, local+UTC time, process, observed
termination type, report filename and restart status; totals count **unique
incident IDs**, not report notifications or error bursts.

Writer design to review independently:
1. Validate the event identity; dedup a repeated notification.
2. Allocate a collision-safe exclusive temporary destination **on the same
   local filesystem**; write schema/metadata/evidence, bounded and redacted.
3. `fsync` the completed temp report and publish with **actual atomic
   no-replace semantics**: `link(temp, final)` followed by temp cleanup, or
   verified filesystem-supported `renameat2(RENAME_NOREPLACE)`; `EEXIST`
   means an already-published incident, **not overwrite**. Then `fsync` the
   containing directory; recover temp files safely. Plain `rename()` or
   Python `os.replace()` is **NOT** no-clobber and can destroy older reports.
4. Under a dedicated cross-process `flock`/`fcntl` lock (not mere lockfile
   existence), enumerate finalized report
   filenames; validate and de-duplicate incident IDs; render the *entire*
   index into a new temporary file, flush/fsync, then atomic **replace** of
   the derived index and directory sync. This intentional replace differs from
   immutable report publication. Never truncate the only index copy before
   rebuilding, or count an incomplete sidecar.
5. On a crash/kill during index update, the next run can reconstruct from
   reports. Failed disk writes should be logged to a separate available
   channel without harming restart behavior.

**Concurrency:** two servers may die simultaneously. Never rely on a
single-process Python threading lock or a per-service append for index
integrity. Locking and uniqueness must work across processes. Reject
untrusted/partial/corrupt report files from the total. Preserve old
reports indefinitely and alert on disk use; never auto-delete.

**Idempotence corner case:** if process death is proven but evidence capture
is partially unavailable, write a minimal report using the same incident
ID, rather than retrying with a fresh ID. A monitor restart must not count
the same death twice. A later backtrace, if needed, must be an immutable,
correlated, no-clobber sidecar rather than a mutation of a finished report.
Sort history by **UTC** rather than local wall-clock time: UK time on
25 October 2026 repeats the 01:00–02:00 hour when BST returns to GMT.
Include numeric UTC offset in each displayed local timestamp.

### Optional Worldserver `auth.uptime` evidence — not a mandatory database dependency

At pinned AzerothCore `8daffdabe`, `LoginDatabase.cpp` prepares uptime session
insert/update with `(realmid,starttime)` and optional `EndTime`,
`ShutdownType`, `ExitCode`, `ShutdownReason`; `World::SaveSessionEnd(false)`
can write a partial shutdown outcome while the process still lives, while
`SaveSessionEnd(true)` writes its final end timestamp on a normal cleanup
path. `World::LoadPreviousSessionInfo()` already warns when prior `EndTime`
is NULL. This is **corroboration of an unfinished session**, not proof of
OS signal, original root cause, or whether that process has actually died.
A deliberate restart that crashes during teardown may retain a planned code
but a NULL end time. Conversely a late death after final DB cleanup can
leave a completed row. Furthermore `starttime` is integer seconds in the
pinned base schema, so `(realmid,starttime)` alone is not a universal
per-invocation unique key; check actual installed schema/update history.
A repeated same-second `(realmid,starttime)` may cause the second uptime
insert to FAIL (no row for that invocation), not a unique process record.
Treat a missing uptime row as **missing evidence**, not a clean shutdown.
Read-only access would require separate owner credentials/approval; this
Worldserver-specific source does not cover Authserver. No live SQL query,
DB account creation, or migration is approved.

## 6. Supervisor-specific adapters — choose only after evidence

| Actual launcher (unconfirmed) | Candidate read-only events to investigate | Caveats |
| --- | --- | --- |
| AzerothCore `simple-restarter` | original child exit vs wrapper status, restart attempt, GDB capture | GDB can change process/exit reporting; guard against loop |
| systemd | service MainPID/InvocationID/result/execution status, journal/coredump | `OnFailure` may reflect a failed unit, not every restart cycle; do not replace units |
| PM2 | observed child PID/restart lifecycle and actual exit code | daemon status is not automatically a signal/root cause |
| custom shell/cron/screen/tmux | actual parent wrapper's `wait` status, deliberate stop markers, log locations | only a parent sees child's wait status; shells may lose signal context; output may be ephemeral |
| `/proc`-only poller fallback | `(boot_id,pid,/proc/<pid>/stat starttime)` disappearance observation | cannot recover child exit code; classify the cause Unknown without separate proof |
| unknown | no implementation selection | require redacted host details first |

A monitoring adapter must never delay or disable the existing restart loop
while awaiting GDB/journal. Capture expensive evidence asynchronously with
limits, distinguish event timestamp from evidence processing timestamp, and
support partial reports when the evidence stream is gone.

## 7. Synthetic acceptance suite (design, NOT yet executable)

Only disposable local subprocesses or mock event streams:

| Case | Required invariant |
| --- | --- |
| 10 distinct abnormal events overnight | Exactly 10 separate named reports and 10 history entries |
| 4 events in same second / same simulated PID | Exactly 4 collision-safe files using distinct invocation IDs |
| Duplicate event from journal, wrapper and GDB | One report/one history entry |
| Worldserver + Authserver fail concurrently | Accurate per-process and total counts; no index loss |
| Normal shutdown / deliberate restart (including confirmed exit 2) | Zero crash count |
| SIGSEGV, SIGABRT, unknown exit and verified OOM | Evidence-based classifications; unknown cause label when required |
| Backtrace unavailable / journal unreadable | Minimal report still written |
| Error storm without process death | Warning only, never counted as crash; rate-limited |
| Corrupt/incomplete temp report | Excluded from index, non-destructive recovery |
| Kill writer after finalized report but before history rename | Rebuild recovers the incident; no duplicates |
| Kill writer during history temp-file write | Old index intact or recoverable |
| Reporter lacks directory write / disk full | Alternative warning channel; no server restart interference |
| Restart succeeds/fails/remains unobservable | Status reflected precisely, without a second incident |
| Reporter restart sees already-recorded event | Dedup remains stable |
| Oversized/untrusted logs or secret-looking values | Bounded truncation/redaction, restrictive permissions |
| 6 quick synthetic deaths with bundled wrapper | Existing anti-loop semantics unchanged; no real server crash |
| 3 collectors see same death with different report timestamps | One deterministic incident, no duplicate filenames |
| Journal, wrapper and GDB see the same death at different UTC times | Identical filename from canonical process start + event ID; body stores all observer times |
| Two distinct deaths reuse same PID but verified different starts | Two distinct incident IDs and reports |
| Planned restart code 2 followed by real fatal teardown | Distinguish scheduled intent from independently proven fatal termination |
| Disposable child exits 0/1/2 and SIGABRT/SIGSEGV under the pinned GDB-enabled `starter` | Recorded probe: GDB statuses 1/1/1/0/0, while `starter` reports 0/0/0/0/0; a monitor must not infer child status, crash, or restart from this masked wrapper status |
| Freeze detector `forcing a crash` warning followed **about 10 seconds later** by its pinned non-Windows null-store SIGSEGV | One report for the same verified invocation, not one report per distinct timestamp. Correlate the delayed fatal signal with the freeze warning; record actual observed signal, not fictitious SIGABRT or a proven original hang cause |
| Two writers concurrently publish one report | Exactly one file; other receives `EEXIST` and retains no duplicate |
| Existing report final filename collision | No old report overwritten, safe alternative error channel |
| Link/publish succeeded but index rewrite interrupted | Rebuild from immutable reports/sidecars, no duplicate |
| Symlinked or world/group-writable path | Refuse publish; no privilege escalation or game-process effect |
| UTC DST fall across 25 October 2026 UK change | Correct chronological history despite two identical local wall times |
| Uncorroborated disappearance in `/proc` poller mode | No invented signal; `Unknown` cause and missing-evidence text |

These are **test cases to implement after an independent S1 architecture
review**, not successful tests. No CI, sample report or binary is created
by this document.

## 8. Review gates and handoff

**CS02 (Grok):** disposable public GDB/starter investigation **reported**
against the pinned source (exit 0/1/2, SIGABRT, SIGSEGV; wrapper status
masking). Independently re-review this corrected final head and ensure that
restart code 2, actual-child event identity and anti-loop safeguards remain
separate from the wrapper's misleading exit status.

**CS03 (Claude):** compare Linux supervisor adapters, lease/locking and
`/root` least-privilege delivery, validate index crash-consistency; plan
synthetic multi-process/race and crash-loop tests.

**CS01:** review replies, choose incident ID/serialization contract only
once the owner's actual startup method is known, then propose scoped,
isolated prototype tests. Do not silently select systemd.

**Owner-only S5/S6/S7 approval:** restore-tested backups of existing
launcher/service unit/config, executable and relevant logs; explicit
permission to install, modify service policies/create root path or start
monitoring. No private DB migration, deployment, server restart, deliberate
Worldserver/Authserver failure or release is authorized here.
