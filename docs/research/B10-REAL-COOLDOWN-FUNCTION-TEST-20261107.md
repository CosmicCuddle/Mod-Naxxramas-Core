# Naxx B10 integrated cooldown methods — actual source native extraction test

**Owner:** CosmicCuddle. **Maintainer:** CS01 Maintenance, 7 November 2026.
**Parent:** [Naxx integrated DRAFT #120](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/120) exact \`599d1cbb211e6f108a2a6ff9fec78242ffe7a37c\`. **Test-only child, no production C++ touched.**

## Why this test is necessary

The prior independent [#156](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/156) ThreadSanitizer tests exercised the new **separate** \`ConsumableCooldownStore.h\` implementation, not the *actual integrated* B10 mutex-protected \`ConsumableCooldownUntil\` implementation in #120. Treating that as proof of #120 race freedom would be inaccurate.

The new \`tests/test_b10_real_cooldown_native.py\` reads #120's actual \`src/Systems/BotRaidConsumables.cpp\` from the checked-out commit. It extracts byte-for-byte:
- original \`CONSUMABLE_COMMAND_COOLDOWN_SECONDS = 10 * 60\`;
- original \`ConsumableCooldownLock\` and \`ConsumableCooldownUntil\` definitions;
- original \`GetConsumableNow\`, \`GetConsumableCooldownRemaining\`, \`StartConsumableCooldown\`, \`ResetConsumableCooldownForGroup\` C++ method definitions.

Only Worldserver interfaces are replaced with **stand-in** \`Player\`, \`Group\`, \`GroupReference\`, \`ObjectGuid\`, \`GameTime\` definitions. Production method **bodies are preserved unmodified**. Both ordinary and 8-worker contention tests exercise those original compiled C++ methods, not a reimplemented store.

The test checks no cooldown, null, start+renew, exact 600-second expiry and removal, death group capture/clear and unrelated group preservation, GUID persistence through different fake player objects, no group game API under lock, and 8 workers on a shared map. Python source guard plus hostile mutations require all three original mutex guards and exact original cooldown. ThreadSanitizer positive suite must remain race-free, and a *deliberately unlocked copy generated only in CI* must trigger a data-race warning to demonstrate sensitivity.

## Explicit boundaries

This is stronger evidence than the #156 separate-store TSAN test, but it **cannot prove**:
- that real \`Player\`, \`Group\`, \`CustomData\` lifetime or callback thread affinity is safe;
- no race in HonorOverflow, ForcedPvP, Warrior/Warlock timer paths or the separate cross-map aura queue;
- actual installed version, Core/Playerbots compatibility, Worldserver startup, config load, 8-map-thread gameplay, GFPP actual owner 120-second behavior, or in-game client behaviour.

No source code or config/SQL/DBC/client data changes in this child. The inherited actual B10 source retains the original owner feature and last reviewed 120-second GFPP duration. Workflow may be blocked by TSAN environment restrictions; distinguish unsupported sanitizer setup from actual race. Owner-approved backups and staged game tests remain mandatory. [Duplicate #155](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/155) and [canonical #114](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/114) still identify source ownership.

**Rollback:** discard this DRAFT child without any runtime or live server effects.
