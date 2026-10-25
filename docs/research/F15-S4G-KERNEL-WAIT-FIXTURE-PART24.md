# F15 S4g — owned-child Linux kernel wait evidence (fixture ONLY)

**DRAFT SOURCE RESEARCH / LOCAL TEST EVIDENCE. NOT A CRASH REPORTER, RESTART CONTROLLER, GDB INTEGRATION OR SERVER DEPLOYMENT.**

This is a deliberately small, independent proof-of-concept complementing F15's [operational adapter contract #151](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/151), [S4 synthetic evidence #139](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/139) and [S4f offline attempt claim #152](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/152).

## New engineering work

- `tools/f15/offline_kernel_wait_s4g.py` starts **only an allowed Python test fixture** through `subprocess.Popen([sys.executable, "-I", this_source_path, "--synthetic-child", allowed_mode])`, never shell=True or an arbitrary executable/PID. It then observes that **specific self-spawned direct child** using real Linux `os.waitpid(pid, 0)`, and interprets the kernel's `WIFEXITED/WEXITSTATUS/WIFSIGNALED/WTERMSIG`. Monotonic timestamps bound the local observation. It can never attach to or observe a server process.
- Eight fixture modes include clean 0, nonzero 2, fake shell 139, real SIGSEGV, real SIGABRT, planned and unplanned SIGTERM, and a wrapper that **reaps its own crashed grandchild and exits 0**. All child outputs go to DEVNULL. Each fixture disables core dumps and uses no owner logs, process manager or network.
- `tests/test_f15_offline_kernel_wait_s4g.py` verifies ten negative/positive cases, prohibits unstarted and replayed `waitpid` on the same child, rejects an arbitrary `"worldserver"` fixture mode and keeps the distinction between **direct child** and grandchild. A parent-registered planned signal is model-only, not authoritative service stop policy.
- `.github/workflows/f15-s4g-kernel-wait-fixture.yml` runs **only** these synthetic Python tests on a GitHub-hosted Linux runner; no Worldserver/Authserver/GDB/systemctl/root commands or secrets.

## What the actual kernel evidence can and cannot prove

| Direct-child fixture observation | Honest conclusion |
|---|---|
| Kernel reports direct child exited **0** | That direct child exited normally. A hidden grandchild may still have crashed. |
| Kernel reports direct child exited **139** | This is merely an exit code, **not** a proven SIGSEGV. A shell/GDB wrapper could have encoded status. |
| Kernel reports direct child died by **SIGSEGV/SIGABRT** | A verified signal **for that same direct fixture child only**. Does not identify the owner's Worldserver or Authserver. |
| Direct child died by **SIGTERM** | Context required; a fixture parent can label a planned case but production must prove service-stop intent using a trusted supervisor, not a string from a child. |
| A Python wrapper masks grandchild SIGSEGV as own exit **0** | The outer watcher must not invent a grandchild death or claim that the grandchild was healthy; require correct waiter/ptrace provenance for the actual target. |

**Actual local execution:** CS01 executed the exact source/test fixture pair using `PYTHONPATH=.../tools/f15 python3 -W error -m unittest discover -s .../tests -p test_f15_offline_kernel_wait_s4g.py -v` on an isolated local Linux container: **10/10 tests OK** (second run, after replacing unsafe multi-threaded `fork()` from the parent with self-contained Python `subprocess.Popen`). No external processes or owner files used. **Current exact GitHub Actions result is not yet available or verified.** Independent CS02/CS03 source review is outstanding.

## Nontransferable proof boundaries

1. The prototype is run under a parent that **owns and spawned** the tested child. Real Worldserver/Authserver may be started by systemd, a shell script, a loop or GDB, so the future adapter must prove which process is the real child, correct wait/ptrace ownership and PID **incarnation**, and have permission to observe it. A random external PID passed by a log/user is NOT trusted.
2. `WaitObservation` is a normal Python value **not cryptographically authenticated** to another process; callers could invent identical fields. No Linux event-broker authentication or durable S2 incident identity is supplied here.
3. This is not continuous supervision: no launcher attach, no watchdog, no service start/stop, no restart reservation, no authenticated readiness, no real logs, **no warning or error ingestion**, no GDB transcript, no privileged report writer, no root output path. The observed direct fixture child is short-lived and controlled.
4. User's future configuration and rollout are unknown; collecting launch/unit/GDB facts is a **separate read-only owner approval gate**. Native C++ integration and actual expected exit code policy are likewise unresolved. Do not use the fixture to decide any production restart.
5. `resource.RLIMIT_CORE=0` applies **only to the Python fixture**; real crashes must not have debugging artifacts silently disabled. A real reporter may require GDB or core dumps under an owner-approved plan.
6. No S4f pending reservation and S4e completed-restart lookup integration yet; even genuine direct-child death does NOT give a controller permission to restart unless an authenticated durable single-writer protocol and process-scope safety have been proven.

## Required next reviews

- CS03/Claude and CS02/Grok independently review this exact SHA, current-head hosted CI and the **wrapper masks grandchild** false-acceptance case. Explicitly distinguish source evidence from real kernel event attestation.
- On a future isolated branch, design a capability-scoped observer/broker link that binds actual supervisor invocation, boot, kernel PID start time, wait/signal result and signed/owned output. No owner unit/service changes or root paths before separate approval.
- Preserve the first gameplay test requirement for **all five FUNCTIONAL fixes together**: GFPP exactly 120 seconds, human Hunter ON/OFF autocast, native-normal human-human quest loot, original PHYSICAL Scarlet entrances/exits, and Atiesh landing OUTSIDE Karazhan. F15 automatic crash **AND error** reporting is separately mandatory to finish.

**Safety:** no merge, installation, host/root/config/SQL/DBC changes, Playerbots edits, new addon, network interaction or live game action. All changes are an isolated default-inert draft.
