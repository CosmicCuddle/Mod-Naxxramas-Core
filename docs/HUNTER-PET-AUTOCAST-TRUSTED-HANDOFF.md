# HPA-G3 — Trusted post-IP completion handoff contract (proposal ONLY)

**STATUS: No IP or core modification has been made or approved.** This is a standalone, dependency-free C++20 state-machine **specification**, not a live Worldserver callback. A passing test does not mean such a callback exists.

## Pin evidence

The pinned [IndividualProgressionSpells.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp) schedules `DelayedPetSpellCheck` on the Pet's event clock. Its event stores **owner GUID and retry count**, then uses `ObjectAccessor::FindPlayer(ownerGuid)` and `player->GetPet()` at execution time. It does not carry an independently verified **original Pet-object token** or handoff generation. The private `ipp_PendingPetSpellCheck.pending` is set false **before** invoking `checkHunterPetSpells`. That flag is not a completion signal. IP can early return, retry while loading, or skip an ineligible Hunter.

The source-only guard [check_hunter_pet_ip_handoff_boundary_pinned.py](../scripts/check_hunter_pet_ip_handoff_boundary_pinned.py) enforces these assumptions against the exact pinned IP revision.

## Required future contract — no implementation

1. An authorised IP-side producer, **not** a packet or Naxx timing observer, must identify the exact scheduled event invocation and its original Pet object, account-independent owner GUID, current owner session, per-pet event generation and process epoch. A PetNumber alone is not an original incarnation token.
2. Verify the current owner and Pet at the time the event begins **and** again when reconciliation returns. If an old event resolves to a replacement Pet after a swap, do not acknowledge the replacement.
3. Report a genuinely **eligible, completed return** from the Hunter reconciliation call. Scheduled, retrying, owner-missing, IP disabled, bot account, outside IP scope, early-return and abort outcomes are NOT success. Since `checkHunterPetSpells` presently returns `void` with early returns, the upstream contract would need to distinguish the path it actually took rather than blindly signalling after a call.
4. The acknowledgement must be emitted **after** the reconciler returns; the private pre-call `pending=false` state, a learned packet, `m_loading=false` or an elapsed timer is not sufficient.
5. The consumer must independently check the same process, owner GUID, owner-session epoch, Pet-instance identity and event generation; reject stale or duplicated acknowledgements, and invalidate outstanding tokens when the Pet is replaced or the owner relogs.
6. Completion is only one gate. The Naxx-only [decision gate](HUNTER-PET-AUTOCAST-DECISION-GATE.md) also requires independently proven human ON/OFF intent, lawful current ability/rank, and appropriate permanent or process-local pet identity. **Even the proposed successful handoff only yields `CandidateOnly`, never permission to call `ToggleAutocast`.**

## Fail-closed standalone model

[HunterPetAutocastHandoffContract.h](../src/Systems/HunterPetAutocastHandoffContract.h) is **not included anywhere in Worldserver**. [Its synthetic C++20 tests](../tests/hunter_pet_autocast_handoff_contract.cpp) exercise incorrect owner, replaced pet, relogged owner, process restart, old generation, private pre-call state, retry/skip, timers, packets, duplicate/replayed signals and invalidation. In all those cases the contract refuses the handoff. It does not read IP internals or toggle a spell.

## Decision needed before functional implementation

No compatible public after-reconcile callback was found on the pinned module-only hook surface. Adding a properly authenticated signal **inside Individual Progression** would be a separately approved cross-repository scope change with its own draft PR, QA, staging backup and rollback. That modification has **not been requested or performed**. Naxx Core remains the only modified repository.

A module-only session-level approach would still need an independently trustworthy signal with these same properties; until it exists, HPA-G3 is BLOCKED.