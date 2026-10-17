# Hunter Playerbot autocast — no-write precedence contract

**Standalone C++20 design model. NOT included by a Worldserver translation unit. No functional restoration.**

## Pinned-source evidence

- `mod-playerbots@037c014` explicitly adds the `pet` strategy in `AiFactory::AddDefaultNonCombatStrategies` for Hunters before constructing the non-combat engine. Its strategy can later be altered by configured `ChangeStrategy` calls; this does not prove an individual bot's current active strategy.
- `HunterPetStrategy::InitTriggers` offers a `has pet` trigger that schedules `toggle pet spell` at priority 60. `HasPetTrigger::IsActive` tests for `pet target` and an unmounted bot. Whether an action actually runs, or when, requires live staging evidence.
- `TogglePetSpellAutoCastAction::Execute` directly calls `Pet::ToggleAutocast` to reassert bot defaults for known native-autocastable spells. For most skills the default is ON, but the bot has a separate disabled-spells list (e.g. Cower and Prowl). It has no native human-packet provenance.
- The prior [native-acceptance review](HUNTER-PET-AUTOCAST-INTENT-PROVENANCE.md) and [IP readiness boundary](HUNTER-PET-AUTOCAST-IP-COMPLETION-BOUNDARY.md) show that an observed packet, changed native state or fixed delay cannot authenticate either a master instruction or IP's completed legal-rank reconciliation.

## Independent advisory verdicts

| Review verdict | Only interpretation; no runtime action |
|---|---|
| `Skip` | Required Hunter-bot, pet-instance, known legal rank, native autocastability, verified IP completion or bot policy evidence is missing; or a claimed master command has not been independently authenticated and applied to the exact Pet and spell |
| `ObserveBotPolicyMatch` | Observed native ON/OFF equals a known bot default; NOT evidence of a human request |
| `ObserveBotPolicyMismatch` | Native state differs from the known bot default; this might be IP re-learning, another actor, an intentional master command or unrun bot action |
| `MasterMatchesBotPolicy` | Hypothetically authenticated, actually applied master instruction still matches the native state AND bot default; cannot authorize storage by itself |
| `MasterConflictNeedsCoordination` | Hypothetically authenticated, actually applied instruction differs from bot default; requires explicit coordination with Playerbot AI, never an external re-toggle loop |

**Important:** `HypotheticalVerifiedMasterCommand`, `postIPReconciliationVerified` and `commandAppliedToExactPetAndSpell` in this synthetic header are test evidence categories. The Naxx module cannot currently produce those authoritative facts and cannot infer them by inspecting packets, pet numbers, spell lists or timers.

## Source-backed counterexamples

Five [synthetic timeline tests](../tests/test_hunter_pet_autocast_bot_precedence_timeline.py) cover legal IP re-learn resetting autocast OFF before a later bot action, master OFF for Bite subsequently undone by bot default ON, master ON for Cower subsequently undone by bot default OFF, unknown AI trigger cadence, and missing-rank non-entitlement. The [C++20 gate tests](../tests/hunter_pet_autocast_bot_precedence.cpp) reject illegality, changed native state and unverified master provenance.

## What is still needed

An authenticated bot-master command source, demonstrated native command application, verified per-pet lifecycle identity, an authoritative post-IP return, and a safe Playerbots policy precedence/override mechanism (if conflicting master instructions should win) are still missing. These may need separately approved cross-repository work. No alternative that repeatedly re-enables/re-disables spells from a Naxx timer is permitted.

**Safety:** No changes to AzerothCore, IP, Playerbots, actual bots, SQL, config defaults, or the installed realm; the new C++ policy is standalone and not registered.