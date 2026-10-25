# F14 S2 — `/who` hiding of Blood Elf and Draenei for Vanilla-stage players (draft, default OFF)

**Status:** isolated S2 source prototype, authorised by CS01's #128 design review (comment `6398544565`). **DO NOT MERGE.** Not tested in game or with a client.

- **Defaults:** `NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0` (stock `/who`) and `GMBypass = 1`.
- **Stacked on #127.** It needs #127's `NaxxramasIpEra::IsVanillaProgression` (`src/Systems/IndividualProgressionEra.h`), as CS01's gate 2 asks.
- **Includes #128.** It carries #128's S1 design, model and fingerprint script unchanged, apart from the one key-contract test that S2 supersedes.

Pins: Grimfeather core `8daffda`, Individual Progression `dd96f2b`, Playerbots `d750b4b`.

## What it does

- **Only `/who`.** The friends list, guild roster, channel member lists, name queries and world visibility are **not** changed. Each of those needs its own S2 (CS01 gate 3).
- **OFF:** `CanPacketReceive` returns `true` for every packet, and the unmodified core handler answers. No packet is built.
- **ON:** for `CMSG_WHO` only, the module applies the S1 rule:

| Rule | When | Result |
| --- | --- | --- |
| R1 | `HideTbcRaces = 0` | stock handler |
| R2 | the observer is not Vanilla-stage | stock handler |
| R3 | `GMBypass = 1` and the observer's account security is above `SEC_PLAYER` | stock handler |
| R4 | the row is the observer's own character | kept (provisional owner choice O1) |
| R5 | the row's race is Blood Elf (10) or Draenei (11) | left out of the list **and both counts** |

- **Who counts as Vanilla-stage.** The **observer's** current IP stage, read from the observer only, on each request.
- **Whose rows are hidden.** Human, Random Bot and Altbot rows are hidden alike, as the owner asked. Other Vanilla-stage Blood Elves are hidden too (O2).
- **Provisional choices.** O1 (own row kept) and O4 (`GMBypass = 1`) are proposals in source, not owner gameplay approvals.

## How it answers `/who` (mirror)

There is no `/who` script hook, so the module answers `CMSG_WHO` itself from `ServerScript::CanPacketReceive` and returns `false`, which skips the core handler.

- **The mirror.** `WhoListingPolicy.h` copies the stock `WorldSession::HandleWhoOpcode` (`MiscHandler.cpp` L220–L414) line for line:
  - field read order;
  - the early returns that send nothing (`zonesCount > 10`, `strCount > 4`, a bad UTF-8 name or guild);
  - the `MAX_LEVEL` → `STRONG_MAX_LEVEL` widening;
  - every row filter (faction with RBAC 28, GM level with RBAC 35, GM visibility, level, class, race, zone, name, guild and free text);
  - the post-increment cap (`CONFIG_MAX_WHO_LIST_RETURN`);
  - the two count offsets: displayed count at 0, matches at 4.
- **The one added line** is the R4/R5 test, placed **before** `matchCount++`, so a hidden row is in neither count. A filter after the increment would leave the match count too high; that was #107's trap, and it is tested.
- **Values the module supplies** are the same calls the stock handler makes: `Utf8toWStr`, `wstrToLower`, `Utf8FitTo`, `HasPermission`, `GetSecurity`, `AccountMgr::IsPlayerAccount`, `sWorld->getIntConfig`, `sAreaTableStore` with the session's DBC locale, and `sWhoListCacheMgr->GetWhoList()`.
- **Drift gate.** `scripts/check_f14_who_handler_fingerprint.py` hashes the core handler and the `CMSG_WHO` opcode row. Any change to either fails CI and forces a re-review of the mirror.

## Threads and settings

