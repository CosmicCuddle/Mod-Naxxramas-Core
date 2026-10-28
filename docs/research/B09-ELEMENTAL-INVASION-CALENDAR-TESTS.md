# B09 P3 — Elemental Invasions calendar: deterministic tests

**Status:** DRAFT. Tests of the real `src/Events/ElementalInvasionCalendar.cpp`, plus one small logging fix that a failing test demonstrated. The feature stays **default OFF** (`NaxxramasCore.ElementalInvasion.Enabled = 0`). No SQL, DBC, config, core, Playerbots or Individual Progression change. Not tested in game.

## How the real source is tested

`tests/elemental_invasion_calendar_tests.cpp` `#include`s the production `.cpp` **unmodified** and compiles it against the four small stubs in `tests/b09_stubs/` (Config, GameEventMgr, Log, ScriptMgr). The stubs match the signatures at Grimfeather `8daffda`.

Determinism comes from three controls:
- **Clock:** `-Wl,--wrap=time` replaces the source's `std::time(nullptr)`.
- **Timezone:** `TZ` + `tzset()`.
- **tzdata check:** the test proves tzdata is present, so DST cases cannot silently run as UTC.

The pinned Worldserver link (core `8daffda`, Playerbots `d750b4b`, IP `dd96f2b`) separately proves that the real file still builds.

## Covered (267,904 checks)

- **Window:** `[1st H:M, (1+D)th H:M)`, start inclusive and end exclusive.
  - Every month of 2023–2030, for start times 00:00, 13:30 and 23:59, and for every duration 1–27: the begin and end boundaries ±1 s, plus every day of the month.
  - Year boundary.
  - Leap years 2028 and 2000; non-leap 2027 and 2100.
  - The 1st before the start time is inactive, and no previous-month window leaks into it.
- **DST:**
  - The window ends at **local** midnight across New York spring/fall and London autumn transitions.
  - Start time inside a DST gap on the 1st (Asuncion 00:00, Sydney 02:30, Lord Howe 30-minute 02:15): starts once on the 1st, at or after the transition, never in the previous month, and ends exactly.
  - Start time in a DST overlap (Sydney 02:30, Lord Howe 01:45): starts once on a valid occurrence and ends exactly.
- **Config:**
  - Defaults when settings are absent: OFF, 00:00, 5 days.
  - Clamps: Hour 24 / UINT32_MAX → 23; Minute 60 → 59; Duration 0 → 1; Duration 28 / UINT32_MAX → 27.
  - `.reload config` re-reads. Core reloads the file **before** `OnBeforeConfigLoad` (`World.cpp` L174 → L187), so the new values are not stale.
- **Event 13, failing closed:**
  - **Disabled:** no event-manager, clock or log call at all.
  - **Missing row** (size 0 or 13), or **event 13 not `GAMEEVENT_INTERNAL`** (all five other states): never starts or stops it, even a running stock event, and reports once.
  - **Normal operation:**
    - starts exactly at the boundary and never repeats;
    - stops exactly at the end;
    - a restart inside the window resumes, and a restart outside it stops a stale run.
  - **Start failure:** retries every minute and reports once; a later failure is reported again.
  - **Check interval:** the first tick syncs, then every 60.000 s; a 10-minute hitch syncs once; `OnStartup` resets the timer.
  - **Uncomputable time:** never starts or stops event 13; control resumes once the clock recovers.

## Defect found and fixed

**Shared error latch.** When the calendar window could not be computed, the code reused `_reportedSetupError`, which the setup check resets just before on every tick. Two effects on main `80e9de1`:
1. "Could not calculate the local Elemental Invasions calendar window" was logged **every minute** instead of once.
2. After such an error, a later "event 13 is not `GAMEEVENT_INTERNAL`" setup error was **suppressed**.

The fix adds a separate `_reportedWindowError` latch, reset on success and in `OnStartup`. Scheduling, starts and stops are unchanged. On the unfixed main source, exactly the three latch checks fail; CI asserts this.

Both effects only matter when `localtime_r` or `mktime` fails, which needs an extreme clock or a broken timezone. Severity is low.

## Not found

No scheduling defect: month lengths, leap years, year rollover, DST and boundaries all behave as documented. Behaviour inside a DST gap or overlap is implementation-defined in `mktime` (glibc: a gap shifts forward by the DST amount, and an overlap picks a valid occurrence). The tests assert properties rather than one libc's choice wherever that matters.

## Noted, not changed

- Disabling the feature with `.reload config` while event 13 is running leaves it running until restart. This is the documented "never touches event 13 when disabled" behaviour.
- Boundary latency is up to 60 s, as documented.
