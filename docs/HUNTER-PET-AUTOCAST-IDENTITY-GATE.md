# HPA-G3 research gate — Hunter pet incarnation / identity

**Status: SOURCE-BASED RESEARCH ONLY — NO PERSISTENCE DESIGN APPROVED.**
**Repository boundary:** only `CosmicCuddle/Mod-Naxxramas-Core` may be changed.
No database migration, native schema alteration, trigger, pet mutation, live realm change or restoration is authorized by this document.

## The problem a sidecar preference store MUST solve

Our desired record is a deliberate ON or OFF choice for a specific Hunter's **specific pet**, not merely a spell default, a spell ID, a pet family, or a Playerbot AI preference.

A lookup by `(owner GUID, PetNumber, spell family)` is not an immutable incarnation identifier:

1. Pinned Grimfeather [`ObjectMgr::LoadPetNumber`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Globals/ObjectMgr.cpp) reads `SELECT MAX(id) FROM character_pet` and sets `_hiPetNumber = max + 1` at startup. [`GeneratePetNumber`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Globals/ObjectMgr.cpp) returns `++_hiPetNumber`.
2. Consider persisted IDs `100, 102, 104`. Delete pet 104 and restart. Native maximum is then 102; `_hiPetNumber` becomes 103, so the very next generated pet number is **104 again**. The same Hunter could tame another animal of the same creature entry. It would have the same owner, pet number and creature type but must NOT inherit the old pet's autocast choices.
3. Native [`Pet::SavePetToDB`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp) can `CHAR_DEL_CHAR_PET_BY_ID` and reinsert an existing pet as part of an ordinary save. **DELETE then INSERT alone is NOT proof that a new animal was tamed**. A naive trigger that rotates an identity on every insert will destroy legitimate saved preferences.
4. Pinned [`PetScript`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Scripting/ScriptDefines/PetScript.h) exposes `OnPetAddToWorld`, not a dedicated, reliable pet-abandon/retirement or post-pet-save callback. A fresh pet object GUID differs across summons, so it is not a replacement for a durable incarnation token.
5. A module may have been disabled or absent while a pet was deleted and its old ID reused. A later snapshot of just `(owner, pet number, creature entry)` cannot distinguish those histories.

**Consequence:** a sidecar table keyed by pet number (even paired with owner and species), a startup-only snapshot, or action-bar data alone cannot be claimed safe. Do not insert or restore persistent preferences until a non-reusable incarnation proof exists. Unknown/ambiguous identity = leave native ON/OFF untouched.

## Native pet database / stable source audit

The [pinned native character_pet schema](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/data/sql/base/db_characters/character_pet.sql) has a PetNumber primary key, owner, creature entry, name, level, experience, save timestamp and actionbar, but no proven non-reusable pet-birth or incarnation token. Names, levels, stable slots, timestamps and actionbars can change legitimately, so neither an exact nor a fuzzy attribute fingerprint is an authoritative pet identity.

The [pinned PetStable::PetInfo](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/PetDefines.h) likewise includes PetNumber, CreatureId, Name, ActionBar, Experience and LastSaveTime, but no source-verified never-reused incarnation marker. Native taming calls GeneratePetNumber. Native ordinary saves delete/replace the same row, which makes simple deletion/insertion triggers non-authoritative.

The new [source check](../scripts/check_hunter_pet_identity_pinned.py) runs against the exact upstream checkout in CI to detect changes in these assumptions. A passing result means the BLOCKER is corroborated; it does not authorize persistence or constitute a live-schema or runtime test.

## Candidate designs (NONE implemented)

| Candidate | Advantage | Unresolved hazard | Gate |
|---|---|---|---|
| Module-owned table keyed by owner + PetNumber | Easy rollback | Recycled number applies old ON/OFF to another pet | **Reject** without independent incarnation |
| Sidecar with startup inventory sweep | Can retire missing rows observed at boot | Misses deletion/reuse while module absent; also race with normal saves / startup ordering | **Research only**; not sufficient alone |
| SQL triggers against `character_pet` | Could observe DB lifecycle even without active module | Core's routine delete+reinsert, transaction semantics, deployment/rollback and SQL coupling | **Do not install**; needs separate design proof + explicit approval |
| A durable, unique incarnation marker persisted atomically with the native pet | Strongest identity concept | No verified module-only hook/native storage contract; modifying `character_pet` schema is invasive | **Blocked** pending independent source + database compatibility review |
| Runtime-only tracking in `Pet::CustomData` | Scoped to the actual pet object with no DB | Lost on dismiss/relog/restart and cannot preserve intended preference | Valid only for read-only diagnosis |

