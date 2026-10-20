# A02 S2 — experimental module-only hunter pet autocast restore

This branch is a **default-off EXPERIMENTAL prototype**. It is **not functional S2 completion**. Michael (owner) approved authoring a module-only S2 draft. That approval is **not CS01 acceptance**.

No edit is made to Individual Progression, Playerbots, AzerothCore, SQL, or DBC. The config default stays `NaxxramasCore.HunterPetAutocastRestore.Enabled = 0`. Nothing here was run on a worldserver or against a live pet. Labels mean:

| Label | Meaning |
| --- | --- |
| VERIFIED | Read at the pinned SHA named in the sentence. |
| POTENTIAL ISSUE | The source can behave this way. It was not executed on a server. |
| UNKNOWN | Not determined from the pinned trees. |
| NOT TESTED | No worldserver, no client, no character database. |

Pins: core `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd` (Pet.cpp, Pet.h, PetScript.h, PlayerScript.h, ScriptMgr.h, CharmInfo.h, PetHandler.cpp, and PetDefines.h are byte-identical), IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`, Playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c`. Hook lines below were read on 2026-10-20.

## Revision 2 (CS01 review 5585418726)

Head under review was `2abb7861e6a3a6cd8e1809472799be076db81192`. This revision answers the five remaining blockers. It is still not functional S2 completion.

### 1. Cross-map state

**VERIFIED** at both pinned cores (file blobs match): `MapUpdater::activate` starts one `std::thread` per worker (`MapUpdater.cpp`). `MapMgr::Update` schedules one `MapUpdateRequest` per map and then `m_updater.wait()` before it returns. `World::Update` calls `UpdateSessions` (`World.cpp:1227`) and only then `sMapMgr->Update` (`World.cpp:1254`).

The previous `std::unordered_map PetMemories`, `PreferenceSequence`, and plain `bool FeatureEnabled` are gone. The cycle is `PetAutocastCycle` in `Pet::CustomData` (`GetDefault` / `Get` on key `naxx_a02_hunter_pet_autocast_restore`). Dismiss destroys the `Pet` and that object with it. Logout marks only `player->GetPet()` when that object's stored GUID is the live GUID. It does not scan a table. `FeatureEnabled` is `std::atomic<bool>`, stored with `memory_order_release` at config load and loaded with `memory_order_acquire`. The preference counter lives on that pet object.

`PetLifetimeStore` in the policy tests summons and dismisses. Twelve dismiss/summon cycles leave `size() == 0` after the last dismiss, and a second live pet does not inherit the first pet's snapshot. **VERIFIED** as that model. **NOT TESTED** under a running MapUpdater or thread sanitizer.

### 2. Choice source

`BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE`

**VERIFIED** from the pinned sources. `Pet.cpp`, `PetHandler.cpp`, `CharmInfo.cpp`, `ServerScript.h`, `WorldSession.cpp`, `World.cpp`, `MapMgr.cpp`, and `MapUpdater.cpp` are the same blob at `a66f1be` and `8daffda`:

- IP's reconcile is `unlearnSpell(id, false, true)` then `learnSpell(keepId)` (`IndividualProgressionSpells.cpp:83-90`). `clear_ab` true removes the action-bar slot (`CharmInfo.cpp` `RemoveSpellFromActionBar`). `learnSpell` goes through `addSpell` with `ACT_DECIDE`, and an autocastable spell is stored `ACT_DISABLED` (`Pet.cpp:1810-1813`). The removed old rank is skipped by the rank-copy loop (`Pet.cpp:1841-1842`), so the old ON byte is not copied.
- `HandlePetSpellAutocastOpcode` (`PetHandler.cpp:955-1008`) calls `ToggleAutocast` then `SetSpellAutocast`. There is no `sScriptMgr` call in that function.
- `ToggleAutocast(false)` changes a spell only when its id is already in `m_autospells` (`Pet.cpp:2274-2286`). A learn-default rank is not in that vector, so a later explicit OFF does not change `active`, the spell state, or `m_autospells`. `SetSpellAutocast(false)` writes `ACT_DISABLED`, which is already the learn-default action-bar type (`CharmInfo.cpp` `AddSpellToActionBar`, `ACT_DECIDE` becomes `ACT_DISABLED`).
- `CanPacketReceive` (`ServerScript.h`, hook `SERVERHOOK_CAN_PACKET_RECEIVE`) runs before `opHandle->Call` (`WorldSession.cpp:461-463`). `OnPacketSent` is an outgoing hook. No post-handler receive hook exists in `ServerScript.h`.
- `m_autospells` can still hold the old rank because `removeSpell` does not erase it (`Pet.cpp:1976-1988`). A later OFF on the new id does not remove the old id. That stale id is the same whether or not the player clicked OFF. `ToggleAutocast(false)` on the removed row can rewrite it to `PETSPELL_CHANGED` (`Pet.cpp:2279-2283`). This module does not call that.

