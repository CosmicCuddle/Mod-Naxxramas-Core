# F15 Part29 — Owner R0 launcher decision gate for BOTH AzerothCore daemons

**PUBLIC, BLANK, REVIEW-ONLY. DO NOT MERGE OR DEPLOY. This document grants NO permission to read the owner's host, run commands, inspect systemd, view configs/logs, enable F15, change process launchers, adjust stdin or perform test crashes.** Keep any completed observation privately; do not post unit files, usernames, paths, process identifiers, character/account information, secrets or unredacted logs to this PUBLIC repository.

## Decision at this checkpoint

**The safe next F15 step is an approved, private, read-only R0 topology inventory, not an adapter deployment.** The current source stack [#170](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/170) has a proven *disposable owned-child* producer; [#171](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/171) has its canonical event contract; separate [#182](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/182) has a safer *offline* report store. Cross-branch [#183](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/183) and pinned-native [#184](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/184) prove their differences. **None is an installed World/Auth supervisor**, and a direct bridging implementation is blocked until per-daemon origin, transport and incident policy have been selected.

### Pinned evidence behind the decision

- Immutable public `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`: `worldserver/Main.cpp:403–409` enables a CLI input thread if effective `Console.Enable` is true. `CommandLine/CliRunnable.cpp:~205,235–239` calls `readline()` and invokes normal `World::StopNow` when stdin EOF occurs. On Linux, `Main.cpp:523–581` unconditionally calls `cliThread->join()` at cleanup without the Windows-only cancel I/O path. **Opening `/dev/null` as stdin can stop the world**; holding an otherwise inert pipe open may make its CLI join dependent on GNU Readline event-hook behavior that has not been tested against the real non-TTY process. Never recommend either as a live wrapper default.
- Public Worldserver `Main.cpp:189–194`, `Log.cpp:244–255`: logging can be async by effective `Log.Async.Enable`; posted work does not carry a durable record receipt. Public Authserver Main calls `sLog->Initialize(nullptr)` in this pin. Public `AppenderConsole.cpp:172–212` sends WARN to stdout, ERROR/FATAL to stderr but only configured loglevel prefix yields an actual severity. Public `.conf.dist` flags are 0. A stream's presence is neither complete delivery nor a severity attestation.
- Public `AppenderFile.cpp:25–150`: sample `Server.log`, `Errors.log`, `Playerbots.log` and `Auth.log` can use `,w` overwrite, rotate by rename and reopen. Early-restart truncation and undisclosed logger-level filtering make **late file tailing incomplete**. `fflush` does not prove fsync/durability.
- Producer #170 `r1r3_owned_child_producer.py`: verifies `waitid(P_PIDFD)` only for an actual *direct disposable child* owned and unreaped by that producer. It cannot authenticate the death of a server started by somebody else; arbitrary `verified=True`, shell `$?`, exit 139, process log text and generic `systemctl status` do not substitute for a verified fatal signal.
- Canonical #171 versus stores #182: `fatal_signal`, `nonzero_exit_not_signal`, and `signal_requires_policy` cannot all become a legacy text 'SERVER CRASH REPORT'; canonical declared WARN/ERROR **lines** cannot be relabeled S4b repeated **bursts**, and `FATAL` is not admitted by S4b's existing WARN/ERROR-only model. Schema/writer migration and origin must be designed together; no adapter selected.

## Decision matrix — assess each daemon **independently**

| Actual owner launch topology (**UNKNOWN today**) | Possible observation boundary after R0 | Proven capability *today* | Non-negotiable gate before any real code |
| --- | --- | --- | --- |
| **A. Direct executable controlled by an owner-approved new parent/launcher** | A permitted parent may own actual child, pidfd/waitid status and **both** pipes. Producer #170 is the nearest starting point for disposable tests. | Disposable children ONLY. No actual World/Auth identity, CLI, restart or privacy proof. | Owner permits changing start/stop path, preserves service UID/stdio/coredump, tests Worldserver stdin/CLI with real binary on restored staging, verifies true signal/exit, source gaps, restart and readiness. Do not assume held-open stdin works. |
| **B. systemd directly owns a real server binary** | An approved systemd/journal/coredump **reader** can potentially obtain manager-maintained result/status, journal cursor and unit/invocation. | None of these authenticated on owner host; #170 cannot `waitid` for another parent's child. | Determine unit `Type`, `MainPID` semantics, restart policy, wrapper chain, permissions and whether actual **child signal** can be positively proven and bound to one invocation. A generic journal line or nonzero service status alone cannot satisfy verified crash. Changing unit requires separate written approval and rollback. |
| **C. systemd runs a shell/restart loop, GDB, debugger, or other wrapper** | Must distinguish monitored wrapper from the actual world/auth process. Might require a *cooperative authenticated supervisor* integrated with that specific wrapper. | Existing prototypes do not bind a wrapped real child. A wrapper exit 0/139 is not child SIGSEGV proof. | Read-only parent/child identity first, privately. Explicit owner-approved architecture for true child death, planned restarts, signal interception, double-restart prevention and readiness; no general substitution by shell `$?` or a GDB transcript. |
| **D. tmux/screen/MobaXterm/manual terminal or ad-hoc detached process** | Best-effort log or terminal capture could give **unverified** text, not full kernel fatal-signal provenance. | No authentic matching, full coverage or approved start ownership. | If owner wants true crash proof, separately approve a supervision/launcher conversion or an authoritative external source with equivalent independently verified origin. Without that, crash proof is **NO-GO**; only explicitly labeled unverified observations might eventually be allowed under a separately decided partial scope. |
| **E. Mixed topology between World and Auth** | Choose separately by daemon; never clone the Worldserver strategy to Authserver without verification. | None operational. | Per-daemon launch, logging, stop, restart and role binding must pass on their own. Do not mark F15 complete if one service is still unobserved. |

**No implicit default winner.** If R0 facts cannot establish a suitable authority over a real child or trusted manager/coredump event, record **BLOCKED**. If the owner declines any launcher change, do not quietly substitute a text-only tailer and claim a real crash monitor. An event classifier must be able to say `source_incomplete`, `unverified`, or `unknown` without inventing success.

## Minimal PRIVATE R0 sheet — one row per daemon; this PUBLIC version remains blank

All cells are **UNKNOWN** until the owner separately approves a **read-only** R0 for Worldserver and Authserver. An owner may supply broad categorical answers without logs or precise server details. Do not copy filled data to the public issue/PR.

| Fact | Worldserver | Authserver | What it decides |
| --- | --- | --- | --- |
| **Launcher category**: direct binary / systemd direct / wrapper / GDB / terminal / other / unknown | UNKNOWN | UNKNOWN | Owned-child pidfd mode versus external manager mode |
| **Actual monitored child** versus shell/debugger wrapper; who restarts? | UNKNOWN | UNKNOWN | Avoid attributing wrapper exit to daemon |
| **Stdio**: pipe/journal/TTY/file/closed/other, for both stdout and stderr | UNKNOWN | UNKNOWN | Whether output is accessible without changing launch or losing messages |
| **Console and stdin**: World `Console.Enable`, actual real stdin, planned shutdown path | UNKNOWN | Not assumed same | Prevent accidental stop, hung join or command injection |
| **Actual logging options**: console level-prefix, logger/appender levels, `Log.Async.Enable` | UNKNOWN | UNKNOWN | Which emitted events have verified severity and possible incomplete queue |
| **File sinks**: enabled, overwrite/append, rotation/backup and pre-restart preservation | UNKNOWN | UNKNOWN | Can a source observer avoid gaps on restart and rotation? |
| **Process trust boundary**: daemon/supervisor/reporting UID permissions, installed binary identity | UNKNOWN | UNKNOWN | Who can honestly claim child death, reporter role and path provenance |
| **Crash evidence**: systemd result/coredump, true child wait status, debugger role | UNKNOWN | UNKNOWN | Whether actual fatal signal can be proved versus exit 139/message text |
| **Retention/backups/readiness**: controlled restore, owner-stated retention, authenticated service ready | UNKNOWN | UNKNOWN | Staging and safe future R2 reservation/rollback |

## Two separate owner authorizations — NOT granted

**Gate R0: private READ-ONLY discovery** of minimal categories for both daemons, with no service/UID/config changes, no tests that cause crashes and no public logs. Before any inspection, get explicit permission on precise scope and tools; preserve no secret values. No server interaction is carried out by this document.

**Gate S4: controlled STAGING, strictly later.** Separate explicit owner approval and verified restorable backups of relevant binaries, configs, DB/world state and report directories; exact source SHAs; rollback owner; disabled production deployment. Test with real server binaries only on that approved nonproduction environment, demonstrating stdout/stderr+WARN/ERROR+FATAL attribution, planned shutdown/restart code, true fatal signal, incomplete pipe and rotated/overwritten file, dual-daemon independence, flood and permission failure, durable writer + restored operation. S4 remains **NOT RUN**.

## Delivery acceptance: pass ALL or remain NOT OPERATIONAL

1. **R1 real origin (World + Auth):** matched actual process incarnation and trusted kernel/manager death, distinguishes normal exit 0, World restart exit 2, ordinary exit 1/139, unplanned SIGTERM, and positively proved fatal signal, while never claiming unknown as crash.
2. **R3 warnings/errors (World + Auth):** trusted origin, declared severity or explicitly unknown, WARN and ERROR independently reported, FATAL mapped by approved policy, file/pipes sourced without fake category/timestamps; S4b burst policy applied only to genuine threshold/categorical evidence, with accurate drops/gaps.
3. **R4 reports:** selected canonical/versioned schema, private immutable files, source authentication separated from daemon UID, no mixed old/new incompatible writer, bounded memory/disk and quotas, explicit durable overflow, safe retention/backups and verified rollback.
4. **R2 restarts:** approved one-controller reservation/deduplication and verified ready outcome for each daemon; no duplicate spawn when current service still live, no auto-kill on observer timeout, and no false ready from PID/TCP alone.
5. **Owner staging acceptance:** independently observed outputs and restored backups; no modifications to production before separate owner deployment approval. Explicit release record per daemon and per event channel; **both must pass**.

## Stop repeating research-only F15 tasks

**Technical handoff decision:** source-only producer/store/schema/route prerequisites have now been independently researched and pinned. The next hard dependency is **owner-approved R0 facts**, not another generic offline mock. Mark F15 as `BLOCKED_AT_R0` and **do not create more speculative reporter adapters or safety-test branches merely because R0 is unavailable**. Effort can instead return to other independently actionable source/review tasks or owner staging preparation, subject to the same non-deploy/backup constraints.

F15 is a must-finish separate from the gameplay acceptance queue, but **not operational now for either Worldserver/Authserver crash OR warning/error reporting**. Protected gameplay #160 and `main` are untouched. Mandatory gameplay accepted remains **0/5**. Claude remains on break.
