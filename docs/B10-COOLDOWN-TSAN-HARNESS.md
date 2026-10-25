# B10 #120 — production-text TSAN harness for the consumables cooldown (test-only)

**Status:** test-only child of review-only #120 at exact `599d1cbb211e6f108a2a6ff9fec78242ffe7a37c`, approved by CS01 in #48 `6401348099`. **DO NOT MERGE.** It changes no runtime file, and CI enforces that (`git diff --quiet 599d1cb HEAD -- src conf`, plus a five-path allow-list).

## What it tests

The #114 fix in #120 keeps command cooldowns in one shared map, `ConsumableCooldownUntil`, guarded by `ConsumableCooldownLock`. A death on one map clears the cooldowns of group members who may be on other maps, so the map is shared across `MapUpdate.Threads` workers. #120's other new state is covered elsewhere:
- per-player state lives in `CustomData`;
- the cross-map aura queue already has its own native and TSAN test (`tests/crossmap_aura_queue.cpp`).

This harness covers only the cooldown path.

## How it uses the real code

- **Verbatim extraction.** `scripts/extract_b10_cooldown_harness.py` copies, byte for byte from `src/Systems/BotRaidConsumables.cpp`:
  - the mutex and map declarations;
  - `GetConsumableCooldownRemaining`, `StartConsumableCooldown` and `ResetConsumableCooldownForGroup`.

  It checks their combined SHA-256 (`535574bb…`) against the reviewed #120 head, then splices them **unchanged** into `tests/b10_cooldown_tsan_driver.cpp`. The driver stubs only what that code needs: `Player`, `Group`, `GroupReference`, `ObjectGuid::LowType`, the cooldown constant and a test clock.
- **No substitute implementation.** If the production text changes, the build fails (exit 3) and the harness must be re-reviewed. The contract tests prove this: removing one production `lock_guard`, or changing a function body, is refused.
- **Negative control.** The same extracted text with its three `lock_guard` statements removed. ThreadSanitizer must report `data race` inside one of the three production functions. The CI step disables `bash -e` around that run so the diagnostic is **captured and checked**, not lost (the #156 lesson).

## Results (local, at this head)

| Check | Result |
|---|---|
| Contract tests (`tests/test_b10_cooldown_harness.py`) | 6/6 OK |
| Extracted production text, C++17 and C++20, `-Werror`: semantics (600 s, expiry removed on read, group reset clears members, non-member kept, solo reset) and 8 threads × 20,000 iterations over 64 players in 16 groups | PASS |
| Same, `-fsanitize=thread` | clean, exit 0 |
| Negative control (locks removed), `-fsanitize=thread` | `WARNING: ThreadSanitizer: data race`, exit 66, frame `StartConsumableCooldown` |

## Limits

- `Player` and `Group` are stubs. This does **not** prove that walking group membership is safe while membership changes on another thread (an older, separate hazard), or `Player::CustomData` thread affinity.
- It says nothing about a running Worldserver or the owner's 8-thread server.
- No GFPP, aura, config or gameplay behaviour is involved, and #120's runtime code and GFPP 120 s are unchanged.
