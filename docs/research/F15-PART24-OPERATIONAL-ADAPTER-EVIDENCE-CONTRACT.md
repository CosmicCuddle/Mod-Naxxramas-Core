# F15 Part 24 — operational Linux crash AND error reporter: evidence contract and staged integration gates

**Status: REVIEW-ONLY REQUIREMENTS / ISOLATED DRAFT. NOT INSTALLED, DEPLOYED, RUN OR AUTHORIZED.** This document deliberately records what must be demonstrated before an actual monitor can be built and allowed near the owner's services. It does **not** claim F15 is operational or that the author's synthetic fixtures constitute Linux evidence.

## Intended capability (end-state, not current state)

For **both Worldserver and Authserver** capture an unexpected, authenticated termination with real cause/exit status, a bounded report for actual warning/error bursts, GDB-safe crash information where obtainable, and an independently verified restart attempt/result. Retain individual immutable event files plus separate derived **Crash-History.txt** and **Error-History.txt**. The intended eventual owner-owned report location is `/root/cosmic_core/logs/Crash Logs/`. **The target path is a requirements label only**; none of these drafts creates or touches it.

This is separate from the owner's first **five-functional-fix gameplay test** (#120 GFPP precisely 120s; human Hunter A02 real ON/OFF; human-human A04 stock group loot; F12 physical Scarlet entrance/exit; F13 Atiesh exterior Karazhan). F15 is nevertheless a high-priority MUST-FINISH system, not merely a synthetic audit.

## Proven synthetic building blocks vs missing real boundary

