# F12 — Scarlet Monastery Cathedral/Armory exits: functional fix design (S1)

**Stage:** S1 design and synthetic tests only. **No C++, config key, SQL,
DBC or server change.** Builds on CS01's synthetic route model (#119,
`fa822f0`) without changing it. C++ needs CS01's go-ahead after review.

**Pins:** Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`,
Individual Progression `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61`, this
module `main` `80e9de1`. External reference data (read only):
MaNGOS Zero `database` `325948a78015794e6cc626212bc19fee70c805b2`
(`World/Setup/FullDB/areatrigger_teleport.sql`) and cMaNGOS `classic-db`
`4e3d118b915924a5caae86f9380baedca22b9c09`
(`Full_DB/ClassicDB_1_12_1_z2815.sql.gz`). The owner's loaded database is
**UNKNOWN**.

**Goal (#28 F12):** leaving the Cathedral or the Armory should put the
player just behind that wing's own entrance door outside.

**Era scope (decision for CS01):** the switch applies to **every IP stage**.
F12 corrects where an exit lands; it is not an era restriction like F13.
The Graveyard and Library exits already land behind their doors in every
era, and the Cathedral/Armory geometry does not change with progression.
No era helper is used. If CS01 prefers Vanilla-only, the F13 shared helper
can gate step 4; the matrix covers both (S22).

## 1. Two independent causes

### Cause A — the baseline exit rows for 604/606 are unlike the other wings

All four SM exits teleport to map 0. Measured against each wing's outdoor
entrance trigger (`areatrigger.sql` L45/L130–L132), with
`tests/test_f12_scarlet_exit_functional_model.py`:

| Exit | AzerothCore baseline (`areatrigger_teleport.sql` L71–74) | Distance to own door / radius | Facing vs "away from door" |
|---|---|---|---|
| 602 Graveyard | `(2913.92, -802.404, 160.333, 3.504)` | 11.3 / 8 | 0° off |
| 608 Library | `(2870.9, -820.164, 160.333, 0.388)` | 12.3 / 8 | 1° off |
| **604 Cathedral** | `(2906.14, -813.772, 160.333, 1.957)` | **20.3** / 8 | **48° off** (faces 132° from the door) |
| **606 Armory** | `(2884.45, -822.01, 160.333, 1.953)` | **18.6** / 6 | **42° off** (faces 138° from the door) |

Graveyard and Library follow the normal "just stepped out of the door,
facing away" pattern. Cathedral and Armory do not; both share an almost
identical facing (~112°). MaNGOS One/Two (TBC/WotLK) carry the same rows as
AzerothCore.

**Vanilla-core rows** (MaNGOS Zero and cMaNGOS classic, identical values):

| Exit | Vanilla-core row | Distance to own door / radius | Facing |
|---|---|---|---|
| 602 | `(2915.34, -801.58, 160.333, 3.49066)` | 9.7 / 8 | away (1° off) |
| 608 | `(2869.32, -820.818, 160.333, 0.349066)` | 10.6 / 8 | away (3° off) |
| **604** | `(2915.13, -823.637, 160.327, 3.49066)` | **10.6** / 8 | **away (3° off)** |
| **606** | `(2885.96, -835.802, 160.327, 0.349066)` | **9.1** / 6 | **away (3° off)** |

In those cores all four exits follow the same pattern, and each landing is
nearest its own door, outside every entrance radius. **Caveat:** both come
from the MaNGOS lineage (not independent of each other) and are not
Blizzard data. The landing height, walls and line of sight are **not
verified in game**.

### Cause B — Dungeon Finder groups never use the rows

`MiscHandler.cpp` L800–807: for a cross-map exit by an LFG group member
inside a dungeon, `TeleportToEntryPoint()` runs first. It goes to the
stored join position (the queue spot, or the nearest graveyard if queued
from inside a dungeon) or homebind, and clears it on first use
(`Player.cpp` L1648–1663, L11471–11506; `LFGMgr.cpp` L2291–2294). So a
second exit in the same run goes home. Fixing the rows alone cannot change
this path.

Which cause the owner hit is **UNKNOWN** (normal party vs Dungeon Finder).
The design handles both, each behind its own switch.

## 2. Module-owned seam (source-verified)

- **Not usable:**
  - `ALEScript::CanAreaTrigger` — returning true makes
    `ScriptMgr::OnAreaTrigger` return **false**, so the handler continues
    (`AreaTriggerScript.cpp` L29–37). It cannot stop the teleport.
  - Per-trigger `AreaTriggerScript` — needs an `areatrigger_scripts` row
    (`ObjectMgr.cpp` L7111–7142). That is SQL.
  - Rewriting the join position — `m_entryPointData` is `protected` (`Player.h`
    L2709/L2749) and only has a const getter (L2428).
  - `OnPlayerBeforeTeleport` — coordinates are passed by value, and it
    cannot tell an exit teleport from any other.
- **Usable:** `ServerScript::CanPacketReceive` on `CMSG_AREATRIGGER`.
  - `WorldSession.cpp` L459–464 calls it before the handler, and `false`
    skips the handler.
  - The opcode is `PROCESS_INPLACE` (`Opcodes.cpp` L311), so it runs where
    the native handler runs.
  - This module already uses the same pattern for quest loot
    (`QuestLootProtection.cpp`, copy of the packet, read cursor kept).
  - Bots do not send this packet through the socket path
    (`HandleBotPackets` skips `CanPacketReceive`), so bots are unaffected.
  - **Known limit:** Playerbots' `teleport` chat command (`e88cc409`,
    `src/Ai/Base/Actions/TeleportAction.cpp` L100–107) replays the bot's
    last area trigger by calling `HandleAreaTriggerOpcode` directly. That
    skips `CanPacketReceive`, so such a bot gets the stock route (live row,
    or join position/homebind in a Dungeon Finder group).

## 3. Proposed handler (S2, not written)

Proposed keys (names are proposals; no config file changes here):
`NaxxramasCore.ScarletExits.Enabled = 0`,
`NaxxramasCore.ScarletExits.UseVanillaDoorTargets = 1`,
`NaxxramasCore.ScarletExits.RouteDungeonFinderExits = 1`.

`CanPacketReceive(session, packet)`:

1. Opcode not `CMSG_AREATRIGGER`, flag off, no player, or packet under 4
   bytes → **true** (stock).
2. Read the trigger ID from a copy. Not 604 or 606 → **true**.
3. Mirror the native early exits (`MiscHandler.cpp` L691–760) and return
   **true** so the stock handler does the same: in flight; unknown
   trigger; outside the trigger radius (`IsInAreaTriggerRadius`, L716); a
   bound trigger script (`GetAreaTriggerScriptId != 0`); a quest tied to
   the trigger; tavern; battleground in progress; OutdoorPvP; no
   `areatrigger_teleport` row; row target map not 0; already on map 0;
   `PlayerCannotEnter(0)` denies. A GM with `.debug areatriggers` on also
   gets the stock path, so debugging shows native behaviour.
4. Choose the path:
   - LFG group in a dungeon: `RouteDungeonFinderExits = 0` → **true**
     (stock); otherwise the module handles it;
   - normal exit: if the door target is off or fails validation → **true**
     (stock, which already uses the live row); otherwise the module handles
     it.
5. **Destination:** the door target (the built-in Vanilla-core point) when
   `UseVanillaDoorTargets = 1` **and** it passes all of: map 0;
   `MapMgr::IsValidMapCoord`; outside its own outdoor entrance (610 or
   612) by the live radius or box + 1 yd (no bounce back in); outside every
   other SM entrance and nearer its own (no wing swap). Otherwise the live
   `areatrigger_teleport` row, which can only happen on the LFG path.
6. `TeleportTo(0, x, y, z, o, TELE_TO_NOT_LEAVE_TRANSPORT)` (same option
   as native). Either way return **false**, so the stock handler does not
   run for an eligible exit. If `TeleportTo` refused, send a short system
   message and leave the player where they are; they can step on the
   trigger again. **Fail closed, no fallback** (CS01 review 6385993172):
   - a stock retry for an LFG member would call `TeleportToEntryPoint` and
     send them to the queue spot or homebind, which is the behaviour F12
     removes;
   - `Player::TeleportTo` can already have done work before a late refusal
     (it ends a duel at L1496 before the `OnPlayerBeforeTeleport` veto at
     L1498), so a second attempt is not a pure no-op.

   `true` from `TeleportTo` means the teleport was accepted, not that the
   player arrived. Ineligible inputs and the flag off still return **true**
   at steps 1–4, so the stock handler runs unchanged for them.

**What changes for an LFG exit:** the module path skips
`TeleportToEntryPoint`, so the join position stays stored, and the remount,
taxi restore and group refresh it schedules
(`Player.cpp` L1650–1652, L1697–1725) do not run. Leaving the dungeon map
still clears Luck of the Draw and disbands one-person groups
(`LFGScripts.cpp` L103–143), which is path-independent.

**Join-position lifecycle after a module exit** (pinned `LFGMgr.cpp`
`TeleportPlayer`):
- walk back in, exit again → door again; the stored position is unused (S18);
- Dungeon Finder "teleport out" from inside → stock `TeleportToEntryPoint`
  (L2272–2276) uses the still-stored queue position, as stock does for that
  button (S19);
- Dungeon Finder "teleport in" from outside → `SetEntryPoint()` refreshes the
  stored position because the player is not in a dungeon (L2291–2294), so no
  stale position survives a new entry (S20);
- switch turned off later → the next exit is stock and uses whatever is
  stored (S21);
- the stored position is saved with the character (`Player.cpp`
  L15045–15059), so it survives relog in every case.

No remount or taxi resume after a module exit is a visible difference from
a stock LFG exit; it is listed for acceptance testing.

## 4. Negative-case matrix (source predictions, NOT test results)

| ID | Case | Expected |
|---|---|---|
| S01 | Flag off | Stock, identical |
| S02 | Trigger 602/608/610/612/other | Stock |
| S03 | In flight / unknown trigger / out of radius | Stock (native ignores) |
| S04 | Bound trigger script or quest on 604/606 | Stock (do not skip it) |
| S05 | Tavern / battleground / OutdoorPvP | Stock |
| S06 | Row missing or target map ≠ 0 | Stock |
| S07 | Normal party, Vanilla targets on | Door target |
| S08 | Normal party, Vanilla targets off | Stock row |
| S09 | LFG in dungeon, LFG routing on | Door target, join position kept |
| S09b | LFG, LFG routing on, Vanilla targets off | Live row (not the join position) |
| S10 | LFG, LFG routing off | Stock (join position / homebind) |
| S11 | Second LFG exit after walking back in | Door target again (no homebind) |
| S12 | Door target fails validation | LFG: live row; normal: stock. Never a bounce |
| S13 | `TeleportTo` refuses on an eligible exit | **Blocked**: message, player stays, no stock fallback |
| S14 | GM | Same as a player; with `.debug areatriggers` on, stock |
| S15 | Bot follows the leader | Not affected (no socket packet) |
| S15b | Bot told `teleport` after touching the exit (Playerbots `TeleportAction` replays the last area trigger) | **Not covered: stock** (known limit, see below) |
| S16 | Cathedral vs Armory | Each uses its own target; never swapped |
| S17 | Other instances' exits | Never touched |
| S18 | LFG: module exit → walk back in → exit | Door target both times; stored position unused |
| S19 | LFG: module exit → walk back in → Dungeon Finder "teleport out" | Stock: stored queue position |
| S20 | LFG: module exit → Dungeon Finder "teleport in" from outside | Stock refreshes the stored position |
| S21 | Switch turned off after a module exit | Next exit is stock (stored position or homebind) |
| S22 | Post-TBC character, switch on | Same as Vanilla (era-independent by design) |

## 5. Alternative for the owner (no module code)

Updating the two `areatrigger_teleport` rows (604, 606) to the Vanilla-core
values fixes cause A without C++, but it is a world-DB change and needs the
owner's approval, a backup and `.reload areatrigger_teleport`. It does not
fix cause B.

## 6. Not verified / owner input needed

- Which path the owner used (normal party or Dungeon Finder), and where
  they landed.
- The owner's live rows 604/606/610/612.
- Landing height, walls and facing at the Vanilla-core points in game; one
  owner `.gps` reading behind each door would confirm or correct them.
- Whether any ALE (Eluna) or other module script handles these triggers on
  the owner's build.
