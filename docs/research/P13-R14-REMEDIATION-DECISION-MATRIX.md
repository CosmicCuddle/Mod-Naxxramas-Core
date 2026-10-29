# P13-R14 — HonorOverflow remediation decision matrix (NOT a decision)

**29 October 2026 UTC | cross-study engineering analysis | DOCUMENTATION ONLY, DRAFT, NO PRODUCTION WORK.**

Pre-registered BEFORE writing at [master coordination #28 comment 6500226959](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6500226959). This is a **new synthesis of existing independent source studies R7–R13**, not a novel executable test, proof of actual owner-host failure, selected solution, or permission to edit economics. Immutable project-protected Mod main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, original HonorOverflow blob `d4f70c511ac5a3e32c7e6b8f913d095915da707c`, pinned Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`. No owner host, installed addon or server process was examined.

## 1. The engineering problem: THREE interlocked contracts

A successful remediation must separately specify, prove and integrate all three:

**C1 — exclusive state ownership / cross-character concurrency.** Original [HonorOverflow.cpp](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L34-L55) declares global `HonorSnapshots` and `BattlegroundHonorSummaries` as `unordered_map` without module-local synchronization; worker callbacks can access these maps for different player keys. Original pinned core dispatches `Player::Update` on map workers. R7 supplies credible **potential concurrent container access** but **did not observe a real live race or payout**. One synchronized read/write transition is needed across all relevant entry points, or data must be exclusively owned by a single execution context. R8 narrows **standard** reload ingress: normal GM/CLI/RA/SOAP config reload and world-tick map join are serial for audited paths, **not** universal reloader or worker-vs-worker safety.

**C2 — attribution, settlement and finality of currency.** Original [HonorOverflow.cpp L168–263](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L168-L263) moves contribution snapshot **before** attempting payment, clips its requested payment against a cap, ignores the `ModifyMoney` bool and later reports/accumulates the *proposal*, not a proven settled amount. Pinned [Player.cpp L11697–11729](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L11697-L11729) can reject positive money on trial limit and **strict** ordinary max-cap equality; its script callback is **pre-admission**. R10 proves conditional proposed-vs-delta mismatch in synthetic original-source tests. R11 confirms an unchanged-contribution update **does not retry** that declined proposal, and BG summary state is erased when closed, including Notify-OFF cases. These are source-level semantics; **never silently introduce a retry or backfill**.

**C3 — real character lifetime / battleground ordering.** BG end and early-leave callbacks perform a forced honor flush followed by summary close; login overwrites snapshot and clears summary; logout clears both. R9 model's **invented incarnation/sequence** is NOT a source-backed token. A pinned core Player can be reattached to a new session under relevant configurations without a fresh `OnPlayerLogin`; ordinary `OnPlayerLogout` does not cover all redirect paths. Never use socket lifetime, `Player*`, naked GUID or a hypothetical epoch as a guaranteed identity across delay/teardown. Queued BG close must not overtake same-character updates; queue overload must not partially award or poison a later incarnation.

**Bottom line:** A mutex-only patch may fix container UB but leave monetary duplication/incorrect reports. A bool-only money patch may fix some rejected awards but not mutable hook amounts, callback reentry or concurrency. A world-queue-only patch may eliminate map-worker writes but change contribution timing, identity and BG-close semantics.

## 2. Immutable source evidence register (not a live test report)

| Study | Pinned evidence established | What it does NOT establish |
| --- | --- | --- |
| [R7 DRAFT #229](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/229), HEAD `1fdcd96ca73b0143c6108f4784b2c24cc0bfd139` | Two process-global unsynchronized maps, map-worker callback route with different GUIDs | Reproduced host race, crash, lost credit or lock remedy |
| [R8 DRAFT #232](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/232), HEAD `7a904433f9326ef4ecc502d2252043a3b95f30b4` | Normal audited world reload/tick scheduling is serial around map join | Arbitrary async reload, hook reentry or all map-worker overlap impossible |
| [R9 DRAFT #233](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/233), HEAD `1f20d3e28398fff0255b2d2d8d1a1f1fed28faa4` | Illustrative world-owner queue alternatives; limited bounded admission and poison models; pinned redirect/reconnection caveats | Real identity epoch, safe Player resolver, bounded actor production implementation, actual award |
| [R10 DRAFT #235](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/235), HEAD `b1e355874ad8a06c507e3e85bf925450d728392b` | `ModifyMoney` bool discarded; cap-equality/trial rejection can mismatch proposed payout and BG accounting | Owner account actually hit a cap or reported wrong currency |
| [R11 DRAFT #237](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/237), HEAD `94b50d0d50d94b220eca0e5cc55c0e59fea1ff2c` | Snapshot consumed before settlement; no unchanged-delta retry; BG summary copied/erased before Notify/session; pre-admission hook | Real loss, actual hook side effects, production BG race |
| [R12 DRAFT #238](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/238), HEAD `9556d6694496a8529433b9b49e396727d719e40a` | Core money callback receives modifiable `int32&` and executes before sign/cap branch; hypothetical hook can change effective delta | A real installed mutating hook exists; live reentry, actual payouts |
| [R13 DRAFT #239](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/239), HEAD `13734623799636846bfe3d957a222d0683b364cf` | Direct pinned Git-tree grep across 3,178 tracked C/C++ files: 6 expected core framework lines, zero *additional literal money-hook name* references in scoped paths; two final exact-head hosted jobs green | Owner-installed/custom/overlay script inventory, dynamic/Lua bridge, current runtime hook absence or no callback possibility |

R13's exact final original full log evidence: [push 40896012724](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40896012724) and [PR 40896025489](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40896025489), **SUCCESS**, each full 945-line job log reviewed by CS01. This R14 document has **no test or CI claim of its own**. PR dates are 29 October 2026 UTC; none was merged.

## 3. Ownership options — no owner selection

| Candidate | Plausible advantage | Unresolved integration danger | Preliminary review stance |
| --- | --- | --- | --- |
| **A. Single world-thread owner** — map workers emit immutable observations and world thread alone updates snapshots, BG summaries and awards | Eliminates process-global map worker-vs-worker mutation if all paths comply, gives one settlement owner | Requires genuine Player lifetime resolver and ordering token, bounded/validated queue, safe handoff and BG-close barrier. Changes *when* credit occurs; queue loss/quarantine must have economics policy; actual core hook seam not proved | **Viable only after lifecycle and payment design; NOT approved** |
| **B. One synchronized module-state gate** — protect each map and transition through one shared lock | Smaller conceptual timing change, could preserve synchronous callback handling | Lock must cover every map access, login/logout/leave and settlement coordination. **Do not hold lock across Player methods, money hook, chat or third-party callbacks** without proven reentrancy and ordering; releasing around credit needs separate per-GUID transaction/lease to avoid double credit | **Requires formal lock-order/atomicity design; NOT a trivial hotfix** |
| **C. Per-GUID actor or serialized transactions** with synchronized key registry | May avoid unrelated character contention | Registry and lifecycle still shared; actor retire/reuse, queue growth and BG close need strict ordering; `Player*`/socket alone is not stable identity. More complex than B | **Possible architecture, high proof burden; NOT approved** |
| **D. thread_local/per-map copy** | Avoids some local contention | Map/worker migration and BG/login/logout need cross-owner state; can split a single character snapshot or summary | **REJECT as stand-alone fix** |
| **E. Only check ModifyMoney bool / only adjust money-cap equality** | Addresses a narrow identified rejection path | Does not synchronize maps, solve hook mutation or honor finality; changes core/payout assumptions if misapplied | **REJECT as stand-alone fix** |

No measured performance ordering is claimed. Option A is not automatically safer than B without the missing Player identity and BG ordering contract; Option B is not automatically deployable simply because a lock compiles. **The owner has selected none of A/B/C.**

## 4. Monetary semantics that cannot be guessed

No implementation may proceed until the owner explicitly approves the complete settlement policy. Keep H-DEFAULT, H-SELFBOT and H-REMEDIATION as **UNSELECTED labels**; this document neither redefines their earlier meaning nor uses a default to quietly select one.

| Scenario | Observed source behaviour (not a recommendation) | Approval decision needed |
| --- | --- | --- |
| Honor gain while option disabled, rate 0, or excluded bot | Snapshot updated before the applicable gate; unchanged later contribution is not retrospectively paid | Whether old gains stay ineligible forever or owner explicitly authorizes other semantics |
| Rejected normal money-cap **equality** or trial limit | Core can refuse positive award; module may still report proposed reward | What counts as settled currency, messaging and BG summary policy; do NOT assume bool success means exact original amount |
| Money-hook changes `int32&`, potentially re-enters | Hook can change local money amount BEFORE sign/admission; owner-installed subscriber presence unknown | Whether to prohibit/allow hook changes, which ledger or transactional seam is authoritative, how to attribute nested transactions |
| Notification OFF or session unavailable | BG summary is erased before Notify/session check | Whether replay is prohibited, and exactly when summary close becomes final |
| BG end, leave and duplicate closure | Flush then erase; same contribution cannot be retried without new earned delta | Which event orders are valid and how to avoid double award and a close-before-drain loss |
| Queue overload, stale or disconnected Player, GUID reattach | R9 queue/epoch models are invented; real stable incarnation handle not proved | Quarantine/retire/drop/retry/compensate policy and finite memory/expiration guarantees |
| Bot inclusion, SelfBot, headless or identity masked | Module's bot identity gate and configured inclusion are separate from underlying Player lifetime | H-SELFBOT policy and bot-identity proof for every relevant control path |

**Do not equate** a balance read before and after `ModifyMoney` with an unquestionably attributable delta in the presence of nested/reentrant or concurrent other money writes. A future design must prove which monetary operation owns an observed balance change. Likewise, blindly retrying a previously refused conversion would *change* R11 finality and could create duplication.

## 5. Review gates before any production-authoring approval

**Gate G0 — current HOLD (source-only):** Freeze these source pins and issue statuses; audit active scripts only through separately authorized read-only source disclosure; no supposition about owner host versions. No code changes as part of R14.

**Gate G1 — owner policy:** Record explicit, durable decisions for H-DEFAULT, H-SELFBOT, H-REMEDIATION and unresolved cap equality, failed credit, retry/no-retry, notification and BG close, accepted currency delta, queue overload/quarantine/expiry, expected per-bot behaviour. Do not silently infer answers from historical values.

**Gate G2 — architecture proof:** Choose A, B or C explicitly; demonstrate all map/summary reader/writer paths participate in ownership; prove lifecycle handle across redirect, same-Player session reattach, logout/map transfer, BG end/leave and shutdown; validate bounded memory and queue backpressure; prove no cross-GUID map races or deadlocks at `MapUpdate.Threads=8`. Revisit config reload and callback reentry only where source supports them.

**Gate G3 — separately approved implementation:** New branch and explicit scope, no edits to protected main or frozen #160; updated source pins; compilation against matching original core, negative source-guard tests, deterministic transaction/BG/reconnect tests, sanitizer evaluation where practical, original exact-head hosted logs and independent code review. Passing fixture CI ≠ successful Worldserver or owner gameplay.

**Gate G4 — owner-host acceptance and rollback (not currently authorized):** Before any high-impact deployment or owner machine/SQL/DBC/client work, explicit approval, dated restorable backup, demonstrated restore, documented rollback and full owner-controlled native/in-game verification. Mandatory owner-accepted gameplay gate currently **0/5**; no release until independently accepted.

No test plan authorizes intentionally racing an owner's live map state. No automatic outstanding-copper calculation, mass compensation, SQL updates, cap rewrite, Playerbots/IP/core patch or battle history migration is authorized.

## 6. Decision record — deliberately open

| Subject | Status | Evidence or blocking dependency |
| --- | --- | --- |
| Default feature/economics **H-DEFAULT** | **UNSELECTED** | No owner-approved policy |
| SelfBot identity/economics **H-SELFBOT** | **UNSELECTED** | No approved entitlement/identity contract |
| Payout/cap/finality **H-REMEDIATION** | **UNSELECTED** | G1 monetary policy not approved |
| State concurrency owner A/B/C | **UNSELECTED** | G2 identity, lock/order and atomicity proof incomplete |
| Thread-local-only option D | **Rejected as sufficient alone**, not selected | Does not preserve cross-worker BG/login/leave state |
| Bool-only option E | **Rejected as sufficient alone**, not selected | Does not fix concurrency, mutable callbacks or finality |
| Exact existing host scripts and settings | **UNKNOWN** | R13 source scope is NOT installed host inventory |
| Authorization to implement/merge/install/launch | **NONE** | G1–G4 unmet; owner accepted gameplay **0/5** |

**Non-negotiable safety:** Protected Mod and private N-Core main and frozen integration DRAFT #160 remain untouched. `MapUpdate.Threads=8` MUST remain **8**; R7 release HOLD. F14 OFF/unwired with unselected global concealment policy; N-Core NoWrite and relay OFF; K1 Step1 not before **1 November 2026**; D18 already-armed in-combat hunter pet A→B **HARD NO-GO**. LAB-004 mining and LAB-005 four elemental Shaman totems/Tempest Shield remain brainstorming only. This is no deployment/change to core, IP, Playerbots, Worldserver, server config, client, database, SQL or DBC.
