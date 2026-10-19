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

**Safety limitation:** The pinned IP delayed event still holds an owner GUID rather than a retained original-pet GUID. This proposal does not rewrite that event and must **not** be approved for deployment until the original-pet scheduling behavior has been examined and accepted. It re-reads only the same current pet within a synchronous reconcile call, so no prior pet preference is sourced from Naxx storage; however an existing stale delayed event could still run IP reconciliation against another current pet. Additional lifecycle correction may be required.

## What the tests establish—and what they cannot

The lightweight review workflow uses `git apply --check` against a disposable checkout at exact IP source SHA. **That command checks patch context without applying it.** The nine standard-library Python synthetic tests cover ON, OFF, pre-existing keep-rank, missing/illegal keep-rank, ambiguous old ranks, uncastable spell, different pet, in-progress load, missing actionbar and learn failure, and patch safety markers.

A successful `git apply --check` and synthetic model is **not** compiled C++, not proof that the code passes all upstream IP/Worldserver rules, and not proof that the owner's bug occurred because of that code. **No automatic promotion, upstream pull request or installation is authorized.**

## Mandatory approval gates before any actual fix

- Confirm the user's **installed** exact IP/core/module versions and effective `VanillaHunterPets`/progression eligibility privately.
- First reproduce with a real player Hunter on an isolated staging copy, using a **verified restorable backup of the full characters database, exact binaries and config**. Compare explicit ON and OFF for at least two real autocastable abilities across ordinary summon/relog **without** rank change and actual legitimate IP rank transition. Follow the [SELECT-only HeidiSQL guide](../docs/HUNTER-PET-PLAYER-AUTOCAST-HEIDISQL-READONLY-REPRO-2026-10-19.md); do not hand-edit spell rows.
- If the issue is real and specifically IP rank replace, obtain **separate explicit owner approval** for a very narrow IP change; do not quietly edit IP outside its own approved branch.
- Review with the IP maintainer before compiling/applying: learned-rank family validity, original-pet event binding, owner vs bot classification, missing actionbar slots, rank-chain inheritance, updated spell packet ordering, and possible alternate upstream rank-preservation mechanism.
- After approval, compile/validate against the **installed** AzerothCore and IP source, test ON and OFF across summon/stable/revive/relog, and prove rollback before any merge or release.

**Release note:** Pet autocast persistence for human Hunters is **not finished**. The proposal represents a candidate implementation awaiting reproduction, code review and approval, not a completed Naxxramas Core feature.
