# Part 27 A02 — pinned C1/C2 source sentinels (standalone research)

**State:** UNWIRED test-only, no module registration, no DB work, no gameplay evidence. This PR is a stacked child of the owner-selected source design #168 at its verified `61fb18e` head; parent and frozen production candidates remain untouched.

## Why these tests exist

The owner chose **C1** module-only pre-handler candidates and later pet observation, plus **C2** a future new restart-persistent database table. Both remain **directions only**. A correct and safe implementation would first require a stable installed handler path, complete packet-hook ordering, reliable pre-login lifetime cleanup and positive human/SelfBot authority. There is no permission for module implementation, SQL, host inspection or any automatic pet write.

The [test fixture](../../tests/test_a02_p27_pinned_c1_c2_source_sentinels.py) is a small **lexical drift sentinel** against actual checked-out **public** `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` sources. It intentionally does **not** parse C++ semantics, call database APIs or fabricate an accepted human receipt.

## What exact-source checks can establish

- `WorldSession.cpp`: all four stock packet dispatch branches call the native handler immediately after a passing `CanPacketReceive` hook with **no intervening source statement**; the separate map/world filters constrain where INPLACE/THREADSAFE/THREADUNSAFE packets may execute. These checks do **not** prove the module observer is last, or that an event always executes on a specific worker.
- `Opcodes.cpp`: the three pet opcodes preserve their reviewed `STATUS_LOGGEDIN` and processing flags: `CMSG_PET_SPELL_AUTOCAST` INPLACE; `CMSG_PET_ACTION` THREADSAFE; `CMSG_PET_SET_ACTION` THREADUNSAFE. A drift in these registrations invalidates the source-only routing assumption.
- `ScriptMgrMacros.h`, `ServerScript.cpp`, `ScriptMgr.h`: enabled hooks iterate in order and stop on a false return, registry holds registered `ServerScript*` pointers and is not to be mutated after startup. The module must compare the exact registered **ServerScript observer pointer**, **not** `WorldScript::this`, in any future approved fail-closed startup check.
- `World.cpp` and `Main.cpp`: `LoadPetNumber` and script database loading precede `OnBeforeWorldInitialized`, whereas `OnStartup` follows the world network listener. A future C2 orphan-sweep research proposal may consider the former boundary only; it must not use the latter.
- `DatabaseWorkerPool.cpp`: `DirectExecute` returns void and discards `connection->Execute(...)` result; `Query` returns null for failure **or** zero rows. Mere call completion or empty result is not successful cleanup evidence. A **positive one-row scalar** check is a possible requirement, **not** proof of exclusivity, transaction durability or real owner DB safety.
- `Pet.cpp`, `ObjectMgr.cpp`: multiple asynchronously enqueued pet-save transactions, broad slot deletion and MAX-based PetNumber reseeding. A fresh sidecar record keyed by owner+number cannot certify the pet birth.

## Negative witnesses and failures

A drift in these source excerpts must make hosted source tests fail rather than silently keeping a module-only proof claim. Small synthetic reversed-dispatch/network-order examples exercise the ordering helper, and an inserted-statement negative witness guards the claimed **adjacency** at all four stock dispatch sites. The pet-save test now stops at the next named function instead of silently using a 4200-character window. These checks still do **not** stand in for runtime evidence. Even a fully green test suite cannot prove the observed pet state came from the client opcode rather than interposed IP/Playerbots/script writers.

## Scope of approval

- The workflow checks out the candidate at its exact PR head, uses a **sparse** pinned public core checkout, checks production runtime and config blob IDs, then runs only Python standard-library `unittest`. No Worldserver build/launch, database connection, pet, packet capture, actual owner SQL or host access.
- Any implementation of a packet observer, new SQL table, startup reconciliation, human/SelfBot classifier, write policy or deployment still requires separate owner permission. `TrustedManualReceipt` stays false for module-only correlations and the #165 v1 fail-closed runtime quarantine remains mandatory. `MapUpdate.Threads=8` stays untouched.
- Parent [#168](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/168) remains the owner-selected architectural record, [#169](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/169) and [#172](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/172) are **unwired** retry-policy test models. There is still no functional A02 or owner gameplay acceptance.

**Repository PUBLIC:** never add the owner's server configuration, SQL, NPC/quest/item/loot mappings, Individual Progression private relationships, host secrets or identifying data here.

## Part 28 targeted source-drift refinement (27 October 2026)

CS02's review of #173 identified missing opcode registration/filter routing coverage and an adjacency assertion named more strongly than it tested. This update addresses those specific shortcomings without changing module, core, Playerbots, Individual Progression, database, config, or A02 feature flags. The added assertions are **lexical safeguards at an immutable public pin**, not acceptance of C1 implementation or proof of safe human-origin or installed owner behaviour. All automatic pet writes remain in #165's fail-closed quarantine.

## Part 28 — C1/C3 actual pinned Playerbots source gap (27 October 2026)

Read-only review of `mod-playerbots/mod-playerbots@d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` adds four narrowly focused **public-source lexical** checks to the existing runner. It pins the known Playerbots `ServerScript::CanPacketReceive` registrations, including its ordinary packet handler, secure-login check and AFK SelfBot logout check. The ordinary hook forwards master packets into bot processing **before** returning `true`; that action is not proof a bot toggled the human's pet, but the packet-hook callback is not assumed pure or side-effect free.

`PlayerbotsMgr::GetPlayerbotAI` looks in a mutable `std::unordered_map` without a visible lock in the exact source path, and returns `nullptr` when Playerbots is disabled regardless of map contents. `IsRealPlayer` relies on that result. `PlayerbotMgr`'s `self` command can attach AI to a live client player (or delete existing AI); `SelfBotLevel=0` is a gate to *new* attachment when an AI is absent, not a positive attached-state receipt. Therefore neither a client session nor a null lookup from an arbitrary map worker satisfies C3.

The new source checks run **offline only**; they cannot establish thread affinity, all concurrent writers, actual installed hook order, C1 native acceptance, a monotonic attach/detach epoch, or a safe C3 observer across eight map workers. An independently verified, safely serialized producer/invalidation contract remains required at both capture and apply. **Owner C1/C3 implementation permission is still absent.** `TrustedManualReceipt=false`; pet writes stay quarantined by #165. No production or Playerbots sources are edited.
