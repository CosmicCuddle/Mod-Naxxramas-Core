# F15 S4c — Immutable independent warning/error reports (OFFLINE DRAFT)

**DO NOT MERGE, DEPLOY OR RUN AGAINST AN OWNER SERVER.** No live launcher, log capture, GDB, Authserver/Worldserver process, root path, SQL/DBC or config files involved.

## Exact stacked foundation

This S4c CS01-owned draft is stacked on **#140** S4b bounded error burst policy, **#139** S4 actual-child evidence model, **#137** S3 immutable restart sidecars and **#136** S2 immutable crash-store primitives. Four additive paths: a Python offline redacted error report store, synthetic tests, exact-head workflow, this design note. All parent drafts stay unchanged/unmerged. S3 offline source peer PASS **requires S2+S3 fully compatible deployment**; an old S2 writer can erase the S3 projection. S4 offline evidence peer PASS does not authenticate real death or solve GDB false negatives.

## What this actually does

- A caller constructs ErrorBurstObservation from the **synthetic S4b BurstAlert**, supplies canonical UTC-second observation and boolean fixture verification. **Caller-set verification is not an authenticated Linux/log stream source**; nothing here reads logs.
- An identity derived from process incarnation, service, source stream, severity, safe error-category, configured threshold, window and monotonic burst-emission uptime gives one immutable report per burst. Repeating an identical event is idempotent. Same identity with conflicting timestamp/text cannot overwrite a finalized report.
- Uses S2/S3 inherited pre-existing-private-directory descriptor pinning; common flock lock; bounded fsynced temp; atomic no-clobber hardlink; fsync directory; then atomic derived summary replacement. No mkdir, subprocess or configured output path.
- Error reports are named independently from crash and restart files, with separate **Error-History.txt**. It counts Worldserver/Authserver and WARN/ERROR separately. **Crash-History.txt and S3 restart sidecars are not touched by publish_error or rebuild_errors.**
- Files include only bounded safe metadata, no raw log text, player identifiers, passwords or private excerpts. SHA-256 trailer is a corruption/integrity consistency check, **NOT authentication**. Symlink, unsafe ownership, public permissions, extra hardlinks, malformed filename, tampered content and implausible future UTC are marked invalid and excluded from verified counts.
- A crash/error summary index can be deleted or suffer an injected replace failure; the immutable report remains available and may rebuild. Separate future operator notes must never mutate reports.

## Remaining important risks

1. This is a **synthetic offline storage model**. Both actual Linux child-exit provenance and per-process log-stream authenticity are missing. The booleans supplied to this model can be spoofed by callers; never forward untrusted app/journal texts as trusted evidence.
2. This only stores categorized bursts. It does not capture individual unique errors, stack traces, repeated exceptions separated by thresholds, private sanitized excerpts or *real* GDB crash output. Comprehensive F15 reporting requires reviewed real-source adapter and privacy policy with the owner.
3. Root destination remains intended as /root/cosmic_core/logs/Crash Logs/ but **no code opens/creates that path**. Actual permission-separated broker, secure admin read access and operator redaction/retention/quota/rotation require explicit owner approval and fault-injected staging.
4. Native source class reuses S3 to avoid mixing old S2 writer and S3-format history. Actual complete S2+S3+S4+S4b+S4c integration must use ONE compatible writer and persist tracker sequencing across restarts or clearly document loss. Here only immutable error records persist; S4b counters are in memory.
5. SHA-256 is not an HMAC or attestation. A malicious actor with write access as the report owner can forge bytes/hashes. Deployment requires permissions, supervisor source authentication and independent operator trust review.
6. Wall-clock skew is bounded (+5m at publish/read), but a persistent bad clock can wrongly exclude old observations or change derived index later. Trusted monotonic + UTC time source proof remains in S4 adapter plan.
7. No owner actual launcher or GDB mode has been discovered. GDB wrapper may return 0 after server SIGSEGV, making a naive actual-child-wait policy falsely miss crashes; direct-exec systemd status must only be trusted if it genuinely waits on the server, never a wrapper. No final choice before read-only owner evidence.

## Required regression coverage

Separate report creation, mode 0600, SHA and metadata privacy, World/Auth and WARN/ERROR counts, multiple bursts, idempotence and conflict, unknown/unverified input, UTC future, filename injection, corrupted file, symlink and hardlink, index reconstruction after deletion, injected index-write failure durability, cross-process concurrency under flock, and invariant that crash history/restart flags do not change. Hosted CI also repeats all S2/S3/S4/S4b model tests on the same exact SHA. **These are NOT in-game, real Linux or real supervisor tests.**

## F15 and gameplay readiness remain separate

Operational F15 still requires owner read-only discovery, authenticated crash/death/restart/readiness and bounded real log streams, least-privilege output broker and full staged failure injection, then owner-approved backed-up S5–S7 deployment, rollback and live acceptance. Nothing changes on user machine. The first combined gameplay test still needs FIVE FUNCTIONAL #120 P0/B10 (GFPP 120s), human-only A02 Hunter autocast, actual A04 human-human stock quest loot, F12 physical Scarlet entrances/exits and F13 Atiesh exterior, in one reviewed Worldserver before owner-authorized testing. Golemagg A01, NT1, Hallow's End F10, F14 Blood Elf/Draenei /who, consumables and historical A/B/F backlog remain in Issue #28.

Grok remains on an owner-reported break (do not touch #135); Claude retains lead engineering work and selective source reviews. Team coordination Issue #48 and complete master checklist Issue #28 remain authoritative.
