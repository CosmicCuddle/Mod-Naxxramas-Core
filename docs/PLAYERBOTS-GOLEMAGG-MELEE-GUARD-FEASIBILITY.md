# Molten Core — Golemagg Melee Altbot Guard: Pinned-Source Feasibility Gate

**Status:** **S1 research only. Module-only runtime listener NOT YET FEASIBLE under the exposed pinned API. No workaround implemented.**  
**Project:** [Master checklist #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) → A01; [tracking issue #27](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/27).  
**Reference:** Playerbots source commit [`037c01418b5d01506917a3db9b44fd56ac5f965c`](https://github.com/mod-playerbots/mod-playerbots/tree/037c01418b5d01506917a3db9b44fd56ac5f965c). **This is a pinned public source audit, not verification of the operator's currently installed source revision.**  
**Observed issue:** During Molten Core Golemagg, non-tank melee Altbots repeatedly retreat/return; tank deaths and wipes near half health. These are observations, not proven causality.

## 1. Exact source findings

1. [`MCHelpers.h`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Raid/MC/MCHelpers.h) has `SPELL_MAGMA_SPLASH = 13880`, `MAGMA_SPLASH_BACK_OFF_STACKS = 20`, and `MAGMA_SPLASH_BACK_OFF_DISTANCE = 12.0f`. These constants are **upstream-owned** and not a contract to hardcode into Naxx Core forever.
2. [`MCTriggers.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Raid/MC/MCTriggers.cpp) → `McGolemaggMagmaSplashTrigger::IsActive` rejects tanks, missing boss, health at/below 10%, and Magma Splash under 20 stacks. Once the bot is at least 12 yards away, the back-off trigger stops firing.
3. [`MCActions.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Raid/MC/MCActions.cpp) → `McGolemaggBackOffAction::Execute` stops the bot casting and `MoveAway`s only the remaining distance needed to reach the 12-yard separation.
4. [`MCMultipliers.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Raid/MC/MCMultipliers.cpp) → `GolemaggMultiplier::GetValue` blocks specific `AttackAction`, `MeleeAction`, and `CastReachTargetSpellAction` while a non-tank has high stacks and Golemagg is above 10%. It **does not include generic `MovementAction`** in that Golemagg branch.
5. [`ReachTargetActions.h`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/ReachTargetActions.h) proves `ReachMeleeAction : ReachTargetAction : MovementAction`. [`MovementActions.h`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/MovementActions.h) also defines `CombatFormationMoveAction`, `SetBehindTargetAction`, `RearFlankAction` and other movement subclasses. Therefore an independent re-approach movement is **source-plausible**, but **which action actually fires for the raid's melee bots is not yet proven**.
6. [`MCStrategy.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Raid/MC/MCStrategy.cpp) schedules the back-off action via a raid strategy trigger, and creates `GolemaggMultiplier`. A separate generic movement path may still be considered by the engine.

**Finding:** The missing generic-movement filter is a concrete source gap. **Do not claim that it definitively caused the user-observed oscillation until exact action execution is observed.**

## 2. Why the first proposed module-only listener is presently BLOCKED

- The pinned [`Engine.h`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/Engine/Engine.h) exposes `ActionExecutionListener`, public `Engine::AddActionExecutionListener` and `Engine::removeActionExecutionListener`.
- However, pinned [`PlayerbotAI.h`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/PlayerbotAI.h) declares `Engine* currentEngine` and `Engine* engines[BOT_STATE_MAX]` as **protected**, with **no public `GetCurrentEngine()` declaration**. Public `GetState`, `ChangeStrategy`, `GetStrategy`, `GetAiObjectContext` and `DoSpecificAction` do **not** establish module-owned access to `Engine::AddActionExecutionListener`.
- The available [`AiObjectContext.h`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/Engine/AiObjectContext.h) exposes actions/strategies/values, not the backing engine or an independent add-listener API. Deriving from `PlayerbotAI` merely to access protected data is not a safe integration with the existing PlayerbotAI object.
- [`PlayerbotAI.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/PlayerbotAI.cpp) builds separate combat, non-combat and dead engines. Combat state transitions call `ReInitCurrentEngine()`; `SelectiveResetStrategies` and `ResetStrategies` rebuild strategy state. The bot AI destructor **deletes all engine objects**. Any future listener needs proof of which engine it is attached to, repeat registration, and correct lifetime across relog/AI recreation.
- Pinned [`Engine.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/Engine/Engine.cpp) deletes every still-registered listener when its `ActionExecutionListeners` is destroyed. Its `Remove` only unlinks: it does **not** delete. Engine-owned listener plus Naxx-owned `unique_ptr`, arbitrary engine pointer caching or duplicated attachment could cause double deletion, stale pointers or leaks.
- **Important behavioural trap:** `Engine::ListenAndExecute` uses `AllowExecution(...) ? action->Execute(event) : true`. A veto skips `Execute` **yet returns true as the action-executed result**, subject to subsequent `OverrideResult`. This can affect scheduling/relevance and may not behave like an ordinary failed action. It is not safe to advertise an unconditional veto as a harmless fix.
- Overriding PlayerbotAI strategy lists or sending repeated master movement commands via exposed public methods is **not** equivalent to a reliable per-action block and risks new tug-of-war/movement loops.

**Decision at this checkpoint:** **Do NOT register an ActionExecutionListener from Naxx Core**, cast around protected `Engine*`, inject into private layouts, take ownership of Playerbots Engine objects or alter upstream files. No module-only veto architecture has passed S1.

## 3. Safe options for the next investigation (not automatically approved)

1. **Verify the operator's exact installed Playerbots SHA and public API.** The public upstream `master` branch can differ from this pin; no conclusion about future builds without repeating the review. Re-check for supported public callbacks and compatible ownership conventions.
2. **Establish the actual movement executor (read-only first).** Collect a short, per-bot action/trigger trace during a safe future controlled Golemagg attempt (Grau Rogue initially); correlate timestamps, Magma Splash stack and remaining duration, boss health, bot-boss distance, action name and intended target. Check `reach melee`, `set behind`, `rear flank`, `combat formation move`, target changes and generic chase. Do not enable a spammy debug strategy on a busy live 40-bot raid without separate approval.
3. **Inspect supported module-facing hooks** on the operator's AzerothCore fork for a genuinely safe action-selection interception or an externally registered strategy/multiplier interface that does not require protected engine access. Prove bot/Altbot identity, teardown and exact source compatibility.
4. If a public module extension proves viable, propose a **minimal default-OFF Golemagg-only guard**; only suppress the specifically proven re-entry action when *its target is the boss*, non-tank melee bot has real >=20 stacks, map is Molten Core (409), encounter is valid and boss health >10%. Preserve survival movement, tanks and Core Ragers. No blanket `MovementAction` denial.
5. If no supported extension exists, submit a **separate minimal upstream Playerbots API/fix proposal** for owner decision. Do **not** edit upstream code, auto-reapply a patch after updates or present a source patch as installed by Naxx Core.

## 4. Future configuration and acceptance gates

These are **proposed settings**, not implemented configuration:

```ini
NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 0
NaxxramasCore.Playerbots.GolemaggMeleeGuard.IncludeAltbots = 1
NaxxramasCore.Playerbots.GolemaggMeleeGuard.IncludeRandomBots = 0
NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug = 0
```

- [x] **S0:** Issue/request scope and raid observation captured in #27.
- [x] **S1 partial:** Reproduce pinned source/threshold/movement inheritance and **document listener access and veto semantics blockers**.
- [ ] **S1 complete:** Prove real action target, safe public extension point and listener ownership/engine lifecycle or document that module-only action veto is infeasible.
- [ ] **S2:** Implementation **only after S1 feasibility** in an isolated Naxx Core draft PR with opt-out/default OFF, no upstream source changes.
- [ ] **S3–S4:** Exact Worldserver C++ compile/link and disabled-mode regression, AI reset/logout/teardown, no leaks/stale listener pointers.
- [ ] **S5:** Operator-approved backup of module, config, SQL (if ever needed) and Worldserver binary; reversible deployment plan. Previous user PC backups of Playerbots source files are **not** authorisation to edit them.
- [ ] **S6:** Test normal attacks, 20-stack back-off, stay out until debuff disappears, final <=10% burn, lava avoidance and other survival movement; first Grau then Enhancement/Fury then nine named melee. Regress Garr, Baron Geddon and Ragnaros; retest altbot relog, death, engine reset and restart.
- [ ] **S7:** Release only after user accepts observed results and a working rollback. **Tank deaths, healing and Core Rager handling remain separate observations.**

## 5. Immediate next action

**S1 continued:** find a genuinely exposed action-level extension API in the exact operator fork, or prove none exists and present a **non-deployed upstream proposal**. Record real movement executor evidence before implementing a combat-time block. Cross-check this issue and master checklist before any new Golemagg change.

**Nothing in this feasibility report implements a live fix, changes Playerbots/AzerothCore/IP, changes config/SQL, merges, recompiles or restarts Worldserver.**
