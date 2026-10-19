# Human Hunter pet autocast — proposed IP legal-rank correction (NOT APPLIED)

**19 October 2026 · owner approval required before applying to Individual Progression.** This is a proposed patch **stored in the Naxxramas Core GitHub repository as ordinary text**. We have **not** edited the external IP repository, installed server, characters database, AzerothCore, Playerbots, configuration, SQL or DBC. PR remains DRAFT/UNMERGED.

Review artifact: [`proposals/hunter-player-ip-autocast-legal-rank-review-only.patch`](../proposals/hunter-player-ip-autocast-legal-rank-review-only.patch). Its target is pinned upstream [`Grimfeather/mod-individual-progression` `4ff4b5fcc1480348f058c632573143e62d4e3a41`](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp).

## Why this is the narrowest currently known correction

AzerothCore already saves each native pet ability's `active` field in `pet_spell`. IP's `checkHunterPetSpells` currently removes undesired legal-rank family members before learning the permitted `keepId`. Newly learned autocastable spells default OFF. A player who previously selected ON may therefore appear to lose the preference **if** the IP rank-change pathway is actually exercised on that saved pet.

The proposal acts **inside one synchronous IP `reconcile` call**, not through a later Naxxramas timer:
1. For a real human Hunter who already passes IP's progression/VanillaHunterPets/bot exclusion gates, inspect currently known and autocast-capable old ranks in that same IP-defined `wipeIds` family before IP removes them.
2. Only if the legally permitted `keepId` is missing, capture the prior native state when **exactly one** old autocastable rank has a saved `ACT_ENABLED` or `ACT_DISABLED` value. Ambiguous or absent states are not guessed.
3. Run **the original** unlearn-all-unwanted / learn-the-permitted-rank logic, including `keepId=0` behavior. The proposal does **not** grant or retain illegal abilities.
4. Restore ON **or OFF** only after a *successful* legal learn, for the **same currently owned Hunter pet**, not being loaded, only if the new spell exists and is autocastable and the action bar contains its exact `keepId`.
5. Use native `Pet::ToggleAutocast` **and** `CharmInfo::SetSpellAutocast`, followed by a native client pet-spell refresh. Never directly write `pet_spell` rows.

**Safety limitation / proposed mitigation:** The reviewed patch now also proposes checking the original runtime pet GUID in IP's delayed event, avoiding a stale event targeting a replacement pet and aborting after the loading retry cap. **Neither change has been applied or C++ compiled**; both need maintainer review, separately authorized real-player staging and original-pet lifecycle evidence. No old pet preference is stored in Naxx.

## Safety review refinement: same rank chain, not merely the same IP wipe list

The first proposed diff treated any single autocastable spell in the
`wipeIds` list as the source of the replacement preference. That was **too
permissive**: IP's lists are eligibility lists and can contain different
types of abilities or several surviving old entries. We should not infer
that two spell IDs are ranks of the same ability merely because they
appear together in one removal list.

The improved, **still unapplied** proposal now insists on **all** of these:
- `keepId` must actually appear in that IP `wipeIds` list, be a known
  native spell, and be autocastable (otherwise leave IP's original behavior
  unchanged).
- Exactly **one** other spell from the list is *currently known* by the
  same pet. Count **every** currently known spell, including passive or
  unrecognized entries; don't hide ambiguity by counting only eligible
  autocast candidates.
- The previous spell and permitted `keepId` must be native
  `SpellInfo::IsDifferentRankOf` members of the **same spell chain**,
  both autocastable, with a valid native `ACT_ENABLED` or
  `ACT_DISABLED` state.
- The replacement must actually be learned and still owned by the same
  loaded player Hunter pet, and its exact spell must have an existing
  action-bar slot. Otherwise, **do not transfer a setting**.
- A failure of these conservative checks does not cancel the original
  legal IP reconciliation; it only refuses preference restoration.
  Consequently some custom IP-defined rank families might not restore
  state until their real spell-chain metadata is independently verified.
  That is deliberate fail-closed behavior.

