# Part 27 A02 — pinned C1/C2 source sentinels (standalone research)

**State:** UNWIRED test-only, no module registration, no DB work, no gameplay evidence. This PR is a stacked child of the owner-selected source design #168 at its verified `61fb18e` head; parent and frozen production candidates remain untouched.

## Why these tests exist

The owner chose **C1** module-only pre-handler candidates and later pet observation, plus **C2** a future new restart-persistent database table. Both remain **directions only**. A correct and safe implementation would first require a stable installed handler path, complete packet-hook ordering, reliable pre-login lifetime cleanup and positive human/SelfBot authority. There is no permission for module implementation, SQL, host inspection or any automatic pet write.

The [test fixture](../../tests/test_a02_p27_pinned_c1_c2_source_sentinels.py) is a small **lexical drift sentinel** against actual checked-out **public** `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` sources. It intentionally does **not** parse C++ semantics, call database APIs or fabricate an accepted human receipt.

## What exact-source checks can establish

- `WorldSession.cpp`: successful `CanPacketReceive` immediately precedes invoking the native opcode handler in the stock `STATUS_LOGGEDIN` dispatch; does **not** prove the module observer is the last enabled script.
- `ScriptMgrMacros.h`, `ServerScript.cpp`, `ScriptMgr.h`: enabled hooks iterate in order and stop on a false return, registry holds registered `ServerScript*` pointers and is not to be mutated after startup. The module must compare the exact registered **ServerScript observer pointer**, **not** `WorldScript::this`, in any future approved fail-closed startup check.
- `World.cpp` and `Main.cpp`: `LoadPetNumber` and script database loading precede `OnBeforeWorldInitialized`, whereas `OnStartup` follows the world network listener. A future C2 orphan-sweep research proposal may consider the former boundary only; it must not use the latter.
- `DatabaseWorkerPool.cpp`: `DirectExecute` returns void and discards `connection->Execute(...)` result; `Query` returns null for failure **or** zero rows. Mere call completion or empty result is not successful cleanup evidence. A **positive one-row scalar** check is a possible requirement, **not** proof of exclusivity, transaction durability or real owner DB safety.
- `Pet.cpp`, `ObjectMgr.cpp`: multiple asynchronously enqueued pet-save transactions, broad slot deletion and MAX-based PetNumber reseeding. A fresh sidecar record keyed by owner+number cannot certify the pet birth.

## Negative witnesses and failures

A drift in these source excerpts must make hosted source tests fail rather than silently keeping a module-only proof claim. Small synthetic reversed-dispatch/network-order examples exercise the ordering helper, but do **not** stand in for runtime evidence. Even a fully green test suite cannot prove the observed pet state came from the client opcode rather than interposed IP/Playerbots/script writers.

## Scope of approval

- The workflow checks out the candidate at its exact PR head, uses a **sparse** pinned public core checkout, checks production runtime and config blob IDs, then runs only Python standard-library `unittest`. No Worldserver build/launch, database connection, pet, packet capture, actual owner SQL or host access.
- Any implementation of a packet observer, new SQL table, startup reconciliation, human/SelfBot classifier, write policy or deployment still requires separate owner permission. `TrustedManualReceipt` stays false for module-only correlations and the #165 v1 fail-closed runtime quarantine remains mandatory. `MapUpdate.Threads=8` stays untouched.
- Parent [#168](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/168) remains the owner-selected architectural record, [#169](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/169) and [#172](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/172) are **unwired** retry-policy test models. There is still no functional A02 or owner gameplay acceptance.

**Repository PUBLIC:** never add the owner's server configuration, SQL, NPC/quest/item/loot mappings, Individual Progression private relationships, host secrets or identifying data here.
