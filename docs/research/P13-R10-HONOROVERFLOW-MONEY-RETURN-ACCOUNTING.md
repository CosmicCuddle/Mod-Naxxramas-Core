# P13-R10 — HonorOverflow proposed-versus-credited copper at money-cap boundary

**Date:** 29 October 2026 UTC  
**Authority:** source-only / disposable tests. **No production correction, owner-host test or policy selected.**

This work was [pre-registered before authoring on coordination issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6498585008). New isolated test/docs/CI DRAFT from immutable project-protected Mod main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`. Original upstream `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`. Do not merge, install, change real configuration or edit owner Worldserver, characters, client, SQL/DBC, core, Playerbots or N-Core.

## Independent original-source evidence

1. Mod [`src/Systems/HonorOverflow.cpp` L239–L251](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L239-L251) computes `requestedCopper = excessHonor * HonorOverflowCopperPerHonor`, calculates `availableMoney = MAX_MONEY_AMOUNT - player->GetMoney()` (or zero at cap), then clips positive `rewardCopper` to `min(requestedCopper, availableMoney)`. It invokes `player->ModifyMoney(static_cast<int32>(rewardCopper))` **without inspecting the returned bool**.
2. The same [module L253–263](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L253-L263) passes the **proposed** `rewardCopper` into `AddBattlegroundSummary`; that unchanged [function at L112–124](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L112-L124) sums it into `summary.AwardedCopper`. Immediate non-BG notifications at later lines also use `rewardCopper`.
3. Pinned core [`Player.cpp` L11697–11729](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L11697-L11729) implements `bool Player::ModifyMoney(int32 amount,bool sendError)`. A positive amount may return false when an applicable `CONFIG_TRIAL_MONEY_CAP` is exceeded. The normal maximum-money branch uses **strict** `GetMoney() < uint32(MAX_MONEY_AMOUNT - amount)`, rejecting the equality case. The money-change script hook may be invoked before the failure path; this audit does not claim it emitted an actual owner-visible side effect.
4. At **exact ordinary money-cap equality**, when `currentMoney < MAX_MONEY_AMOUNT` and the *proposed reward equals the remaining gap*, the module clips to `MAX_MONEY_AMOUNT-currentMoney`, but the original core's strict comparison rejects that increment. The module could nonetheless report the proposed positive sum as credited. This is an independently source-derived conditional accounting discrepancy — **not** a proven payout incident or active owner configuration.

## Disposable literal-source witness

`tests/test_p13_r10_money_credit_source.py` pins and reads untouched original blobs:

- Module HonorOverflow original blob `d4f70c511ac5a3e32c7e6b8f913d095915da707c`.
- Core Player.cpp original blob `138e7eab4905ec366338a54cc18e6cfe749a3670`.

It extracts and compiles the **original `Player::ModifyMoney` C++ body**, the original module proposed-reward C++ slice, and the original `AddBattlegroundSummary` C++ function into a temporary C++17, C++20 and UBSan fixture. The test supplies dummy `Player`, `World`, `Session`, money and GUID types only. It uses an intentionally small hypothetical **1,000-copper maximum** and an illustrative conversion rate of one copper per honor point; these are **not** original AzerothCore live cap/config values or probabilities. The fixture checks the proposed amount, the actual in-memory money delta and the proposed amount added to the BG summary.

| Illustrative fixture | Proposed copper | Real simulated money delta | Interpretation |
|---|---:|---:|---|
| Ordinary account, well below cap | 200 | 200 | matches |
| Ordinary account, one copper below cap (not exact cap) | 99 | 99 | matches |
| Proposed amount exactly fills remaining maximum-money gap | 100 | 0 | **mismatch** (strict `<` rejects equality) |
| Proposed amount exceeds gap and is clipped to exact gap | 100 | 0 | **mismatch** |
| Trial account, proposed award exceeds trial-money cap | 200 | 0 | **mismatch**, conditional on trial restriction |
| Trial account, award stays below trial-money cap | 50 | 50 | matches |
| Already at ordinary cap (zero proposed reward) | 0 | 0 | matches |

Four **must-fail source mutation guards** cover: core equality change, trial-account rejection removal, module beginning to check `ModifyMoney` return, and module switching the BG summary amount. **If any original source changes, this audit must be reviewed rather than silently still claiming the original mismatch.**

## Boundary of what is known

**Established in pinned source:** the current module can **overstate accounted/announced copper** on real positive-return-failure branches of `ModifyMoney`, because it discards the result and passes the proposed number into summary/notifications.

**Unproven/unknown:** whether owner host has HonorOverflow enabled or uses specific configuration (H-DEFAULT unselected); whether trial restrictions ever apply to an eligible player; how frequently boundary amounts occur; how a client displays particular messages; whether a real account received or missed money; whether any other scripts modify money in the hook. No runtime or economic impact has been measured on the owner's host.

**Not authorised:** changing core `<` to `<=`, adjusting money caps, returning different copper, retrying a declined award, compensating prior payouts, editing default settings, SQL/DBC or Playerbots integration. Any future correction needs owner-approved exact-once and cap-handling policy, separate concurrency plan for R7, native test evidence, dated restorable backups, documented restoration/rollback and explicit release permission.

Keep `MapUpdate.Threads=8`, F14 OFF/unwired, K1 NoWrite/relay OFF, D18 already-armed Pet A→B HARD NO-GO, frozen integration DRAFT #160, Mod/N-Core protected-by-project mains unchanged and mandatory owner-accepted gameplay **0/5**.
