# Scarlet Monastery: Cathedral and Armory exits (F12)

**Status:** review-only prototype. Default **OFF**. Not installed, not
tested in game. The design was reviewed as S1 in PR #124
(`docs/research/F12-SCARLET-EXIT-FUNCTIONAL-S1.md` on that branch).

## What it changes

With `NaxxramasCore.ScarletExits.Enabled = 1`, leaving the Cathedral (area
trigger 604) or the Armory (606) puts the player just behind that wing's own
entrance door, facing away from it, like the Graveyard and Library exits
already do. Nothing else is touched.

Two problems are covered, each with its own switch:

| Problem | Stock behaviour | With the switch on |
|---|---|---|
| The baseline 604/606 rows land 18–20 yd from their doors, facing 40–50° off | Lands there | `UseVanillaDoorTargets = 1`: lands at the Vanilla-core point 9–11 yd behind the door |
| A Dungeon Finder group member is sent to the queue position or hearthstone | `TeleportToEntryPoint` | `RouteDungeonFinderExits = 1`: leaves by the door too |

The Vanilla-core points come from MaNGOS Zero `database` `325948a` and
cMaNGOS `classic-db` `4e3d118` (identical in both). They are used only after
the live entrance rows confirm the point is outside its own door by the
door's radius + 1 yd, outside every other Scarlet Monastery entrance, and
nearer its own door than any other. Otherwise the live
`areatrigger_teleport` row is used. Applies at every Individual
Progression stage.

## How

- `src/Systems/ScarletMonasteryExits.cpp` — a `ServerScript` with only
  `SERVERHOOK_CAN_PACKET_RECEIVE`. For `CMSG_AREATRIGGER` with trigger 604 or
  606 it gathers the same facts the native handler checks
  (`MiscHandler.cpp` `HandleAreaTriggerOpcode`, core `8daffda`) and asks the
  policy. The packet is read from a copy, so the native read cursor is not
  moved.
- `src/Systems/ScarletExitPolicy.h` — dependency-free decision and geometry
  rules, unit-tested natively.

These cases leave the stock handler in charge. Some are native early
returns (in flight, unknown trigger, outside its radius, tavern,
battleground in progress, missing row, entry denied). The rest are deferred
**conservatively** because the native handler may do extra work there: a
quest on the trigger (credit, no return), a bound trigger script, OutdoorPvP,
a GM with `.debug areatriggers`, a row not on map 0, or already being on
map 0 (native still teleports to the row).

**Fail closed:** once an exit is eligible, the native handler does not run
for it. If `TeleportTo` refuses, the player stays in place with a short
message and can step on the trigger again. A stock retry could send a
Dungeon Finder member to the queue position, and `TeleportTo` can already
have ended a duel before a late refusal. `TeleportTo` returning true means
the teleport was accepted, not that the player arrived.

## Known differences and limits

- **Dungeon Finder exits** skip `TeleportToEntryPoint`, so no remount or
  taxi resume, and the stored queue position stays stored. The Dungeon Finder
  "teleport out" button still uses it; "teleport in" from outside refreshes
  it.
- **Bots:** bots do not send this packet through the socket, so they are
  unaffected. Playerbots' `teleport` chat command replays the last area
  trigger through `HandleAreaTriggerOpcode` directly and gets the stock
  route.
- **Not verified:** ground height, walls and facing at the two points in
  game; the owner's live rows 604/606/610/612; any Eluna or other private
  trigger scripts on the owner's build.

## Tests

- `tests/scarlet_exit_policy.cpp` — native C++17/C++20 `-Werror`: door table,
  geometry (both points safe, swapped wings, inside/margin, missing or
  wrong-map entrance, a real box trigger) and every decision case.
- `tests/test_scarlet_monastery_exits.py` — source contract: default OFF,
  loader, opcode fast exit, packet copy, mirrored early exits, fail-closed
  return, no database access, no rejected seams.
- `.github/workflows/scarlet-monastery-exits.yml` — the above plus a pinned
  full Worldserver link and symbol check.

## Rollback

Leave `NaxxramasCore.ScarletExits.Enabled = 0` (the default) and restart.
