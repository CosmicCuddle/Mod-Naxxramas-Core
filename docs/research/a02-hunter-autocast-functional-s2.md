# A02 S2 — default-OFF human Hunter pet autocast writer

**Status:** isolated draft. The config key defaults to 0. **FUNCTIONAL S2 REMAINS BLOCKED.** In-game behaviour is **NOT TESTED**. This draft does not establish gameplay, does not speak for the owner, and is not a merge.

**Author:** CosmicScript02. Independent exact-head review requested from CosmicScript01.

The S1 contract remains `docs/research/a02-hunter-autocast-functional-s1.md`. This note only records the writer that contract authorised.

A later pass on this branch checks the session, holder-lock, and login-hook avenues this note left open. No positive human signal was found. Runtime is unchanged. The API proposal, which still needs the owner's separate approval, is `docs/research/a02-hunter-autocast-positive-human-signal.md`. Allowlist S2b is not approved.

## What the module does

`NaxxramasCore.HunterPetAutocast.RestoreHumanChain` is 0 in `conf/mod_naxxramas_core.conf.dist`. The C++ fallback passed to `GetOption<bool>` is `false`. The cached flag starts false. Both hooks return on that flag before a pet read, a config lookup, or a `CustomData` allocation.

When the flag is on, `OnUnitUpdate` stores one baseline on that pet (`CustomData.GetDefault`, then mutated in place). The lookup key is one process-lifetime `std::string`. `DataMap::Get` takes `std::string const&` (`DataMap.h:29` at the pinned core), so a string literal would allocate a temporary on every tick. `GetDefault` returns the existing object after the first call (`DataMap.h:53-56`). `OnWorldObjectUpdate` on the same update reads it back with `Get`.

Both hooks compare the live book to that baseline with `LiveBookMatches` before `FillBook`. The compare uses one stack `SpellView` and `ViewFieldsEqual` (spell, chain, active, autocastable, bar, vector, duplicate bar, present). It builds no vector. When the book is unchanged, `OnWorldObjectUpdate` returns before `DecideChains`. A same-id autocast toggle changes those fields, so it still reaches `DecideChains` and stays `NO_WRITE`. A rank replacement still reaches `DecideChains`. After that decision the stored book becomes the post-decision book, and the next identical ticks take the fast path again. One thousand identical snapshots in the native test call `DecideChains` zero times and construct zero decision vectors. Removing the fast path makes that test call `DecideChains` on every snapshot.

The chain key is `SpellMgr::GetFirstSpellInChain`. The 31 pinned Bite, Claw, Furious Howl, and Prowl rows are not hardcoded. A missing chain stays `NO_LEARN`.

The only writes are `ToggleAutocast` and `SetSpellAutocast` on a successor whose active byte, bar type, and `m_autospells` membership already agree, followed by one `PetSpellInitialize` when the post-write read agrees. A disagreement is reverted in the model and is not claimed. No spell is learned. Cower 1742 is not restored. `owner->GetPet() == pet` is required before a toggle. Warlock pets stay out of scope.

`ClassifyOwnerOnMapThread()` returns `Uncertain`. `WriteAllowed` is false for that value, and the restore hook returns before any toggle. The writer does not include `Playerbots.h` and does not call `IsRealPlayer`. The investigation below did not find a positive human classification that this module can store and later read. Turning the key on does not by itself restore a dropped autocast byte. That is fail-closed, not a gameplay result. There is no production-path witness that reaches `ToggleAutocast`: the only `ConfirmedHuman` values are the native test seam.

