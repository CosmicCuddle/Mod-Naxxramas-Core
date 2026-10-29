# P13 — HonorOverflow bot identity and default-state decision packet

**Status:** Research and owner decision preparation only, 28–29 October 2026 UTC. **NOT an approval, patch, merge, deployment, runtime test, or policy selection.** This record consolidates independently verified P13/R1–R6 tests and original pinned source. A CI-green synthetic counterexample is *not* a live Worldserver incident.

**Scope boundary:** Mod-Naxxramas-Core protected `main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, N-Core protected `main@74e45933454385b3b1168bf2c03da34ee1027985`, frozen PR #160 unchanged. Mod-Naxxramas-Core F14 is UNWIRED, A02 NoWrite/relay OFF, D18 active in-combat armed pet A→B HARD NO-GO, `MapUpdate.Threads=8`. Mandatory owner-accepted gameplay **0/5**. No source code, config, SQL, DBC, client, server, DB or live characters changed by this research.

## 1 — Owner decisions that must remain explicit

**Decision H-DEFAULT (not selected):** What should a *future* production HonorOverflow default be?

- **D0: retain current source/distribution default ON.** The [protected source file](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp) initializes `HonorOverflowEnabled = true` and calls `GetOption<bool>("NaxxramasCore.HonorOverflow.Enabled", true)`. The [distributed config](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/conf/mod_naxxramas_core.conf.dist) states `# Default: 1` and `NaxxramasCore.HonorOverflow.Enabled = 1`. **Source/distribution are ON, not OFF.** This is not proof of the owner's effective installed config.
- **D1: require OFF by default in a future, separately authorised change** to both the distributed config and C++ fallback. This is the cautious release-policy candidate but is **not** an instruction to switch the live server. It withholds the feature from legitimate humans until a later explicit enablement and acceptance.
- **D2: operator-controlled explicit override with current defaults documented.** This still depends on the actual deployed configuration and does not itself repair bot classification.

**Decision H-SELFBOT (not selected):** If a player has an existing SelfBot AI attachment that becomes invisible when `Playerbots.Enabled=false`, should HonorOverflow count this character as human-eligible, as a bot-excluded character, or pause rewards until identity is known? Do not copy Claude's **F14 visual/UI M1 recommendation** into economic reward policy. An AI being temporarily **not ticked** is different from proving that an AI is **not attached**.

**Decision H-REMEDIATION (not selected):** Any production identity change requires source-backed coverage of legitimate client-backed humans and RandomBots/AltBots/SelfBots under enabled/disabled/reload transitions. See the deliberately unselected options below.

## 2 — Exact source facts: what is known

