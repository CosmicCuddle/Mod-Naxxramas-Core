# Mod-Naxxramas-Core — Part 37 Living Development Checklist

**Opened:** 29 October 2026 UTC. **Status:** active documentation-only continuity for owner-controlled research and isolated DRAFT code/test work; **not a gameplay/release checklist approval**.

**Mandatory reading:** [Complete Part 36 → Part 37 Handover](2026-10-29_PART36_TO_PART37.md) AND this complete checklist. For detailed original job logs and historical progression read the [Part 36 Living Checklist](2026-10-28_PART36_LIVING_DEVELOPMENT_CHECKLIST.md) (sections A–P) plus [P13 decision packet](../research/P13-HONOROVERFLOW-IDENTITY-DECISION.md). This new checklist intentionally separates DONE source proof from OPEN policy/real-world requirements.

## A — FIRST / Part 37 startup verification

- [x] Handover authored as a NEW file on isolated documentation-only branch `docs/cs01-part36-to-part37-handover-20261029` branched from exact prior docs-only DRAFT #220 `c5f4d2d39f08ecadfdf4e08048658962df4cb24f`; historical Part 36 documents untouched.
- [x] **Part 37 startup 29 Oct UTC:** BOTH complete docs read; independently refreshed Mod/N-Core main SHAs, frozen #160, DRAFT #220/#231 and live P13/F14 heads, master #28/Claude #143/Grok #48; re-fetched P15 exact-head 1,025-line original job log and new P13-R8 original hosted CI. **Important GitHub API finding:** both project-protected mains report GitHub branch API `protected=false` (rules not technically enforced there); project DO-NOT-EDIT policy unchanged.
- [ ] **Owner project safety:** no merges, releases, installers, build activation, owner Worldserver, client/characters/items/DB, SQL/DBC, upstream core/Playerbots/IP edits, config flips, new runtime hooks or changing `MapUpdate.Threads=8` without scoped permission, dated restorable backups, proven restore and rollback. GitHub discussion posts do not start Claude/Grok sessions.
- [x] Last independently checked at handover: protected Mod `main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, protected N-Core `main@74e45933454385b3b1168bf2c03da34ee1027985`, frozen DRAFT #160 `a7523ebb823169edc969d971d00aa293119f2f05`; all untouched.
- [ ] **Owner-accepted gameplay remains 0/5.** Do not count CI, mock tests or Worldserver linking as acceptance. A04 H1/H2 exact two-human private Need/Greed/receipt/overflow unverified. No gameplay greenlights.

## B — P13 HonorOverflow identity evidence: source-test CLOSED, policy OPEN

- [x] Pinned module `HonorOverflow.cpp` predicate uses `GET_PLAYERBOT_AI`, which masks an attached PlayerbotAI when `Playerbots.Enabled=false`. Actual source-conditional false-negative **not a live award incident**.
- [x] [P13 original DRAFT #219](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/219) source witness, 11 strict C++17/20 synthetic scenarios, original PR run `40764828891` SUCCESS.
- [x] [R1 #221](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/221) `ef2292b`: reload mask/default check 7 cases per standard; both original CI events SUCCESS. **Unexpected distributed/source default ON** versus project preferred default OFF remains owner question.
- [x] [R2 #222](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/222) `49cb8de`: registered player destruction cleanup conditional skip, 9 cases per C++17/20, both hosted CI green; alternate lifecycle unknown.
- [x] [R3 #223](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/223) `2db985c`: bulk logout and per-bot disabled getter guard; 9 cases per standard, both CI green, mock logout stub not production WorldSession.
- [x] [R4 #225](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/225) `11d8885`: `IsRealPlayer` and `IsSelfBot` masked helper false-positive, 8 cases per standard, both original CI green.
- [x] [R5 #226](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/226) `8ccf3f4`: pinned Grimfeather const `IsHeadless` is no-socket flag; 10 C++17/20 cases, both hosted events green; client-backed masked SelfBot not solved.
- [x] [R6 #227](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/227) **current repaired/restored head `b1cd662544bad11967c0c5decadc36dbb9ffead0`**, exactly original two test/CI files; latest push `40867396609` and PR `40867401693` both original logs green at CURRENT head; 15 literal C++20 RandomBot/AddClass membership scenarios. Source classification still partial. **No duplicate R6 branch, test or PR**; previously concurrent duplicate two files were deleted safely. Original historical tested head `3a1b8b2` + failed YAML/fixture parser infrastructure fixes are transparently recorded in Part 36.
- [ ] **H-DEFAULT owner choice NOT selected:** source/distributed `HonorOverflow.Enabled=1` vs project default-OFF release expectation. Actual installed effective config UNKNOWN. [Decision packet](../research/P13-HONOROVERFLOW-IDENTITY-DECISION.md) D0/D1/D2 are options, no auto-edit.
- [ ] **H-SELFBOT owner choice NOT selected:** classify config-hidden/inert-but-attached SelfBot as bot-ineligible, human-eligible, or hold until certain for **money**, independent of F14 display rules.
- [ ] **H-REMEDIATION owner choice NOT selected:** only a proposed, separately authorised future source-of-truth identity API/ledger/policy after all user/bot cases and lifecycle/thread ownership are understood. **DO NOT** blindly use `IsRealPlayer`, `IsHeadless`, Random/AddClass account flags or F14 M1 for payout decisions.
- [ ] No actual owner Worldserver full reload sequence, retained AI map after real player teardown, honor/copper award, account behaviour, or money-cap acceptance observed. Other unknown lifecycle mechanisms may mitigate synthetic state.

## C — P13-R7 unsynchronized shared-map potential race (NEW release-level hold)

- [x] Independently pin `Grimfeather@8daffdabe9202c228e45d833c9a1d399597a15cd` threaded update chain `MapUpdate.Threads` -> `MapUpdater` -> `Map::Update` -> `Player::Update` -> `ScriptMgr::OnPlayerUpdate`. Source module `HonorSnapshots` and `BattlegroundHonorSummaries` are namespace-global unsynchronized `std::unordered_map`; worker callbacks can potentially overlap.
- [x] [R7 test-only DRAFT #229](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/229) exact `1fdcd96ca73b0143c6108f4784b2c24cc0bfd139`: only 2 test/CI paths, original [push 40864302158/job 123415039262](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40864302158) 538-line log SUCCESS and [PR 40864357128/job 123415230311](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40864357128) 551-line log SUCCESS. Both strict UBSan C++17/20 source-extracted helpers used **single thread**; tests identify potential shared-map race source topology, **do not provoke or disprove real data races**.
- [ ] **No production mitigation authorised:** requires owner-signed threading/ownership plan (world vs map workers, any BG/world-call interleaving, locks, iterator/pointer lifetime, login/logout/relog, cap/money tests), one isolated production DRAFT only after permission, pinned native full Worldserver compile and future gameplay/rollback.
- [ ] Actual data race overlap, crash, corruption, gold event or owner-host threads **NOT independently observed**. Avoid claiming incident or changing `MapUpdate.Threads` as workaround.

## D — Claude/CS03 F14 source-only completed tracks; UI owner policy remains OPEN

- [x] [P12 DRAFT #224](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/224) `33bf0d3`: masked SelfBot test and 13 pinned Playerbots source facts/negative fixtures, 27 C++17/20/sanitizer checks, 8 mutant cases. Original hosted run `40769980410` SUCCESS.
- [x] [P14 DRAFT #228](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/228) `eec8211`: true #145 `/who` seam, 12 core facts, 23 checks, 2,000 randomized request samples, 9 mutants, original `40775174328/job 123122495963` SUCCESS (699 log lines independently read in Part 36).
- [x] [P15 DRAFT #230](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/230) exact `a4d14f7c9533b199c9ff33c7a82a57629c039250`, five new paths, ephemeral composition of P12+P14 with no production source edit. Original [run 40867809769/job 123426905306](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40867809769) **COMPLETED SUCCESS**; full original **1,025-line job log independently inspected at Part 37 handover**. 27-check C++17/20, sanitizer/TSAN **8-worker synthetic matrix**, 9/9 mutants; inherited tests and ephemeral sibling tree verified.
- [x] **CS01 P15 independent peer review posted [#230/6496539833](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/230#issuecomment-6496539833)**: exact original `a4d14f7` five added test/doc/CI paths inspected; original P15 run `40867809769`, job `123426905306`, **1,025 raw lines re-read**, P12/P14 composite, 27 checks (C++17/20/ASan+UBSan/TSAN, modeled 8 workers) and 9/9 mutants. **SOURCE-ONLY bounded peer evidence; no production sign-off, runtime proof, F14 policy selection or merge.**
- [ ] **F14 unwired/disabled.** Owner F14 A/B, M1 masked-SelfBot-as-human, M2/M3/M4, observer handling and board `maxAge` not selected for deployment; no actual `/who`/phase gameplay acceptance. Claude's M1 is a **display-only recommendation**, not the owner's choice and not P13 payout policy.
- [ ] Real race/name-query or character-model visibility outside `/who` not comprehensively hidden; no client packet rewrite proposed.

## E — Grok/CS02 N-Core K1 individual-pet data safety

- [x] Owner wants every Hunter pet's personal autocast choices (including same-name/same-family) kept separately. Server-issued per-pet identification + server-stored desired per-ability state **design preference**, store-and-return only; not authorised SQL/server apply.
- [x] Outside `character_pet` writers, DB restores, same-species replacement not excluded. Owner **FAIL-CLOSED**: any uncertain identity → **NO SAVED SETTINGS**, never assign A's preferences to B. High-water checks, species checks, UID counters incomplete proof.
- [x] Recent Grok design-only [#48/6483030197](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6483030197) GET/SET/ACK binding; CS01 [#48/6495206755](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6495206755) unverified 3.3.5a sender/event/transport notes; BOOT-3d conditional manager receipt case [#48/6495927719](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6495927719) held.
- [ ] **NoWrite**, relay **OFF**, D18 already-armed in-combat Pet A→B **HARD NO-GO**, BOOT-3d/D17/W1 HELD. P1 Option A only display fresh current-pet validated postcombat prompt; protected human click required for application, not auto-apply.
- [ ] Owner relayed **after 1 November Step 1 docs/tests ONLY**, recheck precise permission; no automatic SQL, code, client install, migration, feature toggle or live test consent. Grok branch/account actual status must be refreshed rather than assumed.

## F — Other modules, owner gates, and peer coordination

- [x] P11 Claude DRAFT #217 production source native/full pinned Worldserver link + independent CS01 source-peer #218 tests verified previously. **No new rebuild needed at unchanged author SHA.**
- [x] P10 HonorReset old/new 56,700 timestamp pair parity peer tests done, no numeric interval policy selected, default OFF. P6 seqlock reader not guaranteed lock-free-progress.
- [ ] **A04 QuestLoot H1/H2** two-human game Need/Greed/receipt/overflow not done; source tests alone cannot replace owner-gameplay criteria.
- [ ] **LIVE deployment/release NO GO:** owner-accepted gameplay 0/5, `MapUpdate.Threads=8` guardrail, N-Core NoWrite, D18, default-OFF safety, F14 unwired, P13 unresolved identity/ON default/race and K1 identity uncertainty.
- [ ] Re-check [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), [Claude #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143), [Grok #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48) before new assignments. Comments are not independent-agent session launchers.
- [ ] LAB-004 mining and LAB-005 Shaman Earthwarden, four new totems / no form / all specs / physical-shield Tempest Shield imbue are **Naxxramas Planning Centre BRAINSTORM** only; no engineering shift/implementation authorised from planning ideas.

## G — Next safe Part 37 actions, in order

1. [x] **Part 37 first live refresh completed 29 October UTC**; exact refs/PRs/issues and original P15 CI verified. Continue checking for NEW head shifts in later turns.
2. [x] P15 five-path peer review completed on #230 comment `6496539833`, no F14 production/policy sign-off. New Claude task needs a fresh active-session acknowledgment.
3. [ ] For P13, distinguish **source potential data race** from observed incident; consider more independent, single-thread/source-only concurrency design evidence and owner-facing H-DEFAULT / H-SELFBOT / H-REMEDIATION decisions. **STOP before production editing** until explicit separate authority. Document alternatives without assuming owner preferences.
4. [ ] Verify latest Grok K1/BOOT-3d context without confusing design suggestions with owner approval; respect post-Nov-1 docs/tests scope.
5. [ ] Record all new verified work here with **exact immutable parent/head, PR DRAFT status, precise changed paths, original CI run/job IDs and complete raw logs**, distinct source/production/live claims; retain untouched protected mains and #160.

**No merged code. No in-world acceptance. No release authorization.**

*End Part 37 initial checklist.*

## H — Part 37 original engineering checkpoint (29 October 2026 UTC)

### H1 — Independent current-state refresh and F14 P15 review

- [x] Verified **current** protected-by-project Mod main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, N-Core main `74e45933454385b3b1168bf2c03da34ee1027985`, unmerged frozen DRAFT #160 `a7523ebb823169edc969d971d00aa293119f2f05`. GitHub branch API currently marks both mains **`protected=false`**; the project's explicit no-main-write restriction still applies. No main or frozen PR modified.
- [x] Live DRAFT heads refreshed: R6 #227 `b1cd662544bad11967c0c5decadc36dbb9ffead0`; R7 #229 `1fdcd96ca73b0143c6108f4784b2c24cc0bfd139`; P12 #224 `33bf0d3feed7f51e10ad6470625d5f14dc601765`; P14 #228 `eec8211ec9f170468d2ed970a325b3bfbd571e6e`; P15 #230 `a4d14f7c9533b199c9ff33c7a82a57629c039250`. Docs DRAFT #231 starting head `6512c0321d09ef3271920b7574fa460efcd0870b` (this checklist is subsequently updated on that docs-only branch).
- [x] P15 independently re-reviewed at actual five-path diff and original [PR run 40867809769/job 123426905306](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40867809769/job/123426905306) COMPLETED SUCCESS; complete original **1,025-line** job log re-read. Source-only peer note [PR #230 comment 6496539833](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/230#issuecomment-6496539833). **No F14 activation, owner policy choice or production approval.**

### H2 — NEW P13-R8 ordinary mutable reload settings (distinct from R1 and R7)

- [x] **Pre-registered before authoring** at [master issue #28 comment 6496575197](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6496575197). Protected module `HonorOverflow.cpp` has four namespace-global **plain non-atomic** reload settings (`Enabled`, `CopperPerHonor`, `Notify`, `IncludeBots`) written by its original `OnBeforeConfigLoad` and read by `ProcessHonorOverflow`/BG summary paths. Pinned Grimfeather `World::LoadConfigSettings` invokes `sScriptMgr->OnBeforeConfigLoad(reload)`, while map-worker source can invoke module `OnPlayerUpdate`. **MapMgr::Update also has an explicit wait**, so actual cross-thread reload overlap is currently UNPROVEN; this is a conditional audit, NOT an observed race or runtime incident.
- [x] New [isolated test-only DRAFT #232](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/232), branch `test/cs01-p13-r8-honor-config-reload-source-20261029`, **parent Mod protected main** `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, exact author head `70bb99f80a81c90cb197a277cdac3bd6d97f7cab`, two new files only: `tests/test_p13_honoroverflow_reload_settings_source.py` and `.github/workflows/naxx-p13-honor-config-reload-source.yml`. No `src/`, `conf/`, N-Core, core, Playerbots, SQL/DBC or host modification.
- [x] **ORIGINAL hosted exact-head CI:** [push run 40873214398, job 123445310925](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40873214398) **SUCCESS**, complete **608-line** original job log inspected; [PR run 40873257111, job 123445455940](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40873257111) **SUCCESS**, complete **614-line** original log inspected. Checks: exact two-path scope, original pinned core source, literal `OnBeforeConfigLoad` compiled/executed **serially** with C++17/20 UBSan, four settings over initial/load/two reload snapshots, three must-reject source-drift cases. No intentional unsynchronized concurrent execution.
- [ ] **R8 timing/authority research OPEN:** distinguish world-thread/GM command reload sequencing from map-worker callbacks and other external reload call sites. Do **not** call R8 a confirmed runnable race without independently verifying actual overlap. Do **not** propose atomics/locks/config changes as approved production remediation. H-DEFAULT/H-SELFBOT/H-REMEDIATION remain unselected; R7 map-state hazard separate and still held.

### H3 — Safety and coordination

- [ ] Recheck Claude #143 and Grok #48 for genuinely new active-session ACKs; a GitHub comment never starts either agent. Do not initiate K1 Step 1 before 1 November or infer SQL/implementation permission.
- [ ] Owner gameplay remains **0/5**; A04 H1/H2 unverified. Keep F14 UNWIRED, N-Core NoWrite/relay OFF, D18 in-combat armed A→B HARD NO-GO, `MapUpdate.Threads=8`. No merging/production change/owner host test or release.
