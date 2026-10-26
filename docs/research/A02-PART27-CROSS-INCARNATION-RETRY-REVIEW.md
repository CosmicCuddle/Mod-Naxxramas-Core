# A02 Part 27 — cross-incarnation retry ceiling, isolated model

**DRAFT / SOURCE-ONLY TEST MODEL / NOT WIRED / NO OWNER SERVER, DB, CORE, IP OR PLAYERBOTS CHANGES.**

This is **one optional source-design alternative**, not the owner's approval of a new retry policy. It is a small stacked child of [A02 #169](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/169), preserving that PR's production blob pins, fixed 32-chain per-summon ledger and 224 original assertions. C1 owner direction remains **MODULE ONLY**, with candidate-only post-state observations and no claim of native accepted human commands. C2 owner direction remains a **NEW restart-persistent table** with separate SQL/backup/rollback approval; this prototype does not create a table.

## New verified hazard from CS03's #169 re-review

[CS03 review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/169#issuecomment-6419605947) demonstrates that the existing per-incarnation 20-attempt ceiling can be reset each time a fresh Pet object appears. The pinned public AzerothCore temporarily unsummons/resummons pets around mount/dismount and far teleports. Thus **10 object incarnations × 20 potential attempts = 200 potential attempts** for one choice even if no new human action occurred. This is a *synthetic source-bound possibility*, not a claim that the owner's server performed 200 actual autocast toggles.

## Independent model

`HunterPetAutocastLifetimeBudgetModel.h` adds a caller-owned, fixed-size **32-key** `Ledger` for the entire logical lifetime of a choice, keyed by:
- authenticated owner identity;
- **hypothetically server-verified durable pet birth** and pet-number hint (NOT name);
- spell chain;
- latest accepted revision and revision domain **inside** each key.

`DecideWithLifetime` first invokes the existing #169 `DecideTracked` with all mandatory trust inputs. Even a candidate whose later snapshot matches **cannot** pass if `TrustedManualReceipt` or `TrustedCurrentBirth` remains false. Next, independently enforce **at most 20 attempts for a particular (verified birth, spell chain, latest accepted revision)** across repeated summon generations and book revisions.

`ReserveWithLifetime` counts **immediately before attempting a toggle** from the same immutable pre-attempt observation on one reviewed serialized owner context. Failed toggles stay counted. It does NOT execute a spell toggle. Newer valid OFF for the same chain gets a fresh choice budget while stale ON is rejected by the inherited revision check. Another spell chain has its own counter, and a **new certified birth** with recycled PetNumber does not inherit the old pet's counter. When all 32 keys are occupied, unknown 33rd key is **NoWrite** (never evict or silently reset). This is an intentionally conservative finite ledger; capacity policy is NOT production-approved.

## Adversarial C++17/C++20 offline tests

The test supplies **fabricated** trustworthy birth and accepted-human fields to explore the conditional policy only. It asserts:
- ten ephemeral incarnations of the same hypothetical birth, with two failed attempts each, accumulate 20 total; the fixture **changes its synthetic IP-allowed rank ID each time while keeping one stable spell-chain key**, so a rank switch cannot replenish the lifetime budget; incarnation 11 is denied even though the old per-incarnation ledger alone would permit another attempt;
- independent Claw/Bite spell-chain allowances and newest accepted OFF vs stale ON;
- recycled PetNumber with a changed certified birth never receives the old choice;
- missing birth trust, missing genuine manual receipt and attached bot mode never permit writing;
- a full 32-key ledger is not bypassed by changing incarnation, but a newer valid revision on an existing key can use a fresh budget;
- an **entirely new in-memory ledger after server restart** permits a fresh 20, **demonstrating why this is not a restart-durable safety guarantee**.

The existing #169 source model and runtime files are unchanged by this child PR. The new workflow compiles the isolated source under strict C++17 and C++20, verifies the original #169 model blob and production module/config blob IDs, and asserts the source does not include real game/server headers. **These tests cannot prove any in-game functionality.**

## CS02 peer follow-up — per-owner isolation and bounded-key liveness

[CS02 review of #172](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/172#issuecomment-6426066110) confirmed the source-model tests and identified two risks. This later source-only revision addresses **owner misuse safety** and records the **unresolved capacity lifecycle**.

- The model's `Ledger.OwnerGuid` starts unbound, is bound only by a successfully reserved hypothetical trusted choice, and thereafter rejects another player's choice with `NoWrite`. The new fixture verifies that a second player needs their own ledger. **This is not thread synchronization**: the real owner context must be per-player, serialized and retained across that player's pet object recreation; no process-global map or mutex is implemented here.
- The 32-key bounded lifetime collection **does not reclaim slots** on `AlreadyCorrect`, a pet temporarily disappearing, or a change of spell rank. Those are **not irreversible retirement proofs**. A source-only regression verifies that when an apparently correct state is independently changed again later, an already exhausted choice **remains exhausted**. Releasing at `AlreadyCorrect` would make the retry cap reset under IP/AI flapping.
- **Liveness remains intentionally blocked when full**: 32 ever-used (verified birth, chain) keys under one player eventually refuse an unknown 33rd key until a separately authorized lifecycle disposition is implemented. A future `RetireVerifiedBirth` concept would need trustworthy *canonical deletion/retirement*, proof no in-flight choices or callbacks can revive the old birth, plus safe concurrent handoff. Pinned public `Pet::SavePetToDB` broad slot deletion and character deletion can remove canonical rows without invoking each pet's `DeleteFromDB`; a single Pet hook is not sufficient. Do NOT add an untrusted reclaim/eviction method or call this capacity policy production-ready.
- Repeat clicks on the SAME birth + chain use the existing slot and replace its revision/attempt count; a new rank within the chain does not consume a new slot. This fact does **not** remove the possibility of exhausting all 32 keys over a player's longer lifetime.
- This prototype deliberately has no stable session owner, real birth certification, C1 causal accepted-human source, C2 durable restart store, C3 positive SelfBot proof or production atomic registration. Every claimed trust input remains synthetic and `NoWrite` is the only defensible operational outcome now.

## Integration and owner approval still blocked

- The owner-directed **module-only** C1 can observe a matching state after a native packet, but *cannot causally prove native acceptance*. `CandidateMatched` remains diagnostic, not `TrustedManualReceipt`. No automatic restore.
- C2 pet-number+player sidecar persistence cannot itself certify birth. The pinned core can recycle numbers and saves the canonical pet row in an asynchronously queued transaction. The real worker count and potential cross-queue ordering are not observed. Even a successful sidecar transaction callback would attest the sidecar only.
- C3 needs a real, thread-safe **positive** human-mode check including attached SelfBot transition races. In this fixture all such bits are fabricated and the source includes no Playerbots calls. Preserve eight map threads.
- An in-memory cross-incarnation ledger loses its counts on process restart. A safe operational policy would require a reviewed per-choice durable count or no automatic writes when continuity cannot be proven, and race-safe revision issuance.
- Owner C4 staging acceptance, backups, in-game tests and separate merge/install approval have not been granted.

**Decision requested later (not presumed):** should a verified choice's retry budget have an additional across-incarnation limit, and if so should it survive restart? That decision requires trusted birth and latest revision sources first. Leave #165's v1 protection and both feature flags OFF.
