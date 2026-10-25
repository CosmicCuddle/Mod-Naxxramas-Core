# F15 S4d — Offline replacement-process/readiness decision gate

**SOURCE ONLY / DRAFT / NO OWNER-SERVER ACCESS OR DEPLOYMENT.** Do not treat these tests as real restart verification.

## Goal

F15's restart status must describe whether Worldserver/Authserver actually restarted **and became ready**, not merely whether a shell exited 0, whether GDB wrote a transcript or whether some process started. Prior S3 restart sidecars accept claimed outcomes but cannot independently produce trustworthy outcomes. S4's offline actual-child admission gate also refuses unreliable wrapper and GDB text. This separate S4d *model* establishes the required trust and ordering contract for a future approved host adapter.

This draft is stacked on unmerged CS01-owned **S4c #141**, itself stacked on corrected S4b #140, S4 #139, S3 #137 and S2 #136. New additive files are a source-only Python model, synthetic tests, source-only exact-head CI and this note. Parent and all other developer branches remain unchanged.

## Synthetic state machine

**Start:** a supervisor-fixture supplies a prior crashed child, its death UTC, one new replacement child with different process incarnation, service/host, PID/start timestamp, incident UUID, named attempt and bounded 1–600 second readiness deadline. Validates chronology, names, numeric fields and service consistency. A start only returns `pending`, never `succeeded`. A guessed PID is not a verified child.

**Ready:** only a `readiness-probe-fixture` observation for the **exact replacement ChildRef** with monotonically ordered elapsed time at or before the deadline can return a synthetic `succeeded`. A real adapter must use an owner-reviewed service readiness signal, not a simple PID-exists check or the server's untrusted self-claim. Worldserver and Authserver checks must remain independent.

**Failure:** a trusted-in-fixture actual-child exit before ready, an authenticated-in-fixture deadline timeout, or a late ready event returns `failed`. Early timeouts and unverified events are rejected without mutating state. Once a decision is finalized, late/duplicate readiness cannot change failed to success.

**Isolation:** wrong child/incarnation, old PID, wrong host/service, wrong attempt, GDB transcript, wrapper text and unverified source cannot yield success. Distinct named attempts have independent outcomes. Pending and completed records are bounded by explicit caps (64 and 128 by default); the completed cache is evicted oldest first. **Evicted completions cannot prove global non-replay**. The trusted adapter must provide unique per-invocation IDs, persisted terminal state if required and never reuse an attempt ID.

**NOT implemented:** actual supervisor spawn/wait, process identity proof, ptrace events, systemd D-Bus, login/DB/Worldserver health probes, real wall/monotonic timestamp binding, sidecar publication, subprocess/service control, DNS/network, error-file writing, root filesystem, or server configuration. No real monitor exists. This function does not call the S3 publisher; a future reviewed integration must authenticate all evidence and map the outcome to a single immutable restart attempt safely.

## Required acceptance blockers

1. Owner-approved **read-only** evidence about actual Linux launcher, GDB mode (including whether GDB hides child SIGSEGV), service account, output and existing auto-restart supervisor. Never assume `systemd` directly supervises the binary when a shell/starter/GDB wraps it.
2. Independently authenticated actual-child wait/ptrace provenance, one stable invocation identity across events and process restarts and checks for lost/reordered events after a supervisor crash. A raw GDB transcript/shell exit code is not enough; direct-exec systemd D-Bus may be a candidate only when PID 1 directly waits for the real process.
3. Proven independent Worldserver/Authserver **service readiness**, deadlines and failure classification without interrupting existing restart loops.
4. S2/S3 source compatibility: **never** let the obsolete #136 S2-only collector rewrite a directory containing S3 restart sidecars. Also verify complete operational event-to-sidecar workflow, no fake `verified=True` source and correct clock provenance.
5. Least-privilege secure output broker for intended `/root/cosmic_core/logs/Crash Logs/`, privacy, error reporting, startup/recovery fault-injection and operator-approved backup/rollback/staged S4, explicit consent for S5–S7 live work.

Synthetic tests include duplicate starts, mismatched old/new children, service/host mismatch, premature timeout, exact/late deadline, child dies before ready, stale/forged ready after failure, same-attempt conflict, unverified GDB/wrapper evidence, malformed sources, pending-capacity and 200 bounded completed attempts. CI additionally repeats all existing F15 S2/S3/S4/S4b/S4c tests on the exact head. Test success never proves that Worldserver/Authserver restarted.

## Other project requirements unchanged

The owner-requested first integrated gameplay build remains blocked on **five functional** fixes together: #120 P0/B10 GFPP exactly 120s, human Hunter A02 addon/autocast, stock human-to-human quest-loot correction A04, F12 *old physical* Scarlet entrances/exits #125, F13 Atiesh arrival outside Karazhan #127. Claude leads 60% #125/#127/#132/#133/F14, while Grok is on owner-reported break (#135 frozen). Golemagg A01, NT1, Hallow's End F10, F14 Blood Elf/Draenei and /who, consumables and full historical master backlog remain tracked. All PRs DRAFT, no merges, service/root/config/DB/DBC/Playerbots-local changes.

[Master checklist #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) · [team coordination #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48)
