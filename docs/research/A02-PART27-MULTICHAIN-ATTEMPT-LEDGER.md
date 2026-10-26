# A02 Part 27 — bounded per-incarnation / per-chain retry ledger

**DRAFT SOURCE-ONLY MODEL. NOT WIRED. NOT A VALID HUMAN COMMAND RECEIPT. NO MERGE OR OWNER SERVER ACTIONS.**

## Proven input

Review at [#166 comment 6417980798](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/166#issuecomment-6417980798) identified a concrete misuse of the existing `AttemptBudget`: one shared instance alternated between two spell chains resets `TotalAttempts` every time `SameSummonChoice` changes chain, allowing 60/60 illustrative attempts instead of a 20-per-summon-and-choice ceiling. The existing 76 C++17/20 tests exercise one chain at a time and do not prevent that incorrect future call pattern. Existing authoring intentionally leaves the legacy single-key `Decide` and `RecordAttempt` unchanged to preserve tests and source semantics; this extension provides a safer **tracked ledger interface**.

## New test-only model API

- `AttemptLedger` is caller-owned by the current pet's owning update thread, not a global map or a cross-thread cache. Its 32 fixed-size entries are keyed by **chain** for **one server-certified pet incarnation**. It uses no heap, DB, locks, Player/Pet pointers, network, timers or game APIs.
- `DecideTracked(choice, current, ledger)` dispatches to the existing policy `Decide` with the *correct chain's budget*, not another chain's budget; if all 32 active slots are occupied, a previously unseen chain returns `NoWrite`. No LRU eviction can let one chain reset another's attempts.
- `RecordTrackedAttempt(ledger, choice, current)` refuses any state without `DecideTracked == ApplyOn|ApplyOff` and only then reserves/counts an actual **attempt** in that chain. This helper does NOT toggle spells. A future caller must pass the **unchanged pre-toggle observation**, count immediately BEFORE issuing a real toggle, and count the attempt even if it subsequently fails. A post-toggle observation may already be `AlreadyCorrect`, so it must not be supplied. Never record a no-op. New accepted intent revision/domain for the SAME chain resets that chain's budget, so a latest human OFF is not blocked by an old exhausted ON; a different chain is unaffected.
- A verified different summon/incarnation resets the entire bounded collection to prevent carrying one summon budget to another. This requires **already proven immutable birth identity** and trustworthy current incarnation; the test literals are *hypothetical* and not core-verified.

## Adversarial regressions

- Alternate two spell chains, two attempts on each of ten independent book revisions (40 total valid attempts, capped 20 **per chain**); assert both chains deny attempt 21 even after alternating.
- Two-attempt same-book cap independent per chain; an accepted newer OFF after an exhausted ON receives its own budget, and does not clear another chain's exhausted attempts.
- New *verified* summon has a fresh budget.
- Fill all 32 entries and assert unknown 33rd chain `NoWrite`, with no eviction of existing chain counters.
- Preserve the inherited **76 assertions** and run strict standalone C++17 + C++20. Results must be independently verified from hosted exact-head CI before citing them.

## Explicit limitations and integration contract

- This does **not** create `AcceptedManualChoice.TrustedManualReceipt`, `TrustedBirthAtReceipt`, `TrustedCurrentBirth`, `OwnerMode::Human`, a real allowed IP rank, per-chain persistent `LatestAcceptedRevision`, packet acceptance or restored pet autocast. All remain **unproven** for production. Any attempt to wire this ledger without separately verified source trust MUST return `NoWrite`. Existing #165 v1 quarantine remains mandatory and unchanged.
- A future receiver must hold the ledger on a justified serialized/owning context; neither the standalone model nor the header establishes eight-map-thread safety for user code. All old single-budget helpers remain *single chain only*; callers must use this tracked interface or maintain a reviewed separate budget per key.
- The ledger bounds work **per accepted revision/chain per incarnation**; repeated new summons or new accepted choices can legitimately get separate budgets. It is not a time-based global rate limiter. It does not claim permanent storage across server restart; the owner-gated C2 identity/persistence decision stays closed.
- The public repository must not contain private owner SQL, NPC/item/quest/loot/IP data. No core, IP, Playerbots, N-Core, host, configs, DBC, source binaries or map thread settings are changed.
