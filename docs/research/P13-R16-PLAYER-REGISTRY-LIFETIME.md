# P13-R16 — Player registry raw-pointer lifetime and world-tick handoff boundaries

**29 October 2026 UTC. ORIGINAL SOURCE ANALYSIS + DISPOSABLE DEMONSTRATION ONLY. NO PRODUCTION PATCH.**

Pre-registered BEFORE authoring on [master #28 comment 6500939957](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6500939957). Immutable Mod main 80e9de1c39a6dc995188a80c31a5e785d0f2a6f9; immutable pinned Grimfeather 8daffdabe9202c228e45d833c9a1d399597a15cd.

## 1. Exact pinned sources

| Original source | Original Git blob |
| --- | --- |
| Mod src/Systems/HonorOverflow.cpp | d4f70c511ac5a3e32c7e6b8f913d095915da707c |
| Core src/server/game/Globals/ObjectAccessor.cpp | 8b15ce734d8f6624a29fe12e23c6917d77e1919d |
| Core src/server/game/Globals/ObjectAccessor.h | d7d2aaa8a723770686512f98498339d9219d9c1d |
| Core src/server/game/Entities/Player/Player.cpp | 138e7eab4905ec366338a54cc18e6cfe749a3670 |
| Core src/server/game/Scripting/ScriptMgr.h | 7f0f30d3ca46cb290636c33ca8e1b2b9c0ffa1f8 |
| Core src/server/game/World/World.cpp | a001fcaf3b00fdecefb80f95f1ec3c1ae14116fe |
| Core src/server/game/Maps/MapMgr.cpp | 46f627a10515001f7edfd956ccdbf4359a267400 |

## 2. Finding: lookup lock DOES NOT create a Player lifetime lease

[Core ObjectAccessor.cpp L31–58](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Globals/ObjectAccessor.cpp#L31-L58) protects its global Player registry Insert/Remove with an exclusive shared-mutex lock and Find with a shared lock. But Find returns a **raw T pointer**, after which the local lock guard is destroyed. It does not give the caller a shared_ptr, lifetime pin, lease, epoch or guard held across later operations.

[ObjectAccessor.cpp L269–285](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Globals/ObjectAccessor.cpp#L269-L285) shows FindPlayer fetches that raw pointer, then checks IsInWorld; FindConnectedPlayer simply returns the raw pointer. The [ObjectAccessor.h global-find API declaration](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Globals/ObjectAccessor.h#L75-L87) explicitly warns: **ACCESS LIKE THAT IS NOT THREAD SAFE**. Its GetPlayers container also requires the caller to hold HashMapHolder's lock. **A protected map lookup is NOT a guarantee that its returned Player is alive when an asynchronous world-owner queue eventually processes it.** This is a proof of API limitations, NOT an observed owner-host use-after-free.

The static registry map and lock are intentionally not destroyed at shutdown to avoid late destructor accesses, but this protects the registry machinery itself and does **not** extend the life of any Player pointer returned from it.

## 3. Real Player construction/destruction callbacks — potential seam, not a completed contract

[Player.cpp around L420–432](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp#L420-L435) calls sScriptMgr->OnConstructPlayer(this) during construction and sScriptMgr->OnDestructPlayer(this) at the start of destruction. [ScriptMgr.h around L697–701](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Scripting/ScriptMgr.h#L697-L701) declares the methods. A direct pinned-source Git grep inventories references in its tracked src/ and modules/ at the tested source commit and reports whether a concrete ScriptMgr::OnConstructPlayer / ::OnDestructPlayer definition spelling is present. **These calls and declarations alone do not certify a supported user-extensible PlayerScript registration, unique object-incarnation token, or synchronization/cleanup contract.**

This may be useful for future research into lifecycle boundaries, but it is **not** an approval to allocate an epoch on construction or access partly constructed/destructed Player state. The real core/source wrapper, plugin dispatch, callback reachability and thread constraints would need independent verification and design review.

## 4. World tick gives a JOIN, not an unconditional safe payment transaction

[World.cpp L1224–1270](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/World/World.cpp#L1224-L1270) updates WorldSessionMgr, then MapMgr, then BattlegroundMgr in the audited ordinary tick order. [MapMgr.cpp around L269–282](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Maps/MapMgr.cpp#L269-L282) schedules map-worker tasks and calls m_updater.wait() before returning. This is a useful **candidate** for bounding map-generated observations prior to a world-thread state transition, not proof of the needed current-player lookup, BG end ordering, late producer quarantine, shutdown/redirect coordination or atomic money payout.

R9's hypothetical sequence/epoch and R15's real Player-across-new-session transfer remain constraints. Holding an ObjectAccessor shared lock while executing Player methods, money scripts or BG callbacks is **not established safe**, because lock order, reentrant callbacks and destructor timing are unproved. Reading a raw pointer after dropping the registry lock is not a substitute.

## 5. Disposable executable scope

The new R16 test pins these seven original blobs; extracts literal original template HashMapHolder methods Insert, Remove, Find, GetContainer, GetLock; compiles them against disposable Player/Guid types in C++17, C++20 and UBSan. The dummy two-Player witness deliberately inserts one dummy Player, retrieves its raw pointer, removes it, inserts a **different still-live dummy Player with the same GUID**, and demonstrates that a fresh lookup now returns the second pointer while the earlier pointer value remains non-owning. It never dereferences freed memory, executes an actual race, mutates owner objects or implies the real character GUID allocator reuses identity immediately.

Original source guards also assert callback declarations and calls, warned API, world-update ordering, MapMgr wait, original honor-state map types; 9 negative source mutations must fail. Direct immutable Git grep lists all available tracked code references to OnConstructPlayer and OnDestructPlayer in the pinned core scope. It does not necessarily resolve dynamically generated or off-tree dispatch definitions.

This source-level design investigation does not run a real Worldserver, real threads racing registration/destruction, Playerbot, IP module, network socket, battleground or actual money transactions.

## 6. Cross-project safety and owner holds

The R14 [owner decision matrix DRAFT #240](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/240) still leaves state-owner A/B/C unselected; R15 [reconnect DRAFT #241](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/241) proves new network sessions can reuse the same Player. This study adds that the existing global registry's raw pointer lookup cannot alone give a lifetime-safe delayed-queue Player handle. No architecture, epoch, retry, credit or remediation selected.

H-DEFAULT, H-SELFBOT and H-REMEDIATION all UNSELECTED. R7 potential shared-container concurrency remains release HOLD. Protected Mod/N-Core mains and frozen integration PR #160 no-write. MapUpdate.Threads=8 MUST remain **8**. F14 OFF/unwired; N-Core NoWrite and relay OFF; K1 Step1 not before 1 November 2026; D18 already-armed in-combat pet A-to-B HARD NO-GO. Gameplay acceptance 0/5. No SQL/DBC, client, owner Worldserver, installed module, DB, core, IP, Playerbots, N-Core, merge or deployment. Future high-impact work requires separate owner approval, dated restorable backups, verified restoration and rollback.

## 7. Refined real lifecycle dispatch (source-verified)

The pinned Git-tree hook-name scan directly found **five** reference lines for each lifecycle method. Original [MiscScript.cpp lines 32–39](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Scripting/ScriptDefines/MiscScript.cpp#L32-L39), blob **a41a3f0d9f48d0c4319a585c591ba7ec722fc37b**, implements both ScriptMgr methods and dispatches through **CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_CONSTRUCT_PLAYER / MISCHOOK_ON_DESTRUCT_PLAYER)**. Original [MiscScript.h lines 23–63](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Scripting/ScriptDefines/MiscScript.h#L23-L63), blob **9ed20ab2304fed3bceb20a7e8dc704e529897365**, defines both hook IDs and virtual callback methods. The original MiscScript constructor registers enabled script callbacks through ScriptRegistry<MiscScript>::AddScript.

**Important correction to the initial open question:** Actual core **MiscScript** construction/destruction callback dispatch IS source-supported, not merely a declaration. It is *not* a normal PlayerScript login/logout callback, and the existing Mod HonorOverflow does not register this MiscScript lifecycle hook. This gives a real extension seam, but no *automatic stable/monotonic Player incarnation identifier, handle for queued raw Player*, or proof of thread ownership/monetary atomicity.

The disposable CI test has therefore been strengthened to require **nine** original blobs including MiscScript.cpp/.h and **11 must-fail source mutation guards**. Hook-name inventory checks the original immutable tree, not GitHub's unindexed code search. It does not invoke live hook dispatch.

## 8. Independently examined original hosted evidence (research checkpoint)

At original updated research checkpoint commit **e5934ad6577b7d22fbe7130eabb02fa5586af562**, the following hosted CI jobs both completed successfully. CS01 independently fetched and read their complete original logs:

- [Push run 40902855113 / job 123549571991](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40902855113/job/123549571991): **SUCCESS, 734 original log lines**.
- [PR run 40902866237 / job 123549607345](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40902866237/job/123549607345): **SUCCESS, 734 original log lines**.

Both exact-head logs independently show: **nine original file SHA guards**, exactly three additive research/test/workflow paths, **11/11 deliberate source-drift mutations caught**, five original tracked-source matching lines for each MiscScript construct/destruct lifecycle symbol (one direct ScriptMgr method-definition line for each), and the original HashMapHolder C++17/C++20/UBSan dummy pointer witness PASS. All results are read-only/dummy; no live memory race, Player lifetime guarantee, installed handler or host incident is proved.

This research document is itself amended after that successful checkpoint, so the **latest final document-head workflow** must still be reverified before calling the DRAFT's final CI current. The authoritative exact current-head CI record is maintained on PR #242 and the Part 38 living checklist.

