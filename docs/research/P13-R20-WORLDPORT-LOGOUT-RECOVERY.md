# P13-R20 — Far worldport ACK and logout transfer-drain guards (R19 clarification)

**29 October 2026 UTC | strict original-source test/research only | no Player, Worldserver or owner host action.**

Before authoring, R20 scope was registered on [master #28 comment 6502829500](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6502829500). Immutable Mod protected main **80e9de1c39a6dc995188a80c31a5e785d0f2a6f9**; original Grimfeather **8daffdabe9202c228e45d833c9a1d399597a15cd**.

## Six pinned original source blobs

| Source | Git blob |
|---|---|
| Mod src/Systems/HonorOverflow.cpp | d4f70c511ac5a3e32c7e6b8f913d095915da707c |
| Core Handlers/MovementHandler.cpp | f21b8464de6f362c21cc2bdf0f4f30c1df483f33 |
| Core Server/WorldSession.cpp | fc96398079b50984ed0b82183d713c666af6939b |
| Core Entities/Player/Player.cpp | 138e7eab4905ec366338a54cc18e6cfe749a3670 |
| Core Maps/Map.cpp | ba4c57ed8e095aef76de9b36e708924cb2c51a09 |
| Core Handlers/CharacterHandler.cpp | d7123a9c503c3363ff2ea08b2d24eec7d07c5643 |

## 1. New crucial qualification to R19

Original [Player::TeleportTo far-map branch](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L1549-L1644) obtains oldmap when in world, removes the Player from the old map with `remove=false` (which does **not** delete the Player or unregister it globally), sends worldport transfer packets when appropriate, saves a destination, and sets the pending `SetSemaphoreTeleportFar` flag. A normal client `MSG_MOVE_WORLDPORT_ACK` dispatches [HandleMoveWorldportAck](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/MovementHandler.cpp#L45-L132).

**Previously missing from R19's narrow branch statement:** [WorldSession::LogoutPlayer](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L686-L805) calls `while (_player && _player->IsBeingTeleportedFar()) HandleMoveWorldportAck();` **TWICE**: first **before** starting its logout sequence, and again **before saving the character**. Thus the source itself actively tries to resolve a pending far teleport instead of always proceeding to the R19 no-map branch. A mapless logout is **not proven to occur routinely** on every disconnected transfer.

The first drain is before `m_playerLogout=true` and `OnPlayerBeforeLogout`; the second is after various Player/BG cleanup callbacks and before `SaveToDB`. The loops have no explicit numeric iteration cap in this method, although the ACK handler clears the far semaphore early; callbacks and fallback TeleportTo may alter pending state again. This **does not** prove a real infinite loop or hang.

## 2. Original ACK branches that still need proof

[HandleMoveWorldportAck](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/MovementHandler.cpp#L51-L130) is conditional:

- **Spurious ACK** when no pending far teleport: returns without changes.
- **Pending far teleport**: clears `SetSemaphoreTeleportFar(0)` **before** validating destination coordinates; invalid coordinates call KickPlayer and return before map creation/admission. This could allow logout's while condition to stop while admission remains unresolved; whether it reaches a real null-map retirement is UNKNOWN.
- **Map creation / cannot-enter failure**: calls Player::TeleportTo(homebind) and returns. That fallback might create another far-teleport request, and it may independently fail; no universal success claim.
- **Map::AddPlayerToMap failure**: resets the map, restores oldMap, attempts homebind TeleportTo and returns. The map's admission routine itself checks coordinate validity.
- **Successful admission**: AddPlayerToMap runs, leading through its normal OnPlayerEnterMap path; the ACK later calls oldMap->AfterPlayerUnlinkFromMap. This is distinct from ordinary OnPlayerLogin, which is not universally retriggered on map transfer.

Separately, original [CharacterHandler reconnect branch](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/CharacterHandler.cpp#L729-L764) uses explicit counters `limitA=10, limitB=10, limitC=10` to constrain its own far/near ACK attempts. **Those counters do not bound the separate LogoutPlayer transfer-drain loops.** The cited source is insufficient to prove a real hung logout, guaranteed successful fallback or memory leak.

## 3. R19 evidence corrected, not erased

R19 [DRAFT #245](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/245) correctly established the conditional fact: if `FindMap()` is NULL at the **final** logout map-removal branch, that direct Map::RemovePlayerFromMap -> registry RemoveObject -> delete Player chain is skipped while SetPlayer(nullptr) still executes. **R20 narrows R19's practical interpretation:** before reaching that branch, the same original function attempts to settle an outstanding far teleport up to two *locations* in its control flow (not a promised count of exactly two ACK invocations). This guards against presenting a source-level conditional branch as a demonstrated host memory leak or expected routine error.

**NO evidence** that the owner reached the null-map condition or suffered a retained Player, leaked money, duplicate HonorOverflow reward, crash or infinite loop. Other cleanup ownership/sidecar callbacks remain unassessed. Do not add unconditional Player deletion, forcibly clear teleport flags or alter currency in response to this research.

## 4. Test contract and limitations

`tests/test_p13_r20_worldport_logout_source.py` pins all six original source Git blobs and parses original C++ method bodies for the far-map TeleportTo branch, worldport ACK and opcode, LogoutPlayer's two transfer-drain sites, conditional world admission and earlier R19 cleanup, and reconnect's separate bounded recovery loop. **20 deliberately incorrect source-block mutations** must be caught. Five synthetic branch cases illustrate conditions only. The test does not invoke an actual C++ Player, teleport, Worldserver or simulated active map; no full-game behavior, race, memory fault or money movement is inferred.

The hosted exact-HEAD results and original complete job logs must be reviewed before recording final success; an isolated synthetic source guard is not a native test.

## 5. Owner controls and design gates

R14 [DRAFT #240](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/240) still leaves architecture A/B/C and monetary H-DEFAULT/H-SELFBOT/H-REMEDIATION **UNSELECTED**. Any G2 state-owner protocol must distinguish pending far teleport, ACK attempts (including fallback and kick), successful map admission, no-map retirement, same-Player session reattachment and BG/currency finality without keeping an unsafe raw Player pointer. R7 concurrency release HOLD stays.

Protected Mod/N-Core mains and frozen #160 no-write. MapUpdate.Threads=8 MUST stay **8**. F14 OFF/unwired, N-Core NoWrite and relay OFF, K1 Step1 not before 1 November and only with separate approval, D18 already-armed in-combat pet A→B HARD NO-GO; LAB-004/LAB-005 planning only. No SQL/DBC, owner server/client/DB/Worldserver, original core/IP/Playerbots/N-Core, merge/install/deploy changes. Mandatory owner-accepted gameplay **0/5**. High-impact future work requires explicit approval, dated restorable backups, verified restoration and rollback.
