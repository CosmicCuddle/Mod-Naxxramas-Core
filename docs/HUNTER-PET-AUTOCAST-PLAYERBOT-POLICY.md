# HPA-G3 — Native Playerbot autocast policy vs per-pet preference storage

**Research only.** Sources are pinned to `mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c`. The user operates Hunter Playerbots; a design that handles only human-owned pet packets is **not sufficient** to solve that use case.

## Verified direct paths

- [`TogglePetSpellAutoCastAction::Execute`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/PetsAction.cpp) examines known native-autocastable spells, then calls `pet->ToggleAutocast(spellInfo, shouldApply)` **without CMSG** when current status disagrees. `shouldApply` defaults to ON; a static `disabledPetSpells` list selects OFF for specific skills including Prowl, Cower, Leap, Spell Lock, Devour Magic and Spirit Wolf Leap. It also removes stale entries from `pet->m_autospells` (separate native list editing). This is AI policy, **not** a verified human preference.
- [`PlayerbotAI.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/PlayerbotAI.cpp) includes at least two command-casting paths that toggle a known pet spell with `pet->ToggleAutocast(spellInfo, !autocast)` and message the master. Even if triggered by a human master, the generic Naxx pre-handler pet-packet observer cannot attribute that human intent; bot actions may have multiple origins.
- [`TameAction.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/TameAction.cpp) and [`PlayerbotFactory.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/Factory/PlayerbotFactory.cpp) call `pet->ToggleAutocast(spellInfo, true)` directly for nonpassive spells (native function independently checks `IsAutocastable`).

**Hunter strategy trigger:** The pinned [`GenericHunterNonCombatStrategy.cpp`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Class/Hunter/Strategy/GenericHunterNonCombatStrategy.cpp) schedules `NextAction("toggle pet spell", 60.0f)` for the `"has pet"` trigger under `HunterPetStrategy::InitTriggers`. This connects the direct policy action to ordinary Hunter non-combat AI, not only factory/taming. It does **not** by itself prove whether that strategy is active on a particular bot, the trigger cadence or the exact time relative to IP reconciliation; those need staging evidence.

## Why this changes the design

An external restoration of ON or OFF could be overwritten by the next `TogglePetSpellAutoCastAction`. Conversely, storing the AI's batch changes as a human preference would accidentally treat its default ON or excluded OFF as a deliberate player choice. The bot's active policy and the IP legal-rank rules must be respected independently.

A bot-master chat command **may** be intentional, but the existing packet observer cannot verify its origin or after-handler application. A separate explicit command/provenance contract and policy precedence would be needed before persisting it; no such authenticated module-only channel has been demonstrated.

## Safest prospective split (not implemented)

1. **Normal human Hunter:** persist only confirmed, native accepted, explicitly attributable player ON/OFF commands for the correct pet and lawful rank, after IP readiness and identity guarantees.
2. **Hunter Playerbot:** observe current Playerbot policy as the bot policy, not a human preference. To preserve a deliberate bot-master override would require a separate authenticated command source and a policy precedence model that does not continuously fight bot AI. The current standalone C++ gate explicitly rejects `isPlayerbot=true` until this is proven.
3. **All known native autocastable abilities:** no blanket ON, forced rank, synthetic dummy spell or unlock. Each known family/rank must remain IP-legal; every OFF is independent of default OFF.

## Tests and blockers

New [pinned source guard](../scripts/check_hunter_pet_playerbot_autocast_pinned.py) verifies the exact direct call sites. [Offline model](../tests/test_hunter_pet_autocast_playerbot_policy_model.py) shows how a later bot policy operation can override a hypothetical external ON or OFF, while excluding removed and non-autocastable spells. The model does not prove how frequently the Playerbot action runs in the real server or cover all bot AI paths.

**No modifications to Playerbots, IP, AzerothCore, live pet data, SQL, or game servers.** Do not activate autocast restoration based on this source reading or the synthetic model. A proper module-only architecture must either coexist with bot policy without overrides or clearly report an unresolvable upstream interaction for separate review.