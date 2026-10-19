# Hunter Pet Autocast — Native State Loss Source Evidence

**RESEARCH ONLY.** Pinned AzerothCore and IP source; no change to pet spells, native tables, gameplay settings, or user realm. A source path being possible does not mean a particular pet has encountered it.

Sources:
- [Pinned core Pet.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp)
- [Pinned Grimfeather IP IndividualProgressionSpells.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp)

## Verified native source behavior

1. `Pet::ToggleAutocast` stores enabled/disabled on `PetSpell.active`, updates `m_autospells`, and changes the persisted spell state flag for native saving.
2. `Pet::_SaveSpells` writes each currently known spell ID with its `active` value into native `pet_spell`, while `_LoadSpells` reads that value back. Normal dismiss/reload can therefore preserve autocast ON and OFF when a spell record remains the same.
3. `Pet::removeSpell` removes or marks a spell record removed. Its earlier `active` status is not a permanent independent ability-family preference.
4. `Pet::addSpell` with default `ACT_DECIDE` sets a genuinely **new autocastable spell to ACT_DISABLED**. Passive/non-autocastable spells use a different state. Ordinary higher-rank replacement can inherit a previously known rank's state, but this is a separate code branch, not a guarantee that IP's remove/relearn keeps it.
5. Pinned IP `checkHunterPetSpells` computes the character's legitimate retained pet rank from known dummy spells; it can `unlearnSpell` other ranks and subsequently `learnSpell` a missing permitted rank. In that sequence a fresh spell can get the default OFF state, even if a removed earlier rank had been explicitly ON.
6. When no rank is removed and the known legal rank remains, this specific loss mechanism may not occur. Reproducing it needs disposable staging evidence; its existence is not proof every summon or revival loses autocast.

## Why the module cannot simply restore native ON for everyone

- Native OFF is ambiguous: it can mean a deliberate player choice OR an implicit default after IP relearning. No user-intent proof exists from the value alone.
- The ordinary native pet spell row is keyed to a pet number that can be recycled. A new sidecar that copies its active state by owner/pet number could apply old choices to a newly tamed pet.
- A legal rank can change across progression, but the module must not learn an unlocked rank, resurrect a removed one, rewrite actionbar slots, or assume every IP-listed spell is autocastable.
- Playerbot AI can directly alter autocast, and IP deliberately skips its bot account category; bot ownership and client packet provenance remain separate gates.
- IP does not expose a verified public post-reconciliation completion event. A delayed sample or load flag is not adequate for automatic restoration.

**Source-only CI gate:** [check_hunter_pet_native_spell_state_pinned.py](../scripts/check_hunter_pet_native_spell_state_pinned.py). It verifies that our understanding still matches the exact checked-out core and IP revisions. It cannot grant approval for persistence, runtime restore, or an installed server change.
