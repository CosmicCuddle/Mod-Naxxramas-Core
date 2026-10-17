# HPA-G3 — Pure C++ Autocast Decision Gate (no runtime restoration)

**STATUS: STANDALONE RESEARCH CODE ONLY.** The header is not included or registered by the Worldserver and contains no access to Player, Pet, SQL, native actionbar, or ToggleAutocast. It is not an implementable server feature yet.

## Why this exists

The present read-only audit observes packets and current native state, but cannot prove a permanent individual pet identity, a verified **human** decision, or IP completion. A standalone, dependency-free policy gate makes these omissions explicit before any future work attempts a restoration.

The [`HunterPetAutocastDecisionGate.h`](../src/Systems/HunterPetAutocastDecisionGate.h) function returns only `Skip` or `CandidateOnly`. `CandidateOnly` is permission to examine a *hypothetical future candidate*, **not** permission to apply any autocast state.

## Required evidence

- An explicitly chosen `On` or `Off`. `Unknown` always skips. The current native default `ACT_DISABLED` does not prove OFF.
- A separately **verified human** source. The two packet hooks run before native validation. A matching later native state is useful evidence, not definitive human attribution. Playerbot direct toggles are ineligible.
- A verified after-IP completion point, not `isBeingLoaded()==false`, elapsed milliseconds, IP's private pending flag, or an SMSG learned-spell packet. **No such verified module-only signal has been established.**
- For a continuous live Pet object, exact runtime-object identity can support a hypothetical candidate.
- For a new Pet object after dismiss/resummon **within the same Worldserver process**, a possible *module-owned RAM-only* cache could use its observed unique PetNumber if the preference was captured during THIS process and the native allocator demonstrably did not reset or wrap. The existing code does not validate either proof, and no cache has been implemented.
- Across **Worldserver restart**, a source-verified never-reused durable incarnation would still be required. Native PetNumber is not durable; no such incarnation proof has been established.
- The owner must be the intended Hunter, the active Pet must be a Hunter pet, its current rank must actually be known, truly autocastable and **legal for that Hunter's current progression**, with exactly one nonambiguous active rank in its canonical family.
- `RankEligibilityProvenance::VerifiedOwnerSpecificIPRules` requires a future source-verified application of the Hunter's **own** rewarded hidden quests, IP configuration, applicable family/dummy reconciliation rules and eligibility. Account-wide maximum or quest stage alone is insufficient. This enum is a hypothetical proof category; the current audit has no producer for it.

## Scopes and blocking outcomes

| Scope | Minimum identity | Current verdict |
|---|---|---|
| Same Pet object, such as continuous life/revival | Exact runtime Pet object plus all other evidence | **BLOCKED**: missing human/IP proofs |
| Different Pet object after resummon or stable, *same Worldserver process only* | Hypothetical fresh volatile preference + proven continuous PetNumber allocator, or durable incarnation | **BLOCKED**: no human/IP proofs or runtime continuity monitor |
| Any Worldserver process restart | Independently verified non-reusable durable incarnation | **BLOCKED**: native PetNumber may recycle |
| Playerbot AI directly toggles autocast | Independent human or bot policy still to be designed | **BLOCKED** for restoration |

## Testing

Run `g++ -std=c++20 -Wall -Wextra -Werror -pedantic tests/hunter_pet_autocast_decision_gate.cpp -o /tmp/hpa_gate && /tmp/hpa_gate` from the module root. Pinned GitHub CI runs that same standalone model before its real Worldserver build. It explores positive *synthetic* complete-proof cases and negative cases for every missing proof, for both ON and OFF, including short-lived identity, conditional same-process resummon and disallowed cross-restart identity.

Do not wire the header into the existing Pet or Player scripts, add SQL, or use `CandidateOnly` as authority to mutate anything until the remaining identity/intent/IP contracts and disposable staging evidence are approved.
