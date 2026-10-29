# P13-R9 — HonorOverflow state ownership and lifetime alternatives

**Scope: SOURCE-ONLY RESEARCH + DISPOSABLE SYNTHETIC TESTS. No production fix approved.**

29 October 2026 UTC. Isolated test-only DRAFT branch from protected-by-project Mod `main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`. Pinned archived core: `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`. No owner server, SQL/DBC, Playerbots, Individual Progression or N-Core edits. Frozen integration DRAFT #160 unchanged. The owner has **not** chosen H-DEFAULT, H-SELFBOT or H-REMEDIATION, nor a concurrency ownership plan. `MapUpdate.Threads=8` is a HARD constraint. Owner-accepted gameplay remains **0/5**.

## 1. Independently verified exact-source facts

| Original source, pinned commit | Relevant source fact | Limitation |
|---|---|---|
| [Mod HonorOverflow.cpp lines 34–55](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L34-L55) | Two namespace-global `unordered_map<LowType,...>` containers store honor snapshots and battleground summaries, with no visible module-local mutex | File-level audit, not a runtime concurrency trace |
| [HonorOverflow.cpp 103–138](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L103-L138) | Both map writes via `operator[]`; BG summary is copied, then erased | Different GUIDs still share each container's internals |
| [HonorOverflow.cpp 168–265](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L168-L265) | `ProcessHonorOverflow` updates the in-memory snapshot **before** enabled/bot checks; then computes cap/delta, may call `Player::ModifyMoney`, and may update BG summary | Moving timing or splitting steps risks missed, duplicate or re-evaluated copper |
| [HonorOverflow.cpp 330–398](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L330-L398) | Login overwrites snapshot + erases summary; logout erases both; update and BG callbacks touch shared state | Race/lock order across teardown and callback sources requires separate design |
| [Core MapMgr.cpp 269–280](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/MapMgr.cpp#L269-L280) and [Map.cpp 436–489](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/Map.cpp#L436-L489) | Map scheduler dispatches several map-worker requests; Map::Update eventually invokes `Player::Update` | Real overlap is conditional, not measured on the owner's server |
| [Core PlayerUpdates.cpp 314](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/PlayerUpdates.cpp#L314) | Player update calls `sScriptMgr->OnPlayerUpdate(this,p_time)` | Invokes the module callback through registered script hooks |
| [Core World.cpp 1225–1270](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/World/World.cpp#L1225-L1270) | Normal world tick: sessions before map-worker **join**, then BattlegroundMgr update | This excludes certain normal same-tick world/BG vs map overlaps, **not** worker-vs-worker map overlap |
| [Core WorldSession.cpp 830–855](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L830-L855) | `OnPlayerLogout` is called before player cleanup/deletion in ordinary non-redirect logout | Other lifecycle, redirect, callback, map transfer and incarnation guarantees require proof |
| [Core Battleground.cpp 949, 1132](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Battlegrounds/Battleground.cpp#L930-L1133) | End reward and remove-at-leave call BG script hooks | Other entry/thread timing of early leave is not exhaustively proved |

**R7 remains a credible potential concurrency / undefined-behavior hazard.** The existing R7 [DRAFT #229](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/229) uses single-thread original-body fixtures: not a live race reproduction. R8 [DRAFT #232](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/232) independently established that ordinary GM/CLI/RA/SOAP config reload paths run outside active map workers; it does not solve R7.

## 2. Future ownership alternatives — none selected

| Candidate | What it could guarantee if implemented correctly | Critical unknowns / changes |
|---|---|---|
| **A — World-thread exclusive state**: map workers publish bounded immutable observations, then the world owner commits and awards after map join | No shared-map mutations by map workers, clean single-thread state ownership; potential clear handoff from worker to world | **Not a drop-in patch.** Changes award time, snapshot timing and BG-end ordering; source does not supply reliable per-character incarnation/sequence, nor a proven current Player resolver. May drop valid rewards on queue pressure; requires explicit owner economics policy, max-delay/memory bounds and world-thread integration seam |
| **B — Single synchronized module state gate**: one lock serializes all map reads/writes, login/logout and BG summary transitions | Preserves near-original callback timing while preventing concurrent map-internal accesses if **all** paths participate | If held across Player methods, `ModifyMoney`, chat or hooks, can introduce reentrancy/deadlock and lock-order inversion. If released before monetary writes and summary aggregation, duplicate-credit/ordering changes remain possible. Need per-GUID economic transaction design, safe lock ordering, lifetime and shutdown/reload analysis |
| **C — Per-GUID serialized state actor/lock**: each player key has its own serialized state and an independently safe registry | Can reduce cross-character contention | Registry itself needs synchronization; player migration, GUID re-use and callback handoff require epoch/lifetime and map-to-world barriers; BG flush must not overtake updates; more moving pieces and no source-verified non-reused pet-like/character epoch contract |
| **D — thread_local/per-map maps** | Reduces same-container worker contention | **Reject as stand-alone remedy**: worker assignment and player map transfer may change; login, logout, BG summary and end-reward cross boundaries. No guaranteed single consistent historical snapshot or one BG summary |

**No recommendation is an owner choice.** Before any production patch, independently decide thread ownership and lock order, specify what is atomic as an economic transaction, capture the relevant bot-identity policy separately and require approval.

## 3. R9 disposable model: exactly what it tests

`tests/p13_r9_world_owner_queue_model.cpp` is a **hypothetical architecture**, not module code. An `Observation` has only immutable GUID, **invented incarnation and sequence**, contribution and a BG marker. There is **no Player***, gold or server call. Eight actual producer threads only append to a **mutex-protected bounded queue**. After joining all workers, a single world-owner thread owns a private map and processes entries. Neither this callback shape nor the incarnation/sequence tokens are already implemented by AzerothCore; the model explicitly **assumes** them.

- 8 producer threads × 40 distinct GUIDs → no duplicate or missing synthetic observations.
- Pending old-incarnation GUID reused after logout/relog → discard old data.
- Duplicate sequence → ignore and do not double-count; missing sequence → invalidate (do not guess).
- A BG flush **before** all pending same-GUID samples have drained → refuse. After drain, accept once; a second close is refused.
- Queue overload → quarantine the **hypothetical (GUID, incarnation)** including already queued items; **fail closed**, not a partial reward. A later incarnation does **not** inherit the old quarantine, including when the old poisoned batch is still pending.
- Player incarnation retired before the drain → late pending event never recreates state.
- **NEW R9 follow-up:** old-incarnation overflow quarantine must not make a later incarnation unserviceable; stale poisoned old batch must not invalidate a new incarnation when logout/relogin precedes queue drain.
- `static_assert` verifies the observation is trivially copyable; it is not proof of real owner-side Player lifetime safety.

Five **deliberately wrong model variants** must fail: missing epoch test, missing duplicate test, accepting queue overflow, BG-close-before-drain, and **GUID-only persistent overflow poison** that incorrectly rejects a new incarnation. All variants operate on the disposable test-only model. No undefined concurrent access to the production `std::unordered_map` is executed.

## 4. Non-negotiable open requirements before production remediation

1. **Identity and lifecycle:** real source-backed session/incarnation handle, no stale `Player*` after logout, no cross-character GUID reuse spill, map/instance transfer, headless/random/Alt/SelfBot masking states, shutdown and restart.
2. **Economy parity or approved change:** snapshots update even while feature OFF; daily contribution reset; honor cap and money cap, exact once-only awards; full/partial cap; `IncludeBots`; BG end and leave with single summary; update ordering around login/logout; visibility/notification does not suppress legitimate awards; queue overflow must have explicit owner-approved resolution.
3. **Performance and synchronization:** no `MapUpdate.Threads=8` change, predictable lock order, no blocking chat/DB/Player calls while holding a shared lock, bounded memory/work, no unsafe callback reentrancy.
4. **Verification:** original pinned-worldserver full build and original exact-head hosted test logs when separately authorised, signed-off design, dated restorable backup and documented rollback before any owner-host test. Synthetic TSAN success is **not** production TSAN or gameplay acceptance.

## 5. Additional R9 post-review model limitation: quarantine lifetime (29 Oct 2026)

Independent review at [DRAFT #233 comment 6497675733](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/233#issuecomment-6497675733) found that the original **model**, not production module code, used `poisoned: unordered_set<GUID>`, so a queue-overflow during one login could prevent `Submit` in the next hypothetical login incarnation. The reviewed model also risked invalidating a fresh incarnation if it applied an old queued quarantine *before* checking that sample's incarnation.

The test-only follow-up uses `(GUID, invented incarnation)` as a **model key**, rejects mismatched-incarnation samples **before** inspecting old quarantine and adds explicit regression witnesses for (a) overflow then retire/relogin and (b) retire/relogin while already queued old poisoned samples remain. An additional deliberately wrong `POISON_SCOPE` variant restores GUID-wide quarantine and must be caught with the direct error `new incarnation rejected by stale overflow quarantine`. **Neither implementation nor any production ownership policy is authorized by this test.**

**Further unresolved problems, not fixed by the model:** the quarantine set is deliberately **unbounded**, historical retired epoch records are not pruned, a flood of stale producers may fill the shared bounded queue and poison a new incarnation, `Begin` assumes a validated monotonic epoch source, and `FinishBgAfterJoin` does not prove real server hook order or real monetary transaction atomicity. This remains a design study and should not be translated into production code without new source contracts and owner approval.

### Related pinned-source lifetime limitation

`Grimfeather@8daffdabe9202c228e45d833c9a1d399597a15cd` [WorldSession.cpp lines 830–858](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L830-L858) executes `OnPlayerLogout` only when `!redirecting`, although cleanup proceeds outside the conditional. The original [HonorOverflow.cpp lines 343–358](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L343-L358) clears shared maps through login reset and `OnPlayerLogout`. **Do not assume every teardown triggers `OnPlayerLogout`**; actual redirect-call reachability, cluster ownership, and stale state cleanup are not independently established here. Do not call this a proven owner-host leak.

**Final state: No production edit, no money award, no owner config or SQL/DBC action, no merge or install. Gameplay accepted 0/5.**
