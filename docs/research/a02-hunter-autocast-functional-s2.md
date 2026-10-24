# A02 S2 — default-OFF human Hunter pet autocast writer

**Status:** isolated draft. The config key defaults to 0. In-game behaviour is **NOT TESTED**. This draft does not establish gameplay, does not speak for the owner, and is not a merge.

**Author:** CosmicScript02. Independent exact-head review requested from CosmicScript01.

The S1 contract remains `docs/research/a02-hunter-autocast-functional-s1.md`. This note only records the writer that contract authorised.

## What the module does

`NaxxramasCore.HunterPetAutocast.RestoreHumanChain` is 0 in `conf/mod_naxxramas_core.conf.dist`. The C++ fallback passed to `GetOption<bool>` is `false`. The cached flag starts false. Both hooks return on that flag before a pet read, a config lookup, or a `CustomData` allocation.

When the flag is on, `OnUnitUpdate` stores one baseline on that pet (`CustomData.GetDefault`, then mutated in place). `OnWorldObjectUpdate` on the same update reads it back with `Get` and may copy one explicit autocast byte onto a single same-chain successor. The chain key is `SpellMgr::GetFirstSpellInChain`. The 31 pinned Bite, Claw, Furious Howl, and Prowl rows are not hardcoded. A missing chain stays `NO_LEARN`.

The only writes are `ToggleAutocast` and `SetSpellAutocast` on a successor whose active byte, bar type, and `m_autospells` membership already agree, followed by one `PetSpellInitialize` when the post-write read agrees. A disagreement is reverted in the model and is not claimed. No spell is learned. Cower 1742 is not restored.

`IsRealPlayer` runs only after a restore is proposed. Without `Playerbots.h` the writer does not treat the owner as human. `owner->GetPet() == pet` is required. Warlock pets and unchanged spell ids, including any spell this writer does not name, stay out of the write.

## Labels

| Finding | Label |
| --- | --- |
| Default 0 / `false`, and the off path returns before allocation | **VERIFIED** by the native policy tests and the source contract |
| Same-pet `CustomData` baseline, no process-global dictionary | **VERIFIED** in source. Live `MapUpdate.Threads` is **UNKNOWN** |
| Same-chain restore, post-write agreement, Cower 1742 not learned | **VERIFIED** by native tests, including mutations that fail when the guard is removed |
| Pinned 31-row chain identity used as a test fixture | **VERIFIED** at the S1 pin. The owner's live `spell_ranks` is **UNKNOWN** |
| Real human only, missing Playerbots header fails closed | **VERIFIED** in source and native tests. The two uncommitted edits on Playerbots `e88cc409` were not read and are **UNKNOWN** |
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
