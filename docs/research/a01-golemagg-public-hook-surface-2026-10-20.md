# A01 Golemagg — inspected public movement extension surface (S1 only)

**Date:** 20 October 2026. **Status:** read-only pinned-source investigation, **NOT** a movement correction, **NOT** installed or in-game tested.

**Pinned dependency evidence:** `mod-playerbots/mod-playerbots` at `037c01418b5d01506917a3db9b44fd56ac5f965c`; `Grimfeather/azerothcore-wotlk` at `8daffdabe9202c228e45d833c9a1d399597a15cd`. Owner-installed Playerbots SHA is **unknown** and must be separately checked before test or upgrade.

## Concrete inspected surfaces

| Potential extension | Verified at exact pin | Limitation |
| --- | --- | --- |
| `PlayerbotAI::ChangeStrategy(name, BotState)`, `GetAiObjectContext()` | Public in `src/Bot/PlayerbotAI.h` | Select/get known strategies; does not offer a public creator registration in the reviewed headers |
| `Engine::AddActionExecutionListener` | Public in `src/Bot/Engine/Engine.h` | Live bot's `currentEngine` and `engines[BOT_STATE_MAX]` are **protected** in `PlayerbotAI.h` — not externally accessible by a regular module script |
| Custom `Strategy::InitMultipliers` | `RaidMcStrategy::InitMultipliers` already inserts `GolemaggMultiplier` in `src/Ai/Raid/MC/MCStrategy.cpp` | Live bot `AiObjectContext::strategyContexts` is protected and the static shared factory registry is private. `NamedObjectContextList` stores const references. Building an unrelated registry does **not** insert into the live engine |
| `MovementHandlerScript::OnPlayerMove` | One hook, `MOVEMENTHOOK_ON_PLAYER_MOVE`, and **void** callback in `ScriptDefines/MovementHandlerScript.h/.cpp` | Carries `Player*`, `MovementInfo`, opcode — **no action name, multiplier, return-veto or per-Playerbots action decision**. Do not assume a movement packet callback intercepts the bot action queue |
| `PlayerScript::OnPlayerUpdate`, `UnitScript::OnUnitUpdate` | **void** update callbacks in `ScriptDefines/PlayerScript.h`, `UnitScript.h` | Can observe/update but offer no named Playerbots `MovementAction` veto, engine listener registration or strategy multiplier injection |
| Existing core MC Golemagg implementation | `GolemaggMultiplier` installed via `RaidMcStrategy`; Magma Splash threshold >=20 stacks, 12yd retreat and <=10% HP burn override verified earlier in issue #27 | Existing multiplier stops *selected attack-related actions*; this is not a proven general anti-reengagement movement barrier |

## Narrow conclusion and limitations

**Finding:** No safe externally registerable *action-level movement veto* is demonstrated by the **particular inspected public surfaces** at these two exact pins. This is NOT a global proof that no hook could exist elsewhere. No speculative private pointer casts, registry rewrites, global `MovementAction` suppression, or disabling the built-in Molten Core strategy.

**Source regression:** `scripts/check_a01_golemagg_public_hook_surface.py` checks these concrete declarations against exact pinned source. It intentionally reports `external_golemagg_action_veto_proven=false`, so even a PASS means the original API **limitation remains**; it does not imply feature completion. Tests check several mutation cases (public/protected boundary changes, void vs bool hook, callback dispatch changes). Any upstream change in these exact signatures must trigger a fresh review, not silently pass. It does not parse all C++ code or audit all hooks.

**Next evidence gates:** establish installed Playerbots SHA; if and only if the owner authorises it, backed-up **Grau-only read-only observer** [#40](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/40) can log the concrete reengagement action without changing movement; determine whether a truly public action listener/multiplier extension is available in that installed version; independently verify tank/Core Rager problem rather than assuming movement oscillation causes every wipe. The current read-only observer builds in [#41](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/41) are **not** a fix. Altering Playerbots source, exposing internal engine APIs, enabling or deploying anything, SQL/DB/gear changes and live tests need separate owner approval and backup/rollback.

**Tracker:** [A01 issue #27](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/27); [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28); [coordination #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48).
