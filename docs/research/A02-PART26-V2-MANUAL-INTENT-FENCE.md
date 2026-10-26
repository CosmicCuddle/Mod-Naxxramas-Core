# A02 Part 26: test-first v2 manual-intent fence (NOT INTEGRATED)

**Status: isolated DRAFT code/review only; zero gameplay effect.** This child branch of #135 adds one dependency-free C++ header plus one native test file. It does **not** modify `HunterPetAutocast.cpp`, `HunterPetAutocastAddon.h`, the module loader, configuration, Playerbots, IP, core, N-Core, client, SQL or DBC. Both A02 switches stay OFF. No merge or deployment is authorised.

## Problem this narrowly addresses

PR #134 v1 keeps preferences per player, not per verified pet instance. It can apply an older pet's choice to the current pet and may replay a stale ON after the player's new OFF has not been reliably captured. PR #135 proposes v2 `server epoch + pet number + summon generation + token`, but its model tests are not a real server receiver. Individual Progression can repeat a delayed rank reconcile after a one-time restoration. Owner policy: **IP chooses the rank; the latest accepted human ON/OFF follows that allowed rank; A02 never learns or re-ranks.**

`HunterPetAutocastIntentFence.h` is an optional, **unwired** final decision seam for a future reviewed v2 server receiver. It refuses to return an apply action unless all required evidence is provided by authenticated, reviewed upstream integrations: identity tuple is complete and matches; receipt is newest and accepted manually; session transport/opt-in and owner human-mode are verified; no unresolved newer click is pending; current pet and legal existing spell match the chain; spellbook agrees; bounded retry has not been exhausted. It emits **only a decision**, never a toggle. No external caller currently supplies these facts.

The tiny `AttemptBudget` tracks at most two attempts **per actual post-reconcile book-revision identity**, stored by a future caller per pet on a map worker. It does not use a fixed 200ms delay; it does not prove IP emitted a completion signal; it never claims an attempted write succeeded. A future integration must assign monotonic revisions ONLY for independently observed relevant book transitions, track revisions across summons and pet-lifetime changes, and fail closed when transitions cannot be classified. Bounded retries may leave a legitimate preference unrestored and must be made visible in diagnostics after authenticated end-to-end evidence.

## Reproducible source-only compilation

```bash
g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems \
  tests/hunter_pet_autocast_intent_fence.cpp -o /tmp/a02_intent_fence
/tmp/a02_intent_fence
g++ -std=c++20 -Wall -Wextra -Werror -pedantic -Isrc/Systems \
  tests/hunter_pet_autocast_intent_fence.cpp -o /tmp/a02_intent_fence20
/tmp/a02_intent_fence20
```

Run only in a disposable development environment. No Worldserver process, player, pet, DB or DBC is involved. Passing assertions prove *only this standalone conditional decision function*.

## Blocking integration questions — must not be silently assumed

1. Prove the pinned 3.3.5a client actually receives a server-authored v2 hello as Lua, returns valid token/epoch in the bounded wire message, and that it cannot be confused by pet A→B→A or recycled PetNumber. Validate server-authoritative pet identity and login/logout token retirement.
2. Resolve N-Core real Lua 5.1 W1 first-click *before* initial snapshot, off-bar pet-book ON/OFF and stale old-pet queue. Until then the client cannot establish a latest accepted manual action. Its relay remains default OFF in the isolated research branch.
3. Obtain a race-safe, **positive** current-human / not-SelfBot result without unsafely reading Playerbots' mutable AI map on eight map threads. `SelfBotLevel=0` is not itself per-player mode proof. Keep all unknown states closed.
4. Find an actual post-IP observed book revision and legal allowed rank without treating a modelled 200ms timer as IP completion, changing IP, learning missing spells or overriding new manual OFF.
5. Require source review, native/hosted integrated Worldserver compilation and separate owner consent for backed-up staging/in-game tests. Keep existing source-build success #160 frozen; its assembly does not contain functional A02/A04 acceptance.

**Evidence:** C++ native fixture with expected TRUE and fail-closed negative cases, not real trust attestation, race test, IP game timing, or functional integration. No source test green is a release sign-off.
