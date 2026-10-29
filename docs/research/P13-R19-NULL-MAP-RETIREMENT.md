# P13-R19 — Null-map logout branch and direct Player retirement coverage

**29 October 2026 UTC | source-only research | no owner-host test, production fix or payout.**

Pre-registered BEFORE authoring in [master issue #28 comment 6502350123](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6502350123). New independent isolated DRAFT based on immutable protected Mod main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` and pinned Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`.

## Six exact source blobs

| File | Pinned original Git blob |
|---|---|
| Mod src/Systems/HonorOverflow.cpp | d4f70c511ac5a3e32c7e6b8f913d095915da707c |
| Core src/server/game/Server/WorldSession.cpp | fc96398079b50984ed0b82183d713c666af6939b |
| Core src/server/game/Maps/Map.cpp | ba4c57ed8e095aef76de9b36e708924cb2c51a09 |
| Core src/server/game/Entities/Player/Player.cpp | 138e7eab4905ec366338a54cc18e6cfe749a3670 |
| Core src/server/game/Globals/ObjectAccessor.cpp | 8b15ce734d8f6624a29fe12e23c6917d77e1919d |
| Core src/server/game/Scripting/ScriptDefines/MiscScript.cpp | a41a3f0d9f48d0c4319a585c591ba7ec722fc37b |

## 1. Source-proven direct branch behaviour

The original [WorldSession::LogoutPlayer lines 686–878](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L686-L878) explicitly acknowledges that a logging-out Player may not currently be in-world or have a map (for example after disconnection during a map transfer). Its direct body then:

- invokes OnPlayerBeforeLogout and battleground departure;
- invokes normal OnPlayerLogout only when `!redirecting`;
- calls `_player->CleanupsBeforeDelete()`;
- calls `_map->RemovePlayerFromMap(_player, true)` and `AfterPlayerUnlinkFromMap` **only if** `_player->FindMap()` returns a Map;
- finally calls `SetPlayer(nullptr)` **outside** that map condition.

If the map exists, [Map::RemovePlayerFromMap lines 719–737](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/Map.cpp#L719-L737) calls Player::RemoveFromWorld, then OnPlayerLeaveMap, then the `remove=true` DeleteFromWorld. The Player-specific [Map::DeleteFromWorld lines 175–180](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/Map.cpp#L175-L180) calls ObjectAccessor::RemoveObject(player), removes its map-update object, and deletes the Player. Player destruction dispatches MiscScript OnDestructPlayer.

If the map is NULL, the **directly shown Map::RemovePlayerFromMap -> registry removal -> deletion chain is skipped**. The normal logout method still detaches the session Player pointer. Original [WorldSession::~WorldSession](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L169-L188) only calls LogoutPlayer(true) if it still has a non-null `_player`. Original WorldSession::SetPlayer merely assigns `_player` and conditionally caches GUID when nonnull; it does not delete its former Player. Player::CleanupsBeforeDelete directly invokes TradeCancel, DuelComplete and Unit::CleanupsBeforeDelete; it has **no explicit Player deletion or ObjectAccessor::RemoveObject** within that method body.

**Bounded conclusion:** We have identified an **unverified direct cleanup coverage gap under a source-acknowledged null-map branch**, not a proven memory leak. Other nested callbacks/handlers, map-transfer ownership, external module code or actual deployed control flow could change ultimate lifetime outcomes. It is **NOT** established that a Player survives indefinitely, that global ObjectAccessor retains it, that OnDestructPlayer never fires, or that owner players lost currency. Do not infer an observed use-after-free, race, money duplication or crash.

## 2. Conditional interaction with HonorOverflow

Original HonorOverflow OnPlayerLogout erases both per-GUID HonorSnapshots and BattlegroundHonorSummaries. A **normal, nonredirecting** logout still directly calls this hook before the map condition. A **redirecting** logout skips it by design; combining redirecting=true and no-map yields neither the normal logout hook nor the directly visible map-based destructor chain. This is a reason to require **explicit lifecycle and finality gates** in any proposed P13 state design, NOT proof of accumulated stale honor maps on the owner host.

## 3. Disposable test and limits

`tests/test_p13_r19_null_map_retirement_source.py` pins the six source blobs and extracts original method bodies for logout, WorldSession destructor/SetPlayer, Player cleanup/destructor, Map remove/DeleteFromWorld, ObjectAccessor unregister, real MiscScript destructor dispatch, and module login/logout. It asserts the map and redirect conditions, source order and absence of a direct unconditional Player deletion in these inspected bodies. **17 deliberately altered source conditions** must be caught. Four explicitly synthetic truth-table examples enumerate normal/redirect x map-found/null-map **direct function calls only**.

This does not run C++ Player methods, read host memory, test actual map-transfer dispatch, call real money hooks, run the native Worldserver, prove all nested code is side-effect free, or evaluate any owner's real database/character. A source-only Python check and hosted CI are not an in-game or memory-sanitizer test. All original logs and exact-head CI must be verified before calling the DRAFT successful.

## 4. Design and release implications

R14 [DRAFT #240](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/240) already identifies incomplete lifecycle coverage after R15–R18. R19 strengthens G2: any future authoritative Player lifetime protocol needs a separately source-proved **mapless logout/redirect retirement owner**, with safe registry removal, pending deferred-work invalidation, and settled BG/credit finality. The no-map branch cannot be treated as equivalent to the map-found branch. **No production repair, extra delete, registry mutation or compensation is safe to introduce based solely on this test.** A blind delete after the branch could create double-free or invalid state if another owner retains responsibility.

Maintain H-DEFAULT/H-SELFBOT/H-REMEDIATION UNSELECTED, state owner A/B/C unselected and R7 shared-map concurrency release HOLD. Protected Mod/N-Core mains, frozen #160 untouched; `MapUpdate.Threads=8` MUST remain 8, F14 OFF/unwired, N-Core NoWrite relay OFF, K1 Step1 not before 1 November by separate approval, D18 armed pet A-to-B HARD NO-GO. No original core/IP/Playerbots/N-Core, production source/config, Worldserver, server/client/DB/SQL/DBC, install/merge/deployment. Mandatory owner-accepted gameplay remains **0/5**. High-impact future work requires owner consent, dated restorable backups, verified restoration and rollback.
