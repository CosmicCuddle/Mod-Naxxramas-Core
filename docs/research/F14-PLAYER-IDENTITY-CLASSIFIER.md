# F14 P1 — human vs Random Playerbot vs AltBot classifier (pure, not wired)

**Status:** DRAFT. A pure C++ classifier, snapshot and dual policy with tests. **Nothing includes it**, so runtime behaviour is unchanged and F14 stays **default OFF**. There is no core, Playerbots, Individual Progression, SQL, DBC or config change, and no gameplay acceptance is claimed (mandatory outcomes remain 0/5).

**Assignment:** #48 6469287886 and 6469977271 (Part 32 P1). The human exception (policy B) is **provisional** and needs an owner decision.

**Pins read:** core Grimfeather `8daffda`, Playerbots `d750b4b`.

## 1. Why not just call Playerbots

| Candidate | Source | Why it is not enough by itself |
|---|---|---|
| `IsRealPlayer(p)` = `p && !GET_PLAYERBOT_AI(p)` | `PlayerbotAI.cpp` L4523–4529 | **Negative evidence.** `GetPlayerbotAI` returns `nullptr` for everyone when `Playerbots.Enabled = 0` (`PlayerbotMgr.cpp` L1858–1862), so every bot then "looks human". |
| `_playerbotsAIMap` lookup | `PlayerbotMgr.h` L135, `PlayerbotMgr.cpp` L1858–1872 | Plain `unordered_map` with no lock. Inserted on bot login and `self`, erased via `RemovePlayerBotData` from `~PlayerbotAI` (`PlayerbotAI.cpp` L247). Reading it from a map worker races those writes. |
| `RandomPlayerbotMgr::IsRandomBot(guid)` | `RandomPlayerbotMgr.cpp` L2254–2261 | Reads `currentBots` (plain `unordered_set`, `.h` L254) and the character cache. Same race from a map worker. |
| `IsAddclassBot(guid)` / `IsAccountType` | `RandomPlayerbotMgr.cpp` L2278–2304, L640–646 | Runs a **synchronous Playerbots DB query** on a cache miss. Unsuitable per `/who` row. Not used. |
| `WhoListPlayerInfo` row | core `WhoListCacheMgr` | No bot field. |

`CMSG_WHO` is `PROCESS_THREADSAFE`, so the F14 `/who` hook runs on the **observer's map thread** (`WhoListing.cpp`, #160). CS01's rule in #48 6469287886 also forbids reading a remote `Player*` there.

## 2. The seam this branch uses

- **Positive human signal: an open client socket.** Every Playerbots bot session is created with a `nullptr` socket:
  - `PlayerbotMgr.cpp` L159;
  - `RandomPlayerbotFactory.cpp` L733;
  - `TravelMgr.cpp` L3399.

  The core's `WorldSession::IsSocketClosed()` (`WorldSession.cpp` L639–642) is `!m_Socket || !m_Socket->IsOpen()`. This is core-owned and not masked by Playerbots config.
- **Sampling point: the world thread, while the maps are idle.**
  - `World::Update` calls `sMapMgr->Update` (`World.cpp` L1254).
  - `MapMgr::Update` returns only after `m_updater.wait()` (`MapMgr.cpp` L280).
  - `sScriptMgr->OnWorldUpdate` runs later in the same tick (`World.cpp` L1355).

  At that point no map worker is running, so reading `GET_PLAYERBOT_AI`, `GetMaster()`, `IsRandomBot` and the session socket does not race the map threads. Playerbots' detached command-server thread (`PlayerbotCommandServer.cpp`) only **looks up** bots (`RandomPlayerbotMgr.cpp` L3105–3127). It does not write these containers, so it adds no write race with a world-thread reader.
- **Publishing:** `IdentityBoard` holds one immutable snapshot behind a `shared_ptr`. The world thread replaces it whole, and map threads copy the pointer under a mutex and read it lock-free. A missing, stale (`maxAge`), future-dated, duplicate or over-cap entry reads as **Unknown**.

## 3. Rules (`Classify`)

