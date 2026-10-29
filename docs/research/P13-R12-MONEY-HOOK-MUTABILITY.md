# P13-R12 — Mutable money-change script hook and HonorOverflow

29 October 2026 UTC. SOURCE-ONLY RESEARCH AND DISPOSABLE TESTS. NO PRODUCTION ACTION.

Pre-registered before authoring: https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6499610820

New separate DRAFT from protected-by-project immutable Mod main 80e9de1c39a6dc995188a80c31a5e785d0f2a6f9; pinned core Grimfeather 8daffdabe9202c228e45d833c9a1d399597a15cd.

## Exact original source evidence

1. Mod src/Systems/HonorOverflow.cpp, blob d4f70c511ac5a3e32c7e6b8f913d095915da707c, computes proposed rewardCopper before calling Player::ModifyMoney. It ignores the return bool, reports the original proposed amount and accumulates it in the BG summary.
2. Original core Player.cpp, blob 138e7eab4905ec366338a54cc18e6cfe749a3670, takes ModifyMoney(int32 amount) by value, then passes its LOCAL modifiable variable to sScriptMgr->OnPlayerMoneyChanged(this, amount) BEFORE the positive/negative branch and caps.
3. PlayerScript.h, blob 0d2314edf7715f383bbab996c6c5fc010b282308, declares PLAYERHOOK_ON_MONEY_CHANGED and virtual OnPlayerMoneyChanged(Player*, int32& amount). The ampersand proves this is mutable reference, NOT a read-only value.
4. PlayerScript.cpp, blob 4ac4571a3d7d8c0f3f27e8477ff5d7f0734e6e05, dispatches that same reference to enabled PlayerScript callbacks.
5. ScriptMgrMacros.h, blob 80895976796c2cc0219256b5b653d3e05c7c908c, iterates enabled hooks and calls the supplied action.

Core methods are pinned at https://github.com/Grimfeather/azerothcore-wotlk/tree/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Scripting

**New independent source implication:** An enabled custom player script COULD alter the core's local credited amount before admission. HonorOverflow retains its earlier proposal, so checking only the original proposed value need not reflect actual money. This is different from R10's original cap-rejection and R11's consumed contribution/no-retry finding.

**UNKNOWN:** No proof that the owner's installed core, modules, Playerbots, IP or any custom script actually registers a money-change handler that mutates amount. No observed player money, server hook reentrancy or actual loss is claimed.

## Literal-source synthetic test

tests/test_p13_r12_money_hook_mutation_source.py pins all five blobs and extracts the ORIGINAL C++ Player::ModifyMoney, ScriptMgr::OnPlayerMoneyChanged dispatcher, macro, module award slice, and BG summary function. It executes them against dummy Player/World/Session/ScriptRegistry and deliberately INVENTED PlayerScript hook implementations in C++17, C++20 and UBSan.

Hypothetical MAX_MONEY_AMOUNT = 1000, 1 copper per excess honor; these are NOT installed/live/original cap or rate.

| Synthetic hook behavior | Module proposal | Dummy actual money change |
| --- | ---: | ---: |
| No hook | 200 | +200 |
| Halve proposed amount | 200 | +100 |
| Force amount to zero | 200 | 0 |
| Double amount | 200 | +400 |
| Reverse amount to negative | 200 | -200 |
| Double into strict cap-equality rejection | 100 | 0 |

The five altered outcomes use intentionally invented callbacks. They do NOT prove a real deployed listener exists. Five must-fail source mutations check hook call, mutable signature, dispatcher forwarding, enabled loop, and module ignoring money return.

## Safety and unapproved decisions

No fix, automatic compensation, modified hook, cap or rate policy, payment, SQL/DBC, production source/config, server/client test, or owner runtime action authorized. H-DEFAULT, H-SELFBOT and H-REMEDIATION remain UNSELECTED. R7 shared-map concurrency remains release HOLD; R9 actual Player lifetime and exact-once accounting unresolved. Keep MapUpdate.Threads=8, Mod/N-Core mains and frozen PR #160 untouched. F14 OFF/unwired; N-Core NoWrite/relay OFF; K1 Step1 not before 1 Nov 2026; D18 already-armed pet A-to-B HARD NO-GO. Mandatory owner gameplay 0/5. Separate owner approval, dated restorable backups, restore verification and rollback required for future high-impact work.
