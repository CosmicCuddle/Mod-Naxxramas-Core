# P13-R15 — Original same-Player reconnect and hook continuity

29 October 2026 UTC. SOURCE-ONLY RESEARCH / DISPOSABLE TEST. NO PRODUCTION ACTION.

Pre-registered BEFORE writing at [master issue #28 comment 6500585161](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6500585161). Original Mod main 80e9de1c39a6dc995188a80c31a5e785d0f2a6f9 and Grimfeather core 8daffdabe9202c228e45d833c9a1d399597a15cd.

## Five original source blobs

- Module src/Systems/HonorOverflow.cpp: d4f70c511ac5a3e32c7e6b8f913d095915da707c.
- Core src/server/game/Handlers/CharacterHandler.cpp: d7123a9c503c3363ff2ea08b2d24eec7d07c5643.
- Core src/server/game/Server/WorldSession.cpp: fc96398079b50984ed0b82183d713c666af6939b.
- Core src/server/game/Server/WorldSessionMgr.cpp: 50598d3913404a6f74ec87fe1e0892d216a969b8.
- Core src/server/game/Entities/Player/Player.h: 5a29ac7b40ade7a11f1fcf36623dc7530ea39595.

## Source fact: conditional reattachment

[Original CharacterHandler.cpp lines 675–795](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/CharacterHandler.cpp#L675-L795) has a specific existing-offline-Player reconnect branch. It verifies the same account/character GUID, live non-kicked Player, CONFIG_ENABLE_LOGIN_AFTER_DC, and an in-world Player with a map after transfer acknowledgement handling. The source detaches the **same** Player from the old WorldSession, sets the **same Player pointer** on the new WorldSession, rebinds Player::SetSession and PlayerMenu, calls HandlePlayerLoginToCharInWorld, and returns without a DB-load login.

[HandlePlayerLoginToCharInWorld lines 1137–1276](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/CharacterHandler.cpp#L1137-L1276) has no DIRECT normal OnPlayerLogin or OnPlayerLogout dispatch, unlike normal HandlePlayerLoginFromDB which invokes sScriptMgr->OnPlayerLogin at line 1126. Reconnected client/packet functions may invoke other script hooks; this finding is NOT proof the whole reconnect path is callback-free.

[WorldSession::SetPlayer lines 1398–1405](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L1398-L1405) updates m_GUIDLow only if the new Player pointer is non-null. SetPlayer(nullptr) therefore leaves the OLD WorldSession holding its previous cached GUID, while the new WorldSession also stores the same GUID. A cached session low GUID is **not a unique active Player-lifetime token**. This is not evidence of a real exploit or unintended payout.

[WorldSessionMgr.cpp lines 120–202](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSessionMgr.cpp#L120-L202) conditionally preserves socket-closed sessions in an offline container and later deletes entries without a Player, after timeout or kicked. Actual owner configuration and reachable callback schedules remain UNKNOWN.

[Module HonorOverflow.cpp lines 330–398](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/80e9de1c39a6dc995188a80c31a5e785d0f2a6f9/src/Systems/HonorOverflow.cpp#L330-L398) stores an initial HonorSnapshot and erases BG summary on OnPlayerLogin; OnPlayerLogout erases both. The original reattachment shortcut does not directly invoke either, so a network session change alone does **not guarantee** new HonorOverflow snapshots. Other normal Player updates may continue while disconnected, so this is no proof the maps remain unchanged on a live server.

## Disposable source-block witness

The R15 test pins all five original blobs; source-checks offline eligibility and cleanup, original reconnect source order, absence of direct normal OnPlayerLogin/Logout calls in shortcut and helper, and original module login/logout semantics. It compiles the literal original core reattachment block, original WorldSession::SetPlayer, inline Player::SetSession and module StoreHonorSnapshot/OnPlayerLogin/OnPlayerLogout in dummy C++ Player/WorldSession and maps. Tests verify the same dummy Player is retained between distinct sessions, stale low GUID remains in the old session, and the module snapshot/BG summary is not reset **solely by the transfer**. The original module normal login/logout callbacks are separately invoked to show their effects.

This is not a full original login handler execution, network/authentication, active Worldserver, race, payment, client, DB or gameplay test. C++17/20/UBSan source snippets with dummy types cannot demonstrate actual owner host behaviour.

## Decision and hard boundaries

The R14 [remediation matrix DRAFT #240](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/240) leaves the state ownership architecture unselected. R15 strengthens its real lifecycle proof requirement: a new WorldSession or retained session GUID is not a valid new Player incarnation token. R9's invented epoch remains invented. No production token, state patch or payment policy is authorized.

H-DEFAULT/H-SELFBOT/H-REMEDIATION remain UNSELECTED. R7 shared-map release HOLD remains. MapUpdate.Threads=8 MUST stay 8. F14 OFF/unwired; N-Core NoWrite/relay OFF; K1 Step1 not before 1 November 2026; D18 armed in-combat A-to-B HARD NO-GO. Mod/N-Core protected mains and frozen PR #160 remain unchanged. No merge, server/DB/client, SQL/DBC, installed core/IP/Playerbots/N-Core mutation, economy change or deployment. Mandatory owner-accepted gameplay 0/5. Separate approval plus dated restorable backups, verified restore and rollback required for high-impact actions.
