# A02 S2 — module-only hunter pet autocast restore

Michael (owner) approved this module-only build. S1 at `a5afd65` still says the synchronous gap has no module hook and that S2 stayed blocked pending that approval. This branch is the approved build. It does not edit Individual Progression, core, Playerbots, SQL, or DBC. The config default is off.

Pinned sources checked while writing this: core `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd` (`Pet.cpp`, `EventProcessor.cpp`, and `EventProcessor.h` are byte-identical; `WorldObject::Update` still calls `m_Events.Update` at `Object.cpp:1076` on both), IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`.

## What the restore does

A `PetScript` on `OnPetAddToWorld` and `OnInitStatsForLevel` queues one owner-GUID event for a hunter pet whose owner is not `isBotAccount`. The bot test reads `IndividualProgression.BotAccountsRegex` through `sConfigMgr->GetOption`. The fallback string is only the same default IP passes when the key is absent. It is not a second match list, and Playerbots control is not treated as the same thing.

The event is `CalculateTime(50)` on `pet->m_Events`. IP's event is `CalculateTime(200)` from the same hooks. `EventProcessor` stores events in a `std::multimap` and runs the smaller key first (`EventProcessor.cpp:43-50`, `:159-161`). While `m_loading` is set, `Pet::Update` returns before `Creature::Update` (`Pet.cpp:659-660`, `:736`), so `m_time` does not advance on that path and neither event runs. After the load flag drops, the 50ms key is the snapshot and the 200ms key is IP's single check. The restore is queued when the snapshot runs, at `CalculateTime(300)`. If `m_time` is still on the 50ms key, that lands 150ms after IP's 200ms key. If one update jumps past both keys, the snapshot runs first in that flush and the restore is queued 300ms after the jumped `m_time`, so it is still after IP and is not due in the same flush.

IP's source still requeues every 200ms while `isBeingLoaded()` and `_attempts < 10`, and attempt 10 runs the check anyway (`IndividualProgressionSpells.cpp:1330-1342`). **VERIFIED** as source text. **VERIFIED** that ordinary `Pet::Update` does not enter that loop, because it does not pump `pet->m_Events` during the load flag. **UNKNOWN** whether any other caller pumps that processor inside the async callback. **NOT TESTED.**

On restore, a chain is touched only when the known rank changed and the saved state was ON. The call is `ToggleAutocast(newRank, true)`, then `SetSpellAutocast(newRank, true)`, then one `PetSpellInitialize` if any chain was turned on. **VERIFIED** at `Pet.cpp:2260-2271` that ON writes `ACT_ENABLED` when the new id is absent from `m_autospells`. **VERIFIED** at `Pet.cpp:2274-2285` and `:1889` that `ToggleAutocast(false)` does not write `ACT_DISABLED` on a rank `learnSpell` just added. OFF is left as that learn default (`Pet.cpp:1812-1813`). This build does not call `ToggleAutocast(false)` and does not claim a separate OFF write.

If the snapshot did not run, one REMOVED row of the same chain can still donate ON. A REMOVED row whose byte is OFF donates nothing. `removeSpell` keeps that byte until the next save (`Pet.cpp:1976-1988`, `_SaveSpells` at `:1588-1591`). **POTENTIAL ISSUE:** a save between IP and the restore erases the fallback. The in-memory snapshot does not depend on it.

`CanPacketReceive` on `CMSG_PET_SPELL_AUTOCAST` keeps an in-memory ON/OFF for that chain. There is no hook named `OnPacketReceive` at either core. A newer packet wins over the snapshot. An OFF packet suppresses a later ON restore. **UNKNOWN** / **NOT TESTED** that the hook actually sees the client packet.

## Risks

- **POTENTIAL ISSUE:** stale old-rank ids stay in `m_autospells`. `ToggleAutocast(true)` does not remove them, and this restore does not call `ToggleAutocast(false)` to try. Same leftover IP already leaves. **NOT TESTED** in `PetAI`.
- **POTENTIAL ISSUE:** the 50ms and 200ms keys are ordered only if both modules sample the same `m_time`. Nothing here proves the processor is idle between the two hook bodies. **NOT TESTED.**
- **POTENTIAL ISSUE:** the event stores the owner GUID and reads `GetPet()` again. A different current pet number is ignored.
- **UNKNOWN:** which listed ids are autocastable, and whether each IP wipe list is one spell chain. A rank that is not the same chain is not copied.
- **NOT TESTED:** worldserver link, in-game summon, relog, and a real rank change.
