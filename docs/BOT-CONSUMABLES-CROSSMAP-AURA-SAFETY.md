# Bot consumables: cross-map aura safety (#114 follow-up)

**Status:** review draft. Default **OFF**. Not installed, not tested in game.

## Problem

`.bot consumables` keeps a tracker for the leader. Each update of the
leader runs on the leader's **map thread**. With `MapUpdate.Threads > 1`,
a prepared bot can be on a different map that another thread is updating
at the same moment. Three map-thread paths touch that bot's auras:

| Path | Today | Risk |
|---|---|---|
| `CheckTrackedAuras` (missing-buff warning) | `HasAura` on the bot or pet | read race |
| `ProcessTimedAuras` (Juju Flurry refresh) | `HasAura` + `AddAura`, gated by map **ID** only | write race (rare: same map ID, other instance) |
| Leaving the profile's instance → `ClearTrackedAuras` (both `tracker.Auras` and `tracker.TimedAuras`) | `RemoveAurasDueToSpell` | write race (realistic: leader hearths out, bots still inside) |

Command paths (`.bot consumables <profile>`, `status`, `clear`) run on the
world thread, which never overlaps the map threads, and are unchanged.
The GFPP one-shot compared `Map` pointers, but only after reading the bot (`IsInWorld`, `IsAlive`); with the flag on it now also proves same-map membership first (CS02 review).

## Change (only when `NaxxramasCore.BotConsumables.CrossMapAuraSafety = 1`)

- **Same-map test:** a bot counts as "on the leader's map" only if it is
  in the leader's own `Map` player list. This is a pointer comparison and
  never dereferences an off-map bot.
- **Checks:** off-map bots are skipped. No warning is sent and the
  "already warned" state is left as is, so the warning resumes when the
  bot is back.
- **Timed refresh:** an off-map bot counts as temporarily unavailable,
  which is the existing 5-second retry with no use consumed.
- **Leaving the instance:** same-map bots lose their auras immediately, as
  today. For off-map bots, `{bot, spell, isPet}` is queued for **both**
  `tracker.Auras` and `tracker.TimedAuras`.
- **Drain:** `WorldScript::OnUpdate` runs on the world thread.
  `World::Update` calls it after `MapMgr::Update`, which waits for every
  map worker (Grimfeather `8daffda`: `World.cpp` L1254/L1355,
  `MapMgr.cpp` `m_updater.wait()`). It:
  - resolves each bot by GUID (`ObjectAccessor::FindPlayerByLowGUID`), not
    through the leader, who may have logged out;
  - takes the pet when the entry is a pet aura;
  - removes the aura.

  A missing bot or pet is skipped. The queue lock is never held during
  these calls.
- **Stale-work gate:** each `{bot, spell, isPet}` has a generation
  number.
  - **Bump:** the module bumps it **before** it applies or takes ownership
    of that aura — at the top of `ApplyTrackedAura` (both the preserve and
    the re-apply path), before the initial Juju Flurry, before a timed
    refresh, and before the GFPP one-shot refresh.
  - **Check:** a queued removal remembers the generation it saw. The drain
    checks it and marks the key "being removed" in one critical section,
    then removes outside the lock.
  - **Wait:** `NoteApplied` for that exact key waits until the removal is
    done; other keys are never blocked.
  - **Result:** every module application either is seen by the check (the
    removal is skipped) or lands after the removal (the new aura
    survives). This closes the check-then-remove window that CS01 found in
    review 6382682125.
  - **Robustness:** the remover never calls `NoteApplied` for the key it
    is removing (`RemoveAurasDueToSpell` does not call module code). An
    exception in the remover still clears the mark.

### Bounded memory (CS01 #118 6383075641)

- **Stamps, not counters:** generations are stamps from one process-wide
  counter that only increases (`_lastStamp`). A stamp is never reused,
  and 0 means "never noted".
- **Retirement:** at the end of every drain, every key that no queued
  removal refers to is retired. A key a queued removal still refers to is
  kept until that removal is drained.
- **Bound:** between drains, the map holds at most the keys noted since
  the last drain plus the keys of queued removals. The drain runs every
  world tick, so this is a per-tick quantity, not a lifetime one.
- **No ABA, twice over:**
  - a key is never retired while a queued removal can compare against it;
  - a retired key that is noted again gets a fresh, larger stamp, which
    can never equal an older queued stamp or 0.
- **Tests:** native tests cover 10,000 keys retired to 0; a referenced key
  kept and still cancelled correctly; and re-login reuse of the same
  GUID and spell, with and without retirement, over 1,000 cycles.
- **Negative controls (identical test source):**
  - no retirement → growth caught (4 failures);
  - blind erase with per-key counters → the stale removal is accepted
    (ABA caught);
  - blind erase with stamps → a queued removal is lost (caught).

