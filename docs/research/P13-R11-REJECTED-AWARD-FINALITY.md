# P13-R11 — HonorOverflow rejected-credit finality and battleground close

29 October 2026 UTC. SOURCE-ONLY RESEARCH; NO PRODUCTION AUTHORIZATION.
Pre-registered on [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6499278191) before authoring. This distinct study follows R10 (credit/report mismatch) and R9 (hypothetical ownership/leases). It does not repeat their test matrix.

## Original pinned source

Module: [HonorOverflow.cpp at Mod main 80e9de1c](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp), blob d4f70c511ac5a3e32c7e6b8f913d095915da707c.
Core: [Player.cpp at Grimfeather 8daffd](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L11697-L11729), blob 138e7eab4905ec366338a54cc18e6cfe749a3670.

**Finding 1 — a failed credit does not cause an unchanged-contribution retry.**
ProcessHonorOverflow updates HonorSnapshots.Honor and TodayContribution BEFORE conversion and ModifyMoney. Earned honor is derived from the contribution delta. Once a positive award is rejected, a later update without any further contribution yields zero earned honor and cannot retry that same rejected award. This is source-level sequence semantics, not evidence that an owner character lost currency.

**Finding 2 — the money-changed script hook is pre-admission.**
The original Player::ModifyMoney invokes OnPlayerMoneyChanged(this, amount) BEFORE trial-cap and ordinary cap checks. In the disposable fixture a dummy hook records one call despite return=false and unchanged money. Whether a real script has side effects or reenters this call is UNKNOWN. A future bool-return handling remedy must examine hooks separately.

**Finding 3 — battleground close removes pending summary even if credit was rejected.**
Both original BG end-reward and remove-at-leave callbacks call ProcessHonorOverflow(player, true) then SendBattlegroundSummary. The send routine erases its in-memory summary before checking Notify/session and formats the proposed AwardedCopper (see R10). A subsequent empty close sends nothing, while a rejected proposed amount can be included in the first report. Actual core invocation timing/reentrancy and real game output have not been proven.

## Distinct executable tests

The new P13-R11 Python harness pins the two original file blobs, extracts literal ORIGINAL C++ methods (StoreHonorSnapshot, AddBattlegroundSummary, SendBattlegroundSummary, ProcessHonorOverflow and Player::ModifyMoney), compiles them with dummy Player, Session, World, ScriptMgr and ChatHandler in C++17/C++20/UBSan, and tests temporal multi-event sequences:

1. Positive ordinary cap failure -> next identical contribution no retry -> one newly earned honor point attempts separately.
2. Trial cap failure -> next identical contribution no retry, with pre-admission hook seen once.
3. BG positive rejected credit -> proposed BG summary -> forced leave after BG state changes -> single erased close and no second summary.
4. BG accumulation while notifications are enabled, then disabled at summary flush -> no message but state is still erased, and re-enabling notifications does not replay the old summary.
5. Source guards for login/logout reset, BG end/leave ordering; six intentionally incorrect source drifts must be rejected (including a hook-removal mutation, NOT a moved-hook test).

Illustrative caps and conversion rate are synthetic: maximum 1000, honor cap 100, trial cap 600, 1 copper per honor. NOT actual AzerothCore live values. Tests do not run a Worldserver, real Player or BG hook dispatch, production threads, network, DB or player payout. Synthetic success never resolves R7 concurrent unordered_map risk or R9 actual Player lifetime.

## Unselected decisions and hard safety

No automatic retry, correction, compensation, reinterpretation of trial or ordinary cap, or altered policy is proposed. H-DEFAULT, H-SELFBOT, H-REMEDIATION and state synchronization design remain unselected; no source/config/SQL/DBC change approved. A source-confirmed failure path is NOT evidence of an owner incident.

No changes to protected Mod/N-Core main, frozen #160, MapUpdate.Threads=8, worldserver, installed client, owner DB, upstream core/IP/Playerbots or private N-Core. F14 unwired; NoWrite and relay OFF; K1 Step1 documentation/tests not before 1 November 2026; D18 already-armed A-to-B pet case HARD NO-GO. Gameplay acceptance remains 0/5. Any high-impact work requires separately authorized dated restorable backups, verified restore and rollback.
