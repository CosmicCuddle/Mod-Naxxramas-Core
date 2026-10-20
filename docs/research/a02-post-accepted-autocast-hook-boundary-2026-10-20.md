# A02 — two accepted Hunter pet autocast write paths (source-only evidence)

**Status:** read-only research with negative regression tests. A PASS confirms a hazard, NOT a working persistence solution. No SQL installation, character modifications, server restarts or merges permitted.

## Source pins

- Old Grimfeather/AzerothCore: a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7.
- Prospective newer Grimfeather/AzerothCore: 8daffdabe9202c228e45d833c9a1d399597a15cd.
- Exact paths: src/server/game/Handlers/PetHandler.cpp, src/server/game/Scripting/ScriptDefines/PetScript.h, src/server/game/Entities/Player/Player.cpp.
- These source revisions have not been verified against the operator's installed binary.

## Both accepted ways of changing pet autocast

1. WorldSession::HandlePetSetAction (PetHandler.cpp around line 694) handles CMSG_PET_SET_ACTION. Once pet ownership and known-spell checks permit processing, ACT_ENABLED can invoke Pet::ToggleAutocast(spellInfo, true) and ACT_DISABLED can invoke ToggleAutocast(spellInfo, false), near lines 795–831. It updates the action bar too.
2. WorldSession::HandlePetSpellAutocastOpcode (PetHandler.cpp near 955) is a different handler. It verifies controlled ownership, HasSpell and IsAutocastable, then calls Pet::ToggleAutocast and CharmInfo::SetSpellAutocast, around lines 957–1008.
3. The publicly listed PetScript hook enum (PetScript.h around 24–58) has OnPetAddToWorld, but no post-accepted-autocast change callback. This negative is scoped only to that inspected public PetScript surface, not a claim about every possible plugin or custom fork.
4. Player::RemovePet saves through pet->SavePetToDB(mode) before SetMinion(pet, false), near Player.cpp lines 9360–9383. This save need not call PlayerScript::OnPlayerSave.

Observing a client packet BEFORE a handler validates it does not prove acceptance. Observing an ON/OFF bit AFTER the Individual Progression rank change cannot necessarily distinguish a player's explicit preference from that rank's learned-default bit. Checking only one packet handler omits another valid acceptance path.

## Source contract and negative tests

scripts/check_a02_post_accepted_autocast_hooks.py checks both handler bodies, their guards/writes, the currently enumerated PetScript hook surface and RemovePet direct-save order in the TWO exact pinned core trees. tests/test_a02_post_accepted_autocast_hooks.py provides synthetic missing-handler, changed-validation, new-hook, and reordered-dismiss fixtures. Any changed source must fail closed and prompt fresh review.

A successful run proves the hazard persists at the selected pinned source SHAs, NOT that the Hunter cache is safe. These tests do not compile a Worldserver, execute SQL, replay packets, connect to a DB, change a pet, or perform live gameplay.

## Practical next steps

CosmicScript02 should fix separately provable human vs Playerbot and live pet identity problems on draft PR #69, while explicitly keeping accepted-choice/dismiss/async-commit/lifetime blockers open. Both cache and RestoreUtility remain default OFF. Do not narrow the user's all-abilities ON/OFF persistence acceptance without saying so.

CosmicScript01 independently reviews exact new heads, maintains master issue #28 and shared coordination #48, and only considers a comprehensive integrated candidate once all gameplay requirements and safety gates are satisfied.

No upstream AzerothCore, Playerbots, Individual Progression, DBC, pet database or owner server changes.
