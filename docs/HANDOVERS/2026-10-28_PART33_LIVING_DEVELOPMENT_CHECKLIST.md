# Mod-Naxxramas-Core — Part 33 Living Development Checklist

**Opened 28 October 2026 UTC. PUBLIC, NONAUTHORISING.** Read the [complete Part32→Part33 handover](2026-10-28_PART32_TO_PART33.md) **and THIS file in full** before working. This checklist is the Part33 active source-development record, not authority to merge/install or to run gameplay. Preserve prior Part32 and older documents unchanged.

## 0. Permanent safeguards

- [ ] **Refresh current SHA + PR + team state before code.** Public GitHub is being changed concurrently by independently opened Claude/Grok/CS01 sessions. Check [#28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), [#48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48), [#143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143), [#109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109), [#194](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/194) and exact relevant PR heads. Do not treat historical “in progress” as a current final result.
- [ ] **Coding-first; no unnecessary repetitive scans/reviews:** CS03 ~60% substantive C++ lead, CS02 ~20% A02/N-Core, CS01 ~20% A04 + integration/coordination. Percentages are ownership targets, not proof that an agent is running automatically; GitHub comments are not agent execution.
- [ ] **Protected/frozen:** Mod-Naxxramas-Core `main` pinned at Part33 entry `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, frozen integration #160, N-Core `main` `74e45933454385b3b1168bf2c03da34ee1027985`. Do NOT modify, merge, deploy, stage, package, run game/client, access owner host/data, edit SQL/DBC, core/PB/IP dependencies, or enable any feature without *separate* explicit owner approval, private installed-version verification and restorable backups/rollback.
- [ ] **Owner gameplay 0/5**: GFPP, F12, F13, A02, A04. Full Worldserver link and synthetic tests are **not** owner acceptance. `MapUpdate.Threads=8` remains, all feature configs default OFF, A02 native NoWrite and N-Core relay OFF. F14 optional human exception provisional. F15 private R0/launcher/retention gate strict.
- [ ] Keep user-visible explanations short, stepwise and dyslexia-friendly. Never claim CS03/CS02 responded until GitHub actually shows it. No private identifiers or logs in public issues.

## 1. Part33 actual entry evidence (refresh)

| Area | Exact SHA at handover | Source/CI status and next gate |
| --- | --- | --- |
| F14 CS03 [#197](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/197) | `b44029da7bc857512400cbb0aaa5eebeafd81586` | PURE classifier 2,936 C++ hosted checks **PASS** [40697016677](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697016677); no world or /who hook. |
| A01 CS03 [#198](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/198) | `c56e69f4cf4ef18f6a37ff58631d1d391b9ee68f` | 320-byte cache source fix, 26 source + 60 native checks **PASS** [40697604608](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697604608) and 40697604305. Multiple **HOSTED FULL LINKS IN PROGRESS** at handover; see below. |
| B09 CS03 [#199](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/199) | `80649c2bc7abfef85b0c365496654b7960f964ee` | 267,904 calendar checks green; old-main 3 expected RED for error-report latch; source success [40698630741](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40698630741), **hosted full link pending** at handover. Default OFF. |
| A03 CS03 [#200](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/200) | `fde9771afb35cc3c939f5b341b07c4e07115b335` | 23 pinned facts source tests **PASS** [40699637704](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40699637704), combined static integration success. **Changed-build AltBot Apply NO-GO**. |
| A04 CS01 [#195](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/195) | `6e9c8c1961d08dbef4e117d1ca43fd7131acbcb1` | H1 evidence label only, 26/26 [40693145215](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40693145215) PASS; NOT loot fix. |
| A04 CS01 [#196](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/196) | `3ddf82943c5574885c3d2c41b4fc88f9debee7f8` | H2 evidence label only, 23 original RED subcases, 30/30 corrected [40696165208](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40696165208) PASS; NOT loot fix. |
| A02 CS02 N-Core source | `f52cbb040a788a25e309bef2896b36c6a28e626b` | Owner-approved Grok *research branch* D17-8/9 source fix, independently hosted Lua 5.1 [N-Core DRAFT #9](https://github.com/CosmicCuddle/N-Core/pull/9) `be71e1f55b11a5e9d8e4fd78eeaf7fffe95e4550`, [40701831895](https://github.com/CosmicCuddle/N-Core/actions/runs/40701831895) **334 numeric assertions + 2 smoke PASS**. NOT secure real client proof. |

## 2. Active lanes — do actual work in the correct one

### Claude / CS03 — ~60% C++ source lead

- [x] Part32 P1–P4 each delivered a real isolated DRAFT artifact #197, #198, #199, #200 (read exact source evidence and status above). These are not merged or gameplay proven.
- [x] [CS03 14:08 UTC ACK of P5](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6471203155) following [#143 task](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6471095561).
- [ ] **FIRST: finish hosted full-link status:** read actual completed **original jobs** for #198 runs [40697604608](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697604608), [40697604436](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697604436), [40697604454](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697604454), [40697604474](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697604474), and #199 [40698630741](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40698630741). **At handover these were in progress, not verified HOSTED PASS**. Claude local Worldserver exit 0 is separately logged; do not conflate. If fail, narrow source fix via isolated child.
- [ ] **P5 NEW actual code:** isolated child of #197 exact `b44029d`: C++ PUBLIC pinned world-thread-only F14 `Facts` adapter, native real-source compile/full link and tests. **No WorldScript registration, no active snapshot, no /who, no actual-world visibility, no config activation, no `Player*` retained across worker/threads, Unknown fallback**, no dependency edits. If no safe seam, precise `BLOCKED_IDENTITY_API`, no guessed heuristic. Later F14 physical phasing and human exception require fresh owner design/approval.
- [ ] Team checkpoint exact P5 PR/commit/tests and next eligible code. No repeated F15/F12 reviews or duplicate #100/#116/#144/#99.

### Grok / CS02 — ~20% A02 specialist

- [x] Source-only owner-approved `f52cbb0` D17-8 false→nil fix and common PreClick/PostClick D17-9 duplicate fix published; no merge/install. [CS02 checkpoint](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6470857986).
- [ ] **D17-9a new edge:** unrelated-slot inner Toggle wrongly suppressed by current `barClickSlot ~= nil`; source RED witnessed but real-client interleaving UNKNOWN.
- [ ] **D17-9b new source corner:** partial initial ten-button hookup with global `barHooked=true`; however pinned historical 3.3.5 FrameXML statically creates all ten buttons, so normal stock reachability NOT proved. [Source qualification](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6471211778).
- [ ] Grok [acknowledged both edge issues](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6471096418), proposed own narrow fix but **HELD for separate owner approval**, not permission to patch. Check fresh owner decision before new source.
- [ ] Actual protected client `HookScript("PreClick")` taint/combat, load-in-combat `SetAttribute`, D18 combat pet A→B, two W1 first clicks, v1 chunks and native NoWrite remain NO-GO. Never call offline CI real-client/gameplay acceptance.

### CosmicScript01 / CS01 — ~20% A04 + integration

- [x] Own H1/H2 diagnostic-only #193/#195/#196 source precision addressed; #196 30/30 hosted.
- [ ] Real owner [#109 H1/H2](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109) unknown: H1 require independently confirmed actual bag/mail receipt to friend; H2 independently sparkle/row/denial plus quest-count vs inventory at first loot view. NO private data in public issue; no speculative loot policy or guard activation. Existing `QuestLootProtection` switches OFF.
- [ ] Check newly demonstrable source bug in **non-peer** integration lane or owner-private R0 (only if separately approved); don't repeatedly edit diagnostics for hypothetical causes or do more broad reviews instead of code.
- [ ] Continue real pinned CI/PR provenance, prevent peer branch conflicts, document original job results and rollback/backup prerequisites before any future authorized staging.

## 3. Other gates

- [ ] GFPP #186, Scarlet F12, Atiesh F13 #187/combined #160 all require genuine owner game tests; no acceptance yet.
- [ ] A01 Golemagg source logger improvement is NOT correction of combat oscillation root cause.
- [ ] B09 event 13 MUST remain OFF; log latch fix #199 does not permit starting an invasion.
- [ ] A03 changed-build talent swap remains disabled, pets/offhands safe, #200 facts research not production permission.
- [ ] F15 crash + warnings/errors for BOTH World/Auth not operational; private launcher, stdin/stdout, genuine death attribution, retention, privileges and backups require separate R0 authorization. No real daemons or logs touched.
- [ ] F14 human exception provisional (genuine humans only, not RandomBots/AltBots; SelfBot policy undecided). #197 pure classifier has **no actual world or `/who` wiring**.
- [ ] `main` and #160 immutable unless later owner approval; remain DRAFT until independent owner acceptance.

## 4. Next Part33 checkpoints

- [ ] Record exact latest Claude P5 code vs blocker; **no inference of background execution** merely because P5 is assigned or acknowledged.
- [ ] Record exact #198/#199 **hosted** Worldserver final verdict and original job IDs; distinguish completed success, failed and still running.
- [ ] Record N-Core research current SHA and precise owner approval for any D17-9a/b correction.
- [ ] Record CS01 actual new code/tests or specific source-level blocker; do not inflate research/coordination as a game fix.
- [ ] Record any changed owner gameplay acceptance ONLY with actual permission, reproducible game test and owner signoff (opening = **0/5**).
- [ ] Append dated succinct exact-SHA checkpoints here; preserve historical handover and previous Part32 docs.
- [ ] Prepare Part33→34 full handover when conversation eventually needs it; avoid losing exact repo work.

**ENTRY VERDICT:** Useful source implementation and hosted unit/contract tests have advanced on Claude and Grok lanes. NO protected main merge, no release/build installed, no private realm/client run; mandatory accepted gameplay **0/5**. This file is NONAUTHORISING.


## 5. Part33 live checkpoint — 28 October 2026 UTC (~14:29)

**Genuine GitHub refresh completed; source/CI only, NONAUTHORISING.** At this checkpoint protected Mod-Naxxramas-Core `main` remains `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; frozen integration #160 untouched. N-Core CS02 research `research/cs02-spellbook-rightclick-fix` is STILL `f52cbb040a788a25e309bef2896b36c6a28e626b`. No new D17-9a/9b author push or owner approval identified. CS02 research remains HELD for secure-client and fresh owner permission; additional source-only load-in-combat negative reported [team #48 comment 6471354071](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6471354071) does not authorize secure changes.

**CS03 P5 actual new C++ DRAFT:** [#202](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/202) exact `60a966886301008c6bae0230672a47ad12c81501`, isolated child of unmodified #197 `b44029d`. New `PlayerIdentityFacts.h/.cpp` read-only, unwired world-thread-token-gated adapter and synthetic source/native test harness; no world/`/who` registration or visibility, no config activation. Actual [hosted run 40703937227](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40703937227) **COMPLETED FAILURE** original job `122870860322`: source contracts 10/10 PASS; real adapter C++17 fixture **PRINTS 36 checks**, but workflow requires **37**, exits 1. Pinned TU/full-link job **SKIPPED**, so no hosted P5 full-link proof. Exact diagnosis and narrow correction requested on CS03 [#143 comment 6471543919](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143#issuecomment-6471543919); do not merely change the expected count before reconciling test coverage. No P5 author response/fix yet verified.

**#198 HOSTED FULL-LINK major progress:** original [run 40697604436](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40697604436) **COMPLETED SUCCESS**, job `122848442589`; original log directly inspected: `[1888/1888] Linking CXX executable src/server/apps/worldserver` and `PASS: read-only Golemagg observer registration found in full linked Worldserver.` Exact #198 head `c56e69f4cf4ef18f6a37ff58631d1d391b9ee68f`. Other original #198 runs **40697604608 / 40697604454 / 40697604474 remain in_progress**. #199 40698630741 also **in_progress** (calendar source tests success, full link pending). No in-game Golemagg root-cause claim.

**CS01 ACTUAL INDEPENDENT SOURCE CI IMPLEMENTATION:** [new DRAFT #203](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/203) is one-workflow-only child of unchanged CS03 #200 `fde9771afb35cc3c939f5b341b07c4e07115b335`; exact final head `c16b8d1af1c4991f334c10db4d99f355a12b3413`, path `.github/workflows/part33-nt1-ep-no-skips.yml`. Uses pinned public core/Playerbots/IP checkout in native `acore/modules` layout; explicitly executes **all 23 P4 NT1 fact/mutation tests and all six EP cases without skips** in one job. Rechecks exact ancestry, source pins, only-workflow diff and NT1 safe=false verdict. Early run 40705733718 ran all 23 tests OK but our overbroad negative-text grep incorrectly treated expected checker `FAIL: [Errno 2]` as a unittest failure. The next commit 6514999 had malformed workflow text due an authoring replacement bug, rejected before jobs (run 40705983362). Both **CS01-owned workflow mistakes corrected**, no peer source edits. [Final hosted run 40706184407](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40706184407), original job `122878825487` **COMPLETED SUCCESS**, original log inspected: `Ran 23 tests ... OK`; `Ran 6 tests ... OK`; each no-skip guard passed; total **29 executed source tests, none skipped**. No full Worldserver in this workflow, no actual talent swap or event acceptance.

**Owner release gates unchanged:** all features OFF, native A02 NoWrite, `MapUpdate.Threads=8`, F14 genuine-human exception provisional, F15 private R0 gate, A04 H1/H2 require private actual receipt/denial evidence. Mandatory owner-accepted real gameplay **0/5**. No merge, staging, deployment, host, SQL/DBC, dependencies, protected client, real gameplay, private data, or physical backup operation. A future approved deployment must be preceded by restorable backup and rollback plan.

**Next:** CS03 fixes #202 CI mismatch on own branch, then checks original hosted P5 job plus remaining #198/#199 links; CS02 stays HELD pending explicit owner approval for any new D17 secure source, CS01 pursues non-overlapping integration evidence; owner-private A04 gameplay remains blocked. Do not describe source green as release.
