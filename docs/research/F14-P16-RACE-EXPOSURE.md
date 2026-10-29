# F14 P16 — where race reaches clients outside `/who` (source audit, test-only)

Status: research and tests only. No change to `src/`, config, SQL, DBC, core,
Playerbots or Individual Progression. No packet rewrite, no hook, and F14
stays default OFF. Nothing here chooses policy A or B, a SelfBot rule, P12
M1–M4 or `maxAge`.

Parent: #202 `205d958`. Pins: core Grimfeather `8daffdab`; #145 writer
`01c6b32` (blob `e66f72c`), read only. Follows P14 (#228), whose facts C8–C10
first flagged the name query and checked friends and guild roster.

## Short answer

The P14 `/who` seam can hide a Blood Elf or Draenei only from `/who`. Today's
source sends the same race through at least six other paths. Two of them
reach clients that never see the player in the world:

- **Name query.** Any logged-in client can ask about any GUID. The handler
  answers with the race, checks nothing about the asker, and answers for
  offline characters from the character cache. The test runs the real
  function against a row that #145 hides and gets the race back.
- **Raid browser (LFR) list.** It sends each listed player's race.

The other paths reach only clients the player is visible to: the race byte
in a public unit field, the model and appearance fields, corpse bytes and
mirror-image data. That includes anyone standing nearby, inspecting, or in
the same instance or battleground.

**Conclusion for the owner:** under any policy, hiding TBC races in `/who`
is a `/who` listing rule, not a way to make those races invisible. Closing
the other paths would mean rewriting outgoing packets or changing models.
That is a separate, much larger decision, and nothing here proposes it.

## Surface table (checked by `tests/f14_race_exposure_facts.py`)

| # | Surface | Verdict | Who receives it | Pinned source at `8daffda` | Can the P14 seam reach it? |
|---|---|---|---|---|---|
| E1–E3 | Name query (`SMSG_NAME_QUERY_RESPONSE`) | **EXPOSES** | Any logged-in client, any GUID, including offline characters | `QueryHandler.cpp` L32–62 (race at L49), L64–70; `Opcodes.cpp` L211 | No |
| E4–E5 | Race byte in `UNIT_FIELD_BYTES_0` | **EXPOSES** | Every client the player is visible to | `Unit.cpp` L16695; `Player.cpp` L535–537; `PlayerStorage.cpp` L5089–5093; `UpdateFieldFlags.cpp` L187 | No |
| E6 | Model and appearance (`UNIT_FIELD_DISPLAYID`, `NATIVEDISPLAYID`, `PLAYER_BYTES*`) | **EXPOSES** (visually) | Same as E4 | `UpdateFieldFlags.cpp` L231–232, L317–319 | No |
| E7 | Corpse (`CORPSE_FIELD_BYTES_1`) | **EXPOSES** | Clients the corpse is visible to | `Player.cpp` L4705–4720; `UpdateFieldFlags.cpp` L1562 | No |
| E8 | Mirror image (`SMSG_MIRRORIMAGE_DATA`) | **EXPOSES** | Any client that asks about a clone of the player | `SpellHandler.cpp` L768–771; `Opcodes.cpp` L1156 | No |
| E9 | Raid browser list (`SMSG_UPDATE_LFG_LIST`) | **EXPOSES** | Clients browsing the raid list | `LFGMgr.cpp` L1343–1353 | No |
| N1 | Party member stats | no race | — | `GroupHandler.cpp` L817–1136 | — |
| N2 | Battleground and arena scoreboards | no race | — | `Battleground.cpp` L1373–1401; `BattlegroundScore.h`; `ArenaScore.h` | — |
| N3 | Arena team roster | no race (class only) | — | `ArenaTeam.cpp` L447–482 | — |
| N4 | Calendar | no race sent (used only to derive the team) | — | `CalendarHandler.cpp` L550 | — |
| P14 C9, C10 | Friends list, guild roster | no race | — | see #228 | — |

Each fact has a negative fixture: a mutated copy of its source that the
checker must reject.

## Counterexample (`tests/f14_race_exposure_tests.cpp`, 12 checks)

`tests/f14_race_exposure_extract.py` copies, unchanged and blob-checked:
- `WorldSession::SendNameQueryOpcode` (`QueryHandler.cpp` L32–62);
- #145's `WhoListingPolicy.h`.

The test compiles both against small stubs and checks:

1. #145 hides an online Blood Elf from a Vanilla-stage observer's `/who`
   (0/0). Stock output shows it (1/1). A human row is still shown.
2. The same observer's name query for that GUID returns the name and race 10.
3. An offline Draenei is answered from the cache with race 11.
4. A different observer gets the identical reply: the function never reads
   who is asking.
5. An online player's live race wins over a stale cache row.
6. Only an unknown GUID gets no race.

Builds: C++17/20 `-Werror`, ASan+UBSan.

Must-fail mutants (`tests/f14_race_exposure_mutants.py`, 5/5 caught):
- the name query masks race;
- it prefers the cache over the live player;
- it refuses offline characters;
- it depends on the asker;
- #145 stops hiding TBC rows.

Each would change the counterexample, which shows the test depends on
today's source.

## UNKNOWN (not settled by this audit)

- **Client behaviour.** How the 3.3.5a client caches name-query answers, and
  what it shows if a server ever sent `RACE_NONE`. Not testable from server
  source.
- **Phasing.** Whether Individual Progression or any module puts players in
  different phases. Object fields (E4–E7) follow normal visibility, so phasing
  could limit them. The name query (E1–E3) ignores visibility either way.
- **Surfaces not audited.** Guild event log, LFG dungeon-finder proposal and
  role-check packets, auction and mail (these send names, which a name query
  then resolves), channel member lists, and GM commands (out of scope).
- **Runtime.** No server was run. Every verdict is a reading of the pinned
  source.

## What the owner would have to decide (not proposed here)

- Whether F14's goal is the `/who` list only, or race visibility in general.
  If it is the general case, E1–E9 each need their own change. Hooks that
  could carry some of them exist (`CanPacketSend`, P14 C11–C12), but rewriting
  them is a new feature with client-side unknowns.
