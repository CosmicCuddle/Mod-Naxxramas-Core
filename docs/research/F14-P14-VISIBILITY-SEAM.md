# F14 P14 — where identity would meet `/who` (test-only, unwired)

Status: research and tests only. No change to `src/`, config, SQL, DBC, core,
Playerbots or Individual Progression. Nothing here registers a hook, and F14
stays default OFF. This is not a proposal to wire anything; it records what a
future, separately approved wiring step would need.

Parent: `claude/cs03-f14-identity-facts-adapter` at `205d958` (#202: the
classifier, `IdentityBoard` and the unwired facts adapter). The `/who`
writer is read, not edited, from #145 head `01c6b32`
(`src/Systems/WhoListingPolicy.h`, blob `e66f72c`).

Pins: core Grimfeather `8daffdab`. Owner-accepted gameplay is still 0/5.

## Short answer

1. **The seam is one line.** #145's writer decides each row with
   `HideRow(race, rowIsObserver)` (`WhoListingPolicy.h` L211). That rule is
   exactly #197's **policy A** (`HideTbcRow` with `HideAllTbcRaces`), for
   every race, observer flag and identity. Policy B needs one more input: the
   row's identity. The test-only variant changes only that call, to
   `ctx.HideRowFor(race, rowIsObserver, guid)`. The context then calls
   `HideTbcRow(policy, race, rowIsObserver, board.Lookup(guid.GetCounter(), now, maxAge))`.
2. **Policy A through the seam is byte-identical to #145 as shipped**, and
   with hiding off it is byte-identical to stock. Wiring the seam therefore
   cannot change any reply until policy B is chosen.
3. **Threading needs no new lock.** The core already builds the `/who` cache
   on the world thread before map threads run. A board published from
   `OnWorldUpdate` runs after map threads have stopped. `IdentityBoard` has
   its own mutex and immutable snapshots in any case.
4. **`/who` is the only surface in reach.** Race also reaches clients through
   the name query and the character model. Hiding a row in `/who` does not
   hide a Blood Elf or Draenei from those. Friends and guild roster packets
   carry no race.

## Pinned core facts (checked by `tests/f14_visibility_seam_facts.py`)

| # | Fact | Source at `8daffda` |
|---|---|---|
| C1 | The who cache is rebuilt every 5 s | `World/World.cpp` L934 |
| C2 | `World::Update` order: who cache L1170 → world-thread sessions L1227 → `MapMgr::Update` L1254 → `OnWorldUpdate` L1355 | `World/World.cpp` |
| C3 | `MapMgr::Update` waits for all map workers | `Maps/MapMgr.cpp` L280 |
| C4 | `CMSG_WHO` is `STATUS_LOGGEDIN`, `PROCESS_THREADSAFE` (answered during the map phase) | `Server/Protocol/Opcodes.cpp` L229 |
| C5 | The stock handler iterates the cache, not live players | `Handlers/MiscHandler.cpp` L294 |
| C6 | Cache rows store the player GUID and race | `Cache/WhoListCacheMgr.cpp` L58–61 |
| C7 | Rows expose `GetGuid()`, so a board lookup needs no extra data | `Cache/WhoListCacheMgr.h` L44 |
| C8 | The name query response sends the race | `Handlers/QueryHandler.cpp` L49 |
| C9 | Friend list entries have no race field | `Entities/Player/SocialMgr.h` L47–55 |
| C10 | Guild roster entries have no race field | `Server/Packets/GuildPackets.h` L105–120, `Guilds/Guild.cpp` L1234–1248 |
| C11 | `CanPacketSend` and `CanPacketReceive` hooks exist | `Scripting/ScriptDefines/ServerScript.h` L65, L75 |
| C12 | Every outgoing packet passes `CanPacketSend` | `Server/WorldSession.cpp` L351 |

Each fact has a negative fixture (a mutated copy of the cited source) that the
checker must reject.