| In world + session | Socket open | Playerbots on | AI attached | Master is self | Random listed | Identity |
|---|---|---|---|---|---|---|
| no | – | – | – | – | – | Unknown |
| yes | yes | – | no | – | no | **Human** |
| yes | yes | – | yes | yes | no | **SelfBot** |
| yes | yes | – | yes | no | – | Unknown (contradiction) |
| yes | yes | – | – | – | yes | Unknown (contradiction) |
| yes | no | no | – | – | – | Unknown (AI lookup masked) |
| yes | no | yes | no | – | – | Unknown (dropped human or masked bot) |
| yes | no | yes | yes | yes | – | Unknown (linkdead SelfBot) |
| yes | no | yes | yes | no | yes | **RandomBot** |
| yes | no | yes | yes | no | no | **AltBot** |

## 4. Policies (`HideTbcRow`)

Applies only to Blood Elf (10) and Draenei (11) rows. The observer's own row is always kept (F14 R4).

- **(A) `HideAllTbcRaces`** (value 0, and the fallback for any other value): hide every such row.
- **(B) `HideBotsOnly`** (value 1, **provisional**): show only rows positively classified **Human**. Unknown, RandomBot and AltBot are hidden. SelfBot is hidden unless `selfBotCountsAsHuman` is set (default false, owner choice).

## 5. Tests (`tests/f14_player_identity_policy_tests.cpp`, 2,936 checks)

- **Classifier:**
  - all 128 fact combinations are checked against an independently written spec;
  - invariants: no Human or SelfBot without a socket, no bot without "Playerbots on + AI", and "no AI" alone never gives Human;
  - named cases cover a dropped human, a linkdead SelfBot, disabled Playerbots and the contradictions.
- **Policy:**
  - A hides every identity's TBC rows and keeps all 254 other race values;
  - B shows only Human (and SelfBot with the flag);
  - the observer row is kept under both;
  - `ParsePolicy` maps -1, 2, 255, 256 and 2^40 to A;
  - a raw out-of-range enum behaves as A.
- **Board:**
  - never-published, unknown GUID and GUID 0 all read as Unknown;
  - the freshness boundary is inclusive at `maxAge`, and +1 ns past it is stale;
  - a future-dated sample, a duplicate GUID, a republish that drops a player, `Invalidate` and exceeding `MAX_ENTRIES` all give Unknown;
  - exactly `MAX_ENTRIES` is accepted.
- **Concurrency:** one publisher (2,000 generations plus invalidations) and four readers under ThreadSanitizer.
- **Build matrix:** GCC C++17/C++20 (`-Wall -Wextra -Werror -pedantic -Wshadow -Wconversion`), Clang C++17, ASan+UBSan and TSAN.
- **Mutants:** `tests/f14_player_identity_mutants.py` makes 22 must-fail edits. All are caught, including a TSAN-only "lookup without lock".

## 6. Not done here (needs a separate assignment and review)

1. **World-thread adapter.** A `WorldScript::OnUpdate` would iterate `ObjectAccessor::GetPlayers()` and fill `Facts`:
   - `IsInWorld`;
   - `GetSession() != nullptr`;
   - `!IsSocketClosed()`;
   - `sPlayerbotAIConfig.Enabled`;
   - `GET_PLAYERBOT_AI`;
   - `GetMaster() == player`;
   - `sRandomPlayerbotMgr.IsRandomBot(player)`.

   It would then call `IdentityBoard::Publish`. This needs Playerbots headers in the module build, using the `__has_include` fallback precedent from A01, and a pinned Worldserver link. Without the Playerbots headers it must publish nothing, so everything stays Unknown and policy B degrades to A.
2. **`/who` wiring.** Replace `HideRow` in `WhoListingPolicy.h` with `HideTbcRow(config, race, isObserver, board.Lookup(guid, now, maxAge))`. That touches CS01's #145/#160 assembly, so it is **not** done here.
3. **Owner decisions:** whether the provisional human exception (B) is wanted at all, whether SelfBots count as human, and `maxAge` (the who cache refreshes on `WUPDATE_WHO_LIST`).
4. **Not covered:** world (non-`/who`) visibility, which is a different hook and thread; a human whose socket drops is hidden until reconnect (fail closed); runtime proof of any of the above.