- **Thread.** `CMSG_WHO` is `PROCESS_THREADSAFE` (`Opcodes.cpp` L229), so `CanPacketReceive` runs on the observer's map thread, as the stock handler does (`WorldSession.cpp` L441–L464). It reads only the observer's own `Player` and session plus the who-cache, which the world thread rebuilds before map workers start (`World.cpp` L1166–L1170, L1254). There are no remote player lookups, no Playerbots calls and no shared writes.
- **Settings.** They are read once at startup by a `WorldScript::OnAfterConfigLoad(false)` hook, before any map worker exists, as on #133. `.reload config` does not change them and logs a warning if they differ. The packet path never calls `ConfigMgr`.
- **IP stage helper.** At the pins, IP's header is on the module include path, so `IsVanillaProgression` uses `sIndividualProgression->hasPassedProgression`. On an install **without** IP's header, its fallback reads `ConfigMgr` on this map thread. That is the same pre-existing residual as on #127, and it is not used at the pins.

## Interaction with other packet hooks

- **Core stops at the first `false`.** `ScriptMgr::CanPacketReceive` returns as soon as one script returns `false` (`ScriptMgrMacros.h` L76–L80).
  - If another module registered **earlier** blocks `CMSG_WHO`, neither this module nor the core handler runs.
  - While F14 is ON, a module registered **later** does not see `CMSG_WHO` from Vanilla-stage observers.
- **No overlap here.** In this repository, F12 (`CMSG_AREATRIGGER`), `QuestLootProtection` (`CMSG_AUTOSTORE_LOOT_ITEM`) and Playerbots `SecureLogin` (`CMSG_PLAYER_LOGIN`) all return `true` for `CMSG_WHO`.
- **Malformed packets.** A short packet throws from the read, inside the core's `try`, exactly as in stock: no reply. The difference is that later-registered packet hooks also don't run for that one malformed packet.

## Tests

- **`tests/who_listing_policy.cpp`** (native, C++17 and C++20, `-Werror`). Byte comparisons against a transcription of the stock handler:
  - **hide OFF:** 3000 random requests and caches are byte-identical to stock, including no-reply and short-packet cases;
  - **hide ON:** 3000 random cases equal stock run on the cache with hidden rows removed;
  - **targeted queries:** name, guild, race masks 10, 11 and both, zone, free text and a composite each return 0/0 while the same query finds rows in stock;
  - **cap:** 80 rows with 20 hidden give `matchCount` 60, display 49, and the first 49 visible rows in cache order;
  - **own row and O2:** the own Blood Elf row is kept and another one is hidden;
  - **malformed input:** zones > 10, strings > 4, a bad UTF-8 name, a bad search string (skipped, as stock) and short packets;
  - **rules:** the R1–R5 truth table.
- **Mutants caught:** the hide check moved after the increment, the cap off by one, and the search-string lowercasing removed.
- **`tests/test_f14_who_listing_s2.py`.** Source contract:
  - OFF returns `true` before any work;
  - the rules decide before any reply;
  - config is read only in the startup hook;
  - the hide check precedes the count, and the early returns are kept;
  - the policy header is dependency-free;
  - no remote lookups;
  - registered once.
- **`tests/test_f14_who_listing_model.py`.** The S1 model. Its "keys not yet added" test is replaced by "keys added once with the proposed defaults, read only by `WhoListing.cpp`".
- **`.github/workflows/f14-who-listing-s2.yml`.** The source, native and fingerprint jobs, then a pinned full Worldserver link with a symbol check.

## Not done or not tested

- **No client tests.** Nothing has been tested with a 3.3.5a client (how the client parses the two counts), in game, or at 8 map threads.
- **No owner decision on the provisional choices.** O1 (own row), O3 (groupmates and guildmates) and O4 (GM bypass) are proposals.
- **Other surfaces are out of scope.** Friends, guild roster, channels, name queries and world visibility.
- **No changes to protected code.** No core, IP or Playerbots change. No SQL or DBC.
- **Owner-approved staged negatives, for later:**
  - a stage change without relog;
  - a Random Bot force-updated to its leader's stage;
  - an opposite-faction Blood Elf with and without RBAC 28;
  - GM invisibility;
  - more than 49 legal rows;
  - an own-name search;
  - IP disabled, and `ProgressionLimit` 1–7.
