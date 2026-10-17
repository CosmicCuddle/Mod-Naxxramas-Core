# Hunter Pet Autocast — IP rank fixed-point investigation

**SOURCE-PINNED, MODEL ONLY. No IP completion event or runtime restoration has been implemented.**

Sources: [pinned Individual Progression checkHunterPetSpells](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp) and [pinned-source no-op guard](../scripts/check_hunter_pet_ip_fixed_point_pinned.py).

## Key finding

Individual Progression's reconciler chooses a keepId from the Hunter's learned dummy spells in **reverse list order**, removes known ranks different from keepId, and learns keepId if it is missing. Therefore, for a specific applicable reconciliation call, **an already-known selected rank with no disallowed extra rank would require neither a removal nor a learn**. Under *identical* Hunter dummy knowledge, progression, family, spellbook and conditional path, repeating that call would not itself reset native autocast.

This is a **fixed-point property of one hypothetical set of inputs**, not proof IP has executed or finished. It may help investigate a future no-change-before-IP strategy without needing to guess an elapsed number of milliseconds.

## Conditions that any future implementation must independently prove

1. Exactly which IP family and conditional calls apply to this Hunter's **current effective progression tier**. Boar Gore is an example of mutually exclusive pre-TBC and later-TBC paths. Never count both as concurrently active.
2. Current Hunter dummy spells and the source order that determines the selected rank. A newly learned dummy changes the selected rank and invalidates earlier no-op evidence.
3. The pet already knows that exact legal rank and no extra conflicting rank in the complete family. All applicable calls that could remove or re-add any rank in the family must be considered; matching the final spellbook is insufficient if the process unlearns then relearns the same ID.
4. Native SpellInfo::IsAutocastable and effective progression legality must be established separately. IP source wipe lists alone do not prove that a spell is autocastable, unlocked or already known.
5. No other script or gameplay event has a pending spell adjustment, and no relevant inputs change. A prior snapshot cannot certify future inputs remain frozen.
6. Human ON/OFF preference attribution and pet incarnation proof remain independent hard requirements. A proven fixed point does not provide either.

## Examples

| Scenario | Synthetic model conclusion |
|---|---|
| Wolf Bite R8 known; correct dummy present; no other Bite rank | Current source reconciler needs no spell mutation under frozen inputs |
| Wolf Bite R7 and R8 known, with R8 selected | IP would remove R7; not a no-op |
| Wolf Bite R8 present but Hunter subsequently learns R9 dummy | Previously valid no-op becomes invalid; IP may remove R8 and learn R9 |
| Pre-TBC Boar Gore removal-only call | No permitted rank can be inferred from an empty dummy list |
| Conflicting calls remove then relearn the same rank | Final spellbook may match but spell active state can be reset; NOT a no-op |

**Observability caveat:** Native `Pet::unlearnSpell` does not emit its commented-out unlearn notification, `learnSpell` suppresses packets while loading, and IP may reach its retry cap while loading continues. Thus identical before/after snapshots, even with no learned-spell packet, cannot prove no remove/relearn occurred. See [IP completion boundary](HUNTER-PET-AUTOCAST-IP-COMPLETION-BOUNDARY.md).

## Limits

The [synthetic model](../tests/test_hunter_pet_autocast_ip_fixed_point_model.py) is not coupled to any live pet or client. [CI's pinned-source contract](../scripts/check_hunter_pet_ip_fixed_point_pinned.py) verifies that this interpretation matches the checked-out IP code. Passing either test does **not** supply the unimplemented VerifiedPostReconciliation contract, permit toggling autocast or establish that another module cannot mutate the pet.

**Next evidence needed:** verify actual installed source revisions, demonstrate effective progression and family-rank classification without writing, and observe the applied branch on an explicitly approved disposable staging Hunter pet with characters DB backup/restoration. No live realm changes have been authorised.