`AtomicModuleOnlyChoiceSourceExists()` is false. `DecideRestore` aborts with `NoAtomicChoiceSource` and an empty plan when a single chain would have been turned ON. `Execute` checks the same constant again before `ToggleAutocast`. No packet cache and no timer is used as the signal. **NOT TESTED** in game.

### 3. Reconciliation flag the runtime does not have

**MISMATCH.** `Execute` passes literal false to `TryCommitSnapshot`. `BookLooksPostReconcile` is true only while a `PETSPELL_REMOVED` autocast row is still in the book. `Pet::_SaveSpells` erases those rows (`Pet.cpp:1588-1591`) and does not write them. `RuntimeObservesIpReconciledFlag()` is false. `RunSequence` commits through `CommitSnapshotRuntime`, which has no reconcile argument.

`RuntimeFaithfulIpSaveThenPoll` is that order: bind, load, IP swap, save, poll, restore. The poll commits the post-IP rank (the new id, autocast off). Explicit ON ends as `NoChange` with zero toggles. That `NoChange` means the post-save book matches the snapshot just taken. It is not a preserved player OFF. Forcing `ipAlreadyReconciled` true on that same post-save book returns `IpAlreadyRan` and does not commit. That forced call is not what `Execute` does. **VERIFIED** as the policy model. **NOT TESTED** on a worldserver.

### 4. Cross-pet pending clear

`ClearPendingAllowed` requires the same owner, live GUID, pet number, and generation. `Execute` returns before any `CustomData` write when `player->GetPet()` is missing or its GUID or pet number differs from the event. `ClearPendingIfBound` also requires `GuidRaw(pet->GetGUID()) != bound.petGuid` to fail closed. A generation mismatch does not clear. The policy test keeps pet B's `pending` set when the event is bound to pet A. **VERIFIED** as that model. **NOT TESTED** as two live summons.

### 5. Multi-chain and stale autocast ids

`DecideRestore` aborts with `AmbiguousBook` unless the snapshot and the book each contain exactly one autocast chain. A bite chain that would have been an ON write beside an unchanged growl chain produces no plan and no write. One chain is not a claim about every hunter pet ability. How many autocastable chains a live pet has is **UNKNOWN** (no Spell.dbc in this repo). Stale `m_autospells` ids are not removed. **NOT TESTED** in `PetAI`.

## What the previous revision changed

The previous head accepted an uncertain account, let `CanPacketReceive` store `CMSG_PET_SPELL_AUTOCAST` before the core handler, keyed memory by owner plus pet number, skipped explicit OFF, and treated a 50/200/350 ms story as ordering. Those paths are fail-closed in the policy tests.