1. **Module award gate.** `src/Systems/HonorOverflow.cpp` (protected `main@80e9de1`) returns `GET_PLAYERBOT_AI(player) != nullptr` for `IsPlayerBot` when compiled with Playerbots. `ProcessHonorOverflow` exits when `!HonorOverflowIncludeBots && IsPlayerBot(player)`, but then has *other* honor delta/cap and money-cap gates before `ModifyMoney`. **A false negative on bot identity does not by itself demonstrate a copper award.** Source `HonorOverflowIncludeBots=false`, distributed `IncludeBots=0`.
2. **Config mask.** Pinned [Playerbots `d750b4b`](https://github.com/mod-playerbots/mod-playerbots/tree/d750b4b3a50effdf22bedc8032f0e8e5f7cb8091): `PlayerbotsMgr::GetPlayerbotAI` and `GetPlayerbotMgr` return `nullptr` when `sPlayerbotAIConfig.Enabled=false`, even if an entry remains in a private map; `PlayerbotAIConfig::Initialize` sets `Enabled` from `Playerbots.Enabled` and returns early when disabled.
3. **Original reload/lifecycle source.** `World::LoadConfigSettings(true)` in pinned Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd` runs `sConfigMgr->Reload` and config hooks. Pinned Playerbots GM/console command paths also invoke `PlayerbotAIConfig::Initialize`. Under disabled lookup, parts of `OnDestructPlayer`, bulk logout and per-bot logout cannot see the AI object. **Other cleanup, lifecycle timing and actual owner-server reachable sequences are not exhaustively proven**; there has been no live reload.
4. **Ordinary Playerbots helpers do not fix masking.** Pinned `IsRealPlayer(player)` is `player && !GET_PLAYERBOT_AI(player)`. Pinned `IsSelfBot(player)` consults that same getter. Thus synthetic masked SelfBot appears like a human through those helpers.
5. **Independent core no-socket property is partial.** Pinned Grimfeather `WorldSession::IsHeadless()` returns `bool const _headless`, set by `_headless(!sock)` during session construction. Bot holder uses `nullptr` socket for constructed bot sessions. A **client-backed SelfBot** uses the existing client's session and can be non-headless. Headless means *session constructed without a socket*, not proof of a PlayerbotAI.
6. **Category membership is partial and may overclassify.** Pinned `RandomPlayerbotMgr::IsRandomBot(Player*)` uses a low-GUID fallback: the configured random-account list **and** `currentBots.contains`. `IsAddclassBot(Player*)` uses a GUID cache or `IsAccountType(account,2)` prepared-DB query. Both can identify **some** config-masked bots. Neither proves the presence/absence of an AI object for every player, including an unlisted SelfBot. Account-type classification may also describe an account, not an individual attached-AI state.

**Important source visibility limitation:** `PlayerbotsMgr::_playerbotsAIMap` is **private**. The inspected public getters are config-gated. No existing source-verified public, independent, universal `HasAttachedPlayerbotAI` indicator has been established. This is a bounded finding about the pinned, examined APIs, **not proof that no other possible signal exists anywhere**.

## 3 — Original, exact-head hosted evidence

| Track | DRAFT | Exact head | Original hosted CI and scope | Claim |
|---|---|---|---|---|
| P13 base | [#219](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/219) | `e2b54e4bde6f375006d86c127bdf515cf2e483b0` | Test-only parent | Synthetic HonorOverflow false-negative risk |
| R1 config reload/source default | [#221](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/221) | `ef2292bb7bb8b48962e8fc1df1f7561cddb5fe84` | Push `40766831802`, PR `40766887763`, C++17/20 7 cases each | Config-masked source transition and ON defaults; runtime not proven |
| R2 destruction lookup | [#222](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/222) | `49cb8de625d55399b6eca71c16e1a3f6cfbd2ec1` | Push `40768987729`, PR `40769020197`, C++17/20 9 cases each | Registered callback's masked lookup may skip deletion |
| R3 bulk logout | [#223](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/223) | `2db985c340ca45dce6724afd2c302770358063d1` | Push `40769565276`, PR `40769595947`, C++17/20 9 cases each | Masked bot skipped in actual-source bulk logout, substitute counter for actual logout |
| R4 public helpers | [#225](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/225) | `11d8885ce5ef85d69543ab05d06dab9b6b0e95db` | Push `40770266645`, PR `40770299953`, C++17/20 8 cases each | `IsRealPlayer` does not distinguish masked SelfBot |
| R5 core headless | [#226](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/226) | `8ccf3f480eecd70490631f6268845fc5e1bac897` | Push `40771278322`, PR `40771317335`, C++17/20 10 cases each | Independent no-socket property detects a subset, not client-backed SelfBot |
| R6 random/AddClass membership | [#227](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/227) | `3a1b8b2caa43b924618db58524853e631dea3a29` | [Push `40773227628`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40773227628), [PR `40773235041`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40773235041), **15/15 C++20 each** | Category fallback detects some masked bots, not universal |

All cited R1–R6 original event runs are recorded in the Part 36 living checklist with independently read original hosted job logs, source pins, and limitations. Tests compile specific source-extracted functions with disposable stubs; none is the real complete gameplay runtime.

P13-R6 transparent test infrastructure history: an unquoted YAML colon originally prevented one workflow run from starting; a separate fixture-output regex rejected the synthetic label `human_type2`. Both were corrected **in test/CI paths** before the exact-head successful runs. Do not erase or recast those failures as core/production behavior.

## 4 — Alternatives for an owner to consider later (NONE selected)

| Option | Scope and benefit | Main unresolved cost / blocker |
|---|---|---|
| **P0: retain current production behavior while blocked** | Zero changes; preserve strict owner control | Current distributed default-ON vs planned default-OFF conflict and masked identity uncertainty remain unresolved; **not a release safety sign-off** |
| **P1: future owner-approved OFF-by-default policy** | Prevent new HonorOverflow awards until explicitly enabled after identity and gameplay verification | Legitimate players lose this optional conversion until enabled; needs source/config change approval and separate evidence |
| **P2: future explicit Playerbots-owned ungated attachment query** | Source-of-truth accessor can distinguish attached-AI presence even if `Enabled=false`, if designed correctly | Requires upstream Playerbots/core integration contract, lifetime/thread safety, ownership review, complete source/binary testing, rollback and **separate owner approval**. Not currently implemented |
| **P3: fail closed for all client-backed users whenever Playerbots OFF or identity ambiguous** | Avoid paying unidentified attached SelfBots | Penalizes actual human players and should **not** be inferred as acceptable; requires explicit owner policy and controls |
| **P4: treat *inert masked* SelfBots as human for HonorOverflow only** | Preserves optional currency for client-controlled masked SelfBots | Changes interpretation from *AI attachment* to *current AI execution*. F14 M1 is unrelated; owner must choose economic semantics separately. Does not explain stale map/cleanup |
| **P5: use headless / RandomBot / AddClass membership as partial hints** | Improves recognition for some categories without new Playerbots public accessor | **Does not solve universal classification**; incomplete coverage and account-type false positives. **Not safe as a standalone approved patch** |
| **P6: module-maintained identity ledger** | Could remember module-observed attaches across config transitions | No source-proven complete hook coverage/atomic cleanup/restores; substantial stale-state and race risks. No guarantee without dedicated verification |

**Research recommendation, not owner selection:** keep P13 production action **BLOCKED**; request explicit H-DEFAULT and H-SELFBOT choices before considering any money behavior change, then prefer *source-of-truth, independently verifiable identity* over guessing from account category or network socket. Do not silently change defaults or approve P3/P4.

## 5 — Proposed future test and release gates, not permission

- [ ] **Owner policy captured independently:** H-DEFAULT and H-SELFBOT decisions recorded, including what counts as an AI-controlled bot during Playerbots OFF and how legitimate humans must be treated. F14 visuals cannot implicitly select an economic rule.
- [ ] **Engineering plan approved:** choose a specific future production branch and API contract, including thread ownership, no stale raw pointer publication, lifecycle when `Playerbots.Enabled` flips, logging/redaction, and failure state; no N-Core or protected-main changes without authority.
- [ ] **Test-only sources first:** genuine human (enabled and disabled), live-attached RandomBot, AltBot, SelfBot, masked headless Random/AltBot, masked client-backed SelfBot, random/AddClass membership absent/stale, same-account human, null session, alternate cleanup, config reload failures, restart/new session, repeat award and BG summary.
- [ ] **Economics controls:** exact honor snapshot, 0 earned, under cap, cap reached, daily contribution reset, full/partial gold cap, BG completion/early leave, `IncludeBots` TRUE/FALSE, no duplicate gold, and unambiguous owner-config effective values.
- [ ] **Original hosted build and test evidence:** exact pinned native Worldserver compile when an approved production patch is proposed, original unmodified source snapshots and full job logs, then *separately authorized* owner-host gameplay checks (currently **0/5 accepted**).
- [ ] **Before any owner-host change:** dated, restorable config/DB/build backup, reproducible rollback plan, explicit permission for each affected surface, safe test realm conditions and captured result. Do not infer permission from this document.

## 6 — Separate active work

Claude/CS03 [F14 P12 DRAFT #224](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/224) independently passed original source/native testing, but **F14 still unwired and M1 not selected**. F14 asks about displayed human/AI progression visibility, **not monetary eligibility**. Grok/CS02 K1 pet UID remains **fail-closed design only**, external DB writers and restores unexcluded, A02 NoWrite, relay OFF; D18 in-combat A→B hard NO-GO. LAB-004 Classic Mining package and LAB-005 four new Shaman tank totems + Tempest Shield remain **planning** and are not authorised module feature work.

**Owner accepted gameplay: 0/5.** No merges, deployment, SQL/DBC writes, live player/server/config changes or upgrades have been authorised by any P13 test result.
