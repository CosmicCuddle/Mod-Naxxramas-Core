# Bot Consumables — map-thread safety fix (#155, draft)

**Status:** P0 source-safety draft, authorised by CS01 in #155 as one Claude-owned branch from main `80e9de1`. **DO NOT MERGE.** No gameplay, config, SQL, DBC or Playerbots change. Default behaviour is unchanged. Not tested in game or on the owner's 8-thread server.

## The problem on main `80e9de1`

`Map::Update` calls `player->Update` (`Map.cpp` L454, L489), which calls `OnPlayerUpdate` (`PlayerUpdates.cpp` L314) on `MapUpdater` worker threads. With `MapUpdate.Threads = 8`, players on **different maps** run that hook **at the same time**.

`BotRaidConsumables.cpp` kept three process-wide `std::unordered_map`s with no lock. Every access:

| Container | Access (main line) | Thread |
|---|---|---|
| `ConsumableAliveState` | `OnPlayerUpdate` find and insert (L4582–L4588), **every player, before any feature check** | map |
|  | `OnPlayerLogout` erase (L4668) | world, or a bot's own map thread (Playerbots self-logout) |
| `RaidConsumableTrackers` | `OnPlayerUpdate` find (L4604) and erase on leaving the instance (L4622), **every player** | map |
|  | `ResetTracker` find and insert (L3570–L3582); `HandleStatusCommand` find (L4281); `HandleClearCommand` find and erase (L4375–L4390) | world (`.bot consumables`; chat is `PROCESS_THREADUNSAFE`) |
|  | `OnPlayerLogout` erase (L4665) | world or the bot's own map |
| `ConsumableCooldownUntil` | `GetConsumableCooldownRemaining` find and erase (L444–L458); `StartConsumableCooldown` insert (L473) | world (command) |
|  | `ResetConsumableCooldownForGroup` erase for the dead player and **every group member** (L491, L508), called from `OnPlayerUpdate` on death (L4596) | **map** |
|  | the same function from the command when the issuer is dead (L4506) | world |

**Why this is undefined behaviour.** Two map threads inserting or erasing (rehashing) while another runs `find` on the same `unordered_map`. That can corrupt the heap or crash.

## The fix

| State | New home | Why it is safe |
|---|---|---|
| Last alive state | `player->CustomData` (`ConsumableAliveData`) | Only that player's map thread (`OnPlayerUpdate`) or its own logout touches it. |
| Raid consumable tracker | `player->CustomData` (`RaidConsumableTrackerData`) | It is always looked up for the `Player*` already in hand: the command issuer, or the updating player. That player's map thread, or the world thread while map workers wait, is the only user. |
| Command cooldowns | `NaxxramasConsumables::CooldownStore` (`ConsumableCooldownStore.h`): one `std::mutex` around one map | Must survive logout, so a relog cannot bypass the 10 minutes, and a death resets **other** members, who may be on other maps. Every public method takes the lock. The lock is never held while calling game code. |

**Facts behind the per-player choice (core `8daffda`):**
- **Lifetime.** `CustomData` is a member of `Object` (`Object.h` L237); `DataMap` is per-object (`common/DataMap.h`). It is the same `Player` object across teleports. At logout, `WorldSession::LogoutPlayer` runs `OnPlayerLogout` and then `RemovePlayerFromMap(_player, true)` → `DeleteFromWorld`, so the state is destroyed with the player. The old code erased it in `OnPlayerLogout`; the new code still erases it there explicitly.
- **No overlap with commands.** World-thread chat commands (`UpdateSessions`, `World.cpp` L1227) and CLI commands (L1350) never overlap map workers: `MapMgr::Update` (L1254) waits in `MapUpdater::wait()` (`MapMgr.cpp` L280) until every map has finished.
- **Precedent.** main already keeps per-player state this way in `OnPlayerUpdate` (`BotGolemaggActionAudit.cpp`, `player->CustomData`).
- **Hot path.** `OnPlayerUpdate` takes **no** lock. The keys are `std::string` constants, so no string is built per update.

**Group reset.** `ResetConsumableCooldownForGroup` first collects member guids **without** the lock, by walking the group as main already did, then calls `CooldownStore::Reset` once. Walking a group whose members are on other maps was already the behaviour on main; it is not made worse here.

## What is unchanged

- **Command behaviour:** the `.bot consumables` command text, cooldown length and messages; "a death or wipe resets the cooldown"; cooldown kept across logout; status and clear output.
- **Timers and aura handling:** profile cleanup when leaving the instance; the GFPP one-shot timer and all aura logic. The 90-second timer on main is **not** changed here.
- **`OneShotEnabled`:** it is still read live at its two sites. A separate reload-preserving snapshot is a later, separate draft.
- **Other modules:** Warrior and Warlock bot timers, ForcedPvP and HonorOverflow are **not** in this PR; they are a later, separate draft.

## Tests

- **`tests/test_bot_raid_consumables_thread_safety.py`** (source contract):
  - the three globals and any guid-keyed global container are gone;
  - per-player state lives on the `Player`;
  - `OnPlayerUpdate` takes no lock;
  - logout still clears and still keeps cooldowns;
  - cooldowns are reached only through the store;
  - the group reset collects guids before locking;
  - every store method locks;
  - the header has no game dependencies.
- **`tests/consumable_cooldown_store.cpp`** (native, C++17 and C++20, `-Werror`):
  - semantics: expiry removed on read, restart, group reset, non-members kept;
  - 20,000-step randomised parity with the old unlocked code;
  - an **8-thread** contention run, which is **clean under ThreadSanitizer**;
  - a **negative control**: the same workload on an unlocked map, which ThreadSanitizer **must** flag, proving the test can see a race.
- **`tests/test_mc_gfpp_one_shot.py`**: one assertion moved from `RaidConsumableTrackers.erase(` to the equivalent `EraseTracker(` (three erase paths). No test was skipped or removed.
- **Pinned full Worldserver link** (core `8daffda`, Playerbots `d750b4b`, IP `dd96f2b`): built locally. On CI, the existing GFPP, Hunter ammo and combined workflows link it whenever this file changes.

## Not verified

- an in-game run, the owner's 8-thread server, or any crash backtrace;
- that this race caused any reported crash;
- that other modules are race-free (see #155 items 2 and 3).