1. **Account.** `ClassifyAccount` returns `ConfirmedHuman`, `ConfirmedBot`, or `Ineligible`. A missing name, a failed lookup, an empty pattern, and a pattern that does not compile are `Ineligible`. Only `ConfirmedHuman` may schedule or restore. `Ineligible` is not "not a bot".
2. **Packets.** The receive hook is not registered. `UnvalidatedPacketDrivesToggle()` is false. `DecideRestore` has no packet argument. An unverified ON does not plan a restore.
3. **Identity.** The cycle stores the owner GUID, the live pet `ObjectGuid::GetRawValue()`, and the pet number captured at hook time. A later pet with the same number and a different GUID aborts (`StaleSnapshot`). Not in world, `IsDuringRemoveFromWorld()`, or session logout aborts. `ScheduleCycle` does not clear a snapshot when `OnPetAddToWorld` and `OnInitStatsForLevel` both run, or when a later schedule repeats.
4. **Explicit OFF.** If the snapshot says OFF and the current rank is ON, the whole pet aborts (`ExplicitOffConflict`) and no chain is turned ON. If the snapshot says OFF and the new rank is already OFF, the outcome is `HonourOff` and nothing is written. `ToggleAutocast(false)` is not called.
5. **Order.** `RunSequence` takes an explicit step list. IP first, module first, the same list as one flush, a load that outlasts IP's 10 retries, a save, relog, a different pet, a same-number resummon, and a second restore are each either one ON write on the bound GUID or an abort with zero writes.

A REMOVED row is not a preference. With no committed snapshot, `DecideRestore` returns `NoSnapshot` even if a REMOVED row still says ON.

## (a) Delayed load, then save, then a hypothetical restore

`CounterexampleDelayedLoadThenSave(explicitOn)` is the negative model. The steps are: bind the live GUID while the pet is loading, complete the load, run IP's learn-default OFF, save (the REMOVED row is erased), then restore. The module poll never runs, so there is no snapshot. Both calls abort.

| Player choice before the swap | Book after IP and the save | Model result | Pet writes |
| --- | --- | --- | --- |
| explicit ON | new rank at learn-default OFF, no REMOVED row | `Abort` / `NoSnapshot` | none. The ON is not invented from the missing row. |
| explicit OFF | new rank at learn-default OFF, no REMOVED row | `Abort` / `NoSnapshot` | none. The learn-default OFF is not recorded as a preserved explicit OFF. |

**VERIFIED** as a policy-test outcome of that step list. **POTENTIAL ISSUE:** on a real server this order loses an explicit ON and does not prove an explicit OFF. **NOT TESTED** in game. The same abort is what a save-without-snapshot does inside `RunSequence`. A snapshot taken before IP is a different step list. It still does not turn the new rank ON: `NoAtomicChoiceSource` aborts with zero writes. See revision 2 above.

## (b) Public hooks at the pinned SHAs

Searched: both cores' `ScriptDefines/*.h` and `ScriptMgr.h`, every `sScriptMgr->` call in `Pet.cpp`, IP `IndividualProgression.h` plus `IndividualProgressionSpells.cpp`, and Playerbots headers at `037c014`. **No synchronous before/after IP rank-reconciliation hook exists.** No public hook supplies a saved-pet identity together with an incarnation counter.

Pet.cpp's script calls, identical at both core SHAs, are only:

| Call | Line | When |
| --- | --- | --- |
| `sScriptMgr->OnPetAddToWorld(this)` | `Pet.cpp:118` | `AddToWorld`, before the async spell load |
| `sScriptMgr->OnPlayerBeforeLoadPetFromDB(...)` | `Pet.cpp:241` | before the pet object is created |
| `sScriptMgr->OnPlayerBeforeGuardianInitStatsForLevel(...)` | `Pet.cpp:1060` | inside `InitStatsForLevel` |
| `sScriptMgr->OnInitStatsForLevel(this, petlevel)` | `Pet.cpp:1434` | same, still before `_LoadSpells` |
| `sScriptMgr->OnPlayerAfterGuardianInitStatsForLevel(...)` | `Pet.cpp:1442` | same |
| `sScriptMgr->CanUnlearnSpellSet(...)` | `Pet.cpp:1930` | level-up spell list only |
| `sScriptMgr->CanUnlearnSpellDefault(...)` | `Pet.cpp:1950` | level-up spell list only |
| `sScriptMgr->CanResetTalents(this)` | `Pet.cpp:2057` | talent reset only |
| `sScriptMgr->OnCalculateMaxTalentPointsForLevel(...)` | `Pet.cpp:2242` | talent points, including once after `_LoadSpells` and before IP |

Callable module overrides, same line on both cores unless noted:

