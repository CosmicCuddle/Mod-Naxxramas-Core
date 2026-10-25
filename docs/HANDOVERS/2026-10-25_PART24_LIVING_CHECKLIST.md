# Part 24 — LIVING DEVELOPMENT CHECKLIST
**Project:** Mod-Naxxramas-Core · **Snapshot:** 25 Oct 2026 · **Maintainer:** CS01 technical PM  
**Read FIRST:** [Complete Part 23 → Part 24 handover](2026-10-25_PART23_TO_PART24.md)

> Keep this checklist current in every Part 24 conversational update. This is a point-in-time **documentation snapshot**; use GitHub [master Issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), [coordination #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48), [Claude queue #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143) and exact CI heads for actual progress. All drafts remain unmerged. Completed source/CI does **NOT** mean completed functionality.

## A. Mandatory first combined gameplay test — all FIVE functionally working

- [x] **P0/B10 #120** individual source/pinned build evidence exists (head `599d1cb`).
- [ ] **P0/B10** verify GFPP exactly **120 seconds** with other 4 required fixes in ONE full build and owner-approved gameplay.
- [x] **A02** technical/negative-protocol research in isolated #134/#135/#146 and N-Core #8; paused Grok v2 #135 frozen.
- [ ] **A02 human-only Hunter pet autocast**: real validated accepted manual ON/OFF, current server-authoritative pet/lineage, fresh boot token/generation/session, bounded HELLO delivery, SelfBot/Playerbot exclusion, functional addon/server state recovery.
- [x] **A04** source audit/model (#122), normal-row candidate (#129), map-scoped guard (#132) only.
- [ ] **A04** obtain one owner-specific anonymized **actual invalid award** (item, quest, source, 2 humans' eligibility, loot method/turn).
- [ ] **A04** implement and test *stock normal human-human group-loot rules* correction including real inventory award and all native alternate paths.
- [x] **F12 #125** original physical Scarlet Cathedral/Armory draft; new safety head `e6d6b09` local tests/compile, startup-only config snapshot.
- [ ] **F12 #125** new head fresh peer review + exact hosted full-link + eventual owner-approved physical entrance/exit/re-entry landing in game. NO Dungeon Finder redesign.
- [x] **F13 #127** outside-Karazhan Atiesh draft; new safety head `b472618` local tests/compile, startup snapshot + no missing-IP fallback on map thread.
- [ ] **F13 #127** new head fresh peer review + exact hosted full-link + eventual owner-approved exterior landing in game.
- [x] **Combined loader/source collision preflight #131** (S1 only); Claude reported unpushed scratch #120/#125/#127/#132/#133 link.
- [ ] **TRUE first combined gameplay candidate:** functional A02 and A04, all five fully linked on ONE exact SHA; independent review, default-safe gates.
- [ ] Owner-approved restorable backups, S5/S6 five-fix gameplay testing and rollback.
- [ ] Merge/release/install only after separate explicit owner approval; NEVER interpret draft as release-ready.

## B. F15 AUTOMATIC CRASH + ERROR REPORTING — HIGH PRIORITY MUST COMPLETE

- [x] S1 source and OS launcher research baseline; actual owner launcher remains UNKNOWN.
- [x] S2 #136 offline immutable crash store 43/43 and narrow Claude review.
- [x] S3 #137 offline immutable restart outcomes and history, peer PASS; **old S2-only writer incompatible with S3 report directory**.
- [x] S4 #139 offline actual-child death admission model, peer PASS; GDB/wrapper false-negative risk remains.
- [x] S4b #140 offline bounded warning/error bursts, 38 new cases, independently PASS on `3a7ee15`, with throttle and bounded per-instance release.
- [x] S4c #141 separate immutable redacted warning/error reports and derived `Error-History.txt`, 24 tests, independently PASS on `656e108`; temp-link recovery.
- [x] S4d #142 model requires same new child plus separate readiness, handles replay/expiry, 37 tests, independently PASS on `d5b7782`; **real durable completion journal/clock validation unimplemented**.
- [x] S4e #147 new isolated read-only S3-completion lookup at `91eb8fc` with [215/215 synthetic offline PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40203613890).
- [ ] **IMMEDIATE:** fix [Claude #147 CONDITIONAL finding](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/147#issuecomment-6399086610): S2 or S3 durable original/sidecar with *abandoned temp hardlink* nlink=2 blocks the new lookup. Reap only genuine private owned temporary entries under shared lock/FD and prove both crash and restart paths; no modification of already approved parent drafts without isolated review. Get new exact-head CI and peer verdict.
- [ ] Reconcile stacked F15 draft branch heads and shared compatible writer design without old S2-only index erasure.
- [ ] Get owner-approved READ-ONLY actual Linux launcher/GDB/wrapper/service-account facts. Do not assume direct-exec systemd or make root changes.
- [ ] Authenticate genuine World/Auth process death, GDB/ptrace and new child identity, restart readiness, error streams, trust clock domain and durable atomic outcomes (not fixture booleans).
- [ ] Design safe quota/backoff, privacy/redaction and independent crash/error history; least-privilege broker for intended `/root/cosmic_core/logs/Crash Logs/`.
- [ ] Actual isolated S4 fault-injected staging after owner approval, then separate S5–S7 backed-up installation and rollback permissions.
- [ ] Demonstrate **actual automatic crash AND error reporting**; synthetic offline counts never satisfy this.

## C. Golemagg, F14 and other module safety

- [x] Golemagg A01 guard #133 `1081445`: hosted pinned solo + combined full Worldserver builds PASS, switch default OFF, early bot-name filter.
- [ ] Prove eight-map-thread lifetime/AI map safety and real named Altbot behavior on later owner-authorized staging.
- [x] Golemagg P5 action-audit #144 `da99ff3`: CS01 source-scope review ACCEPTED for startup config snapshot; source CI success and local 20 tests.
- [ ] #144 exact head hosted full links still IN_PROGRESS at snapshot, verify and review; later runtime approval.
- [x] F14 `/who` S1 #128 source/model 21 tests, and S2 Claude #145 `e07a1e` draft with stock fallback when no IP header, local/native wire tests.
- [ ] #145 exact hosted full Worldserver (PENDING at snapshot), source final review and deliberate F13 base reconciliation; owner provisional own-row and GM-bypass behavior NOT approved.
- [ ] Other F14 visibility: friends/guild/channel/world and addon/bot cross-visibility stage rules.
- [x] Claude map-thread `ConfigMgr` source audit identified other candidates under env-var overrides [Issue #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6399077758).
- [ ] Review and prioritize remaining per-hook ConfigMgr reads **without breaking reload semantics**, especially BotRaidConsumables's intended reload disable. Isolated default-OFF drafts only.
- [ ] NT1, Hallow's End F10, Hunter consumables/ammo, Meeting Stones, previous P1–P4 and remaining historical A/B/F master backlog. Retain all older master items.

## D. Team/project management and safeguards

- [x] [Issue #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143) established by owner direction: Claude **always** has primary + ranked safe backup tasks and advances at review checkpoints rather than idling. Claude acknowledged and has continued with #144/#145/#146.
- [ ] **Part 24 delegation rule:** every Claude assignment explicitly references #143 and includes one primary **plus 2 or more backups**, expected SHA/CI evidence, blocked dependencies and no-go boundaries.
- [ ] Grok **ON BREAK** until the owner confirms return; don't touch Grok-owned #135 or claim active Grok review.
- [x] Preserve exact main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` (unchanged at handover).
- [ ] Before claiming any source/CI pass, refresh and pin exact PR SHA; don't reuse old-head verdict for F12/F13 fixes.
- [ ] Maintain additive [Issue #48 coordination](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48) and [Issue #28 master](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) without replacing history; show THIS checklist's status after **every conversational response**.
- [ ] Never merge/enable/release/run owner server/SQL/DBC/core/IP/Playerbots root/config/service operations or owner test without explicit permission. Preserve two local Playerbots files and `MapUpdate.Threads=8`.
- [ ] Request owner A04 sample and future true launcher evidence only when needed, with readable step-by-step instructions and minimal private data. Offer backups before any later authorized invasive action.

## E. Priority order at Part 24 opening

1. Verify current #147 head/Claude review and **fix abandoned S2/S3 temp-link false rejection** in a separate safe draft; source CI + new peer gate.
2. Review changed #125 F12 and #127 F13 exact heads and hosted tests; don't carry prior S4 verdict. Check #144/#145 hosted statuses and #145's stale F13 base.
3. Send Claude explicit **primary + backup queue** handoff referencing #143: A04 award-path sample dependency, A02 research-only, F15 new review, recent config audit, F14 and F12/F13.
4. Advance A04 native stock correction research and A02 human Hunter protocol safety; never treat test GAP PASS as functional success.
5. Continue F15 owner-approved read-only launcher/secure OS adapter design; keep production permission gate explicit.
6. Update #48 and #28 and include a concise progress table in response.

**Do not turn any unchecked owner/runtime item to checked based solely on Python tests or a Worldserver link.**


## F. Part 24 live checkpoint — 25 Oct 2026 (additive, supersedes old status snapshots)

- [x] CS01 read both Part24 transition documents, refreshed exact PR heads and current Actions. No merge/install/owner-server changes.
- [x] **F15 #149 NEW ISOLATED DRAFT** current `ac8558af26bf980baf68c9fafe59b534df955c3a`, stacked on untouched #147 `91eb8fc`, adds narrowly locked/private same-inode S2/S3 abandoned-temp recovery and 8 synthetic regression test methods. This is an **authored fix awaiting proof**, not a passed or operational system.
- [ ] **F15 #149** inspect latest exact-head hosted workflow and obtain Claude independent CONDITIONAL/PASS verdict after hostile-alias, crashed-writer and replay review. F15 real Linux crash + error reporter, authenticated process/death/ready, least-privilege root broker, GDB/wrapper, backup/rollout S4–S7 all remain unfinished and owner-gated.
- [x] **F12 #125** `2294a147` documentation-only over code `e6d6b09`: CS01 [source review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/125#issuecomment-6399331923) accepted only the startup-snapshot ConfigMgr change. **No current-head hosted link or physical gameplay PASS**.
- [x] **F13 #127** `31f312b5` documentation-only over code `b472618`: CS01 [source review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/127#issuecomment-6399332335) accepted only startup snapshot and no missing-IP map-thread fallback. **No current-head hosted link or exterior-Karazhan gameplay PASS**.
- [ ] F12/F13 current exact-head pinned Worldserver builds and old physical Scarlet (not LFG) / Atiesh outside Karazhan S5/S6 tests.
- [ ] **#144 Golemagg** dedicated pinned link still in progress when checked (3 of 4 workflow runs were success); **#145 F14** dedicated link pending (7 success, one in progress, eight pending among 16 run objects) and needs deliberately reconciled newer F13 parent before integration. No owner runtime proof.
- [x] **CS03 Claude assigned PRIMARY #149 review + four ranked SAFE BACKUPS** in [queue #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6399369451). Complete a checkpoint and advance unblocked backup instead of idling in an active session. Grok #135 frozen while owner-reported on break.
- [x] Additive [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6399370192) and [coordination #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6399369826) checkpoints posted. No historical item removed.
- [ ] **FIRST FIVE-FIX PLAYABLE GATE STILL UNMET:** P0/B10 exactly 120 seconds, human A02 real pet ON/OFF, A04 real human-human quest-loot stock correction, F12 original physical Scarlet portals, F13 Atiesh exterior Karazhan, all in ONE pinned/restorable independently verified and explicitly owner-approved build. A02/A04 functional blockers remain. No owner server changes made.