## One world tick, as the seam would see it

```
World::Update (world thread)
  L1170  who cache rebuilt (every 5 s)        writes rows      <- C1, C6
  L1227  world-thread sessions                 may read rows
  L1254  MapMgr::Update -> map workers         read rows (CMSG_WHO, C4/C5)
         MapMgr.cpp L280: wait()               all workers done
  L1355  OnWorldUpdate                         would publish IdentityBoard
```

- **Writers never overlap readers.** Rows are written at L1170 and the board at
  L1355; both are read only between them. `SampleFacts` must run at L1355
  (its compile-time token already forbids map-thread callers).
- **Freshness.** A cache row can be up to 5 s older than the board. A player who
  logged out in that window is missing from the next board. The lookup is then
  `Unknown`, which hides a TBC row under policy B (fail closed). A non-TBC row
  is never affected. A board older than `maxAge`, or apparently from the
  future, is not trusted, and policy B then behaves exactly like policy A.
- **Key.** The board is keyed by the GUID counter (`GetCounter()`), as #202's
  adapter stores it. The test checks that the high GUID bits do not matter.

## What the test proves (`tests/f14_visibility_seam_tests.cpp`, 23 checks)

The test compiles #202's real `PlayerIdentityPolicy.h` with both
`WhoListingPolicy.h` and the generated `WhoListingSeam.h`, extracted by
`tests/f14_visibility_seam_extract.py`. The extractor checks the blob and
requires exactly five changed lines: the guard ×3, the namespace, and the call.

| # | Property | Evidence |
|---|---|---|
| 1 | #145 `HideRow` equals #197 policy A | Exhaustive: 256 races × observer × 5 identities × SelfBot option |
| 2 | Hiding off: seam reply = stock reply | 2000 random requests, wire bytes |
| 3 | Policy A through the seam = #145 as shipped | 2000 cases, any board |
| 4 | Policy B (default and SelfBot-as-human) = stock reply minus rows the identity rule hides | 2000 cases each; B differs from A in more than 10% of cases |
| 5 | Stale, future or missing board → exactly policy A; at exactly `maxAge` still trusted | 2000 cases each |
| 6 | Named rows: human elf shown; SelfBot, RandomBot and AltBot TBC rows hidden; hidden-only query → 0/0; non-TBC bot shown | 8 checks |
| 7 | Lookup by GUID counter; unknown GUID hidden; own row kept | 3 checks |
| 8 | An over-full board is invalid → policy A | 2 checks |

Must-fail mutants (`tests/f14_visibility_seam_mutants.py`, 9/9 caught):
- identity ignored;
- wrong board key;
- observer not exempt;
- hiding while the feature is off;
- stale board trusted;
- future board trusted;
- `Unknown` shown under policy B;
- SelfBot option ignored;
- partial over-full snapshot.

## What a wiring step would need (not done here)

1. Define `WorldThreadSamplingGrant` in one reviewed world-thread hook at
   L1355. Sample every in-world player and publish one board per tick (or per
   5 s, with a matching `maxAge`).
2. Add `HideRowFor` to #145's `CoreWhoContext` and change the one call in
   `WriteWhoReply`. Read the policy and the SelfBot option once at startup, as
   #145 already does for its own settings.
3. Owner decisions that are still open:
   - policy A vs B;
   - whether a SelfBot counts as human;
   - the P12 masked-SelfBot case (M1–M4);
   - `maxAge`.
4. Accept the limit in C8. Race stays visible through name queries and in the
   world. Hiding it there would mean rewriting outgoing packets
   (`CanPacketSend`, C11–C12). That is a different and much larger change,
   and nothing here proposes it.

## Not verified

- No server run. Only the writer is exercised; the module's `CanPacketReceive`
  intercept (#145) is unchanged and was not re-tested here.
- Map-thread scheduling is a source reading (C2–C4), not a runtime trace.
- Newer core revisions than `8daffda`.