- `virtual void OnInitStatsForLevel(Guardian* guardian, uint8 petlevel)` — `PetScript.h:43`, `ScriptMgr.h:678`
- `virtual void OnCalculateMaxTalentPointsForLevel(Pet* pet, uint8 level, uint8& points)` — `PetScript.h:45`
- `virtual bool CanUnlearnSpellSet(Pet* pet, uint32 level, uint32 spell)` — `PetScript.h:47`
- `virtual bool CanUnlearnSpellDefault(Pet* pet, SpellInfo const* spellInfo)` — `PetScript.h:49`
- `virtual bool CanResetTalents(Pet* pet)` — `PetScript.h:51`
- `virtual void OnPetAddToWorld(Pet* pet)` — `PetScript.h:58`, `ScriptMgr.h:742`
- `virtual void OnPlayerBeforeGuardianInitStatsForLevel(Player* player, Guardian* guardian, CreatureTemplate const* cinfo, PetType& petType)` — `PlayerScript.h:519`, `ScriptMgr.h:394`
- `virtual void OnPlayerAfterGuardianInitStatsForLevel(Player* player, Guardian* guardian)` — `PlayerScript.h:522`, `ScriptMgr.h:395`
- `virtual void OnPlayerBeforeLoadPetFromDB(Player* player, uint32& petentry, uint32& petnumber, bool& current, bool& forceLoadFromDB)` — `PlayerScript.h:525`, `ScriptMgr.h:396`
- `virtual void OnPlayerBeforeLogout(Player* player)` — `PlayerScript.h:358`, `ScriptMgr.h:336`
- `virtual void OnPlayerSave(Player* player)` — `PlayerScript.h:377`, `ScriptMgr.h:340`
- `virtual bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)` — `ServerScript.h:75`, `ScriptMgr.h:160`

`CanPacketReceive` is a real hook. It runs before `HandlePetSpellAutocastOpcode` (`PetHandler.cpp:991` rejects a spell the pet does not have). It is not a validated autocast signal, and this module does not subscribe to it. **VERIFIED** the signatures. **NOT TESTED** that a live packet reaches the hook.

Saved pet data is `PetStable::PetInfo` (`PetDefines.h:214`). The fields are name, action bar, `PetNumber` (`PetDefines.h:220`), creature, display, experience, health, mana, happiness, last save time, created-by spell, level, react, type, and renamed. There is no incarnation field. `CharmInfo::GetPetNumber()` (`CharmInfo.h:132`) is that same number. `Pet::LoadPetFromDB` allocates a new low GUID with `map->GenerateLowGuid<HighGuid::Pet>()` at `Pet.cpp:267`. A newly tamed pet does the same at `Pet.cpp:1017` and `sObjectMgr->GeneratePetNumber()` at `Pet.cpp:1018`. The live GUID is readable on the `Pet*` passed to `OnPetAddToWorld` and `OnInitStatsForLevel`, and those hooks still run before `_LoadSpells` (`Pet.cpp:435`) and before IP. That is this summon's object id, not a durable incarnation stored with the saved pet.

IP's only hunter reconcile entry from this module's point of view is `void checkHunterPetSpells(Player* player)` at `IndividualProgression.h:430`. It is the reconcile itself, not a before/after wrapper. `IndividualProgressionSpells.cpp` contains no `sScriptMgr` call. **VERIFIED** by search of that file. The only caller is `DelayedPetSpellCheck::Execute` (`IndividualProgressionSpells.cpp:1342`), which reads `player->GetPet()` from the owner GUID (`:1321-1324`). **PendingPetSpellCheck is not a public hook.** The class is file-local at `IndividualProgressionSpells.cpp:1252` and is absent from `IndividualProgression.h`.

Playerbots at `037c014` has no `PetScript`, no `OnPetAddToWorld`, and no `OnPlayerBeforeLoadPetFromDB` in its headers. **VERIFIED** by `git grep` of that commit. The autocast surface is an AI action, `bool TogglePetSpellAutoCastAction::Execute(Event event)` (`PetsAction.cpp:342`, declared at `PetsAction.h:30`). It is not a saved-pet incarnation signal and not an IP reconcile hook.

