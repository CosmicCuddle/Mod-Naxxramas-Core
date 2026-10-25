# A02 — native pet autocast acceptance and pet lineage (CS03 source trace, research only)

**Status:** read-only source research at Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`. It answers CS01's #146 review `6399066149` and #143 item 1. **No module code, no Hunter fix, and no change to #135, #134 or the N-Core addon.** These are source facts, not game results.

## 1. When does the server accept a human's manual autocast choice?

There are two client packets. Neither has a script hook **after** the native handler; the only module seam is `ServerScript::CanPacketReceive`, which runs **before** it (`WorldSession.cpp` L461–L505). `PetScript` has no autocast hook (`PetScript.h` L26–L32).

### `CMSG_PET_SPELL_AUTOCAST` (right-click toggle)

- **Opcode row:** `PROCESS_INPLACE` (`Opcodes.cpp` L886), so it runs on the world thread or the player's map thread.
- **Handler:** `WorldSession::HandlePetSpellAutocastOpcode` (`PetHandler.cpp` L955–L1001). It returns **without any change** when:
  - the pet GUID does not resolve (`GetCreatureOrPetOrVehicle`);
  - the spell ID is unknown;
  - the target is not the player's `GetGuardianPet()` or `GetCharm()`.
- **Per pet**, for each controlled pet with the same entry, it **skips** the pet unless `pet->HasSpell(SpellID) && spellInfo->IsAutocastable()`.
- **Then** it calls `Pet::ToggleAutocast(spellInfo, enabled)` and `CharmInfo::SetSpellAutocast(spellInfo, enabled)`.
- **`Pet::ToggleAutocast`** (`Pet.cpp` L2247) checks again: autocastable, and present in `m_spells`. It then sets `PetSpell.active` (`ACT_ENABLED`/`ACT_DISABLED`), marks it `PETSPELL_CHANGED` and updates `m_autospells`.

### `CMSG_PET_SET_ACTION` (dragging on the pet bar; can carry an ENABLED or DISABLED state)

- **Opcode row:** `PROCESS_THREADUNSAFE` (`Opcodes.cpp` L503), so it runs on the world thread.
- **Handler:** `WorldSession::HandlePetSetAction` (`PetHandler.cpp` L696–L835). It returns when:
  - the GUID is not `GetFirstControlled()`;
  - the slot position is ≥ `MAX_UNIT_ACTION_BAR_INDEX`;
  - it is a one-button removal of a command or reaction slot.
- **Per pet:** command and reaction swaps are checked against the current bar. A spell entry with `ACT_ENABLED`/`ACT_DISABLED`/`ACT_PASSIVE` the pet does not know is **not** applied. `ACT_ENABLED`/`ACT_DISABLED` call `Pet::ToggleAutocast`, then `CharmInfo::SetActionBar`.

### What this means for A02
- **A request is not an acceptance.** Seeing `CMSG_PET_SPELL_AUTOCAST` in `CanPacketReceive` proves only that a request was made, not that it was **accepted**: unknown spell, wrong pet, not learned, or not autocastable all leave state unchanged. That confirms CS01's point.
- **The acceptance rule is pure and public.** It is "the owner's current guardian or charm, the spell exists, `HasSpell`, `IsAutocastable`", and every input can be read by the module on the same thread **before** the handler runs. A module can mirror that rule exactly, the same technique as F14 (#145) with a handler fingerprint. Alternatively it can **observe after**: read `PetSpell.active` on the pet's next update. That observes the result but cannot tell a human toggle from an IP rank reconcile in the same tick.
- **Whether the request came from a human or a bot is a separate question.** It needs the session to be a real client, not Playerbots (`PlayerbotsMgr::GetPlayerbotAI` is null, or the SelfBot gate). That decision stays with the owner or CS01, as CS01 noted.
- **Native persistence already exists.** `Pet::_SaveSpells` (`Pet.cpp` L1572) writes `pet_spell.active`, and `Pet::_LoadSpells` (L1559–L1567) restores it with `addSpell(..., ActiveStates(active), ...)`. The A02 loss comes from what happens after load (IP rank reconcile, #28), not from a missing save.

## 2. Is `PetNumber` a durable lineage key?

- **Where numbers come from.** `CharmInfo::GetPetNumber()` is the `character_pet.id` row. New numbers come from `ObjectMgr::GeneratePetNumber()` (`ObjectMgr.cpp` L8163–L8167; mutex-guarded `++_hiPetNumber`). Taming assigns one in `Unit::InitTamedPet` (`Unit.cpp` L13447).
- **Within one process:** numbers only go up, so they are unique.
- **Across restarts: NOT unique.** `ObjectMgr::LoadPetNumber` seeds `_hiPetNumber` from `SELECT MAX(id) FROM character_pet` at startup (L8116–L8128). Abandoning a pet (`CMSG_PET_ABANDON`, `PROCESS_THREADUNSAFE`, `Opcodes.cpp` L505 → `HandlePetAbandon` L931) runs `RemovePet(..., PET_SAVE_AS_DELETED)` (`PetHandler.cpp` L948), which deletes the row. If the abandoned pet held the **highest** number and the server restarts before a higher one is saved, **the next tame reuses that number**.
- **Consequence:** a client `db.pets[petNumber]` entry for the abandoned pet would then be applied to a different, newly tamed pet. Same-pet ON/OFF across relog and stable swaps is still keyed correctly, because those keep their row.

### Suggested mitigations, for the protocol owners to choose
1. **Add the entry.** Include the pet's creature `entry` (already in `character_pet.entry`) in the server HELLO, and key the addon as `db.pets[petNumber .. ":" .. entry]`. A reused number then also needs the same beast entry to collide.
2. **Forget on abandon.** On abandon the server can tell the client to drop the old record. The module can see it before the handler via `CanPacketReceive(CMSG_PET_ABANDON)` (world thread at this pin), or by noticing the row's absence on the next login.
3. **Optionally, a durable server-side lineage ID** in a module-owned table. That needs SQL and owner approval, so it is not proposed here.

## Not verified
3.3.5a client behaviour, the N-Core addon, a running server, `MapUpdate.Threads = 8`, and whether the owner's realm ever had its highest-numbered pet abandoned before a restart.
