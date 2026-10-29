# P13-R18 — Registry admission, map callback and redirecting retirement order

**29 October 2026 UTC. Original-source-only audit and conditional synthetic ordering tests. No production implementation or owner-host action.**

Pre-registered BEFORE authoring: [master #28 comment 6502165670](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6502165670). Immutable protected-by-project Mod main **80e9de1c39a6dc995188a80c31a5e785d0f2a6f9**. Original Grimfeather core **8daffdabe9202c228e45d833c9a1d399597a15cd**.

## Seven exact pinned source blobs

| Original source | Git blob SHA |
| --- | --- |
| Mod src/Systems/HonorOverflow.cpp | d4f70c511ac5a3e32c7e6b8f913d095915da707c |
| Core Handlers/CharacterHandler.cpp | d7123a9c503c3363ff2ea08b2d24eec7d07c5643 |
| Core Maps/Map.cpp | ba4c57ed8e095aef76de9b36e708924cb2c51a09 |
| Core Server/WorldSession.cpp | fc96398079b50984ed0b82183d713c666af6939b |
| Core Globals/ObjectAccessor.cpp | 8b15ce734d8f6624a29fe12e23c6917d77e1919d |
| Core Entities/Player/Player.cpp | 138e7eab4905ec366338a54cc18e6cfe749a3670 |
| Core Scripting/ScriptDefines/MiscScript.cpp | a41a3f0d9f48d0c4319a585c591ba7ec722fc37b |

## Actual admission order — source-supported

In [original CharacterHandler.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/CharacterHandler.cpp#L796-L1128), ordinary database login constructs a Player, attempts LoadFromDB, and if that fails deletes the Player without reaching global registration or OnPlayerLogin. On successful load, the original function executes **ObjectAccessor::AddObject(pCurrChar)** *before* the attempt at **GetMap()->AddPlayerToMap(pCurrChar)**. The normal **OnPlayerLogin(pCurrChar)** dispatch is later in the same function.

In [Map::AddPlayerToMap](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/Map.cpp#L258-L285), valid coordinates are checked first. On a successful path the Player is added to grid, its AddToWorld method runs, and **OnPlayerEnterMap(this, player)** dispatches **before** map admission returns true. That means the successful common path is:

1. Validated database load and GUID initialization.
2. Global Player registry insertion.
3. World/map admission and OnPlayerEnterMap.
4. Normal OnPlayerLogin.

**Do not interpret this as unconditional entry.** AddPlayerToMap may return false for invalid coordinates, and the login handler may attempt teleport/alternate handling before continuing. A registered Player can potentially be queried via FindConnectedPlayer **before** it is confirmed in-world, because this function returns the raw registry pointer. Registry membership alone is neither world admission nor a safe delayed lifetime lease (R16).

## Actual retirement order and redirecting exception

In [original WorldSession::LogoutPlayer](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L686-L865), OnPlayerBeforeLogout runs before battleground departure and other cleanup. The **ordinary OnPlayerLogout callback is inside an `if (!redirecting)` branch**. Later the code calls map removal if `_player->FindMap()` returns a Map, then clears the session Player pointer.

In the map-found and `remove=true` path, original [Map::RemovePlayerFromMap](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/Map.cpp#L719-L737) calls RemoveFromWorld, then OnPlayerLeaveMap and DeleteFromWorld. The Player-specific [Map::DeleteFromWorld](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/Map.cpp#L175-L181) first removes the Player from ObjectAccessor's registry and then deletes the Player, causing the real MiscScript OnDestructPlayer callback.

This yields an IMPORTANT conditional distinction:

- **Normal nonredirecting, map-found logout:** OnPlayerLogout, then map leave callback, registry removal, destruction.
- **Redirecting, map-found logout:** skips normal OnPlayerLogout but still reaches map leave, registry removal and destruction.

**Not proved:** the exact routing or reachability of all `redirecting` call sites, actual owner sidecar configuration, the rare no-map logout path, concurrent worker overlap, or whether the owner has encountered this conditional case. It is **not** safe to assume every destruction was preceded by OnPlayerLogout, or that normal OnPlayerLogout is the final destruction hook. Conversely, this source does not by itself prove any stale HonorOverflow snapshot on the owner's host. The original module's OnPlayerLogout erases its per-GUID honor and BG summary maps; R7 already identifies unsynchronized global-map hazards.

## Disposable source-only test

`tests/test_p13_r18_admission_retirement_source.py` pins the seven original source SHAs and extracts original method bodies for normal login, successful map admission, logout, map removal, Player deletion, global registration, FindConnectedPlayer, destruction and original HonorOverflow login/logout. It checks original statement ordering, redirecting conditional, failed-load early exit, map-find prerequisite and branch limitations. **Sixteen must-fail source mutations** challenge the assertions. Four **synthetic** event arrays illustrate the path differences, but the test **does not execute the original C++ Worldserver flow**, run a real logout, dereference a stale pointer, reproduce a live race, or credit copper.

The intended CI validates only exact original source facts and nonproduction three-file scope. It does not certify a stable epoch, safe Player ownership handoff, BG finality, actual installed script inventory, full native Worldserver build or gameplay.

## Architecture implications, NO new approval

R14 [remediation decision DRAFT #240](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/240) remains unselected. R15 proves conditional same-Player reattach without normal OnPlayerLogin, R16 finds raw returned Player lookup is not lifetime pinned, R17 proves construct hook is pre-GUID. R18 adds that neither global registry addition nor normal login/logout is by itself a universal well-formed lifecycle transition across failed admission, redirects and actual destruction.

Any future A/B/C ownership model must specify separate **post-load admission**, **world/map entry**, **character observation**, **redirect/quiescence**, **registry removal and destruction** states, with source-proven matching cleanup and valid thread ownership. No new epoch, queue, mutex, callback wiring, payout, retry, compensation or cap policy is approved.

**Nonnegotiable:** H-DEFAULT/H-SELFBOT/H-REMEDIATION UNSELECTED, R7 race release HOLD, Mod/N-Core protected mains and frozen #160 no-write, MapUpdate.Threads=8 must remain **8**, F14 OFF, N-Core NoWrite and relay OFF, K1 Step1 not before 1 November with separate approval, D18 armed in-combat pet A→B HARD NO-GO, LAB-004/LAB-005 brainstorm-only. No core/IP/Playerbots/N-Core/server/client/SQL/DBC/DB/install/merge/deploy work. Owner-accepted gameplay **0/5**, future high-impact work needs separate owner approval and dated restorable backups, verified restoration and rollback.
