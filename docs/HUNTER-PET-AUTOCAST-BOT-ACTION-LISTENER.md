# Hunter Playerbot action execution listeners — module-only boundary

**SOURCE-PINNED RESEARCH ONLY — no ActionExecutionListener registered in Naxxramas Core or Playerbots.**

## A real but incomplete integration surface

At pinned [Playerbots Engine.h](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/Engine/Engine.h), `Engine::AddActionExecutionListener` and `removeActionExecutionListener` expose internal callbacks around actions. [Engine.cpp](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/Engine/Engine.cpp) invokes the listener chain before and after `action->Execute(event)`. This is **closer** to bot-policy execution than the chat or Pet packet observer.

However, it is NOT currently a safe Naxx-to-Playerbots public integration: `PlayerbotAI` stores `currentEngine` and `engines[]` as **protected** members with no verified public engine accessor or listener-registration proxy. A module cannot assume it can attach to an existing bot engine by using PlayerbotAI's public interface. Subclass/cast/private-field hacks are not acceptable.

## The `After` boolean is not evidence of an actual pet toggle

The pinned dispatcher evaluates `AllowExecution(action,event) ? action->Execute(event) : true`. **If `AllowExecution` vetoes the action, the returned value becomes true without an action call.** It then runs `OverrideResult` before calling `After(action, executed, event)`, so another listener can change the result either way. Even a genuinely executed [`TogglePetSpellAutoCastAction::Execute`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/PetsAction.cpp) only returns an aggregate `toggled` flag after visiting multiple known autocastable spells. This does not identify which spell changed, which native command actually applied it, or whether a later actor overwrote it.

`Event(std::string const source)` defaults its owner pointer to null; ordinary `Trigger::Check` creates that event without a real master. A default Hunter `has pet` bot-policy action is NOT a deliberate human instruction merely because an after-listener ran.

## Ownership risk

`ActionExecutionListeners::~ActionExecutionListeners()` deletes every pointer still registered. `Remove()` merely removes the pointer from its list. Any cross-module subscription must define safe registration after bot Engine creation, safe detach before either Engine or external plugin destruction, a **single** owner for allocations, and relog/reinit/engine-switch handling. Registering now without this contract could cause leaks, dangling pointers or double-free.

## What can be considered later

A separately reviewed integration could expose a supported observer registration API on PlayerbotAI, paired with lifecycle-safe owner rules. A **true native applied per-spell result**, human/AI origin and IP/pet identity would still require independent proof. Adding only a listener accessor is insufficient. No upstream edits or runtime callbacks have been made.

The [source guard](../scripts/check_hunter_pet_playerbot_action_listener_pinned.py) detects changes in these assumptions. [Synthetic unit tests](../tests/test_hunter_pet_autocast_action_listener_model.py) demonstrate false positives caused by veto and overridden results, multiple spells sharing one boolean, a default event without a master and pointer ownership ambiguity. They do not simulate the real engine's full lifecycle.

**Safety boundary:** no preference capture, no native ON/OFF alteration, no database writes, no live realm testing, no enabled audit, no merge or release.