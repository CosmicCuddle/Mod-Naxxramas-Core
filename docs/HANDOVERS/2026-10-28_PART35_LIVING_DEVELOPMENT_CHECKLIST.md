# Mod-Naxxramas-Core — Part 35 Living Development Checklist

**Created:** 28 October 2026 UTC by CS01. **Purpose:** live development checklist for the next chat; this page is part of a **docs-only isolated DRAFT**, not an implementation authorization.

**MANDATORY:** read the full [Part 34 → Part 35 complete handover](2026-10-28_PART34_TO_PART35.md) **and this entire checklist** before continuing. The checked items are source/CI/documentation milestones, not owner gameplay or release acceptance.

## A. Owner-controlled boundaries (always apply)

- [x] Protected `CosmicCuddle/Mod-Naxxramas-Core main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` unchanged at Part 35 handover; frozen combined **PR #160** untouched. New work must stay isolated DRAFT.
- [ ] **No protected main merge, PR #160 change, install, package/release, deploy, owner server/client, private realm/characters/SQL DB, configuration activation or server start** without owner authorization and dated restorable backups/rollback.
- [ ] No SQL/DBC or external Grimfeather AzerothCore/Playerbots/Individual Progression dependency edits; public source pins in handover are immutable test references, not permission for upstream change.
- [x] Preserve `MapUpdate.Threads=8`, all relevant feature defaults OFF, native **A02 NoWrite**, N-Core relay OFF.
- [ ] Mandatory owner gameplay **0/5 accepted**, not 5/5. No source harness, sanitizer or Worldserver link substitutes for actual owner-accepted outcomes.
- [ ] **A04 QuestLoot H1/H2** private two-human incidents not verified: no guessed correction or installed test.
- [ ] **F14** actual human vs random/controlled bots Blood Elf/Draenei racial phasing and `/who` / visibility / exemption policy remain undecided and **unwired**.

## B. First Part 35 live GitHub check — do before touching code

- [x] Re-fetch exact Mod protected main and frozen #160 statuses; exact N-Core protected main and Grok author branch.
- [x] Re-fetch **CS03 P6 DRAFT #206 HEAD `601fd957`** and [run 40735432468](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40735432468): native **123009093659 SUCCESS at handover**, pinned TU/Worldserver **123009797423 IN PROGRESS**. Inspect original final job/log and exact commit before claiming gate complete.
- [x] Re-fetch **CS03 P10 DRAFT #213 HEAD `e3fe22b`** and [run 40736456319](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40736456319): native **122986206767 SUCCESS at handover**, pinned TU/Worldserver **122986999482 IN PROGRESS**. Inspect original log and exact linked source before claiming gate complete.
- [x] Re-fetch Claude direct issue #143 and Grok issue #48 for actual new author commits/ACKs. Comments do **not** automatically run Claude/Grok sessions.
- [ ] Re-fetch original CS01 peer source test heads and relevant CI only when a new patch or changed acceptance contract requires it. Do **not** re-run already completed full links merely to have activity.
- [ ] Add verified deltas here with exact immutable SHAs, run/job IDs, source/CI limitations and owner gates.

## C. Claude / CosmicScript03 — substantial C++ lead (~60% intended)

