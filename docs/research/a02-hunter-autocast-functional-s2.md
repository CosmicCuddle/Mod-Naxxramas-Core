# A02 S2 — default-OFF human Hunter pet autocast writer

**Status:** isolated draft. The config key defaults to 0. In-game behaviour is **NOT TESTED**. This draft does not establish gameplay, does not speak for the owner, and is not a merge.

**Author:** CosmicScript02. Independent exact-head review requested from CosmicScript01.

The S1 contract remains `docs/research/a02-hunter-autocast-functional-s1.md`. This note only records the writer that contract authorised.

## What the module does

`NaxxramasCore.HunterPetAutocast.RestoreHumanChain` is 0 in `conf/mod_naxxramas_core.conf.dist`. The C++ fallback passed to `GetOption<bool>` is `false`. The cached flag starts false. Both hooks return on that flag before a pet read, a config lookup, or a `CustomData` allocation.

When the flag is on, `OnUnitUpdate` stores one baseline on that pet (`CustomData.GetDefault`, then mutated in place). The lookup key is one process-lifetime `std::string`. `DataMap::Get` takes `std::string const&` (`DataMap.h:29` at the pinned core), so a string literal would allocate a temporary on every tick. `GetDefault` returns the existing object after the first call (`DataMap.h:53-56`). `OnWorldObjectUpdate` on the same update reads it back with `Get`.

Both hooks compare the live book to that baseline with `LiveBookMatches` before `FillBook`. The compare uses one stack `SpellView` and `ViewFieldsEqual` (spell, chain, active, autocastable, bar, vector, duplicate bar, present). It builds no vector. When the book is unchanged, `OnWorldObjectUpdate` returns before `DecideChains`. A same-id autocast toggle changes those fields, so it still reaches `DecideChains` and stays `NO_WRITE`. A rank replacement still reaches `DecideChains`. After that decision the stored book becomes the post-decision book, and the next identical ticks take the fast path again. One thousand identical snapshots in the native test call `DecideChains` zero times and construct zero decision vectors. Removing the fast path makes that test call `DecideChains` on every snapshot.

The chain key is `SpellMgr::GetFirstSpellInChain`. The 31 pinned Bite, Claw, Furious Howl, and Prowl rows are not hardcoded. A missing chain stays `NO_LEARN`.

The only writes are `ToggleAutocast` and `SetSpellAutocast` on a successor whose active byte, bar type, and `m_autospells` membership already agree, followed by one `PetSpellInitialize` when the post-write read agrees. A disagreement is reverted in the model and is not claimed. No spell is learned. Cower 1742 is not restored. `owner->GetPet() == pet` is required before a toggle. Warlock pets stay out of scope.

`ClassifyOwnerOnMapThread()` returns `Uncertain`. `WriteAllowed` is false for that value, and the restore hook returns before any toggle. The writer does not include `Playerbots.h` and does not call `IsRealPlayer`. Pinned Playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` stores bots in `std::unordered_map` `_playerbotsAIMap` (`PlayerbotMgr.h:135`) with no mutex. `GetPlayerbotAI` finds that map at `PlayerbotMgr.cpp:1868`. `AddPlayerbotData` erase/emplace is `PlayerbotMgr.cpp:1828-1834`. `RemovePlayerBotData` erase is `PlayerbotMgr.cpp:1842-1845`. The AI destructor removes at `PlayerbotAI.cpp:247`. `OnBotLogin` inserts at `PlayerbotMgr.cpp:514`. `.bot self` inserts at `PlayerbotMgr.cpp:1117`. `OnPlayerAfterUpdate` reads the map from the player update at `Playerbots.cpp:248-250`. `IsRealPlayer` (`PlayerbotAI.cpp:4523-4528`) is that read. `OnPlayerLogin` adds manager data for every non-headless session (`Playerbots.cpp:148-150`), and `IsSelfBot` (`PlayerbotAI.cpp:4531-4535`) is a non-headless player whose AI master is itself, so `IsHeadless` is not a positive human test. Concurrent find/emplace/erase is a data race. No happens-before against `MapUpdate.Threads` was proven. The writer therefore does nothing when it cannot be sure: a proposed restore is not written. Turning the key on does not by itself restore a dropped autocast byte. That is fail-closed, not a gameplay result.

CS01 resolved the startup config-order question from pinned Grimfeather `8daffdabe9202c228e45d833c9a1d399597a15cd` (`Main.cpp` loads module configs, `ScriptMgr::Initialize` registers scripts, then `World::SetInitialWorldSettings` calls `OnBeforeConfigLoad`). This draft does not change that hook.

## Labels

| Finding | Label |
| --- | --- |
| Default 0 / `false`, and the off path returns before allocation | **VERIFIED** by the native policy tests and the source contract |
| Unchanged book skips `FillBook` / `DecideChains`; 1000 identical snapshots do no decision work | **VERIFIED** by the native policy test and the source contract. A mutation that removes the fast path fails those tests |
| Map-thread `IsRealPlayer` / `_playerbotsAIMap` read | Not used. **VERIFIED** fail-closed in source and native tests. Thread safety of the pinned unlocked map was **not** proven. In-game effect of leaving the byte unrestored is **NOT TESTED** |
| Same-pet `CustomData` baseline, no process-global pet dictionary | **VERIFIED** in source. The baseline key is one process-lifetime string, not a pet map. Live `MapUpdate.Threads` is **UNKNOWN** |
| Same-chain restore, post-write agreement, Cower 1742 not learned | **VERIFIED** by native tests, including mutations that fail when the guard is removed. The production map-thread gate does not reach the toggle |
| Pinned 31-row chain identity used as a test fixture | **VERIFIED** at the S1 pin. The owner's live `spell_ranks` is **UNKNOWN** |
| Startup `OnBeforeConfigLoad` order | **VERIFIED** by CS01 at the pinned core cited above. Unchanged in this draft. Not an in-game pass |
| Real human only | The writer does not call `IsRealPlayer`. **VERIFIED** fail-closed. The two uncommitted edits on Playerbots `e88cc409` were not read and are **UNKNOWN** |
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

No SQL, DBC, core, Individual Progression, or Playerbots file is edited.
