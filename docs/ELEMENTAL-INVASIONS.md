# Monthly Elemental Invasions

## Behaviour

The original AzerothCore **Elemental Invasions game event 13** runs on a true
calendar schedule rather than a fixed `occurence` minute interval.

- Begins on **the 1st day of every calendar month**, at the configured **worldserver local time**.
- Remains active for **five calendar days** by default.
- Ends on **the 6th day** at the same clock time (the end time is exclusive).
- After a restart, a running invasion resumes automatically if the current
  date/time is within the active window; otherwise event 13 is stopped.
- Checks once a minute while enabled. At the exact boundary the event may be
  started or stopped up to 60 seconds after the configured clock time.
- Does not reset other game events or modify Elemental Invasions mobs, quests,
  gameobjects, loot or scripts.

## Why the `world_event=5` change is required

Normal game events use `start_time`, `end_time`, `occurence` and
`length`. Their `occurence` is a **fixed number of minutes**. Months do not
have a constant number of minutes.

When the original event is marked `GAMEEVENT_INTERNAL` (5), AzerothCore
does not automatically end it according to its old minute-based schedule.
The custom WorldScript uses AzerothCore's public `StartInternalEvent` and
`StopEvent` APIs on event 13 at calendar boundaries. This is the same
internal-event mechanism already supported by the core.

The SQL update only changes `game_event.world_event` for event 13. Its
existing `occurence` and `length` are preserved, as are all other rows.

## Installation — backup first

1. In HeidiSQL, select your **world** database (often `acore_world`).
2. Export the **entire original row** from `game_event` for
   `eventEntry = 13` to a dated SQL backup outside the repo. You can inspect it
   first:

   ```sql
   SELECT * FROM `game_event` WHERE `eventEntry` = 13;
   ```

3. Back up your currently working module and active
   `mod_naxxramas_core.conf`.
4. Apply `data/sql/db-world/2026_10_09_00_monthly_elemental_invasions.sql`
   to the **world** database, unless the module updater has already applied it.
   It only changes the stock row if event 13 is currently the normal
   `Elemental Invasions` event.
5. Verify the state before enabling:

   ```sql
   SELECT `eventEntry`, `description`, `world_event`,
          `occurence`, `length`
   FROM `game_event`
   WHERE `eventEntry` = 13;
   ```

   The `world_event` value must be **5**. If it is not, do not enable the
   scheduler: review your custom event row or existing event module first.

6. Recompile AzerothCore with the updated module. Update the **active**
   configuration file:

   ```ini
   NaxxramasCore.ElementalInvasion.Enabled = 1
   NaxxramasCore.ElementalInvasion.Hour = 0
   NaxxramasCore.ElementalInvasion.Minute = 0
   NaxxramasCore.ElementalInvasion.DurationDays = 5
   ```

7. Restart worldserver. The database state is read during worldserver
   startup; changing it while the server is running is not sufficient.

## Notes about clocks and the website

The module uses the **operating system's local timezone on worldserver**.
Its calendar windows are calculated with `mktime`, accounting for varying
month lengths and local daylight-saving transitions.

Set the Resource Hub's Elemental Invasions countdown to the same time and
timezone. The website currently has a fixed `Etc/GMT-2` timezone setting:
this is **always UTC+02:00**, even in winter. If the server uses a
daylight-saving IANA timezone (for example Europe/Berlin), change the website
timezone to match before relying on the displayed countdown.

The website is informational. The game server is authoritative for whether
mobs and event content are active.

## Validation

- **Outside the monthly window** (for example 9 October 2026), event 13
  should remain inactive. The next start is 1 November 2026.
- **Inside the window** (for example 3 November 2026), event 13 must be
  active; restarting worldserver in this window should restore the event.
- **On the 6th** at the configured clock time, event 13 must stop; any active
  game-event spawns should despawn normally.
- Check an Elemental Invasions location for the original NPCs and behaviour.
- Check that other events (including Brewfest, Darkmoon Faire and Battleground
  Call to Arms) remain unchanged.
- Do not change the production server clock to test this. For a manual spawn
  check, temporarily disable this controller in config, restart the server,
  use the normal GM `.event start 13` / `.event stop 13` commands, then
  restore the configuration and restart.
- If the SQL prerequisite is missing or the event is disabled by another
  system, the module logs an error instead of overriding another event.

## Rollback / uninstall

1. Change `NaxxramasCore.ElementalInvasion.Enabled = 0` in the active
   configuration, then **stop worldserver**.
2. Restore the backed-up `game_event` row for event 13. If your original
   `world_event` was **0** and this migration only changed it to **5**, the
   following targeted rollback is sufficient:

   ```sql
   UPDATE `game_event` SET `world_event` = 0
   WHERE `eventEntry` = 13 AND `world_event` = 5;
   ```

3. Restore the prior module version or keep the new controller disabled.
   Rebuild only if reverting module code, then restart worldserver.
4. The original game's `occurence`, `length`, start/end dates, creatures,
   loot, quests and all other events were not changed by this migration.

**Caution:** Switching the config off without restoring the database row will
leave event 13 internally controlled (and therefore unscheduled). Restore
both the config and world-event state during a complete rollback.
