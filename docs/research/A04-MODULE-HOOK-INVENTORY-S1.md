# A04 — This module's loot hook inventory (S1 static; DO NOT MERGE)

**Scope: only this module.** This is an exact-source static inventory, not an entire server audit, a diagnosis of the owner's human-friend pickup, or a functional quest-loot fix. We searched all **38 C++/header sources under `src/`** on protected `main` `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, as inherited by CS01-owned draft #122 (before this test was added). This inventory is **not the entire server**: AzerothCore, other installed modules, Playerbots, Individual Progression, live runtime hooks, SQL/DBC data and owner's local Playerbots changes were not enumerated.

## Exact source results

- The single `CanPacketReceive(...)` implementation and `SERVERHOOK_CAN_PACKET_RECEIVE` registration in this module's current main-derived tree are in `src/Systems/QuestLootProtection.cpp`. The loader registers `AddQuestLootProtectionScripts()` once at `src/NaxxramasCore_loader.cpp`.
- The following potential native quest eligibility / award hooks have **no implementation declarations matching those method names under this module's `src/` tree**: `OnPlayerBeforeFillQuestLootItem`, `OnAllowedForPlayerLootCheck`, and `OnPlayerLootItem`. This is a **bounded text/source scan**, not proof nobody subscribes through another module or dynamically loaded script.
- The existing guard receives `CMSG_AUTOSTORE_LOOT_ITEM` and, when enabled, considers grouped creature/vehicle **corpse** packets using a quest-slot view and three group loot methods. It returns early on ordinary `loot.items` slots, game objects, chest/pickpocket paths and unsupported group methods; rolls/master awards and other item grant routes are **not covered**. An award can happen outside this narrow packet hook.
- The current #122 parent still calls `ObjectAccessor::FindPlayer(loot.roundRobinPlayer)` in the legacy guard; its public core 8-map-thread safety is **not proven**, and Claude's independently linked default-OFF [#132](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/132) only replaces that with map-scoped lookup, leaving residual pointer lifetime review **CONDITIONAL**. Do not conflate #122's static research with #132's C++ change.
- `NaxxramasCore.QuestLootProtection.Enabled = 0` in this branch's distributed config; this is **not a statement about the owner's live effective configuration**. The module guard itself has no direct `StoreNewItem()` or loot-turn assignment. It denies some packets before the native handler but does **not** prove that a different award caller cannot grant the same item.

## Why this matters

For the owner's **actual human friend receiving apparently ineligible quest loot**, no one may conclude that this module alone changed item entitlement, nor may anyone conclude that the rest of the server is clean. The client's sparkle, packet acceptance, native `LootItem::AllowedForPlayer`, actual `Player::StoreLootItem` inventory receipt, and quest-template flags are distinct pieces of evidence. Without the quest/item ID, generated loot source, group turn, and actual inventory award, we cannot select a safe production correction.

The verified stock source trace in `A04-NATIVE-VISIBILITY-VS-AWARD-SOURCE-TRACE.md` already explains why `QuestRequired=0` quest-related items can remain shared one-copy loot. Protect valid stock group rules, per-player `ITEM_FLAG_MULTI_DROP` and rights for both human players. Do not invent exclusive "tagger owner" or multiply personal drops.

## Automated scope gate

```bash
python3 -m unittest discover -s tests -p 'test_a04_module_hook_inventory_s1.py' -v
```

This gate scans all currently checked-out `src/**/*.cpp` and `src/**/*.h` files for the named hooks and fails if new module source adds a matching receiver/eligibility hook without an accompanying source audit. It **does not** assert hook absence in AzerothCore, any other installed modules or private owner sources. No owner gameplay, server startup, SQL writes, database access or live instrumentation occurs.

**Follow-up:** Claude can continue nonconflicting #132 thread/lifetime review; CS01 continues #122/#129 scope checks. A possible other-module subscriber or alternative native award route must be verified on the actual installed source inventory *before* any correction or test-build signoff. Functional human-human A04 remains open.