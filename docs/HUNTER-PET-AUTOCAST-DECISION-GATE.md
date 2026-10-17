# HPA-G3 — Pure C++ Autocast Decision Gate (no runtime restoration)

**STATUS: STANDALONE RESEARCH CODE ONLY.** The header is not included or registered by the Worldserver and contains no access to Player, Pet, SQL, native actionbar, or ToggleAutocast. It is not an implementable server feature yet.

## Why this exists

The present read-only audit observes packets and current native state, but cannot prove a permanent individual pet identity, a verified **human** decision, or IP completion. A standalone, dependency-free policy gate makes these omissions explicit before any future work attempts a restoration.

The [`HunterPetAutocastDecisionGate.h`](../src/Systems/HunterPetAutocastDecisionGate.h) function returns only `Skip` or `CandidateOnly`. `CandidateOnly` is permission to examine a *hypothetical future candidate*, **not** permission to apply any autocast state.

## Required evidence

- An explicitly chosen `On` or `Off`. `Unknown` always skips. The current native default `ACT_DISABLED` does not prove OFF.
- A separately **verified human** source. The two packet hooks run before native validation. A matching later native state is useful evidence, not definitive human attribution. Playerbot direct toggles are ineligible.
- A verified after-IP completion point, not `isBeingLoaded()==false`, elapsed milliseconds, IP's private pending flag, or an SMSG learned-spell packet. **No such verified module-only signal has been established.**
- For the same *currently alive Pet object*, exact runtime-object identity can be sufficient for a restricted same-object candidate. It is NOT sufficient after dismiss/summon, stable, logout, or server restart. Those scenarios require a source-verified never-reused durable incarnation. **No such identity has been established.**
- The owner must be the intended Hunter, the active Pet must be a Hunter pet, its current rank must actually be known, truly autocastable and **legal for that Hunter's current progression**, with exactly one nonambiguous active rank in its canonical family.

## Scopes and blocking outcomes

| Scope | Minimum identity | Current verdict |
|---|---|---|
| Same Pet object, such as a continuous lifetime across revival | Runtime object proof, plus all other verified evidence | **BLOCKED** in production: no post-IP completion/human provenance proof |
| Dismiss, summon, stable, relog, process restart | Independently verified non-reusable incarnation plus all other evidence | **BLOCKED**: native pet number can be reused |
| Playerbot AI directly toggles autocast | Independent human or bot policy still to be designed | **BLOCKED** for restoration |

## Testing

Run `g++ -std=c++20 -Wall -Wextra -Werror -pedantic tests/hunter_pet_autocast_decision_gate.cpp -o /tmp/hpa_gate && /tmp/hpa_gate` from the module root. Pinned GitHub CI runs that same standalone model before its real Worldserver build. It explores positive *synthetic* complete-proof cases and negative cases for every missing proof, for both ON and OFF, including short-lived identity versus reload identity.

Do not wire the header into the existing Pet or Player scripts, add SQL, or use `CandidateOnly` as authority to mutate anything until the remaining identity/intent/IP contracts and disposable staging evidence are approved.