This corrects an **identified semantic weakness** in the first review
proposal; it does **not** establish the real-player cause or grant
permission to modify IP. The expanded model has 13 cases, including
mixed families, unknown extra old spells, out-of-list `keepId` and an
invalid state that must not be interpreted as OFF.

## Original-pet delayed event guard — second independent defect candidate

The pinned IP `IndividualPlayerProgression_PetScript` enqueues
`DelayedPetSpellCheck` on a particular **pet's** event processor but
retains **only the player-owner GUID**. On delivery it searches
`player->GetPet()` again, which could be a different pet after dismissal
or stable swapping. Even where this might be prevented by event queue
destruction, the source alone does **not** guarantee original-pet identity.
The current loop also runs IP reconciliation after exhausting ten loading
retries, even if `Pet::isBeingLoaded()` remains true.

A **second hunk within this same UNAPPLIED proposed patch** would pass the
originating runtime `pet->GetGUID()` into the delayed event, preserve that
GUID on any retry, and reject an event if the owner now has no pet or a
different pet GUID. It would **stop without reconciling** if native spell
loading is still unfinished at the retry cap, clearing its pending marker
on the matched pet so a future pet lifecycle event is not permanently
suppressed.

This is intentionally **transient original-object identity**, not a new
durable preference identifier. It cannot prove that a destroyed pet number
will never be reused. The event still lives on the original pet's own
event queue; the GUID check is an additional fail-closed lifecycle gate.

The extended synthetic model now checks stale swapped pets, missing
original identity, exhausted-loading state and the positive case of the
**same, fully loaded pet**. This is **not** proof of how the original
Worldserver behaves during a real stable swap. A full modified IP C++
compile, upstream maintainer review, controlled test and owner approval
are required before the event change can be considered safe.

## What the tests establish—and what they cannot

The lightweight review workflow uses `git apply --check` against a disposable checkout at exact IP source SHA. **That command checks patch context without applying it.** The seventeen standard-library Python synthetic tests cover ON, OFF, pre-existing keep-rank, missing/illegal keep-rank, ambiguous old ranks, uncastable spell, different pet, in-progress load, missing actionbar and learn failure, and patch safety markers.

A successful `git apply --check` and synthetic model is **not** compiled C++, not proof that the code passes all upstream IP/Worldserver rules, and not proof that the owner's bug occurred because of that code. **No automatic promotion, upstream pull request or installation is authorized.**

## Mandatory approval gates before any actual fix

- Confirm the user's **installed** exact IP/core/module versions and effective `VanillaHunterPets`/progression eligibility privately.
- First reproduce with a real player Hunter on an isolated staging copy, using a **verified restorable backup of the full characters database, exact binaries and config**. Compare explicit ON and OFF for at least two real autocastable abilities across ordinary summon/relog **without** rank change and actual legitimate IP rank transition. Follow the [SELECT-only HeidiSQL guide](../docs/HUNTER-PET-PLAYER-AUTOCAST-HEIDISQL-READONLY-REPRO-2026-10-19.md); do not hand-edit spell rows.
- If the issue is real and specifically IP rank replace, obtain **separate explicit owner approval** for a very narrow IP change; do not quietly edit IP outside its own approved branch.
- Review with the IP maintainer before compiling/applying: learned-rank family validity, original-pet event binding, owner vs bot classification, missing actionbar slots, rank-chain inheritance, updated spell packet ordering, and possible alternate upstream rank-preservation mechanism.
- After approval, compile/validate against the **installed** AzerothCore and IP source, test ON and OFF across summon/stable/revive/relog, and prove rollback before any merge or release.

**Release note:** Pet autocast persistence for human Hunters is **not finished**. The proposal represents a candidate implementation awaiting reproduction, code review and approval, not a completed Naxxramas Core feature.
