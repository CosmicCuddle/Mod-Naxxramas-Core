# A02 P26 — Proven pet birth vs transient summon identity (isolated model review)

**Source-only DRAFT. Absolutely not wired into gameplay.** This is a review-addressing child of the actual default-OFF v1 runtime quarantine [#165](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/165) exact `0bec377725addedf0257e93765b7fd72b3a55ac9`; it changes ONLY the pre-existing unwired `HunterPetAutocastIntentFence.h`, its standalone native fixture, source-only CI and this note. The actual pet writer remains quarantined; old v1 preferences still cannot write.

## Critical independent review resolved in this pure decision model

[CS02 review of #163](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/163#issuecomment-6415199696) caught that requiring the same `SummonGeneration` or `ServerToken` would **reject the very same pet after resummon/relog**, contrary to the owner's approved policy direction A. The suggested fix was PetNumber alone. That is not sufficient: exact pinned [core `Pet.cpp:1572-1577`](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Pet/Pet.cpp#L1572-L1577) explicitly states **pet numbers are recycled**.

The new model distinguishes:

- `SameBirth`: matching `PlayerGuid + PetNumber + BirthToken`, and a **separately verified server-side durable birth binding** at choice capture AND at current apply; transient epoch/generation/server token may change. It *models* policy-A persistence after resummon/relog **only if** a genuine immutable birth identity can be proven.
- `SameIncarnation`: matching the same verified birth **AND** current `ServerEpoch + SummonGeneration + ServerToken`. Only used to bind in-flight work and retry accounting, not to bind long-term accepted manual ON/OFF.
- `RevisionDomain`: a nonzero verified counter domain must match `LatestRevisionDomain`, so a reset/reused `Revision=1` after a new login cannot impersonate a newer accepted choice. Real shared cross-thread/manual receipt producer is still missing.
- `AttemptBudget`: at most **two actual attempts per real spellbook revision**, and at most **20 attempts over all book revisions per summon+accepted intent**. An authorized newer manual OFF gets an independent budget, and resummoning the *same verified birth* gets a fresh bounded budget. This prevents infinite alternation if IP or another module keeps changing the book.

Synthetic test scenarios include: same authenticated birth new summon/new session (hypothetical positive); same PetNumber with a DIFFERENT birth token (negative); missing/unauthenticated birth; wrong player; missing ephemeral incarnation token; domain reset, older ON vs newer OFF; repeat IP book revision 1..11 with a total 20-write bound; new intent and new summon budget reset.

**Major blockers not removed by this test:**

1. `BirthToken` and `TrustedCurrentBirth`/ `TrustedBirthAtReceipt` are **fixture assumptions**, not production evidence, nor cryptographic authentication by merely comparing equal bytes. No source can mint/persist this independently across sessions today. No private DB schema, storage, root, core, pet save/replace behaviour or owner host changes are approved. Until a trustworthy lifetime record exists, fail closed for uncertain resummon/relog and all pet-number reuse.
2. The native `CMSG_PET_SPELL_AUTOCAST` candidate from the 3.3.5 client is **observed pre-stock-handler** by the available `ServerScript::CanPacketReceive` hook. It does not prove handler acceptance, human vs SelfBot, or event sequencing between `PROCESS_INPLACE` map/world and `PROCESS_THREADUNSAFE` chat/set-action. [CS02 pinned counterexamples](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/164#issuecomment-6415197470) stand. A new post-validated receipt producer, shared latest-revision counter, and positive up-to-date human mode are unresolved.
3. This model does not prove that an observed `BookRevision` corresponds to an IP rank change rather than our own write, nor provide an authoritative permitted-rank oracle or real client proof. The 20-attempt ceiling can cause missed legitimate retries; it is safer than unlimited pet writes. No hardcoded 200ms settle assumption is introduced.
4. Source CI can show the pure conditional logic runs; it **cannot show working A02**, real pet identity, a real server write, safe Playerbots concurrency or 3.3.5 in-game acceptance. Original #163, #164, #165, frozen #160 and all live owner files are unmodified.

## Native verification

```bash
g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems \
  tests/hunter_pet_autocast_intent_fence.cpp -o /tmp/a02_birth_fence17
/tmp/a02_birth_fence17
g++ -std=c++20 -Wall -Wextra -Werror -pedantic -Isrc/Systems \
  tests/hunter_pet_autocast_intent_fence.cpp -o /tmp/a02_birth_fence20
/tmp/a02_birth_fence20
```

CI's isolated exact-head job additionally pins the **five unchanged production blobs inherited from PR #165** (instead of stale #163 pins) so model-only PASS cannot hide runtime edits. No host/deployment/game proof, no merge approval.
