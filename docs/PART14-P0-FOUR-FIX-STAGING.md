# Part 14 P0 Four-Fix Source Staging — NOT AN APPROVED INTEGRATION

Staging preparation only. No final combined PR yet, no runtime, no merge, no installation, no SQL/DBC/client work, no release artifacts.

**Source baseline:** `main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`.

Exact PR source versions:
- GFPP 120 seconds: #98 `5f13ffa668bc9a2118dc5db328242d9f507a29c5`
- Warlock ritual: #99 `afa09b0f557ca644f540f61b19500e5ff7ecf7ed`
- Shaman totems: #100 `ce33fb5e0068d27854f77237098b7cbc37a54cc4`
- Golemagg reach guard: #101 `987bfac6b21e4e87a877a5ada51e0b05f55e2449`

Four independent PRs touch **17 unique source paths / 19 path instances**.
Two overlaps have been reconciled, without silently selecting one PR's whole file:

1. `src/Systems/BotRaidConsumables.cpp`: start with #100's no-permanent-totem-grants version; apply exactly three unique #98 90-to-120-second timer/comment changes.
2. `conf/mod_naxxramas_core.conf.dist`: start with #101's default-OFF one-name Golemagg config; apply exactly three unique #98 GFPP 120/240-second config wording changes.

All other 15 paths are copied using their **original Git blob SHAs**, so their contents are byte-for-byte identical to the specific individual PR heads. Source-only integration smoke checks added at `tests/test_part14_four_fix_staging.py` verify both overlap resolutions and key Warlock/Golemagg contracts.

**Explicitly excluded:** NT1 experimental PR #102, historical Hunter-autocast experiments and all other unfinished backlog code; they have independent reviews and separate approval gates.

**Outstanding before final combined draft:** #98, #99, #101 full linked Worldserver CI completion, exact-head peer review closure, current-main confirmation, new combined source/native/real pinned full Worldserver CI plus CS02/CS03 complete independent integrated diff reviews. No synthetic proof implies live behavior. Later, owner must separately approve protected-main merge and one host recompile/pilot. Default OFF and empty one-bot allowlist must remain fail-closed.

This staging branch is an internal source assembly checkpoint, NOT final user acceptance or approval to test live.