| Source-only model (already draft) | What its tests model | What is NOT yet authentic |
|---|---|---|
| S2 incident store [#136](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/136) | Immutable/private per-incident records, canonical deterministic identity, derived history and collision handling | Real kernel child death, actual owner directories, privileged writer |
| S3 restart sidecar [#137](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/137) | Separate immutable completion note and source/history projection | Authenticated supervisor child, proof of replacement ready, durable begin→finish atomicity |
| S4 child-exit model [#139](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/139) | Reject misleading wrapper/GDB/systemd text vs asserted actual child evidence | Trusted `waitpid/waitid`, process tree under owner's launcher, ptrace actual signal |
| S4b warning/error burst [#140](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/140) | Bounded per-category/instance alerting and cooldown | Trusted stderr/logger source identity, stream boundary, retention policy |
| S4c error store [#141](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/141) | Separate immutable error events, private temp recovery, Error-History | Real error records and permitted operator output path |
| S4d readiness [#142](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/142) | Synthetic old-child/new-child/deadline/readiness sequence, reject bad evidence | Real readiness proof and matched Linux clock origins |
| S4e lookup [#147](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/147), temp-link correction [#149](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/149) | Completed outcome replay check and interruption-recovery handling | Atomic cross-process reservation preventing lookup→write race; #149 needs new-head CI and peer approval |

**Critical:** even when an offline suite is green, passing a fixture field such as `verified=True` cannot attest kernel death, a particular source account, real readiness, log origin, or a true restarted server. **A report hash proves integrity relative to its bytes, not who supplied the record**.

## Gate R0 — read-only actual launcher discovery (must be separately owner-approved first)

We do not know whether this owner starts Worldserver/Authserver directly, through systemd, a shell, a loop/restart script, GDB, a service manager, a terminal tool or a mixture. Therefore no adapter can safely be chosen from public AzerothCore defaults.

Gather only the **minimum redacted, read-only evidence** from the actual host, **after explicit separate owner permission**, preferably provided by owner without sharing secrets:

1. For each daemon: executable location/binary identity; start method and restart owner; parent→wrapper→**actual child** process relationship; whether systemd watches the *wrapper* or the *server*; whether multiple wrappers exist.
2. Crash/stop behavior: where actual wait status is observable, and whether the wrapper or GDB hides a child SIGSEGV behind an exit-0 shell/GDB exit. Treat wrapper status, one `systemctl status` line or a log string as insufficient proof of child death.
3. Service ownership: unprivileged runtime UID, separate launch/supervisor UID, permitted read-only telemetry inputs, mount/namespace/cgroup identity, PID reuse prevention, any existing safety watchdog and restart schedule.
4. Readiness: a supported **authenticated** Worldserver/Authserver readiness signal (not only a new PID or TCP connect). A successful accept or process survival for a few seconds is not by itself game/application readiness.
5. Error sources: actual logger/stderr paths and whether logs are rotated/replaced; warning vs error categories; clock/timezone/log format; rate and maximum report size. Do not paste actual credentials, tokens, client account names, player identifiers or raw secrets into GitHub.
6. Privileged report destination: parent directory ownership and mode, whether a separate **least-privilege output broker** can own the exact fixed path, backup/retention policy and restore procedure. Do not change permissions or create any path during discovery.

**Privacy & scope:** never copy an entire `Environment=` value, secret-filled service file, full log, DB dump or personal player identifier into GitHub. Only approved redacted fields and proof of *whether* relevant variables are set, not their values. This document executes **zero commands** and provides **no permission** to inspect the actual machine.

## Gate R1 — actual event admission and fail-close identity

Any future event producer must prove an event came from its authorized supervision relationship, rather than trusting arbitrary JSON, a packet, a log line or child-provided `verified`:

- Old child identity = service, host/boot ID, stable invocation ID, PID plus **kernel start time**/process incarnation, supervising parent identity and corresponding trusted exit observation. A reused PID alone is never enough.
- Observe direct kernel child exit/signal with the permissioned waiter. If GDB/ptrace acts as the waiter, require a reviewed, authenticated event bridge; **do not equate GDB transcript text, shell `$?`, exit 139 or generic journal text with an actual SIGSEGV**.
- Distinguish Worldserver/Authserver normal stop policy, planned 0/2 statuses (they differ by executable/launch mode), SIGTERM/service stop and verified unexpected death; unknown origin must be **unverified**, never counted as crash.
- A startup/authentication failure without a trusted child death is an **error or unknown**, not an invented crash. Loss of supervisor/event source cannot generate a success claim.
- Use monotonic timers from **one verified domain** for deadlines and elapsed time, and UTC only for display/retention. Never subtract unverified cross-process monotonic values.

## Gate R2 — durable attempt reservation (S4e's missing atomicity)

`finished_lookup(key) is None` is a *snapshot*, not exclusive authorization to start a replacement. Before any real restart:

1. Under a **single coherent interprocess lock** and pinned trusted directory, validate immutable original incident identity, current server process incarnation and any completed sidecar; check a durable **attempt reservation or completion** record.
2. Atomically and durably publish a unique `PENDING` attempt/reservation tied to `incident + supervised child + attempt` using no-clobber/create and fsync-before-action. A contender seeing an existing reservation must not start a second replacement.
3. Only the authenticated supervisor holding the lease/claim can attempt replacement, after re-checking the original child is dead and no other live server owns that service. Retain a single-controller principle across the real restart, not just across the read.
4. Authenticated replacement PID/start/invocation and actual application readiness transition the attempt to `SUCCEEDED`; an observed failure or verified deadline expiry becomes `FAILED/UNVERIFIED` according to evidence. Persist exactly one terminal outcome via no-clobber finalized sidecar. No forced success from absent events.
5. On writer crash/restart, reconcile orphan `PENDING` records against *current trusted process facts* and previous durable state. Never simply delete a pending file to retry, and never let S2-only writers silently coexist with S3 history.
6. Define and test lock failures, fsync failure, renamed directory, corrupt records, hardlinks, same-UID interference, concurrent independent observers, PID reuse, partial finalization, lost readiness and reboot. **A new draft needs negative tests and source review before any real adapter**.

**This is a proposed contract**, not a working protocol, schema or permission to modify the owner's services.

## Gate R3 — warning/error ingestion without crash spoofing

- Error stream capture is bound to an authenticated service invocation and **log source**, including log rotation/reopen and truncation handling; unexpected EOF isn't automatically a crashed child.
- Use bounded buffers, explicit maximum line bytes, UTF-8 replacement/sanitization, secrets/identifiers redaction where required, filename-safe service/category allowlists, per-category burst cooldown and retention quotas. No raw untrusted log content can choose the output path.
- Create one immutable warning/error event and update **Error-History** independently of the crash store; avoid collapsing all warnings into a fake crash or losing error evidence when a crash coincides.
- A sustained error flood must not exhaust disk or flood reports; dropping/coalescing must be disclosed as a count, never silently mark service as healthy.
- A malicious plugin's forged ERROR string is a *trusted-process emitted log* at most; it is not proof of kernel failure or independent producer authenticity.

## Gate R4 — privileged output boundary

World/Auth/game plugins, bots, the addon and untrusted log text should **not** gain arbitrary access to `/root`. The future approved broker is the only component allowed to write the owner-selected reports, and it must:

- Use a fixed, pre-created and owner-approved output root; pin directory FDs and refuse symlinked or writable-by-others path components. Avoid path traversal, symlink following, hardlink alias writes and owner-changing operations.
- Authenticate the producer and service, validate serialized size/schema and allowed event categories, ensure private ownership/mode/ACLs, atomic no-clobber finalization, file+directory fsync and bounded retention without deleting active/hardlinked/unknown files.
- Keep reports, derived history and recovery journal mutually consistent across crashes, including separate World/Auth source IDs; never reassemble a successful restart from a spoofed hash or unauthenticated log.
- Provide restart-safe diagnostics if unable to write; broker failure must not itself restart or halt the game unless separately owner-approved.

This is **not** a suggestion to change directory ownership, setuid, sudoers, service unit or any file now.

## Gate R5 — staged negative acceptance and rollout

| Stage | Evidence required to advance | Owner consent |
|---|---|---|
| R0 | Redacted read-only launch/process/GDB/readiness/log source facts; exact running binary/module/Playerbots/IP pin inventory | Separate explicit read-only permission |
| R1–R4 | Reviewed real adapter design, trusted OS provenance, journal concurrency/crash-recovery, warning/error boundedness, broker threat model, source/native/hosted tests | Source-only drafts possible without host access |
| S4 isolated staging | Disposable stand-in daemons + controlled exit 0/2/SIGTERM/fatal signal; GDB wrapper cases; concurrent restarters; readiness lost; log rotation/flood; filesystem failure/rollback; no owner live process touched | Explicit permission for isolated staged fault injection |
| S5 operator rehearsal | Approved backups/restores and reversible runbook against exact installed binaries/config/supervisor, no user-visible outage assumed | **Separate explicit approval** |
| S6–S7 controlled deployment | Verified service start/stop policy, world/auth report path, retention/rollback, human witnessed success, error and crash tests in authorized maintenance window | **Separate explicit approval** |

**Stop condition:** if any key source/owner/path/clock/writer evidence remains ambiguous, record `UNKNOWN / NOT VERIFIED` and stay source-only. Never claim a green synthetic build proves genuine automatic crash+error reporting.

## Next engineering work from here

1. Independent source/security review of this requirement contract. Seek contradictions with #139–#149 and the owner's actual approved launcher mode before adding code.
2. Design **S4f offline durable attempt reservation and single-writer reconciliation** against **fabricated private fixture directories**, with adversarial multiprocess tests. No real restart or root paths.
3. In parallel, design a **read-only adapter interface** that consumes authenticated provenance facts. Avoid a boolean `verified` supplied by untrusted callers; include negative tests for forged wrapper and missing child evidence.
4. After the owner grants separate read-only discovery consent, collect only redacted facts needed to select the correct supervision implementation. Then propose actual least-privilege adapter in a separate DRAFT, test offline/isolated, and request S4–S7 approvals one stage at a time.

**Governing threads:** [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), [team #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48), [Claude #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143). Grok has returned; A02 remains specialist work. All drafts stay OFF and unmerged. Historical milestones and the owner's two locally edited Playerbots files plus eight map threads must be preserved.
