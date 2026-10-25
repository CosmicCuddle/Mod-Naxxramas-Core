# Part25 P0 + F12 + F13 + F14 source assembly (REVIEW ONLY)

**Status: isolated DRAFT. No merge, owner installation, live host access or gameplay acceptance.**

## Exact component lineage

1. Canonical P0/B10: PR #120 at 599d1cbb211e6f108a2a6ff9fec78242ffe7a37c; source retains GFPP 120 seconds, thread-safety and Golemagg guard.
2. Physical Scarlet Cathedral and Armory F12: original unmodified source/test/docs from #125 at 2294a147fcd7733e6bff28cd3902352cf7b5fabd.
3. Atiesh Vanilla exterior Karazhan F13: original unmodified source/test/docs from #127 at 31f312b5fe1678ea7aaf3fa935b9b00802a320c1.
4. Blood Elf/Draenei Vanilla-stage /who F14: original unmodified source/test/docs from #145 at e07a1e18f7525f8b2c0d1bb6215e31c985717540.

Git trees reuse the nineteen actual reviewed feature blob SHAs, not recoded or translated copies. The independent five-test suite pins all of them and key production P0 blobs. Loader modifications are strictly the addition of F12, F13 and F14 script declarations/calls, preserving every P0 registration including the Golemagg guard and BotRaidConsumables. It verifies this by stripping the three lines and hashing the original loader. Configuration preserves the exact first 19,381 bytes of #120 and appends the three reviewed F12/F13/F14 default-OFF sections. No runtime switch is enabled.

## Source and build proof

The new exact-head hosted workflow checks five original source-assembly tests, each F12/F13/F14 source-contract Python suite, native policy tests in both C++17/C++20, the native pinned WHO-handler fingerprint, and a full Worldserver compile/link against immutable public Grimfeather AzerothCore, pinned Playerbots and Individual Progression. Final symbol checks require BotRaidConsumables, Golemagg guard, Scarlet, Atiesh and WhoListing in the SAME executable. Neither host processes nor private databases/log files are used. A new full build MUST be observed green at the actual head before this candidate is considered build-ready.

## What this is NOT

F12/F13/F14 are still OFF until separately owner-authorized actual gameplay. This is NOT a completed five-fix package. A02 human Hunter accepted ON/OFF remains blocked on durable pet identity, real N-Core transport and human-versus-bot exclusion. A04 real human-human quest loot remains unproved, preserving stock group-loot rules. F15 real automatic Worldserver/Authserver crash AND warning/error reporting is also NOT operational. GFPP source 120 seconds is not a stopwatch test.

Do not merge, deploy, change MapUpdate.Threads=8, touch the owner server/root/services/config/SQL/DBC/core/IP/N-Core/locally modified Playerbots or publish private source mappings. Later backed-up rollback-safe operator staging and gameplay require explicit owner approval and independent Claude peer review.