### Why no other thread races the drain (pinned sources)

- **World loop** (`World.cpp` at core `8daffda`):
  - L1227 `UpdateSessions` runs `PROCESS_THREADUNSAFE` opcodes, including
    `CMSG_MESSAGECHAT` (`Opcodes.cpp` L280), so `.bot consumables` runs on
    the world thread;
  - L1254 `MapMgr::Update` schedules every map and calls `m_updater.wait()`;
  - L1355 `OnWorldUpdate` runs the drain.

  The world thread is single-threaded, so nothing else runs during the
  drain. The new wait is a second line of defence, not the only one.
- **Bot map changes** (Playerbots `e88cc409`): the worldport
  acknowledgement (`PlayerbotHolder::UpdateSessions` →
  `HandleTeleportAck` → `HandleMoveWorldportAck`) runs from
  `SessionScript::OnSessionUpdate` and `WorldScript::OnUpdate`, both on the
  world thread. A bot is therefore only added to a `Map`'s player list from
  the world thread.
- **Player-list iteration:** `IsPlayerOnMap` iterates the **leader's own**
  map list on that map's own thread, where it cannot change concurrently.
- **Drain lookups:** `ObjectAccessor::FindPlayerByLowGUID` returns only
  in-world players, and logout and deletion happen in `UpdateSessions`
  earlier in the same world loop, so the pointer is valid for the drain.
  `GetPet()` resolves the bot's *current* pet.

With the flag at 0, generations are not recorded, nothing is queued, and
every path behaves exactly as before. The drain always runs, so removals
queued before a config reload that turned the flag off still happen.

## Known limits

- **Pets:** pet identity is pinned when the aura is applied.
  - **What is recorded:** `ApplyTrackedAura` stores the receiving unit's
    GUID (`TrackedAura::TargetGuidRaw`), on the thread that applied it.
  - **At drain time:** a queued pet removal goes ahead only if
    `bot->GetPet()` is that exact pet.
  - **New pets:** a new or re-summoned pet gets a new GUID
    (`Map::GenerateLowGuid<HighGuid::Pet>`) and is left alone. Its aura,
    if it still has one, expires on its own. Today's immediate removal
    would have hit the pet present at that moment; at worst, deferral
    leaves a re-summoned pet's buff to time out.
  - **Same-map safety:** `Player::GetPet()` resolves only through the
    owner's own map (`ObjectAccessor::GetPet` → `GetMap()->GetPet`). So
    once the bot is confirmed on the leader's map, a pet it returns is on
    that map too. Map-thread `HasAura` and `RemoveAurasDueToSpell` on that
    pet stay on that map's thread.
- **Same-map pet clear:** the immediate (same-map) clear removes the aura
  from the bot's current pet without a GUID check, as before. It runs on
  that map's own thread, so it is not a race. Only queued removals check
  the pet GUID.
- **Remover exceptions:** if the remover threw, the rest of that drain
  batch would be dropped. The production remover does not throw.
- **Other sources:** an aura applied by something other than this module
  between the queue and the drain is removed, just as the immediate removal
  would remove it today.
- **Timing:** removal normally happens in the same world tick. No strict
  bound is claimed.
- **Wait cost:** a map worker re-applying the exact aura that the world
  thread is removing waits for that one removal. By the ordering above,
  this does not happen in practice.
- **Group walk:** the walk in `ResetConsumableCooldownForGroup` is out of
  scope (see #114).
- **Not tested:** build and link prove compilation only. Runtime behaviour
  at `MapUpdate.Threads = 8`, the owner's Playerbots `e88cc409` with local
  edits, and gameplay are **NOT TESTED**.

## Tests

- `tests/crossmap_aura_queue.cpp` — native queue tests (C++17, C++20 and
  ThreadSanitizer). They cover:
  - once-only drain, the stale gate, per-spell and pet keys, a missing
    bot, re-entrant enqueue and concurrent producers;
  - CS01's mandatory case: the leader teleports while the bot keeps a
    tracked buff, a pet buff and a timed Juju Flurry, and a newer Juju
    survives;
  - CS01's review interleaving: the check passes, the same aura is
    re-applied mid-removal, and the re-application waits and survives;
    other keys are not blocked; a remover exception clears the mark.
    Against the previous queue, the interleaving checks fail.
- `tests/test_crossmap_aura_safety.py` — source contract: default OFF,
  OFF parity, both vectors deferred before any dereference, world-thread
  drain, generation bumps and lock discipline.
- `.github/workflows/crossmap-aura-safety.yml` — the above, plus a pinned
  full Worldserver link and symbol check.

Rollback: leave the flag at 0 (the default).
