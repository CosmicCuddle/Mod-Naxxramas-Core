# A02 — positive human signal, avenues after the S2 note

**Status:** no module-only positive human signal. Runtime is unchanged and stays default-OFF and fail-closed. **FUNCTIONAL S2 REMAINS BLOCKED.** In-game behaviour is **NOT TESTED**. This note is not the owner's decision and is not a merge.

**Author:** CosmicScript02. CS01 decision 6389165257 is accepted: an allowlist is not human proof, and Hunter stays in scope. Allowlist S2b is not approved.

The closed AI-map, `!IsHeadless`-only, world-thread `find`, command-hook, and empty `CustomData` record stays in `docs/research/a02-hunter-autocast-functional-s2.md`. This note covers the session facts, holder locks, and login-hook registry that note left open.

Pins read for this pass, and not modified:

| Tree | Commit |
| --- | --- |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` |

The owner states `MapUpdate.Threads = 8`. The live config was not read and is **UNKNOWN**. The owner's Playerbots `e88cc409` plus two uncommitted edits were not read and stay **UNKNOWN**.

`ClassifyOwnerOnMapThread()` still returns `Uncertain`. No production path reaches `ToggleAutocast`.

## Session facts on the map thread

These reads do not touch `_playerbotsAIMap`. None of them is a positive human fact once SelfBot is included.

### Remote address and the socket

**VERIFIED** safe to read. **VERIFIED** not a positive human fact.

`m_Address` is assigned only in the `WorldSession` constructor: the socket's remote IP when a socket exists (`WorldSession.cpp:160`), otherwise the literal `"headless"` (`:165`). `GetRemoteAddress` returns that string (`WorldSession.h:512`). `_headless` is `const !sock` (`WorldSession.cpp:148`, `WorldSession.h:1234`, stored `:1350`). `AddPlayerBot` constructs the session with a null socket (`PlayerbotMgr.cpp:158-160`), so a random bot, an addclass bot, and an alt logged in from the master's account are all `"headless"`.

SelfBot does not construct a session. `OnPlayerLogin` attaches a manager only when `!IsHeadless()` (`Playerbots.cpp:148-150`). `SelfBotLevel > 2` then calls `HandlePlayerbotCommand("self")` on that same session (`PlayerbotMgr.cpp:1733-1734`). The `"self"` command registers an AI on `master` (`:1115-1118`). The address and `_headless` stay the human client's values. A non-headless address is the human client's address, including after SelfBot attaches.

`IsSocketClosed` (`WorldSession.cpp:639-641`) reads `m_Socket`, which the network thread can close. That read from a map worker is a **POTENTIAL ISSUE**. An open socket is the same SelfBot case. It is not used.

### IsBot-style session flags

**VERIFIED** absent at the core pin.

`WorldSession` exposes `IsHeadless` and does not expose `IsBot`. `Player.h` has no bot field. A search of the pinned core `src` for a playerbot or `IsBot` flag on the session or the player finds `IsHeadless` and the movement check at `PathGenerator.cpp:774` only. Playerbots cannot add a field to `WorldSession` from the module. The `"self"` command does not call `SetSecurity` (`WorldSession.h:511`) or write `m_Address`. There is no session flag that flips when an AI attaches.

### Account id and the bot account lists

**VERIFIED** as a bot-account deny. **VERIFIED** not a positive human fact. The lists are **not** immutable after startup.

`GetAccountId` returns `_accountId` (`WorldSession.h:502`). The id is set in the constructor (`WorldSession.cpp:120`) and has no later assignment in `WorldSession.cpp`. After the session is published to a map task, that `uint32` is safe to read. The number itself does not say whether the character is a human, an alt, or a SelfBot. SelfBot keeps the human account.

There is no closed integer account range. The config is a name prefix and a count (`PlayerbotAIConfig.h:300-301`). Membership is a vector of database ids.

`RandomBotAccounts` (`PlayerbotAIConfig.h:154`) is appended in `CreateRandomBots` (`RandomPlayerbotFactory.cpp:693`), called from `PlayerbotAIConfig::Initialize` (`PlayerbotAIConfig.cpp:761`). `IsInRandomAccountList` is an unlocked `find` (`PlayerbotAIConfig.cpp:951-953`). `AssignAccountTypes` (`RandomPlayerbotMgr.cpp:492`) `clear`s `rndBotTypeAccounts` and `addClassTypeAccounts` (`:497-498`) and refills them (`:629-632`). It is called from the same `Initialize` (`PlayerbotAIConfig.cpp:768`). `IsAccountType` runs a Playerbots database query on every call (`RandomPlayerbotMgr.cpp:640-645`). `IsAddClassAccount` is an unlocked `find` of `addClassTypeAccounts` (`:648-651`).

`Initialize` runs from `OnBeforeWorldInitialized` (`Playerbots.cpp:509`, `:531`). That hook is `World.cpp:1033`, after `MapMgr::Initialize` has already started map workers when `MapUpdate.Threads > 0` (`World.cpp:941`, `MapMgr.cpp:56-62`). It also runs again from the in-game `"reload"` command (`PlayerbotMgr.cpp:1075-1079`) and from `rndbot reload` (`RandomPlayerbotMgr.cpp:2532-2534`). `RandomBotAccounts` is never cleared, so a second `Initialize` appends. The type vectors are cleared and rebuilt. The lists change after startup.

The first fill is sequenced on the world thread before the world loop schedules map tasks, and `PCQueue::Push` / `WaitAndPop` publishes that fill to a later map task. A later reload runs on the world thread in session update (`World.cpp:1227`) before that tick's `sMapMgr->Update` (`:1254`). `MapUpdater::wait` (`MapUpdater.cpp:124-131`) and `update_finished` (`:161-169`, `memory_order_acquire`, and the mutex only on the last worker) do not prove that a non-last worker's read of those vectors happens-before the reload's `clear` or `push_back`. There is no mutex on the vectors. A map-thread read concurrent with reload is a **POTENTIAL ISSUE**. `IsAccountType`'s synchronous query from a map worker is a separate **POTENTIAL ISSUE** (`MapUpdater.cpp:174-176` warns on sync queries). Neither call is added.

A hit in `RandomBotAccounts` means the account was created under the random-bot prefix (random or addclass). That is a bot deny. A miss includes the human account. SelfBot uses that account. An alt logged in with `AddPlayerBot` on the master's own account uses that account too, and its session is the null-socket session above. A miss is not a human.

## PlayerbotHolder and PlayerbotMgr ownership

**VERIFIED** no lock. **VERIFIED** not a positive human fact.

`PlayerbotHolder` (`PlayerbotMgr.h:30-73`) holds `playerBots` (`:70`, `std::map`) and the static `botLoading` map (`:72`). `PlayerbotMgr` (`:75`) adds no mutex. `PlayerbotsMgr` (`:111-137`) holds `_playerbotsAIMap` (`:135`) and `_playerbotsMgrMap` (`:136`) and no mutex. A search of `PlayerbotMgr.cpp`, `PlayerbotMgr.h`, and `RandomPlayerbotMgr.cpp` / `.h` finds no mutex, `lock_guard`, or `shared_mutex`. The world-thread processor mutex (`PlayerbotWorldThreadProcessor.h:139`) guards that processor's queue, not these maps. Raid and perf locks elsewhere in the module do not guard them.

`GetPlayerBot` finds `playerBots` with no lock (`PlayerbotMgr.cpp:493-497`). `OnBotLogin` inserts it (`:509-515`) from the world-thread processor (`Playerbots.cpp:549`). `RemoveFromPlayerbotsMap` erases it (`PlayerbotMgr.cpp:488-490`). The logout command reaches that erase from `HandleCommands` (`PlayerbotAI.cpp:575`, command at `:1137-1168`) inside `OnPlayerAfterUpdate` (`Playerbots.cpp:248-255`), which runs on a map worker. Concurrent `find` and `erase` on that `std::map` is a data race. A live crash was **NOT TESTED**.

The `"self"` command does not insert `playerBots`. It only `AddPlayerbotData(master, true)` and `SetMaster(master)` (`PlayerbotMgr.cpp:1115-1118`). A SelfBot is absent from every holder's `playerBots`. Absence is not a human. Presence means that holder logged the character in as a bot, which is a bot deny, and the container is still unsynchronized.

`GetPlayerbotMgr` finds `_playerbotsMgrMap` with no lock (`PlayerbotMgr.cpp:1878-1891`). A manager is inserted for every non-headless login (`Playerbots.cpp:148-150`, `PlayerbotMgr.cpp:1814-1824`), and SelfBot keeps that manager. Presence of a manager is not a bot, and the find is the same unlocked-map **POTENTIAL ISSUE** already recorded for the AI map.

## Login and logout hooks as a module registry

**VERIFIED** the hooks exist on the world thread. **VERIFIED** they have no positive human fact that excludes SelfBot. No registry was added.

`OnPlayerLogin`, `OnPlayerBeforeLogout`, and `OnPlayerLogout` are `PlayerScript.h:355`, `:358`, and `:361`. `OnPlayerLogin` is called at the end of `HandlePlayerLoginFromDB` (`CharacterHandler.cpp:1126`), from session login inside `UpdateSessions` (`World.cpp:1227`), before that tick's map update (`:1254`).

Playerbots' own login hook, for a non-headless session, calls `AddPlayerbotData(player, false)` (`Playerbots.cpp:148-150`). That inserts the manager and then `PlayerbotMgr::OnPlayerLogin` (`PlayerbotMgr.cpp:1824`, `:1710`). `SelfBotLevel > 2` attaches the AI before that login function returns (`:1733-1734`, `:1117`). Script order inside one `OnPlayerLogin` broadcast is not a contract. The session fields a module can see from its own login hook are the fields above. The `"self"` path does not change them. A latch of `!IsHeadless`, of the account id, or of the remote address is a fact SelfBot still has. The populating signal would not be positive human proof.

Seeding the latch by calling `IsRealPlayer` from the login hook is `GetPlayerbotAI`'s unlocked `find` (`PlayerbotMgr.cpp:1868`). Other map workers can erase that map during this login. That is the same world-thread **POTENTIAL ISSUE** as the S2 note, not a new safe window.

`AddPlayerbotData` has three call sites and no script hook: the manager insert (`Playerbots.cpp:150`), `OnBotLogin` (`PlayerbotMgr.cpp:514`), and `"self"` (`:1117`). `OnBotLogin` is queued and runs from `OnWorldUpdate` after the map phase (`Playerbots.cpp:545-549`, `World.cpp:1355`). A module cannot observe the AI transition from a login or logout hook without reading the unlocked map. A mutex around a module registry does not create a signal the hook does not have.

## What stays unchanged

No C++ change. The config default stays 0. `ClassifyOwnerOnMapThread()` stays `Uncertain`. No SQL. No core, Playerbots, or Individual Progression edit. In-game autocast, relog, resummon, stable, and the client bar remain **NOT TESTED**.

## Labels

| Finding | Label |
| --- | --- |
| `m_Address` / `IsHeadless` readable on the map thread, and a non-headless address includes SelfBot | **VERIFIED** |
| `IsSocketClosed` from a map worker | **POTENTIAL ISSUE**. Not a human fact. Not used |
| No `IsBot` session or player flag at the core pin | **VERIFIED** |
| Account id readable; bot account vectors are a prefix-membership deny; a miss includes SelfBot and same-account alts | **VERIFIED** |
| `RandomBotAccounts` and the type vectors mutate again on `"reload"` / `rndbot reload`; no mutex; overlap with a map-worker read is not ordered by `wait()` | **POTENTIAL ISSUE**. Not immutable. Not used |
| `IsAccountType` database query from a map worker | **POTENTIAL ISSUE**. Not used |
| `playerBots`, `botLoading`, `_playerbotsAIMap`, `_playerbotsMgrMap` have no lock; SelfBot is absent from `playerBots` | **VERIFIED**. Map-worker `erase` against `find` is a source-reachable data race. A live crash was **NOT TESTED** |
| Login/logout hooks can feed a module registry with a positive human fact | **VERIFIED** they cannot. No registry added |
| Runtime writer | Unchanged. Fail-closed. **FUNCTIONAL S2 REMAINS BLOCKED** |
| In-game behaviour, live `MapUpdate.Threads`, owner Playerbots `e88cc409` plus two uncommitted edits | **UNKNOWN** / **NOT TESTED** as already recorded |
| Allowlist S2b | Not approved. Not implemented |

## PROPOSAL - REQUIRES OWNER APPROVAL

This is a proposal for a future public Playerbots method. It is not implemented. It edits no Playerbots, core, or Individual Progression file. It needs Michael's separate explicit approval before anyone writes it. CS02 does not treat this text as that approval.

### Signature

On `PlayerbotsMgr`, declared next to `GetPlayerbotAI` in `src/Bot/PlayerbotMgr.h` and defined in `src/Bot/PlayerbotMgr.cpp`:

```cpp
// True only when player is non-null and no PlayerbotAI is registered
// for player->GetGUID(). Same rule as IsRealPlayer
// (PlayerbotAI.cpp:4523-4528). A SelfBot is false: the AI is registered
// and its master is the player (PlayerbotMgr.cpp:1117-1118,
// PlayerbotAI.cpp:4531-4535).
bool IsRealPlayerSynchronized(Player const* player);
```

The class gains one private `std::mutex` (a `std::shared_mutex` is the same API). `AddPlayerbotData`, `RemovePlayerBotData`, `GetPlayerbotAI`, `GetPlayerbotMgr`, and `IsRealPlayerSynchronized` all take that mutex for the whole `find` / `erase` / `emplace` of `_playerbotsAIMap` and `_playerbotsMgrMap`. A method that locked only itself would still race the existing unlocked call sites, so the lock is part of making this signature true. No new public type, callback, or config key.

### Thread contract

Safe to call from the world thread and from any map worker, including `Pet::Update` when `MapUpdate.Threads > 0`. The caller holds no Playerbots lock. The bool is linearizable with AI attach and detach. The caller copies the bool and drops the lock before any pet spell write.

`IsHeadless()` stays a separate deny, and it already exists. `OnBotLogin` (`PlayerbotMgr.cpp:506-514`) runs from `WorldScript::OnUpdate` (`Playerbots.cpp:545-549`, `World.cpp:1355`) after that tick's `sMapMgr->Update` (`World.cpp:1254`). A headless bot can be in the world for that map phase with no AI yet, so `IsRealPlayerSynchronized` would be true for that one phase. `AddPlayerBot`'s null socket keeps those sessions headless. The module predicate, after this method exists, is:

```cpp
session && !session->IsHeadless() && sPlayerbotsMgr.IsRealPlayerSynchronized(owner)
```

SelfBot attach from `SelfBotLevel > 2` finishes inside `OnPlayerLogin` before `HandlePlayerLoginFromDB` returns (`CharacterHandler.cpp:1126`, `PlayerbotMgr.cpp:1733-1734`), which is the session phase before the map phase. A later `"self"` chat command runs through `HandlePlayerbotMgrCommand` (`PlayerbotMgr.cpp:911-934`) on that same session/world thread, before that tick's `MapMgr::Update`. All three `AddPlayerbotData` sites are on the world thread. Map workers remove an AI on logout; they do not add one. A locked read during the map phase observes a SelfBot attach that already happened on the world thread.

### Why this is the smallest surface

The missing fact is current AI membership, and the missing property is a happens-before for that membership. One method plus the mutex that the existing mutators and readers already needed is the whole public change. A login callback would still need that mutex, and this module would then keep a second registry. Core cannot host the method: the pinned core has no AI map. Individual Progression's account regex does not see SelfBot or a same-account alt.

After approval and a Playerbots build that contains the method, this module would call it only after `WantsWrite`, in place of the `Uncertain` return, still behind the default-OFF key, still requiring `owner->GetPet() == pet`, and still never learning Cower 1742. That call is not in this commit. Until the method exists, the writer stays fail-closed.
