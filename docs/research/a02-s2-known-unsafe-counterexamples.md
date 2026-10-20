# A02 S2 — adversarial counterexamples for the default-OFF pet restoration draft

**Scope:** exact baseline [PR #60](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/60) at `9f0b6a25af49ca6e8b130f9a47da3591bcbede35`. Five standalone C++ source/policy counterexamples. This document and fixture are **not a fix**. A passing run means the risks are *still present*. The fixture intentionally models no real player, pet, spell cast, database, network request, hook order, or login.

## Negative examples and source basis

1. **Fail-open non-bot gate.** In `HunterPetAutocastRestore.h::AccountIsBot`, an unknown account name, an empty pattern, or a bad `std::regex` returns **false**. The runtime `IsHumanHunter` in `HunterPetAutocastRestore.cpp` treats `!IsBotAccount` as human eligibility. The policy may therefore select an unverified owner. The test verifies the bad return values; it does *not* invoke the PlayerScript gate.
2. **Unverified packet preference.** `CanPacketReceive` caches a client-received `CMSG_PET_SPELL_AUTOCAST` ON before the core's actual handler decides whether the spell is owned/valid. `PlanRestores` can consume that ON when the current rank changes and return a mutating plan. The fixture provides a packet ON where ownership of the old spell is unproven and shows it can plan a restore. The packet hook's actual presence in live runtime is still **UNKNOWN**.
3. **Explicit OFF not actively enforced.** `PlanRestores` ignores any chosen preference with `autocastOn=false`. Under the pinned default unlearn/relearn path the rank usually becomes OFF; in a different ordering that leaves the new rank ON, this plan cannot enforce a previously explicit OFF. The synthetic fixture constructs this adverse state; it does not claim it happened on the owner's server.
4. **Same-number, different-incarnation pet.** `PetNumberMatches` checks a stable pet *number*, not a live pet GUID or exact incarnation. If an event from a previous summon is evaluated against a later summon of the same number, the policy cannot identify the difference. No live pet swap was performed.
5. **Removed fallback may disappear.** If the old `PETSPELL_REMOVED` entry is pruned by `_SaveSpells` between IP's rank swap and a deferred module restore, `PlanRestores` has no original ON state without the snapshot/packet. The fixture demonstrates the absence of a fallback with an otherwise valid current rank.

## Acceptance implications

A genuinely safe module-only implementation needs *confirmed* human eligibility (fail closed on unknown config/name), authoritative validated preferences and client command success, exact pet instance identity and lifecycle cancellation, preserved ON **and** OFF, and reliable ordering against IP without relying on unproven private timers. Also review stale `m_autospells` and rank-chain identity. Strictly default OFF is necessary but insufficient. No live Hunter-pet toggle should follow automatically from either model or native translation-unit CI.

**Known provenance:** two pinned Grimfeather cores `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd`; IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`. Only policy API is compiled in this new fixture. Native compile of the runtime TU belongs to the separate parent PR #60 jobs.

The fixture deliberately emits `A02_S2_KNOWN_UNSAFE_COUNTEREXAMPLES_REPRODUCED` when the **bad candidate semantics** are present. A change in implementation may cause this fixture to fail; that means the evidence must be revised, **not** that the implementation suddenly passed production acceptance. Keep A02 functional S2 blocked until a fresh independent exact-head positive safety review, real pinned Worldserver compilation, backups, and separate human-authorized in-game tests.
