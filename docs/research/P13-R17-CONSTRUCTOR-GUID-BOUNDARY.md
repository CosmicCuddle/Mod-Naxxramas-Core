# P13-R17 — Player construction hook occurs before GUID-field initialization

**29 October 2026 UTC — original-source-only research, NOT a code fix or live player test.**

Pre-registered BEFORE authoring [master coordination #28 comment 6501334185](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6501334185). Base immutable protected Mod main 80e9de1c39a6dc995188a80c31a5e785d0f2a6f9 and pinned original Grimfeather 8daffdabe9202c228e45d833c9a1d399597a15cd.

## Exact immutable sources (8 blobs)

| Original file | Blob |
| --- | --- |
| Mod src/Systems/HonorOverflow.cpp | d4f70c511ac5a3e32c7e6b8f913d095915da707c |
| Core src/server/game/Entities/Object/Object.cpp | 39a24ef072321c567892d4257bfc7a9ba9f30791 |
| Core src/server/game/Entities/Object/Object.h | ac391a9975b43f89fd84b8336b2b57db1e8d189e |
| Core src/server/game/Entities/Unit/Unit.cpp | ce188c543c00aa020a593641cb5491a48fb12ffa |
| Core src/server/game/Entities/Player/Player.cpp | 138e7eab4905ec366338a54cc18e6cfe749a3670 |
| Core src/server/game/Handlers/CharacterHandler.cpp | d7123a9c503c3363ff2ea08b2d24eec7d07c5643 |
| Core src/server/game/Scripting/ScriptDefines/MiscScript.cpp | a41a3f0d9f48d0c4319a585c591ba7ec722fc37b |
| Core src/server/game/Scripting/ScriptDefines/MiscScript.h | 9ed20ab2304fed3bceb20a7e8dc704e529897365 |

## What the actual constructor ordering proves

Original [Object.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Object/Object.cpp#L76-L139) initializes `m_uint32Values = nullptr` and `m_valuesCount = 0`. Its `Object::_Create(ObjectGuid)` allocates the value fields if missing, then writes `OBJECT_FIELD_GUID`. Original `WorldObject` and `Unit` constructors in this pinned core do not call `_InitValues` or `_Create`. Original [Player.cpp constructor](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L158-L427) sets `m_valuesCount = PLAYER_END` but does **not** allocate the backing value fields or create a GUID, then calls `sScriptMgr->OnConstructPlayer(this)`.

The original `MiscScript` construct callback dispatch is real (verified in R16), but that does **not** make `GetGUID()` safe within this callback. `Object::GetGUID` in original [Object.h](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Object/Object.h#L121-L125) calls `GetGuidValue(OBJECT_FIELD_GUID)`, and original `Object::GetGuidValue` reads from `m_uint32Values[index]`. At the constructor callback boundary, the underlying value storage is not initialized in these original constructor paths. **Do not execute a GetGUID call at that point, assume it yields 0/empty, or propose GUID-based token registration there.** The current test intentionally DOES NOT dereference uninitialized memory.

Original [CharacterHandler.cpp character-creation path](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/CharacterHandler.cpp#L549-L566) calls `new Player(this)` **before** calling `newChar->Create`, whose original implementation calls `Object::_Create(guidlow, ... HighGuid::Player)`. Original [database login path](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/CharacterHandler.cpp#L796-L815) calls `new Player(this)` **before** `pCurrChar->LoadFromDB`. If LoadFromDB returns false, it explicitly deletes pCurrChar, so original `Player::~Player` and its `OnDestructPlayer` hook can run for a partially initialized, never-logged-in object.

In that ordinary DB-login handler, `ObjectAccessor::AddObject(pCurrChar)` occurs **after** a successful LoadFromDB, and normal `OnPlayerLogin(pCurrChar)` occurs after registry addition. This provides **distinct lifecycle stages** that should not be conflated: raw object construction, GUID/values initialization, validated character load and registry insertion, normal player login, and destruction. None of those facts alone proves a lifetime-safe delayed-money reference.

R15 already confirmed a distinct reconnect branch can reuse the **same** Player object on a new session without direct ordinary login hook. R16 confirmed the globally locked registry returns non-owning raw pointers. Together they exclude a naive design that assigns a GUID-derived incarnation at `OnConstructPlayer` or mistakes a new socket for a fresh Player.

## Test contract and limitations

`tests/test_p13_r17_player_preinit_source.py` verifies the **eight original blob SHAs**, extracts original C++ constructor, initialize, GUID accessor, normal create/login, real MiscScript dispatch, failed-load deletion and HonorOverflow normal login source bodies, and checks their relative ordering. Twelve deliberately wrong source mutations must fail. This is a Python test of original **textual control-flow anchors**; it does not compile or execute a Player, prove all possible hidden callback orders, exercise C++ UB, load an account, observe a real bot, or diagnose a host incident. The original C++ source is inspected but **no unsafe null-pointer dereference is attempted**.

Any owner-installed custom lifecycle callbacks and all real Worldserver/client/DB behavior remain **UNKNOWN**.

## No implementation or approval

R14 design gates G0–G4 remain open. There is still NO approved allocator of an actual lifetime token and NO proven safe deferred owner/handoff. We must not use the early constructor callback to access GUID or full Player state, even if it appears attractive for a lifetime counter; that would require a separately designed and proven phase transition after successful initialization. No automatic payout, retry, saved money data, lock policy or state-owner A/B/C selected.

P13 H-DEFAULT/H-SELFBOT/H-REMEDIATION UNSELECTED; R7 concurrency release HOLD. Protected Mod/N-Core main and frozen PR #160 remain no-write. Keep MapUpdate.Threads=8 at 8. F14 OFF/unwired; N-Core NoWrite and relay OFF; K1 Step1 not before 1 November 2026; D18 already-armed in-combat pet A-to-B HARD NO-GO. LAB-004/005 brainstorming only. Owner-accepted gameplay **0/5**. No core/IP/Playerbots/N-Core modification, Worldserver/client/DB/SQL/DBC activity, deployment, merge or installation.