- [x] **F14 P5** [DRAFT #202](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/202) `205d958`: original hosted native SUCCESS and pinned Worldserver SUCCESS, [run 40710438920](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40710438920), job 122937499809. **Unwired adapter**, not phasing gameplay permission.
- [x] **P7 talent completion** [DRAFT #208](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/208) `bb4911a`: native and pinned Worldserver SUCCESS (job 122941996431); both public Playerbots config compatibility Worldserver jobs **122941523038/122941523631 SUCCESS**, [matrix 40723801301](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40723801301). No owner install/gameplay.
- [x] **P6 coherent six-field publication** [DRAFT #206](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/206): `2cea46c` native **122963705275 SUCCESS** and original full Worldserver job **122964047733 SUCCESS**, [run 40730082736](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40730082736). Correct source: sequence-lock coherent generation, reader **mutex-free**, may spin if writer stalled.
- [x] **P6 newest `601fd957` exact-head link**: author wording correction to `2cea46c`; new native job 123009093659 SUCCESS; Worldserver 123009797423 still IN PROGRESS at handover. Not certified by older source HEAD alone.
- [x] **P10 interval arithmetic** [DRAFT #213](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/213) `e3fe22b`: source narrow guard for unsafe weeks→`tm_mday` count and nonforward loop progression, **no new administrator cap**, HonorReset **default OFF**. Original native **122986206767 SUCCESS**, [run 40736456319](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40736456319). Independent old/new 56,700 direct timestamps #214 green.
- [x] **P10 exact-head Worldserver job 122986999482** was IN PROGRESS at handover; do not call complete until original hosted link passes.
- [x] **Assign P11, a meaningful nonoverlapping lead-source package**, following [Claude request 6476668742](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6476668742). Candidate F14 unregistered sampling hook needs owner/policy authorization; NT1 classifier needs unavailable concrete spell/talent evidence. Prefer an independently proven bounded source issue with real C++/tests and no owner host. Do not invent scope just to fill percentage, and do not repeat reviews.
- [ ] All Claude changes remain **DRAFT**, source-only; no merge, activation, player policy change or owner live test.

## D. CS01 — independent engineering / integration (~20% intended)

- [x] **#209 P6 mixed-generation controlled C++ witness** `62b53f0` hosted [40726497839](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40726497839) SUCCESS: first independent relaxed-atomic P6 mixed generation, historical negative control; not a real owner defect/TSAN race. Revised coherent P6 separately tested.
- [x] **#210 ForcedPvP conditional TSAN witness** `c6b5525`, hosted [40727958230](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40727958230) SUCCESS. **Do NOT implement config atomics on this alone**: normal in-game and console reload paths are serialized with map worker updates at pinned Grimfeather source. P8/P9 production patch on this evidence **HELD**.
- [x] **#211 HonorReset source nonprogress+DST witness** `b24cb7a`, hosted [40735871777](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40735871777), job 122984126577 SUCCESS: 40 original ordinary schedule checks (2 standards × 2 TZ × 2 seasons × 5 valid intervals) plus four extreme bounded nonprogress expected RED. No production source changed. Historic fixture CI failures corrected/disclosed.
- [x] **#212 P6 CV-gated no-sleep coherence witness** `b6a0bc`, hosted [40733408419](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40733408419), job 122975448757 SUCCESS: C++17/20 original coherent P6 source whole-generation PASS; missing odd check / final recheck / writer odd mutations all expected RED, without 300-ms scheduling guess.
- [x] **#214 P10 exact old/new timestamp parity** `b9b0e23`, hosted [40738036898](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40738036898), job 122991781095 SUCCESS: **56,700 individual matching old/new actual scheduled timestamps** across valid intervals/calendar years/time zones/compiler standards, plus 100 zero/extreme fail-closed tests. Two test/CI files only, child of immutable author P10 #213.
- [x] Previously tested A04 public fixtures #204/#205 (44/62 case source tests); still **NO actual owner H1/H2 acceptance**.
- [x] Continue genuine independent code/testing on a source-backed hole, not passive report loops. Keep owner backup and rollback guidance attached to future high-impact changes.
- [ ] Update master [issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) and this checklist with *new* verified facts and linked logs; avoid flooding Claude/Grok with duplicate requests.

## E. Grok / CosmicScript02 — N-Core secure addon separate project (~20% intended)

- [x] Owner approved **narrow BOOT-3a/b/c source-only fail-closed correction**, Grok branch `CosmicCuddle/N-Core@fc4710cfdcde99a2f393ade06ff81db4ae6e3466` (fast-forward from `438678e`), protected addon main `74e45933454385b3b1168bf2c03da34ee1027985` remains unchanged. No merge/install/client test.
- [x] Missing getter/guard API/driver ref fails closed; out-of-combat guarded `RegisterStateDriver` call and readback. Author `24 passed / 0 failed`, combat source `20/0`; CS01 original pinned [N-Core hosted 40740561950](https://github.com/CosmicCuddle/N-Core/actions/runs/40740561950) job 123000688953 SUCCESS.
- [x] Synthetic **BOOT-3d trust residual**, not proven real-client defect: preseeded `state-pak` + silent no-op registration can create false readiness in a disposable mock. Independent N-Core **DRAFT #11** `34f0b4` hosted [40740279896](https://github.com/CosmicCuddle/N-Core/actions/runs/40740279896) SUCCESS with author 24/0 and 5 positive/1 expected safety RED. Grok explicitly ACKed [#48/6476596909](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6476596909). Do **not** invent client receipt or speculative code fix.
- [x] Owner **P1 Option A** selected and documented: fresh *current pet's own* saved choice may trigger **automatic prompt display after combat**, separate deliberate protected human click still required for actual restoration. No old Pet A intent replay or silent autocast.
- [ ] Owner **K1 shared pet-name vs truly individual persistent profile** policy remains undecided, and ambiguous ownership is not valid as distinct Pet B preference.
- [ ] **D18 already-armed in-combat Pet A→B: HARD NO-GO**. Family+name restricted summary does not uniquely establish identity, owner rejected accepting weaker identity risk without in-game proof.
- [ ] **D17 taint, W1 protected first click, BOOT-3 genuine 3.3.5a registration receipt** remain held; native A02 NoWrite, relay OFF, older v1 unsafe. No real client, protected click, addon install, source merger or feature enable without new owner permission and rollback.
- [x] Parallel CS01 N-Core Part 13 research [DRAFT #8](https://github.com/CosmicCuddle/N-Core/pull/8) `d334bbf`: issue #48 [6477574977](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6477574977) certifies latest 7/7 workflows and 19/19 inspected jobs; source/model safety REDs deliberately retained. Treat as independent N-Core project context, **not Mod release approval**.
- [ ] No artificial new Grok coding assignment while only gated protected-client uncertainties remain; separate authority needed.

## F. Integration and user-facing Part 35 work

- [x] **Part 34 complete predecessor checklist preserved** in docs-only DRAFT #207 `a68d7ea541c345f6fd2e7412895ad019211880e4`; new Part 35 docs based on its exact HEAD with two new Markdown files.
- [x] Read both Part 35 documents in full at beginning of next chat; fetch live remote state before interpreting job completion.
- [ ] Keep source pins, commits, exact workflow/job IDs and original logs separated from claims of runtime deployment.
- [ ] For all future potential installs/SQL or deployment changes, require owner permission **and** dated restorable backups and a tested rollback path.
- [ ] Reconcile remaining gameplay acceptance **0/5** only when owner supplies actual valid evidence; do not silently mark source tests as gameplay.
- [ ] Avoid repetitive broad audits; spend most work on approved engineering and objective blocking tests.
- [ ] **Chat handover success** does not change main, enable any config or authorize a build/install. A future chat can continue work only within previously approved source boundaries.

## G. Quick links and continuation queue

- [Part 34 → Part 35 Complete Handover](2026-10-28_PART34_TO_PART35.md)
- [Part 34 predecessor checklist](2026-10-28_PART34_LIVING_DEVELOPMENT_CHECKLIST.md)
- [Claude work / P11 request](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6476668742)
- [Latest reported Claude P6 build status](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6477434539)
- [CS01 master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28)
- [Grok source branch / owner BOOT-3 response](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6476253986)

**First actual Part 35 task:** independently confirm latest P6 and P10 full-link CI status, communicate only verified deltas, then authorize a **source-safe, bounded and nonoverlapping P11 test/engineering task** for Claude in DRAFT without choosing gameplay policy for owner. Full gameplay/merge/release remains HELD; **0/5 accepted**.

## H. Part 35 actual 28 October 2026 UTC live engineering checkpoint (post-handover)

### H1 — Verified original hosted exact-head build completions, NOT gameplay
- [x] **P6** author DRAFT [#206](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/206) remains `601fd957a04253d99d47b34a9b3ef9fefc33e707`; original [run 40735432468](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40735432468) COMPLETED SUCCESS at exact head, native **123009093659 SUCCESS**, pinned TU/full Worldserver **123009797423 SUCCESS**, original log independently read, `[1891/1891] Linking CXX executable src/server/apps/worldserver` at **19:02:15 UTC**. Coherent six-field reader is **mutex-free, not formally lock-free**.
- [x] **P10** author DRAFT [#213](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/213) remains `e3fe22bfec18c55be0bf60fc459f19c3f940f5ae`; original [run 40736456319](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40736456319) COMPLETED SUCCESS at exact head, native **122986206767 SUCCESS**, pinned TU/full Worldserver **122986999482 SUCCESS**, original log independently read, `[1891/1891] Linking CXX executable src/server/apps/worldserver` at **18:56:05 UTC**. No owner-host honor reset/interval config applied.
- [x] **Protected state**: Mod `main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, frozen #160 unchanged, handover docs DRAFT #215 open; N-Core protected `main@74e45933454385b3b1168bf2c03da34ee1027985`, Grok author `research/cs02-spellbook-rightclick-fix@fc4710cfdcde99a2f393ade06ff81db4ae6e3466`. Source/CI success **not** gameplay pass.

### H2 — NEW genuine CS01 test-first code, not another build review
- [x] New isolated **TEST/CI-ONLY DRAFT [#216](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/216)** exact `5b0e26d452a99a7c1b1e5bc0bd72cd6848e90cb2` from protected immutable main, exactly two new paths `tests/test_bot_consumables_partial_add_witness.py` and `.github/workflows/naxx-p11-consumables-delta-witness.yml`. No module production C++/config/SQL/main changed.
- [x] Independent pinned-core source predicate: `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` `Player::AddItem` can return true after reducing requested quantity by `noSpaceForCount`. Mod main `TopUpToCount` incorrectly increments `ItemsAdded`/`ReagentsAdded` by original requested count on partial success.
- [x] Original source-extracted C++ test **push run [40751323960](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40751323960), job 123038475761 SUCCESS** and exact-head **PR run [40751374387](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40751374387), job 123038652297 SUCCESS**; both original logs read. With 4 requested/2 actually granted, unchanged source reports **4**, independent test-only delta control **2**; full, no-space and already-sufficient cases preserve original outcomes. **Expected mismatch confirms an accounting flaw; NOT a production fix or player inventory incident**.

### H3 — Real lead P11 allocation
- [x] CS03/Claude specific source-backed **P11 C++ correction package assigned** in [issue #143 comment 6478112071](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6478112071): new independent author-owned DRAFT from main; preserve grant quantity, return/failure, defaults, bank/command/cooldown and other feature behavior; count only measured positive bag delta in `TopUpToCount` with arithmetic guards, native negative/positive, strict C++17/20 and exact-head pinned Worldserver link. Do not edit CS01 #216, Hunter ammo #32 or Shaman totem #100. Assignment comment does **not** mean Claude's session is running.
- [ ] **P11 production code/author ACK pending.** No Claude implementation or new workflow result can be claimed yet.
- [ ] **Grok source-only BOOT-3d/K1 evidence** still pending independent authorization and credible genuine 3.3.5a source/client receipt; do not invent private-client tests or silently patch. P1 Option A prompt display only, D18 HARD NO-GO, D17/W1 HELD.

### H4 — Owner-controlled release boundary (unchanged)
- **NO merge/release/installation/deployment, owner host/client/character/DB, SQL/DBC or upstream dependency edits**; protected main and #160 not altered. `MapUpdate.Threads=8`, all relevant features DEFAULT OFF, native A02 NoWrite, N-Core relay OFF. F14 actual human versus random/Altbots Blood Elf/Draenei policy **unwired**. A04 private two-human H1/H2 unverified, mandatory owner gameplay **0/5 accepted**.
- Any eventual owner-authorised installation requires **dated restorable binary, configuration and relevant database backups, documented rollback, and separately approved human gameplay verification**. Existing original linked-source gates are not authorisation.
