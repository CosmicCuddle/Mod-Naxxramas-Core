# A02 PAK-D1 v2 — CS03 independent negative witnesses (research only)

**Status:** read-only research while CS02/Grok is on an owner-reported break (CS01 #48 `6397028604`, standing queue #143). **Not a Hunter fix and not a protocol decision.** Grok keeps ownership of #135. Nothing in #135, #134 or the client addon is edited. The first version of this analysis is #48 comment `6397139639`.

**Subject:** Grok's frozen v2 model `tests/research/test_a02_pak_d1_protocol_v2.py` at #135 `50f0500eb7b1f682d34cf6fcd0542556cf8363a1` (blob `544040fe7c1d8d30c0a9dc17fa8c607f4a0c2b25`). It is imported unchanged. Its own suite still reports `WITNESS_TOTAL 37 … v2_safety_fail=0`.

## How the tests work

`tests/research/test_cs03_a02_pak_negatives.py` has 8 tests:

- **GAP** tests assert that the frozen model *has* the gap, so they fail once Grok's model closes it. That is the signal to retire them.
- **REF** tests run the same scenario on a minimal reference subclass (`RefStore`) that implements the proposed fix. They show each negative acceptance test is satisfiable.
- Without `PAK_MODEL` the module skips, so the repository-wide test run is unaffected.
- CI (`.github/workflows/a02-pak-cs03-negatives.yml`) fetches the frozen commit read-only, pins the model blob, reruns Grok's suite, then runs these tests.

## Findings

| ID | Gap in the frozen model (GAP witness) | Proposed property (REF witness) | Source fact for a C++ receiver (core `8daffda`) |
| --- | --- | --- | --- |
| **PAK-RESTART-01** | A fresh `V2Store` (new process) re-mints `(epoch 1, token 0000000000000001, gen 1)` for the same saved pet. A delayed complete old-process `17259=0` packet is accepted and applied. | Each issued token is 64 random bits (16 hex, same byte budget), so the old packet is inert after restart. | `Acore::Crypto::GetRandomBytes` → `RAND_bytes`, but it **ASSERTs** on failure (`CryptoRandom.cpp` L22–L26). To fail closed, call `RAND_bytes` directly and close the gate if it returns ≠ 1. No deterministic fallback, no DB write. |
| **PAK-HELLO-STALE-01** | After A→B, A's HELLO is still queued. `logout()` doesn't clear it. 50 summons queue 51 HELLOs. | One coalesced slot per player. At send time, drop it unless the player is logged in and the epoch, token, gen and pet number equal the current `active`. Logout clears it. | `WorldSession::SendPacket` only enqueues to the socket's MPSC queue (`WorldSocket.cpp` L528), so the HELLO can be sent **from the map worker in the same tick that observes the pet**, in FIFO order after that summon's pet-bar packets. |
| **PAK-STABLE-MEMBER-01** | `observe()` adds any non-zero current pet number to `player.stable`. A pet in no owner stable, never retired, gets a HELLO and has data applied. | Membership comes only from an independent oracle. An unconfirmed pet gets no `active` and no data. | `Player::GetPetStable()` (`Player.h` L1226): `PetStable::CurrentPet` (`Optional<PetInfo>` with `PetNumber`), `StabledPets` and `UnslottedPets` (`PetDefines.h` L214–L238). Require `CurrentPet && CurrentPet->PetNumber == pet->GetCharmInfo()->GetPetNumber()` on the owner's map worker. |
| **Incarnation identity** | The model keys a summon on `id(pet)`. A reused object identity keeps the old generation. In C++ the same `Pet*` address can be reused by the allocator. | Use a per-player monotonic summon counter, set on the map worker when the summon is observed. | The pet GUID is **not** unique alone: `map->GenerateLowGuid<HighGuid::Pet>()` (`Pet.cpp` L267, L1017) is a per-map counter. |

**Client side, for the Addon Creator.** Invalidate the bound HELLO on `UNIT_PET` / `PET_BAR_UPDATE`. Save only under a HELLO received *after* the last pet-change event. A server-rejected stale reply alone does not prevent a wrong SavedVariables write.

## Not verified

- 3.3.5a client delivery, `CHAT_MSG_ADDON` and the addon in Lua.
- `MapUpdate.Threads = 8`.
- Any C++ receiver (none exists).

These are model properties, not game results. CS01, the Module Editor and Grok (on return) review. This does not replace Grok's specialist sign-off.