## Stale autocast ids

**POTENTIAL ISSUE.** `Pet::removeSpell` (`Pet.cpp:1976-1988`) does not erase `m_autospells`. `Pet::ToggleAutocast(SpellInfo const* spellInfo, bool apply)` (`Pet.cpp:2247-2287`) returns if `m_spells.find` misses. A `PETSPELL_REMOVED` row is still found. The OFF branch erases the id from `m_autospells` only when it is present, then if the row state is not `PETSPELL_NEW` it assigns `PETSPELL_CHANGED` (`Pet.cpp:2276-2283`). A removed row is not new, so the call would resurrect that rank for the next save. That is not a public-API-safe removal. This prototype does not call `ToggleAutocast(false)`. Stale old-rank ids stay in `m_autospells`. **NOT TESTED** in `PetAI`.

`ToggleAutocast(true)` does write `ACT_ENABLED` when the new id is absent from `m_autospells` (`Pet.cpp:2260-2271`). A fresh autocastable learn stores `ACT_DISABLED` (`Pet.cpp:1810-1813`). `ToggleAutocast(false)` does not write that byte on an id that is not already in `m_autospells`. Honouring OFF in this prototype means "the new rank is already OFF, so do not write". It does not mean an explicit `ACT_DISABLED` store. **VERIFIED** as those source lines. **NOT TESTED** in game.

## Ordering the runtime can actually see

`Pet::Update` returns before the event processor while `m_loading` is set (`Pet.cpp:659-660`). `IpDelayedCheckOnPump(PetUpdateWhileLoading, ...)` does not run IP's check, including past attempt 10. **VERIFIED** as that model of the cited early return. **UNKNOWN** whether any other caller pumps `pet->m_Events` during the async callback. **NOT TESTED.**

If some other pump does run IP's attempt 10 while the pet is still loading (`IndividualProgressionSpells.cpp:1330-1342`), the model refuses a later snapshot (`IpAlreadyRan`) and does not toggle. If the book was empty because `_LoadSpells` had not run, IP's one-shot check does not swap, the flag is cleared, and the module still refuses the snapshot because `ipReconciled` is set. **VERIFIED** as the model. **NOT TESTED** as server behaviour.

The runtime does not treat 50 ms / 200 ms / 150 ms as proof. It snapshots only a loaded, in-world, not-being-removed pet whose book has no `PETSPELL_REMOVED` autocast row, then calls `DecideRestore`. IP first, a GUID change, logout, removal, an unknown chain, two REMOVED rows, a REMOVED byte that no longer matches the snapshot, or a missing snapshot produces no `ToggleAutocast`. **VERIFIED** in the policy tests. **NOT TESTED** as wall-clock order on a worldserver.

`BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE`. A post-swap explicit OFF that leaves the new rank at learn-default `ACT_DISABLED` looks the same as "IP just learned it OFF". `DecideRestore` does not plan an ON write for that book. The visible conflicts still abort: snapshot OFF with the new rank ON (`ExplicitOffConflict` on a single chain), a second autocast chain (`AmbiguousBook`), and a REMOVED row whose ON/OFF byte disagrees with the snapshot. **NOT TESTED** in game.

**POTENTIAL ISSUE.** After a cycle is applied, refused, or abandoned, `ScheduleCycle` will not open a second cycle for that same live GUID. A later level-up on that same object does not start another restore. **NOT TESTED.**

## Tests and limits

The policy binary covers the five corrections: ineligible account, no restore from an unvalidated packet, explicit OFF abort-or-honour with no OFF write, live GUID mismatch abort, and no restore without a snapshot. It also covers the orders above, including `CounterexampleDelayedLoadThenSave` for explicit ON and explicit OFF. A pass is **NOT TESTED** as summon, relog, rank change, or worldserver link.

**UNKNOWN:** which hunter pet spell ids are autocastable (no Spell.dbc here), whether each IP wipe list is one chain, and which account names the owner's live `IndividualProgression.BotAccountsRegex` matches.
