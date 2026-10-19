# Hunter Pet Autocast — pinned AzerothCore pet identity and reuse research

**Source-only feasibility review; 19 October 2026. Not a gameplay patch, persistence feature, SQL migration or deployment plan.** Exact audited core: `Grimfeather/azerothcore-wotlk` commit `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7`. Draft Hunter Pet PR #26 remains the read-only diagnostic/standalone safety model, not a writer or preference restorer.

## What the pinned source actually demonstrates

| Source | Directly verified behaviour | Identity implication |
| --- | --- | --- |
| [`Pet::GetLoadPetInfo`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp#L171-L214) | PetStable selects by `PetNumber` from current, stabled or unslotted entries when supplied; otherwise chooses current/entry/nonstabled according to arguments | PetNumber is a **real stable-row key for an existing saved pet**, not a mere per-session pointer |
| [`Pet::LoadPetFromDB`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp#L216-L299) | Map creates a **new `HighGuid::Pet` low GUID** on load; `Create(...)` and `SetPetNumber(...)` reuse persisted `petInfo->PetNumber` | Current object GUID can change across summon/load; object pointer/GUID must not be a durable preference key |
| [`Pet::CreateBaseAtTamed`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp#L1014-L1020) | New tame creates both map pet object GUID and `GeneratePetNumber()` | Fresh pet should not inherit any prior preference merely because family/name/entry match |
| [`Pet::FillPetInfo`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp#L2466-L2483) | In-memory stable record retains `m_charmInfo->GetPetNumber()` | Use owner+verified PetStable link as a necessary cross-summon check |
| [`Pet::SavePetToDB` / `DeleteFromDB`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp#L502-L620) | Saves `PetNumber` into `character_pet` under owner low GUID and slot; delete branch removes that id and related spell/aura/cooldown records | Preferences require independent deletion/swap invalidation and owner checks; current pet merely having the same number is insufficient proof of original incarnation |
| [`ObjectMgr::LoadPetNumber` / `GeneratePetNumber`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Globals/ObjectMgr.cpp#L8104-L8116) ([allocator](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Globals/ObjectMgr.cpp#L8150-L8154)) | On restart, allocator starts from `MAX(id)` in **currently existing** `character_pet` rows, then increments in memory | **Deleted highest-number pet may permit id reuse after a later restart**. No permanent non-reuse guarantee is established by this source; never assume PetNumber alone is an eternal incarnation ID |
| [`Player::LoadPetStable`](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Player/Player.cpp#L16324-L16347) | Loads `character_pet` id and slot as `PetStable::PetInfo::PetNumber` | Owner identity + current/other stable-record association is available to review, but loading a row alone does not give an immutable creation UUID |

**Nuance:** There is genuine evidence that an existing PetNumber can survive dismissal/stable/re-summon/relog, so do not dismiss it as unusable. There is **no evidence here** that it can distinguish a deleted pet from a future id reuse after restart. A runtime object GUID is different on load; the persistent database key is stronger, but not sufficient for unbounded preference lifetime.

## Minimum fail-closed identity contract before implementing restoration

1. **Owner first:** only a verified Hunter's own currently controlled and eligible pet; never infer ownership or bot-master security from PetNumber or name. Distinguish account ID, character GUID and approved bot master role. Do not log account names.
2. **Saved pet row:** match `PetNumber` and owner GUID against the authoritative current/stabled `PetStable` record, and validate hunter type + creature entry where supported. On missing/invalid row, return **NotReady**; no side-effect.
3. **Lifecycle generation:** use a transient generation/token to bind any *pending* IP reconcile or Playerbots master-toggle event to the **original summoned pet object**, invalidating on dismiss/revive/re-summon/stable swap, even if the durable number remains. Never compare only current `owner->GetPet()` after an async callback.
4. **Durable incarnation:** before SQL preferences, prove a **nonrecycled pet creation identity** or explicit lifecycle-specific invalidation/tombstone retained across Worldserver restart. Current allocator based on `MAX(id)` does not prove this. If no public API provides it, a narrowly scoped upstream identifier/hook needs a separate owner-approved change; do not synthesize an immutable ID from name/family/PetNumber alone.
5. **IP and legal ranks:** allow restoration only following an authoritative **completed eligible, same-original-pet** reconciliation signal, current legal rank spellbook and current native autocastability; do not treat void method return/cleared pending marker as success.
6. **Playerbots master origin and precedence:** accept separately authenticated, native-applied per-spell master ON/OFF outcomes while ignoring AI-default toggles. Any precedence coordination belongs in the accepted Playerbots producer, not in a Naxx timer repeatedly retoggling the pet.
7. **Storage/provenance:** if ever approved, key by verified character+durable pet incarnation+spell family (not rank id alone); tolerate rank replacements, enforce deletion cleanup, idempotence and separate test approval. Keep migration reversible with a **verified restore of the complete characters DB**.

## Source-only test matrix (not yet an in-game test)

| Scenario | Required readiness/result |
| --- | --- |
| Dismiss/re-summon the **same** saved pet | Same PetNumber may reappear, but lifecycle token changes; after *new* IP completion, existing verified preference may be considered |
| Stable swap to a different saved pet | New number/incarnation, cancel old pending callbacks and never copy preferences |
| Pet death/revive | New readiness epoch; never use stale IP ready signal |
| Relearn / rank upgrade | Current native legal rank decides; old rank ID not blindly restored |
| New pet of same family/name | No preference inheritance based on descriptive attributes |
| Delete highest pet id, restart server, tame again | Guard against potential number reuse caused by `MAX(id)` seed; reject old preference until true durable identity proven |
| IP excludes real account due to `BotAccountsRegex` | Explicit ineligible result; refuse restoration |
| AI default versus accepted master OFF | AI default not treated as player preference; no fight-by-retoggle |
| Delayed IP retry cap / pet changed during work | Stale generation or non-success returns NotReady; do not infer success |

## Decision / approval boundary

**Proposed next work is an interface review, not authorisation to implement it.** The pinned source confirms PetNumber is persisted but not a proven forever-unique incarnation identifier. First see whether installed core or a supported public hook offers a monotonic durable Pet UID/deletion event; verify that from the installed **exact revision**. If not, propose the smallest separately approved core/IP/Playerbots interface change before Naxx-owned persistent preferences. No SQL/DBC, runtime module, server, configuration, or upstream code modified by this research. Track with [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28).