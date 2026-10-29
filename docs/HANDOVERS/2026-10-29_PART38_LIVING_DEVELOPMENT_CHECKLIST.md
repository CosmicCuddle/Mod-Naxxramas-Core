# Mod-Naxxramas-Core — Part 38 Living Development Checklist

**Opened:** 29 October 2026 UTC. **Research/documentation-only continuity; NO operational authorization.**

Read BOTH the [complete Part 37 → Part 38 handover](2026-10-29_PART37_TO_PART38.md) and this entire checklist before working. For original full evidence and chronology also read [Part 37 Living Checklist](2026-10-29_PART37_LIVING_DEVELOPMENT_CHECKLIST.md). This is a living checkpoint; refresh live refs and record any later discoveries here.

## A. First actions and safety

- [x] New Part 38 docs branch created from exact latest Part 37 docs DRAFT #231 commit 878ea0d6cd77be4a1289678c6eb02eba9433d36f; new handover/checklist only, historical docs untouched. Verify the final new DRAFT PR head after creation.
- [x] Live Mod main **80e9de1c39a6dc995188a80c31a5e785d0f2a6f9** and private N-Core main **74e45933454385b3b1168bf2c03da34ee1027985** independently refreshed and unchanged. They remain project no-write even if GitHub API says protected=false.
- [x] Frozen integration DRAFT [#160](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/160) **a7523ebb823169edc969d971d00aa293119f2f05** unchanged, unmerged.
- [x] Part 38 startup: reread both complete documents and independently refresh current GitHub HEADs, changed paths, original hosted CI/logs, master [#28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), Claude [#143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143), Grok [#48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48).
- [ ] **Owner safety:** no protected-main/frozen-PR edits, merge, server start, installation/deployment, private client/character/DB/SQL/DBC/config changes, Worldserver activation, upstream core/Playerbots/IP modifications, or changes to **MapUpdate.Threads=8** without explicit separate owner approval and dated restorable backups, verified restoration and rollback.
- [ ] **Mandatory owner-accepted gameplay remains 0/5.** Source-only, synthetic TSAN, CI and native link never count as a gameplay pass.

## B. P13 HonorOverflow R1–R8

- [x] R1–R6 original source identity and config-masked Playerbots witnesses complete; avoid duplicates. R6 [#227](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/227) restored head b1cd662544bad11967c0c5decadc36dbb9ffead0 green at original hosted CI. Source default HonorOverflow ON versus project default OFF expectation; installed effective config unknown.
- [ ] Owner H-DEFAULT, H-SELFBOT and H-REMEDIATION all **UNSELECTED**. Do not enable payouts, reinterpret bot identity, change defaults, fix sources, retry money or compensate accounts.
- [x] R7 [DRAFT #229](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/229) head 1fdcd96ca73b0143c6108f4784b2c24cc0bfd139: global unsynchronized HonorOverflow unordered_maps accessed from different-map worker callbacks, credible potential race, not observed server incident. **Release hold remains.**
- [x] R8 [DRAFT #232](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/232) head 7a904433f9326ef4ecc502d2252043a3b95f30b4: audited standard GM/CLI/RA/SOAP config reload is serialized before/after map worker join. No normal-route overlap witness; custom callers not exhaustively audited. Original hosted push 40874910206/PR 40874920964 green at exact head.
- [ ] Any future R7 ownership/lock order, exact-once transactions and BG end/leave summary safety require owner design approval before a production edit.

## C. P13 R9 — latest reconnect and lease models

- [x] [DRAFT #233](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/233) exact latest head **1f20d3e28398fff0255b2d2d8d1a1f1fed28faa4**: only 3 added test/doc/CI paths. Alternatives A world-owned queue, B single mutex, C per-GUID serialization **all unselected**. Original queue retains unbounded quarantine; separate bounded synthetic admission has invented leases (not core API).
- [x] **NEW real source finding:** pinned Grimfeather offline session recovery can reattach SAME Player object to a new network WorldSession with CONFIG_ENABLE_LOGIN_AFTER_DC; it does NOT call new Player OnPlayerLogin. **Socket reconnect is not necessarily new Player lifetime.** R9 synthetic reconnect tests preserve snapshot/BG pending until true player retire/new DB Player; 4 additional source drifts, RECONNECT_ROTATE/RECONNECT_CLEAR mutants.
- [x] Current-head original [push 40885156678/job 123486769113](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40885156678) and [PR 40885169741/job 123486814802](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40885169741) both successful, original complete **813-line** logs reviewed in Part37; 9/9 test-only mutants, C++17/20, ASan/UBSan and synthetic 8-worker TSAN. No production or game parity claim.
- [ ] Verify actual authority for stable Player lifetime, redirect/logout, map migration, shutdown, BG summary flush and world-safe Player resolution. Owner reconnect setting unknown; no real leak proven.

## D. P13 R10 — new real-source money mismatch

- [x] [DRAFT #235](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/235) exact head **b1e355874ad8a06c507e3e85bf925450d728392b**, 3 newly added source tests/docs/CI paths from unchanged main. HonorOverflow reports **proposed** rewardCopper although it ignores the bool result of actual Player::ModifyMoney. Original core uses a strict cap inequality and trial-cap rejection; conditional mismatch possible, **not observed on owner server**.
- [x] Original current-head [push 40886916434/job 123493010867](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40886916434) and [PR 40886926843/job 123493046232](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40886926843) green, complete **613-line** original logs read per Part37. Seven illustrative original-body cases, 3 proposed-vs-actual differences and 4 matches, 4 drift mutants. Synthetic caps/rate not owner values.
- [x] Early failed CI 40886782709 was TEST REPORTING substring error (MATCH inside MISMATCH); corrected at tested head, not a live bug.
- [ ] Next: research distinct source-only **exact credited currency vs proposed award**, BG summary, cap/trial and interaction with R7/R9. Do not patch core or money automatically, grant compensation, or select H-REMEDIATION.

## E. F14 Claude and K1 Grok

- [x] F14 P12 [#224](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/224), P14 [#228](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/228), P15 [#230](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/230) original source CI verified, no wiring.
- [x] NEW F14 P16 [#234](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/234) exact **fe5123d07b26cf24e1927265a7c33a1fe571488e**, six test/docs/CI paths. Original [CI 40881516749/job 123473967298](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40881516749) green 689-line log, 13/13 source facts and negative fixtures, 12-case real name-query source counterexample, 5/5 mutants. /who-only race hiding cannot hide race in name queries and certain public fields/models; source-only, no client behavior tested.
- [ ] Owner F14 policy A/B, masked SelfBot M1–M4, maxAge and NEW goal **/who-only vs general race concealment** UNSELECTED. **F14 OFF / UNWIRED**. No packet rewrite or enabling. New Claude assignments require genuinely active separate-session ACK.
- [x] K1 individual Hunter pet settings must **fail closed** for ambiguous restored/reused pet identity. ACK means stored not applied, postcombat fresh current-pet prompt and separate protected human click. N-Core native NoWrite and relay OFF; D18 already-armed in-combat Pet A→B **HARD NO-GO**; BOOT-3d/D17/W1 held.
- [ ] K1 Step1 documentation/synthetic tests **NOT BEFORE 1 November 2026**, no C++/addon/SQL/runtime tests or installs. Grok latest original Lua click source research [#48 comment 6498281421](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6498281421) is not real-client proof.

## F. Remaining project and continuing handover

- [ ] A04 genuine two-human Need/Greed/receipt/overflow H1/H2 NOT accepted; mandatory owner gameplay **0/5**. P11 native pinned link and P10 source parity historical success do not authorize deployment.
- [ ] LAB-004 mining and LAB-005 Shaman tank four brand-new totems, Tempest Shield physical shield imbue, Earth Pulse/Stonehide and classic Earth Shock/Rockbiter are **brainstorming only**; no numeric/spell/DBC implementation approved.
- [ ] New engineering: pre-register separate bounded source-only task on #28, isolated DRAFT, exact parent/HEAD and changed paths, full original hosted logs and caveats; avoid repeating prior green tests. Document all new evidence in this Part38 checklist without overwriting concurrent changes.
- [ ] Before chat limit, prepare complete Part38 → Part39 handover and next living checklist.

**End Part38 startup checklist. No merges, installations, gameplay approval or release authority.**


## G. Part 38 active engineering — P13-R11 (29 October 2026 UTC)

- [x] **Both Part 38 docs reread IN FULL** from exact opening #236 head 1b425dfb1e1a8912b140571ea39cdf6e7346d641. Independently refreshed live Mod project-no-write main 80e9de1c39a6dc995188a80c31a5e785d0f2a6f9, private N-Core no-write main 74e45933454385b3b1168bf2c03da34ee1027985, frozen #160 a7523ebb823169edc969d971d00aa293119f2f05, and previous R7 #229, R8 #232, R9 #233, R10 #235, F14 #234, all unchanged/open DRAFT. Part38 #236 remained DRAFT, unmerged, original exact two Markdown paths; update below is documentation-only.
- [x] Refreshed original coordination #28 (latest at startup comment 6499019557), #143 (P16 active-session success at 6497897419), #48 (K1 design/evidence, current issue update 29 Oct 13:41 UTC). Other sessions are NOT activated by comments. No new F14 product scope, K1 before-1-Nov work or policy presumed.
- [x] **New DISTINCT P13-R11 pre-registration** [#28 comment 6499278191](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6499278191) BEFORE authoring. Isolated additive-only [DRAFT #237](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/237) at exact **b2cb80c73e99b791581e2763fca756b008893f86**, based on immutable Mod main 80e9de1c; exactly 3 NEW paths: tests/test_p13_r11_rejected_award_lifecycle.py; docs/research/P13-R11-REJECTED-AWARD-FINALITY.md; .github/workflows/naxx-p13-r11-rejected-award.yml. No production src/conf, core, SQL/DBC, client or owner-host edits.
- [x] **New source-conditional finality finding:** Original ProcessHonorOverflow advances HonorSnapshots.TodayContribution BEFORE calling ModifyMoney. Failed positive credit followed by unchanged contribution does NOT reattempt the rejected award; later newly earned honor starts a separate attempt. Original core calls OnPlayerMoneyChanged BEFORE trial/ordinary cap rejection, so a script callback can be invoked in a failed-credit path; no real hook side effect/owner impact established. BG end/leave both use force=true then SendBattlegroundSummary, which erases pending summary before notification checks. This extends prior R10 proposed/credited mismatch with multi-event lifecycle semantics. Does **not** select automatic compensation or a retry policy.
- [x] **Exact-head hosted R11 evidence independently fetched and FULL raw logs read:** [push 40891426725 / job 123508962932](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40891426725) **SUCCESS, 600 original lines**; [PR 40891464364 / job 123509103503](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40891464364) **SUCCESS, 600 original lines**. Both at b2cb80c73e99b791581e2763fca756b008893f86; source blob and three-path checks pass; literal original method slices compiled/executed C++17/C++20/UBSan with DUMMY Player/World/Session/ScriptMgr; 3 time-sequence assertions groups and 6/6 negative source-drift guards. This is NOT owner runtime, native entire Worldserver, actual game output, full race/lifetime proof or gameplay acceptance. The mutant log label "hook after trial check" represents removal of the pre-admission hook in this fixture, not an actual relocation test.
- [ ] **Open:** P13 H-DEFAULT, H-SELFBOT, H-REMEDIATION, exact-once economics/failed-credit treatment, unproven core-hook reentrancy and real BG callbacks/Player lifetime. R7 shared-map potential concurrency release hold unchanged; R9 synthetic leases not native API. K1 Step1 not before 1 November, F14 scope unselected and unwired.
- [x] **NO-GO reaffirmed:** No merges, real Worldserver, SQL/DBC, production/client/N-Core/MapUpdate.Threads edits. N-Core NoWrite, relay OFF, pet D18 already-armed A-to-B HARD NO-GO; mandatory **owner gameplay 0/5**.
