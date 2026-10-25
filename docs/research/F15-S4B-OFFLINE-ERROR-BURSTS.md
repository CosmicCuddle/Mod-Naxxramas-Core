# F15 S4b — Bounded warning/error bursts (OFFLINE / DRAFT)

**DO NOT MERGE / INSTALL / ENABLE / APPLY TO THE USER'S SERVER.** No actual log tail, process observer, deployment, binary, root-path creation or production event report exists here.

## Motivation

F15 must eventually report **errors and abnormal deaths**, not only fatal crash incidents. Warnings and repeating errors cannot be treated as Worldserver crashes; a log message saying that a process crashed is not authenticated evidence that an actual process died. High-volume logs also cannot flood the report directory or retain unbounded/private messages.

This small S4b research draft is stacked on our CS01-owned S4 source-only [#139](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/139), which in turn is stacked on #137 S3 and #136 S2. It adds exactly one in-memory pure policy class, synthetic tests, a source-only GitHub Actions workflow and this note. No parent/other developer branch edits.

## Model semantics

A synthetic LogEvidence has an explicit service (worldserver/authserver), process incarnation identifier, stream (stdout/stderr/world-log/auth-log), severity (WARN/ERROR), allowlisted category code, monotonically increasing sequence number and per-process elapsed milliseconds. `source="verified-stream-fixture"` and `verified_stream=True` are **untrusted caller assertions** in this OFFLINE fixture: they do not constitute OS authentication. Production validation must independently bind log bytes to a known process invocation and control the origin.

- Default threshold: 3 events in an inclusive rolling 60,000ms interval, separately for each process incarnation/stream/level/code. A single synthetic burst triggers one summary. Continued high-rate noise cannot trigger repeated reports; the category rearms as soon as the rolling in-window count drops below its threshold, even when a slow trickle prevents complete quiet.
- Sequence strictly increases per (service, instance, stream); replay/duplicate/out-of-order sequence is rejected. A sample with backward uptime is rejected rather than generating false bursts.
- Invalid category fields, injection/newlines, unexpected severity/stream, noncanonical names, bad integer/boolean values, non-evidence inputs and wrong source are refused without mutating counters. Both service groups remain separate.
- Finite `max_groups=256` and `max_streams=128` default caps, with bounded per-group deque of at most the threshold number of timestamps. At capacity, new groups return a visible **capacity** status rather than silently evicting evidence or using unbounded memory. A new synthetic InstanceExit / finish_instance API reclaims all stream and category slots for a verified-in-fixture ended process incarnation and retains a bounded tombstone queue to reject stale queued events. **Its caller-set verified_actual_exit is NOT OS-authenticated**; future adapters must prove child exit and drain the stream before calling it. This fixes Claude's 200-process-restart capacity witness without claiming real process monitoring.
- No raw message/body, credentials, player names, IP addresses, other human/user data, or log text is accepted or stored by this model. A burst output carries only category and bounded metadata. A later owner-approved privacy policy will decide whether/how sanitized real error excerpts may be included.
- No disk writes; no `Incident`, `Crash-History.txt` or S3 restart state mutation; warning/error bursts are not additional crash incidents. Publishing independent immutable warning/error files and a separate error-history summary are **future reviewed work**, not implemented now.

## Production design questions and blockers

1. Owner-approved **read-only** discovery of actual launch/supervisor/GDB mode, stdout/stderr routing, world/auth log configuration, service account, rotation/restart semantics and log storage. Do not assume a systemd unit or scrape a guessed root path.
2. Future adapter must authenticate process incarnation, stream origin, sequence and uptime or monotonic order, detect log rotation/truncation and duplicate stdout/logging echoes. Never accept caller-set booleans as proof.
3. Error categories should be selected from trusted parsing rules, not untrusted arbitrary raw messages. Real warning/error sources must be bounded, redacted and owner reviewed; the user's requested individual reports and derived history require independent secure immutable report schema and testing.
4. Unknown/overflow/invalid events must be visible without fabricating a crash; operator-readable throttling, restart persistence/re-arm semantics, collector crash recovery and clock-skew policies require staging design.
5. Owner's exact intended output destination `/root/cosmic_core/logs/Crash Logs/` and existing auto-restart **must not be modified** without explicit owner approval, least privilege and tested rollback. SQL/DBC and local Playerbots files are never in scope.

## Synthetic verification

```bash
python3 -m unittest -v tests.test_f15_error_bursts_s4b
python3 -m unittest -v tests.test_f15_exit_evidence_s4 tests.test_f15_restart_sidecar_s3 tests.test_f15_offline_store_s2
```

Regression cases: threshold boundaries, continuous flood suppression, slow-trickle-to-new-burst rearm, 200 ended process incarnations with verified-fixture cleanup, old-instance replay, unverified-exit refusal, codes/severities/services/streams/instances isolated, duplicate/replay/backward clock negative, unverified log-source rejection, malformed/unhashable fields, caps, privacy and no crash/restart contamination. GitHub CI runs the inherited suites on the exact same SHA without the owner's server or accounts. **Passed unit tests are not F15 S4 staging or working automatic monitoring.**

Tracking: [Master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) and [team Issue #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48). Grok is on owner-reported break; do not touch #135. Claude retains lead 60% feature workload and peer-review reservations. First functional combined gameplay build requires P0/B10 #120 GFPP 120 seconds, actual A02 Hunter addon/server autocast, actual A04 human-human quest loot, F12 old physical Scarlet and F13 exterior Atiesh, all working together.

## 25 Oct independent review resolution

Claude [CONDITIONAL review in PR #140](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/140#issuecomment-6398267997) identified two formerly missing negative cases: a slow 50-second trickle could indefinitely suppress fresh bursts, and memory capacity could never recover after repeated World/Auth restarts. The isolated current draft changes the rearm test and adds bounded, explicitly verified-in-fixture instance retirement; five regression tests include **200 distinct process lifetimes**. Prior 127/127 and earlier peer verdict DO NOT carry to the updated SHA; independently review updated head. The bounded retired-incarnation cache is not proof of real kernel process identity or persistence across collector restart.
