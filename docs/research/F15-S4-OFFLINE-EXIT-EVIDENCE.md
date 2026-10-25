# F15 S4 preparation — exit evidence admission contract (OFFLINE)

**DO NOT MERGE, INSTALL, RUN ON OWNER SERVER OR CLAIM F15 OPERATIONAL.**

## Scope and lineage
- New isolated CS01 draft branch based on F15 S3 #137 exact f19041601dcbe7bee6ffc2167947b9e7a4111c1c, itself stacked on independently S2-scoped approved #136 exact a2b1185f29f32b8d71ed17f53058a62baea0e435.
- Adds only a pure Python fixture admission model, synthetic tests, a source-only CI workflow and this note. No actual process spawn, shell wrapper, GDB invocation, root path, SQL, DB, WoW modules or config.
- This is **preliminary S4 research/source contract** and does not meet S4 real-supervisor staging or S5–S7 requirements. No source is merged.

## Why a separate evidence admission boundary?

Reviewed pinned Grimfeather AzerothCore revision 8daffdabe9202c228e45d833c9a1d399597a15cd:
- worldserver returns 0 on normal stop and 2 on planned restart (World.h lines 53–55); error exit is 1. Authserver has no equivalent planned code-2 restart.
- The pinned startup-scripts/src/starter can run the server under GDB. When GDB is enabled, its wrapper may exit 0 after a child SIGSEGV. The simple-restarter shell uses the wrapper's status, and its text says an exit code that is **not authenticated actual-child wait status**.
- GDB transcript filenames are only second-resolution and can collide if both services or multiple runs use the same crash path. A log line mentioning SIGSEGV is useful context, not sufficient authenticated incident identity.

These are verified **pinned scripts/source semantics** and prior disposable tests, not evidence of the owner's actual launcher, binaries or GDB config. The owner's actual supervisor/GDB/PM2/systemd/screen/tmux/custom start method remains UNKNOWN.

## New model contract

The pure function evaluate_exit_evidence(ExitEvidence) returns:
- **unverified:** wrapper return code, restarter log, GDB transcript, systemd summary, journal text, any other non-direct-child-wait channel, or direct child identity not proved by the synthetic fixture.
- **ignored:** verified direct-child fixture that is not independently unexpected, has clean World/Auth code 0, Worldserver code 2, or a corroborated planned ordinary SIGTERM/SIGHUP/SIGINT.
- **rejected:** contradictory signal and exit-code claims, absent or invalid process identity, malformed UTC, invalid service or wrong boolean types.
- **candidate:** valid synthetic direct-child fixture and actual-child unexpected-death classification pass inherited S2 incident policy, including verified fatal SIGSEGV or code 1; Authserver code 2 is not a Worldserver planned restart. Exit 139 remains **exit 139**, never silently inferred to be SIGSEGV.

No result is written to an incident store. A **candidate is not an authenticated OS observation**: fixture booleans are arbitrary model inputs. A later actual launcher-specific adapter must independently establish kernel child identity, provenance, startup and death epochs, actual wait status, planned/abnormal termination and uninterrupted event ownership before converting a candidate to any immutable report. Never set verified_actual_child based on text, command-line PID alone, shell $?, guessed 128+N signal, or addon/Worldserver self-report.

The model uses S2 Incident directly for policy consistency. The current module import form is test-path-based only; package/import cleanup is part of future reviewed production integration. S3 sidecars **still do not verify restart attempts or readiness**. Recovery after supervisor crash, service continuity, log error/warning bursts, stale temporary files, secure root broker and installed staging remain out of scope.

## Tests and expected evidence
- Synthetic direct exits: world 0/1/2, auth 2, verified SIGSEGV/SIGXFSZ, planned/unplanned SIGTERM, planned SIGKILL, planned abnormal exit 1, missing status, exit 139 without signal inference.
- Negative attribution: shell wrapper 139, GDB SIGSEGV line, simple-restarter 0 under GDB, systemd/journal/unknown, unverified child, malformed identities, contradictory status, recycled PID with a distinct process start.
- Run python3 -m unittest -v tests.test_f15_exit_evidence_s4 from the repository root with Python 3. Compatible S2 storage suite should also remain green.
- After CI, request independent exact-head review; do not infer S4 functional completion from tests.

## Operational requirements still blocking full F15
1. **Read-only owner-authorized discovery** of actual launch/supervision, GDB, service users and paths, no credential copying.
2. Trusted **actual-child** unexpected-death capture for both Worldserver and Authserver; reproducible lifecycle attribution despite GDB masking, process crashes, log rotations and PID reuse.
3. Independently verified restart attempts **and service-readiness**, with no fake succeeded labels, and no interference with existing auto-restart.
4. Separate bounded warning/error-burst capture that cannot fabricate crash events.
5. Least-privilege secure broker for exact destination /root/cosmic_core/logs/Crash Logs/, fsync/no-clobber/recovery/fault-injection and hardened clock/ownership semantics.
6. Exact environment staging, backups and tested rollback, with **distinct owner approval** for installation, restart or all S5–S7 live acceptance.

Maintain complete master #28 and team coordination #48. Grok is owner-reported on break: #135 remains unmodified. Claude owns lead module engineering #125/#127/#132/#133 and selected independent reviews. No protected main, Playerbots local modifications or any user server paths are touched.
