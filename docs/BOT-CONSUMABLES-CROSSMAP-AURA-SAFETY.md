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
The GFPP one-shot already compares `Map` pointers and is unchanged.

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
- **Stale-work gate:** each `{bot, spell, isPet}` has a generation number.
  The module bumps it whenever it applies or takes ownership of that aura:
  `AddTrackedAura`, the initial Juju Flurry, a timed refresh, or the GFPP
  one-shot refresh. A queued removal remembers the generation it saw, and
  the drain skips it if the generation has moved on. A delayed removal
  therefore never strips a newer module application.

With the flag at 0, generations are not recorded, nothing is queued, and
every path behaves exactly as before. The drain always runs, so removals
queued before a config reload that turned the flag off still happen.

## Known limits

- **Pet swap:** a queued pet removal applies to the bot's pet at drain
  time. If the bot summoned a different pet in between and the module did
  not buff it, that pet loses the same spell's aura. Today the original pet
  would have lost it. The module re-buffing the new pet cancels the
  removal.
- **Other sources:** an aura applied by something other than this module
  between the queue and the drain is removed, just as the immediate removal
  would remove it today.
- **Timing:** removal normally happens in the same world tick. No strict
  bound is claimed.
- **Group walk:** the walk in `ResetConsumableCooldownForGroup` is out of
  scope (see #114).
- **Not tested:** build and link prove compilation only. Runtime behaviour
  at `MapUpdate.Threads = 8`, the owner's Playerbots `e88cc409` with local
  edits, and gameplay are **NOT TESTED**.

## Tests

- `tests/crossmap_aura_queue.cpp` — native queue tests (C++17, C++20 and
  ThreadSanitizer). They cover once-only drain, the stale gate, per-spell
  and pet keys, a missing bot, re-entrant enqueue, concurrent producers,
  and CS01's mandatory case: the leader teleports while the bot keeps a
  tracked buff, a pet buff and a timed Juju Flurry, and a newer Juju
  survives.
- `tests/test_crossmap_aura_safety.py` — source contract: default OFF,
  OFF parity, both vectors deferred before any dereference, world-thread
  drain, generation bumps and lock discipline.
- `.github/workflows/crossmap-aura-safety.yml` — the above, plus a pinned
  full Worldserver link and symbol check.

Rollback: leave the flag at 0 (the default).
