# F15 R1/R3 — owned-child producer prototype (launch mode A), DRAFT

**Status:** isolated draft, **UNSELECTED and OFF**, approved as a source-only proposal by CS01 ([#143 6415818621](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6415818621)), child of contract #162 `2f27ac3`.

- It only observes disposable Python children that its own tests spawn.
- It is **not** an owner launcher, is not installed, and must not be run against a real Worldserver/Authserver.
- Running the real World/Auth binaries, even in CI without a database, is a separate S4 rehearsal that needs the **owner's** explicit permission (CS01 Q3: not approved).

Files: `tools/f15/r1r3_owned_child_producer.py` (stdlib only), `tests/test_f15_r1r3_owned_child_producer.py`, `tests/r1r3_fixture_child.py`, and `.github/workflows/f15-r1r3-owned-child-producer.yml`.

## Verified vs unverified

| Claim | Status | How / why not |
|---|---|---|
| Which process incarnation ended | **VERIFIED for our own disposable child** | `(boot_id, pid, starttime, ppid, pgid)`. A pidfd pins the child straight after spawn. The producer is its parent and has not reaped it, so the PID cannot be recycled in between. The pinned process is then cross-checked to be our own child (`ppid == getpid()`), or `start()` refuses. |
| How it ended | **VERIFIED for that child** | `waitid(P_PIDFD, WEXITED)` only. `CLD_EXITED`, `CLD_KILLED` and `CLD_DUMPED` stay distinct. Exit 139, printed "SIGSEGV" and a wrapper's 0 are never a signal death. |
| Missing kernel support | **fail closed** | Without `pidfd_open`, `P_PIDFD`, `waitid`, `CLD_DUMPED` or `boot_id`, construction raises `Unsupported`; no event is produced. |
| A planned stop | **only a harness-declared plan** | The producer **sends no signals at all**. A test may declare `planned_signal` before start and then deliver it itself. Only that exact signal counts as `planned_signal`; anything else is `signal_requires_policy` (SIGSEGV/ABRT/BUS/FPE/ILL/SYS are `fatal_signal`). |
| Output lines | **VERIFIED as bytes from our own pipes** | Read from the **stdout and stderr** pipes the producer created (attestation `owned-stdout-pipe` / `owned-stderr-pipe`). Each record carries its `stream`. Identity is attached by the producer and can't be set by child text. This does **not** authenticate what the text claims. |
| Severity | **`unknown` by default** (CS01 decision, #167 6418335424) | A level is decoded only when the caller **declares** `prefix_loglevel=True`, an owner R0 fact that the console appender has flag `0x02`. Parsing is positional: after ANSI removal, an optional **declared** timestamp (`%Y-%m-%d %X `), then `FATAL|ERROR|WARN|INFO|DEBUG|TRACE ` at the line start. A level word elsewhere in a line is never a severity. INFO/DEBUG/TRACE are counted, not recorded. |
| Stream hint | **hint only, never a severity** | `severity_hint` is `error_or_fatal_candidate` (stderr) or `below_error_candidate` (stdout), with `hint_source=pinned_console_route` (`AppenderConsole.cpp@8daffda` L174: ERROR/FATAL→stderr, the rest→stdout). Other code (libc, the MySQL client, sanitizers) can write to either stream. A hint can't trigger a report. |
| ANSI colour | **stripped, counted, never used** | CSI/ESC sequences are removed before parsing (`ansi_sequences_stripped`). Stock consoles are coloured and print the reset **after** the newline, so the next line starts with `\x1b[0m`. A line empty after stripping is counted in `lines_blank`. |
| stdout timing and completeness | **NOT claimed** | stdio block-buffers a pipe (the pinned core never calls `setvbuf`), so stdout lines can arrive late. `stdout_tail_lost_on_crash_possible` is set on any signal death (tested: a buffered tail is lost while stderr is kept). `cross_stream_order="unknown"`. |
| Role | **declared, descriptive only** | `role ∈ {worldserver, authserver}` is required and recorded on the observation and both streams. It is not authentication of the executable. |
| stdin | **fixture setting only** | `stdin_mode="devnull"` or `"held_open"` (an owned pipe never written, closed only after the child is collected, including after a hand-off). A worldserver with `Console.Enable=1` calls `World::StopNow(0)` on stdin EOF (`CliRunnable.cpp` L236–238). A fake console fixture shows both behaviours. The real stdin destination is an R0/owner decision. |
| No stall under a flood | **VERIFIED for a 48 MiB flood** | One nonblocking select loop drains the pipe whether or not the child has exited. Past the retention budget, bytes are dropped and counted. The child's own write time stays under 10 s. |
| Byte accounting | **VERIFIED** | `bytes_drained == bytes_retained + bytes_framing + bytes_dropped`, all non-negative. Lost *lines* are not claimed exactly: `lines_unclassified` counts lines with no kept bytes, and partial framing is flagged. |
| Descendants holding the pipe | **SOURCE_INCOMPLETE, never killed** | After the child exits, a single-shot grace deadline waits for EOF. On expiry, `deadline_hit` and `source_incomplete` are set and only our own read end is closed. |
| Failure after spawn (`pidfd_open`, `/proc` read, PPID/boot mismatch) | **no event; child handed off** | `StartFailed` carries a reaper thread that drains and counts stderr, collects the exit (pidfd, or `poll()` if no pidfd) and closes our descriptors. No zombie or fd leak (tested), no signal. |
| Child still running at the observation deadline | **no event; child handed off** | `ObservationTimeout` carries the same reaper. Our read end stays open and drained, so the child's later writes still succeed (tested: exit 0, not EPIPE). |
| Unexpected error before the exit is collected (read error, selector registration, `waitid`) | **no event; child handed off** | `ObservationFailed` carries the same reaper, never a closed pipe and an abandoned child. Each injection is tested; the child keeps writing successfully and is collected. An error *after* the exit was collected is re-raised, since nothing owned is left. |
| A writer that never pauses | **cannot starve the loop** | At most 16 × 64 KiB reads per event-loop turn, then exit and deadline checks run (tested with a read source that never returns `EAGAIN`). |
| Process group emptiness | **NOT provable here** | `group_members_seen_after_exit` comes from a best-effort, read-only `/proc` scan with `group_scan_complete`. A listing or entry permission error marks the scan incomplete and never fails the observation (tested). Even a complete empty result is not proof, because a descendant can leave the group with `setsid()` (tested). |
| Real Worldserver/Authserver, systemd/journal, log files, GDB, restart (R2), reports (R4) | **NOT IMPLEMENTED** | Each needs R0 facts and/or owner permission. |

## Tests

51 tests with real child processes:
- clean exit; startup error (exit 2 with an ERROR line); exit 139; real SIGSEGV and SIGABRT; forged crash text;
- a wrapper hiding a grandchild's SIGSEGV;
- unplanned TERM; a declared plan delivered by the harness, and a plan for TERM that doesn't cover INT;
- an error and a crash together;
- exact-incarnation matching (wrong start time, boot ID, PID or PPID never match; an exited zombie and a released pidfd don't either);
- refusing a pinned process that isn't our child; child text can't change the incarnation;
- each missing kernel primitive fails closed;
- a descendant holding the pipe, still alive afterwards and invisible to the group scan;
- a same-group helper is visible to the scan;
- a 48 MiB flood, fully accounted;
- multiline, split-write, invalid UTF-8 and escape-sequence framing; truncation;
- the executable allowlist, single use, and a source guard: **no signal-sending call exists in the module**.
- lifecycle (CS01 review): failure after spawn in `pidfd_open` and in `/proc` reads, each reaped with no zombie or fd leak; a live child at the deadline handed off and still writing successfully; a never-pausing read source; a descendant flooding after exit within the one-shot grace, fully accounted; group-scan listing and entry permission failures; one-shot injected read, selector-registration and `waitid` failures while the child is alive.
- dual-stream (CS01 R3 decision): unknown-by-default severity with stream hints; hint and message words never becoming a severity; declared positional prefix after ANSI, with a mid-line level ignored; a declared timestamp prefix; a 40 MiB stdout flood that cannot hide a stderr ERROR (separate budgets, full accounting); a lost buffered stdout tail on SIGSEGV; one stream ending without ending the other; roles; `devnull` vs `held_open` stdin with a fake console, including after a hand-off; the reaper draining both streams.

Thirty-three must-fail mutants are each caught (21 earlier, 12 dual-stream):
1. exit status >128 treated as a signal;
2. "SIGSEGV" text trusted;
3. a wrapper's 0 treated as a crash;
4. draining stopped at quota;
5. the EOF grace re-armed;
6. the group killed on deadline;
7. identity by PID only;
8. the PPID check removed;
9. dropped bytes not counted;
10. the capability gate removed;
11. any signal treated as planned;
12. an exited child still matching;
13. the group scan returning empty;
14. the stream identity taken from elsewhere.
15. a start failure not handed off;
16. the deadline closing a live child's pipe;
17. unbounded draining;
18. group-scan errors propagating;
19. the reaper not draining;
20. an unexpected failure abandoning the child;
21. that failure reported as a plain timeout;
22. content prefixes decoded without a declaration;
23. a hint turned into a severity;
24. a level word anywhere in a line;
25. ANSI not stripped;
26. stdout not captured;
27. a held stdin closed at start;
28. the reaper draining stderr only;
29. the lost-tail flag never set;
30. the timestamp made optional in timestamp mode;
31. one stream's EOF ending the observation;
32. a shared retention budget;
33. blank lines recorded.

## Limits

- **Console capture only.** Stock AzerothCore also routes output to files (`Server.log`, `Auth.log`, `Errors.log`) and possibly the journal. A pipe sees none of that, and those adapters need R0 facts.
- **Redaction:** only ANSI and control characters are removed. That is not production privacy redaction.

- **The reaper is a prototype mechanism, not a service guarantee.** It is a daemon thread that waits as long as the child lives. It ends if the observer process itself exits, and an unexpected error inside the reaper closes our descriptors without guaranteeing collection. The tests show it finishing for finite disposable children only. A real 24/7 supervisor needs an owned-process design chosen after R0, not this thread.

Launch mode A only, disposable children only, Linux only. The kernel facts are genuine, but only for processes this prototype starts itself. Whether the owner's real launch path is mode A at all is an R0 question.
