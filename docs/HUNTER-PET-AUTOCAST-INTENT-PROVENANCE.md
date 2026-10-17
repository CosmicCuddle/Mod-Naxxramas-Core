# HPA-G3 — Explicit human autocast intent and native handler provenance

**STATUS: PINNED SOURCE RESEARCH + SYNTHETIC MODELS ONLY. Not an active preference recorder.**

## Two different things that look the same

The pre-handler `ServerScript::CanPacketReceive` hook sees a client-format command **before** `WorldSession::HandlePetSpellAutocastOpcode` or `HandlePetSetAction` runs. Native handlers can reject a missing/foreign Pet, an unknown or unlearned spell, actionbar positions/moves, or a disabled command. After the hook runs, they can call `Pet::ToggleAutocast` / `CharmInfo::SetSpellAutocast` when accepted. `Pet::ToggleAutocast` itself checks native eligibility and can be called without going through either network handler.

The existing read-only audit compares a prior candidate with a *later native state* but this creates a provenance ambiguity: **a rejected packet followed by a direct state change by another actor can produce the same observations as a successfully accepted packet**. Conversely, a valid human packet can be immediately overwritten by another actor. No public post-handler-accepted pet-autocast callback is exposed by the pinned `ServerScript` interface.

Even if a packet was accepted by its handler, a packet-format command and session alone cannot identify whether it originated from a real human, automation, or a bot; authoritative client/actor attribution would need independent proof. Bot direct `ToggleAutocast` paths require separate analysis and must never become user preferences.

**Pinned Playerbot confirmation:** The [bot-policy investigation](HUNTER-PET-AUTOCAST-PLAYERBOT-POLICY.md) proves that actual bot actions can call `Pet::ToggleAutocast` directly and independently reassert default ON/OFF settings. A bot command can be master-issued but remains unidentifiable through the client pet-packet hook. Do not silently store it as a verified human preference, and do not treat the current explicit `isPlayerbot` veto as a complete solution for Hunter Playerbots.

## Necessary evidence (still not available)

1. A **verified native handler-applied change** for this exact owner, Pet instance, spell, state and command operation, rather than an observed receive packet or matching state afterward.
2. An **independently attributable human choice** for the same operation. Neither post-state alone nor a network-format packet on its own establishes it.
3. Existing pet-incarnation, current lawful rank, native autocastability, independently verified IP completion and no later conflicting actor state.

The standalone C++ review gate now has a separate `NativeAcceptanceProof` field. The current audit deliberately cannot populate `VerifiedNativeHandlerChange`; a hypothetical full-proof model can, but that is **not** native runtime evidence. The [synthetic Python model](../tests/test_hunter_pet_autocast_intent_provenance_model.py) demonstrates rejected packet plus direct actor, bot override, headless/nonhuman source and explicit OFF vs default OFF. The [pinned source checker](../scripts/check_hunter_pet_intent_provenance_pinned.py) verifies native handler ordering and validation.

**Boundary:** To get trustworthy post-handler native acceptance would require a supported proven hook or a separately approved core change. No socket-based heuristics, log parsing, synthetic proofs or interception will be used to unlock preference persistence. All changes remain inside Naxx Core draft PR #26 with no gameplay/SQL changes.