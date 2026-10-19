# Hunter Pet Autocast — Smallest upstream integration roadmap

**REVIEW PROPOSAL ONLY — no changes approved or made to AzerothCore, IP, Playerbots, SQL or live realms.**

This plan converts the existing isolated Naxx Core safety models into bounded, independently reviewable changes if the owner explicitly approves cross-repository work. It does **not** mean that any proposed callback or durable pet identity already exists.

## Order of work and why

1. **Freeze exact installed dependencies in a disposable staging clone.** Record actual AzerothCore, IP, Playerbots and Naxx Core commits and build flags. Make a verified, restorable **characters database** backup before any stage that can modify pet or progression state. Existing pinned GitHub CI proves source compatibility only, not the owner's live install.
2. **Pet lifecycle identity proposal.** Define a non-recyclable persistent pet incarnation (if cross-restart persistence is required), owner identity, and a volatile session/event generation. Prove native `character_pet` delete/reinsert and restarted PetNumber allocation cannot mistakenly reuse preferences. Prefer a small identity hook/DB transaction guarantee reviewed separately before preference SQL. No migration without explicit approval and rollback.
3. **Individual Progression after-return signal proposal.** In the source of the actual Hunter spell reconciler, issue a tokenised result only after the correct pet's eligible reconciliation returns. Preserve original pet identity and event generation through its delayed event; explicitly distinguish retry, early return, blocked bot account and legal fixed-point no-op. Its current private pending flag is cleared before the call and cannot certify success. Approve any IP change separately.
4. **Playerbots per-spell applied-state signal proposal.** Use a narrow Playerbots-owned notification at actual `Pet::ToggleAutocast` call sites and after state verification, rather than exposing protected `Engine*` or using its aggregate `ActionExecutionListener::After(bool)`. Include verified origin (`BotDefault`, factory/tame, other AI, or an authenticated master command), exact Pet/session, spell/family, BEFORE and AFTER native states, and a **single monotonic sequence stream** across all relevant spells for that Pet lifecycle. Classify an unchanged operation separately; it is not a native change. If an authenticated master's exact ON/OFF request passed native validation, it can nevertheless be deliberate intent, provided the producer proves the accepted request independently of chat ingress.
5. **Master override versus AI precedence.** Carry a genuinely authenticated master command through Playerbots' security-filtered and deferred command pipeline to the applied per-spell result. To preserve a deliberate master override that conflicts with the `has pet` bot policy, the AI itself needs a clearly scoped/expiring override rule. **Never** install a Naxx timer that repeatedly forces ON/OFF against Playerbots.
6. **Only then consider Naxx Core preference storage.** Combine the independently proven pet identity, IP after-return, native applied master origin, legal current rank, native autocastability, exact spell family, and bot-policy coordination. First deliver optional read-only correlation logs; then separately review any storage schema, transaction boundaries and rollback.
7. **Staging and release gates.** Test the real cases: all legal autocastable Hunter pet abilities; explicit ON and OFF; bot versus human; first tame, dismiss/resummon, death/revive, stable swap, Hunter relog, restart, pet deletion/replacement, stage/rank changes, and master-vs-policy conflict. Rehearse characters DB restore before enabling any persistent writes. Merge/install/enable only after separate owner approval.

## Minimal ownership boundaries

| Owner | Must prove | Must not pretend to prove |
|---|---|---|
| AzerothCore / pet lifecycle | Real unique pet incarnation and lifecycle, when necessary | PetNumber alone is permanent identity |
| Individual Progression | Actual eligible reconciliation finished for original pet/event | `isBeingLoaded=false`, packet or cleared private pending marker means completed |
| Playerbots | Native per-spell applied result and honest AI-versus-master origin, policy precedence | An action-listener boolean or chat receipt proves a specific human change |
| Naxxramas Core | Correlate verified immutable events; fail closed on mismatch/replay | A C++ test fixture proves live provenance or authorises ToggleAutocast |

## Approval boundary

Keep each upstream proposal in its own draft PR, with a non-mutating prototype first. Do not merge, install, enable restoration, add database tables or upgrade other modules unless explicitly approved. If one required upstream interface cannot be made safe, preserve the existing disabled diagnostic and report the blocker rather than deploying a heuristic.

**Present implementation:** all of the above remains an architecture proposal. Naxx Core contains standalone safety models only; its optional runtime audit is read-only and OFF by default.