CS01 resolved the startup config-order question from pinned Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd` (`Main.cpp` loads module configs, `ScriptMgr::Initialize` registers scripts, then `World::SetInitialWorldSettings` calls `OnBeforeConfigLoad`). This draft does not change that hook.

## Positive human classification — investigated, not found

Pins read for this pass, and not modified:

| Tree | Commit |
| --- | --- |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |

The question was whether this module can prove a human owner, store that result in state owned by that `Player`, and let the map thread read it, without an unlocked `GetPlayerbotAI` / `_playerbotsAIMap` read, without `!IsHeadless` as the sole proof, and without a new global cache. No such proof exists at these pins. The guard is unchanged. **FUNCTIONAL S2 REMAINS BLOCKED.**

### The AI map is written from a map worker

**VERIFIED** as source structure. A live crash was **NOT TESTED**.

`PlayerbotsMgr` has no mutex (`PlayerbotMgr.h:111-137`). `_playerbotsAIMap` is `PlayerbotMgr.h:135`. `IsRealPlayer` (`PlayerbotAI.cpp:4523-4528`) is `player && !GET_PLAYERBOT_AI(player)`. `GET_PLAYERBOT_AI` is `Playerbots.h:31`. `GetPlayerbotAI` (`PlayerbotMgr.cpp:1858-1875`) `find()`s the map at `:1868` with no lock. `AddPlayerbotData` erase/emplace is `:1828-1834`. `RemovePlayerBotData` erase is `:1842-1845`. The AI destructor calls that remove (`PlayerbotAI.cpp:247`).

`MapMgr::Initialize` starts map workers when `MapUpdate.Threads > 0` (`MapMgr.cpp:56-62`). The owner states 8. The live config was not read and remains **UNKNOWN**. `MapMgr::Update` schedules each map and then `wait()`s (`MapMgr.cpp:273-280`). `MapUpdateRequest::call` runs `Map::Update` on a worker (`MapUpdater.cpp:44-47`). `Map::Update` (`Map.cpp:436`) calls `player->Update` at `:489`. `Player::Update` calls `OnPlayerAfterUpdate` (`PlayerUpdates.cpp:431`).

`OnPlayerAfterUpdate` (`Playerbots.cpp:248-255`) `find()`s the map for every updated player and, when an AI exists, calls `PlayerbotAI::UpdateAI` (`PlayerbotAI.cpp:250`). That calls `UpdateAIInternal` at `:438`. The early return at `:259-261` skips the update when the session is already logging out. It does not skip a queued chat command. `UpdateAIInternal` calls `HandleCommands` (`:575`). The `"logout"` command (`PlayerbotAI.cpp:1138-1168`) calls `LogoutPlayerBot` (`PlayerbotMgr.cpp:394`). The instant-logout block (`:446-452`) calls `LogoutPlayer(true)` on that same worker, which destroys the `Player`. `OnDestructPlayer` (`Playerbots.cpp:397-402`) `find()`s the map and `delete`s the AI. The destructor erases the map.

So one worker can `erase` while another worker is in `find()` during the same map phase. Concurrent `find` and `erase` on that `std::unordered_map` is a data race. This is source-reachable. It is not an observed crash.

`IsSelfBot` (`PlayerbotAI.cpp:4531-4535`) is the same unlocked `find`, plus `GetMaster() == player`. `IsRandomBot(Player*)` (`RandomPlayerbotMgr.cpp:2239-2244`) also calls `GET_PLAYERBOT_AI`. `currentBots` (`RandomPlayerbotMgr.h:254`) is an `std::unordered_set` with no mutex in that class, and a miss there is not a human: alt bots and SelfBots are not random bots.

### A world-thread read is not proven safe either

**VERIFIED** as a missing happens-before. Not used.

`MapUpdater::update_finished` (`MapUpdater.cpp:161-169`) does `pending_requests.fetch_sub(1, std::memory_order_acquire)` and takes `_lock` only when this worker was the last one. `wait()` (`:124-131`) waits on that mutex until the counter is 0. An acquire RMW does not publish the worker's earlier writes. A non-last worker's `erase` therefore does not happen-before the world thread's code after `wait()` returns. `PCQueue::WaitAndPop` (`PCQueue.h:71-83`) locks the queue only when that worker loops back for another task (`MapUpdater.cpp:172-188`), which can be after `wait()` has already returned.

A `GetPlayerbotAI` call from a login hook or from `OnSessionUpdate` would still be an unlocked `find` on a map that a map worker mutates. It is not a synchronized Playerbots API. The world-thread processor mutex (`PlayerbotWorldThreadProcessor.h:139`, `:149`) guards that processor's queue and its stats, not `_playerbotsAIMap`.

`OnSessionUpdate` itself is on the world thread: `SessionScript.h:37-43`, and `WorldSession::Update` calls it only for `ProcessUnsafe` (`WorldSession.cpp:596-598`). `World::Update` runs `UpdateSessions` (`World.cpp:1227`) before `sMapMgr->Update` (`:1254`). That places the hook outside `Map::Update` in program order. Program order plus a `wait()` that does not synchronize every worker is not a happens-before against the worker's `erase`. This module does not call `GetPlayerbotAI` there.

### `!IsHeadless` does not prove a human, including later bots and SelfBot

**VERIFIED** at the pin.

`_headless` is a const `!sock` (`WorldSession.cpp:148`, declared `WorldSession.h:1234`, stored `:1350`). It is safe to read after the session has been published, and it does not by itself identify a human.

Bots created after startup are still headless. `AddPlayerBot` constructs the session with a null socket (`PlayerbotMgr.cpp:158-160`; the fourth parameter is `std::shared_ptr<WorldSocket>`). The login callback (`PlayerbotMgr.cpp:252-283`) calls `HandlePlayerLoginFromDB` and queues `OnBotLoginOperation` (`PlayerbotOperations.h:493-512`) instead of inserting the AI inline. `PlayerbotWorldThreadProcessor::Update` runs from `WorldScript::OnUpdate` (`Playerbots.cpp:545-549`), which is `World::Update` at `World.cpp:1355`, after that tick's `wait()`. `OnBotLoginOperation::Execute` calls `OnBotLogin` (`PlayerbotOperations.h:512`, `PlayerbotMgr.cpp:506-514`), which `AddPlayerbotData(bot, true)`. Those players fail `!IsHeadless`. They are the easy deny. They are not the proof.

A human session is constructed with a socket, so `IsHeadless()` stays false for the life of that session. SelfBot is an AI attached to that same session:

- `OnPlayerLogin` calls `AddPlayerbotData(player, false)` only when `!IsHeadless()` (`Playerbots.cpp:148-150`). That inserts `_playerbotsMgrMap`, not the AI map (`PlayerbotMgr.cpp:1814-1824`).
- If `SelfBotLevel > 2`, `PlayerbotMgr::OnPlayerLogin` then calls `HandlePlayerbotCommand("self", player)` directly (`PlayerbotMgr.cpp:1733-1734`). That is not a chat packet and not an `AllCommandScript` hook.
- The `"self"` command (`PlayerbotMgr.cpp:1100-1122`) deletes the AI when one exists (`:1102-1105`) and otherwise `AddPlayerbotData(master, true)` plus `SetMaster(master)` (`:1115-1118`).

`IsSelfBot` is exactly "AI present and master is this player". After either the config path or the command path, `!IsHeadless` is still true. A latch taken from `!IsHeadless` at login would call a SelfBot a human. Hook order cannot repair that: `OnPlayerLogin` is one broadcast (`CharacterHandler.cpp:1126`, end of `HandlePlayerLoginFromDB`). This module does not control whether it runs before or after Playerbots' login hook, and a later `"self"` command would stale a login latch anyway.

`AllCommandScript::OnTryExecuteCommand` is declared (`AllCommandScript.h:49`) and defined (`AllCommandScript.cpp:28-30`). It does have a caller. `ChatCommandNode::TryExecuteCommand` calls `sScriptMgr->OnTryExecuteCommand` (`ChatCommand.cpp:326`) and, only if that returns true, invokes the command at `:333`. `ChatHandler::_ParseCommands` reaches that at `Chat.cpp:238`. The hook therefore runs before the command. It sees the command text. It does not see whether `AddPlayerbotData` ran. Returning false from the hook skips the invoker (`ChatCommand.cpp:326-327`), which would suppress the chat command rather than classify the player. The direct `SelfBotLevel > 2` call never enters `TryExecuteCommand`, so the hook does not observe that path. A string match on `"self"` is not a positive human fact either way: the command toggles, it can fail (`SelfBotLevel` 0 or 1 at `PlayerbotMgr.cpp:1110-1113`), and a player who never types it can already be a SelfBot.

No account-name test is used. `^RNDBOT.*` remains IP's check, not this module's.

### The publication channel is real, and it has nothing safe to carry

**VERIFIED** as a happens-before in one direction. Unused, because there is no positive human fact.

Writes on the world thread that are sequenced before `MapUpdater::schedule_task` (`MapUpdater.cpp:134-138`) happen-before the worker's `Map::Update`. `schedule_task` `Push`es under `PCQueue::_queueLock` (`PCQueue.h:39-46`). The worker `WaitAndPop`s under that same mutex (`PCQueue.h:71-83`) before `call()`. That is a real happens-before from a session-phase store to a later map-phase load.

`Player::CustomData` is public (`Object.h:237`). `DataMap::GetDefault` inserts once (`DataMap.h:49-59`). The container is an unlocked `std::unordered_map` (`DataMap.h:73`). An insert from the world thread before the player is published, followed by atomic stores into that object, would be a per-player channel the map thread could load. A later `GetDefault`/`Set` from the other thread would race the container. This module does not add that channel.

There is no payload. Playerbots does not mention `CustomData`. The pinned core game sources have no `Playerbot` field on `Player`. The AI object's only durable home is `_playerbotsAIMap`. `PlayerbotAI`'s constructor sets taxi-cheater only when that cheat bit is on and the player is not one already (`PlayerbotAI.cpp:148-149`). Core also sets taxi-cheater for `CONFIG_ALL_TAXI_PATHS` (`CharacterHandler.cpp:1055-1056`). That flag is not a human bit and not a SelfBot bit.

### What this pass does not do

The production writer still returns before `ToggleAutocast` when `ClassifyOwnerOnMapThread()` is `Uncertain`. No login hook, session hook, or command hook was added. Default stays 0. No SQL. No core, Playerbots, or Individual Progression edit. In-game autocast, relog, resummon, stable, and the client bar remain **NOT TESTED**. The two uncommitted edits on Playerbots `e88cc409` were not in the published commit and were not read. They are **UNKNOWN**.

## Labels

| Finding | Label |
| --- | --- |
| Default 0 / `false`, and the off path returns before allocation | **VERIFIED** by the native policy tests and the source contract |
| Unchanged book skips `FillBook` / `DecideChains`; 1000 identical snapshots do no decision work | **VERIFIED** by the native policy test and the source contract. A mutation that removes the fast path fails those tests |
| Map-thread `IsRealPlayer` / `_playerbotsAIMap` read | Not used. **VERIFIED** fail-closed in source and native tests. A same-phase worker `find` plus `LogoutPlayerBot` `erase` is a **VERIFIED** source-reachable data race. A world-thread `find` after `wait()` is **not** proven safe (**POTENTIAL ISSUE**). In-game effect of leaving the byte unrestored is **NOT TESTED** |
| Same-pet `CustomData` baseline, no process-global pet dictionary | **VERIFIED** in source. The baseline key is one process-lifetime string, not a pet map. Live `MapUpdate.Threads` is **UNKNOWN** |
| Same-chain restore, post-write agreement, Cower 1742 not learned | **VERIFIED** by native tests, including mutations that fail when the guard is removed. The production map-thread gate does not reach the toggle |
| Pinned 31-row chain identity used as a test fixture | **VERIFIED** at the S1 pin. The owner's live `spell_ranks` is **UNKNOWN** |
| Startup `OnBeforeConfigLoad` order | **VERIFIED** by CS01 at the pinned core cited above. Unchanged in this draft. Not an in-game pass |
| Real human only | The writer does not call `IsRealPlayer`. **VERIFIED** fail-closed. No positive human fact was found at the pins below. **FUNCTIONAL S2 REMAINS BLOCKED**. The two uncommitted edits on Playerbots `e88cc409` were not read and are **UNKNOWN** |
| Later `OnWorldObjectUpdate` subscribers | **UNKNOWN**. This module registers one restore hook. A later subscriber can still overwrite the bar. **POTENTIAL ISSUE**. Not solved with a global map |
| Hosted public-pin compile and link | Proves that pin only. It is not an owner-installed compile and not S5/S6 |
| In-game autocast, relog, resummon, stable, client bar | **NOT TESTED** |
| PR #69 | Not modified. Still blocked |

## Tests

```
python3 -m unittest discover -s tests -p 'test_a02_hunter_autocast_functional_s1.py' -v
python3 -m unittest discover -s tests -p 'test_a02_hunter_autocast_functional_s2.py' -v
g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems tests/hunter_pet_autocast_policy.cpp -o /tmp/hunter_pet_autocast_policy
/tmp/hunter_pet_autocast_policy
```

This classification pass was run locally from the module root. S1: 14 tests, OK. S2: 18 tests, OK. The C++17 and C++20 native policy binaries both print `PASS: Hunter pet autocast restore policy`, including the 1,000 identical snapshots that do not call `DecideChains`. `python3 -m unittest discover -s tests -v` ran 344 tests with 6 errors, all `IndexError` in `tests/test_ep_tower_module_only.py` (`ROOT.parents[1]`). Those tests expect this module to be nested inside a core checkout. This checkout is the module repository alone. The errors are not from this change and are not an A02 pass. The hosted pinned worldserver link of this SHA is **NOT TESTED** until CI runs.

No SQL, DBC, core, Individual Progression, or Playerbots file is edited.