If all accessible module-only hooks fail to bind a durable identity, record this as a **module-only limitation** rather than weakening the safety condition.

## Independent IP-readiness gate

**Pet event-clock finding (source audit):** pinned `Pet::Update` returns while `m_loading` is true; normal `Creature::Update` → `Unit::Update` → `WorldObject::Update` otherwise advances `m_Events`. IP uses this same pet queue for its `DelayedPetSpellCheck`. Pinned [`EventProcessor::Update`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/common/Utilities/EventProcessor.cpp) advances `m_time` for the full tick **before** executing due callbacks; a delayed IP retry calls `CalculateTime(200)` relative to that current time. Therefore an audit marker at pet-clock +2500ms can execute **before a future IP retry** after an unusual large tick, and is never a completion hook. The experimental observer now records one *read-only* +2500ms pet-owned queue snapshot alongside its existing Player-update samples. It does not act on that marker. Two offline timing counterexamples explain the guard; staging must validate the actual lifecycle.


The pinned [IP `DelayedPetSpellCheck`](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp) begins at 200ms. It reschedules while `isBeingLoaded()` is true for **at most 10 retries**, then calls `checkHunterPetSpells` even if the flag is still true. There is no verified public callback that denotes reconciliation completion. `SMSG_PET_LEARNED_SPELL` may not be sent if a legal rank was already present, and revival can occur in-world without another `OnPetAddToWorld`.

Therefore, a fixed 3-second timer, the first observed `isBeingLoaded()==false`, or a single learned-spell packet **must not** enable writes/restoration. A source-proven ordering contract or controlled staging evidence must resolve summon, loading race, revive and stable scenarios independently. The read-only audit's timed sample is a diagnostic, not a readiness flag.

## User intent and Altbot policy gate

- Accept neither a raw `CMSG_PET_SPELL_AUTOCAST` nor a `CMSG_PET_SET_ACTION` packet as durable preference by itself. Both run through pre-handler packet hooks; even a matching next-update state does not prove which actor caused the transition.
- Preserve **explicit OFF** as a first-class value, not absence of ON. Unknown preference must have its own representation and must never silently turn ON.
- Pinned [Playerbots `TogglePetSpellAutoCastAction`](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/PetsAction.cpp) can call `Pet::ToggleAutocast` directly. The module does not currently receive an explicit-user-source signal for such changes, so no automatic bot switch may be promoted to deliberate ON/OFF.
- Keep Altbots **unsupported for restoration** unless a separate safe user-intent path and bot-policy arbitration can be demonstrated with no Playerbots source edits.

## Required evidence before HPA-G3 can pass

1. Verify a **durable, unambiguous per-pet incarnation** through deletion, retame, same-species pets, stable swaps and full server restarts, including module-disabled gaps.
2. Validate both native packet paths and competing direct AI toggles; distinguish deliberate ON, deliberate OFF and unknown in a reproducible test.
3. Prove safe after-IP execution for summon/revive/relog; not just time elapsed.
4. Design a **module-owned, reversible** migration only when prerequisites 1–3 pass; independently verify character-DB backup and restore in staging, with exact core pins matching deployment.
5. Demonstrate that ONLY the already-known, IP-legal rank is toggled, client actionbar matches, and Rank 6 is never learned/enabled prematurely.
6. Keep the owner approval gate for any actual SQL, install, restart or gameplay test.

## Offline model tests

`tests/test_hunter_pet_autocast_identity_model.py` reproduces the pinned ID-allocation counterexample and fail-closed decision semantics. It is **not** a test of AzerothCore or SQL runtime behavior and does not prove any persistence strategy safe.
