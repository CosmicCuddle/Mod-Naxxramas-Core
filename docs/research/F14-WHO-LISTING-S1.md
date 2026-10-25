# F14 S1 — `/who` listing by Individual Progression stage (CS03)

**Status:** design and model only. No C++, no config entry, no SQL, no
loader change. **DO NOT MERGE.** No executable S2 until CS01's design
review (CS01 directive, #48 comment `6386275975`, item 3). In-game
behaviour is **NOT TESTED**.

**Scope:** the `/who` part of F14 (owner record: #28 comment `6366478251`,
#48 comment `6366502362`). World visibility, combat and pets are separate
(my trace, #48 comment `6368163054`). CS02's PR #107 (`/who` and IP-stage
audit) is used as evidence only. Every citation below I re-read myself at
the pins.

## Pins

| Tree | Commit |
| --- | --- |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` |
| `mod-playerbots` (CI pin) | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |
| This module, base | `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` (`main`) |

## 1. The rule

Owner decisions this rule follows:

- the **observer's** IP stage decides, not level, race or account unlock;
- there is one switch for both races;
- `/who` is always filtered while hiding is on;
- hidden characters leave **both** counts, for every query shape.

Evaluated once per row, **before** the core's `matchCount++`. "Hidden"
means the row is omitted from the list, from `matchCount` and from the
displayed count.

| Rule | When | Result |
| --- | --- | --- |
| **R1** | `HideTbcRaces = 0` | Stock packet, byte for byte |
| **R2** | Observer is not Vanilla-stage (§2) | Stock |
| **R3** | `GMBypass = 1` and observer account security `> SEC_PLAYER` | Stock |
| **R4** | The row is the observer's own character | Kept (see **O1**) |
| **R5** | Row race is Blood Elf (10) or Draenei (11) | Hidden |
| — | Anything else | Stock filters decide |

Notes on the rule:

- **Target kind does not matter.** A human, Random Bot or Altbot Blood Elf
  is hidden alike, as the owner asked ("including applicable Random
  Playerbots and controlled AltBots"). The who-cache row has no bot flag
  (`WhoListCacheMgr.h` L44–L56), and the rule needs none.
- **No `IncludePlayerbots` key.** Telling bots apart would need a lookup
  on another player (`ObjectAccessor` plus `GET_PLAYERBOT_AI`) from the
  observer's map thread, for no owner-requested benefit. The owner allowed
  simplifying the tentative keys.
- **Bots as observers do not arise.** Bots have no client. Nothing in
  Playerbots `d750b4b` `src/` or IP `dd96f2b` `src/` sends `CMSG_WHO` or
  reads the who cache (grep for `CMSG_WHO`, `SMSG_WHO`, `HandleWhoOpcode`,
  `GetWhoList`). This closes #107's open item on other Playerbots files.
- **Stock filters still run unchanged:** faction (L296), GM level (L300),
  GM visibility (L303–L305), level, class, race mask, zone, name, guild
  and free text. R5 only removes more rows.

### Open owner cases (not decided here)

- **O1 — own row.** The owner wrote that Blood Elf and Draenei characters
  "must see themselves and play normally".
  - **Proposed default:** keep the observer's own row (R4).
  - **Strict variant:** also hide it. Then a Vanilla-stage Blood Elf
    searching their own name gets 0/0.
  - Both variants are modelled.
- **O2 — other Vanilla-stage Blood Elves and Draenei.** With no exception
  they are hidden from a Vanilla-stage Blood Elf, as from anyone. No
  exception is invented.
- **O3 — group, raid and guild members.** A hidden groupmate or guildmate
  is also absent from `/who`. The guild roster and party frames are other
  surfaces (**O6**). Default: no exception.
- **O4 — `GMBypass` default.** Proposed `1`: GM accounts see everything,
  matching the core's own GM test (`AccountMgr::IsPlayerAccount`, which is
  `gmlevel == SEC_PLAYER`).
- **O5 — IP disabled or `ProgressionLimit` 1–7.** The proposal follows IP
  exactly, through the existing era helper:
  - IP disabled: nobody is Vanilla-stage, so `/who` is stock.
  - Limit 1–7: everyone is Vanilla-stage, so Blood Elves and Draenei are
    hidden from all non-GM observers.
- **O6 — other listing surfaces, not traced in this S1.** These are out of
  F14 `/who` unless CS01 or the owner add them:
  - friends list;
  - guild roster;
  - channel member list;
  - name-query responses (which carry race);
  - `CMSG_WHOIS` (GM-only, RBAC 43).

## 2. Observer stage

**Reuse the module's existing era rule.**
`NaxxramasIpEra::IsVanillaProgression(Player*)`
(`src/Systems/IndividualProgressionEra.h`, draft #127) is a verbatim copy
of `MeetingStoneProgression.cpp`'s rule, kept in step by a source test:

- with IP's header: `!sIndividualProgression->hasPassedProgression(player, 8)`
  (IP `IndividualProgression.cpp` L31–L39);
- without the header: the same `Enable` / `ProgressionLimit` gates, plus a
  scan of rewarded quests 66008–66018.

Why this choice:

- **Live:** it is read on each `CMSG_WHO`, so a stage change (Into the
  Breach, or IP's bot force-update to the leader's stage) applies to the
  next `/who` without relog.
- **Cheap:** at most 18 `GetQuestStatus` lookups, no database query, once
  per request rather than once per row.
- **Safe:** it reads only the observer's own player, on the thread that
  already handles the observer's packet (§3).

**Dependency:** S2 needs that helper on its base. CS01 decides whether it
lands with #127 or moves first.

## 3. Module-owned seam (proved at the pin)

There is **no `/who` script hook.** A search of every
`src/server/game/Scripting/ScriptDefines/*.h` for "who" finds only
unrelated parameter names. `HandleWhoOpcode` makes no `sScriptMgr` call.

**The seam:** `ServerScript::CanPacketReceive` registered with
`{ SERVERHOOK_CAN_PACKET_RECEIVE }`. For `CMSG_WHO` only, it builds the
reply itself and returns `false`. This is the same hook F12 (#125) and
`QuestLootProtection` use; each returns `true` immediately for every other
opcode.

| Fact at `8daffda` | Source |
| --- | --- |
| `CMSG_WHO` is `STATUS_LOGGEDIN`, `PROCESS_THREADSAFE` | `Opcodes.cpp` L229 |
| For `STATUS_LOGGEDIN`, `CanPacketReceive` runs inside the session `try`, only when `_player->IsInWorld()`, and `false` skips `opHandle->Call` | `WorldSession.cpp` L441–L464 |
| `PROCESS_THREADSAFE` with the player in world runs in `Map::Update` (`MapSessionFilter`); `WorldSessionFilter` takes it only when not in world | `WorldSession.cpp` L66–L107, `Map.cpp` L441–L449 |
| The cache is rebuilt on the world thread (`World.cpp` L1166–L1170) before `sMapMgr->Update` (L1254), which waits for all map threads (`MapMgr.cpp` L280) | same order as the stock handler |
| A malformed packet throws `ByteBufferException` inside the same `try`, which logs "Skipped packet" | `WorldSession.cpp` L546–L548 (catch) |

Everything the stock loop reads is public:

- `sWhoListCacheMgr->GetWhoList()` (`WhoListCacheMgr.h` L90) and every row
  getter (L44–L56);
- `WorldSession::HasPermission` (`WorldSession.h` L495, public section from
  L431) with `rbac::RBAC_PERM_TWO_SIDE_WHO_LIST` (28) and
  `RBAC_PERM_WHO_SEE_ALL_SEC_LEVELS` (35);
- `GetSecurity` (L490) and `GetSessionDbcLocale` (L646);
- `AccountMgr::IsPlayerAccount`, `sWorld->getIntConfig`, `sAreaTableStore`,
  `Utf8toWStr`, `wstrToLower` and `Utf8FitTo`.

**What the mirror must repeat exactly** (`MiscHandler.cpp` L220–L414):

- the field read order;
- the early returns, which send nothing (`zonesCount > 10` L240,
  `strCount > 4` L253, name or guild UTF-8 failure L275);
- the `levelMax >= MAX_LEVEL` → `STRONG_MAX_LEVEL` widening (L283);
- every row filter, in any order, since they are pure;
- the post-increment cap (L393);
- the `put(0, displaycount)` / `put(4, matchCount)` layout (L409–L410).

The R-rule goes anywhere before L393. The model shows every placement
before the increment gives the same packet, and a filter after it leaves
`matchCount` too high (#107's trap).

**Drift gate.** The mirror copies core code, so a core pin change must
force a re-review. `scripts/check_f14_who_handler_fingerprint.py` hashes
`HandleWhoOpcode` and the `CMSG_WHO` opcode row:

| Item | sha256 at `8daffda` |
| --- | --- |
| `HandleWhoOpcode` (signature through closing brace) | `e6e6faca12a307088b8a9f83ed5f2c5b73e3a7786364f49f96f8f51e4e5f1f2e` |
| `CMSG_WHO` row in `Opcodes.cpp` | `a86c1a56c832e96f995fb36244c3bb7d473f7ec7ebdaccf7c13963be2d7cdbc3` |

Both hashes were checked against `git show 8daffda:<file>`. A one-character
change to the handler fails the check.

**Rejected seams:**

- **`CanPacketSend` on `SMSG_WHO`:** the packet is const, and returning
  false drops it whole.
- **Editing the cache:** it is global, not per-observer.
- **A new core hook before L393:** the cleanest option (#107 §b), but it
  needs a core edit and separate owner approval.

**Residual risks:**

- Another installed module's `CanPacketReceive` could return `false` for
  `CMSG_WHO` first. **UNKNOWN** on the owner's build: other modules, Eluna.
- Rows are up to 5 s stale, as in stock (`World.cpp` L934).
- No client parse of the two counts has been made: **NOT TESTED**.

## 4. Config proposal

Not added to `conf/mod_naxxramas_core.conf.dist`; for review only:

```
NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0
NaxxramasCore.ExpansionRaceVisibility.GMBypass = 1
```

- `HideTbcRaces` is the one switch for both races. Default `0`, so `/who`
  is stock.
- When the world-visibility part lands, the same switch must drive it,
  because the owner wants no separate `/who` key.
- `GMBypass` has no effect while `HideTbcRaces = 0`.
- **For CS01:** the tentative `Enable` master is redundant next to a
  single hide switch. Keep it only if F14 gains a second hide rule.

## 5. Tests in this branch

`tests/test_f14_who_listing_model.py` executes a model of
`HandleWhoOpcode` plus the rule:

- **Stock parity:** with R1, R2 or R3 in effect, every packet equals
  stock. Checked over 400 random requests and 40 random caches, and for
  broken packets (no reply either way).
- **Hiding:** for a Vanilla-stage observer, no race 10 or 11 row appears,
  and `matchCount` drops by exactly the number of hidden rows.
  - Targeted queries return 0/0: exact name, name substring, race mask with
    only bit 10 or only bit 11, class plus zone, guild, free-text zone
    name, and a composite query.
- **Cap:** 80 rows with 20 hidden give `matchCount` 60, display 49, and the
  displayed rows are the first 49 visible rows in cache order.
- **Placement:** predicate placement before the increment does not change
  the packet; a filter after the increment is a detected mutant.
- **Scope:** faction and GM filters still run first; bot and Altbot rows
  are not distinguishable and are hidden alike.
- **O1–O2:** both own-row variants, plus a GM without bypass.
- **Note contract:** pins, rule and case ids, keys absent from conf and
  code, no `IncludePlayerbots` key, and fingerprints equal to the script.

`.github/workflows/f14-who-listing-s1.yml` runs those tests and the
fingerprint against a sparse checkout of the pinned core.

**Future S2 negatives** (native, then in game, owner-approved only):

- the byte-level stock parity above against the real handler;
- a stage change without relog;
- an IP Random Bot force-updated to its leader's stage;
- Blood Elves and Draenei on the opposite faction, with and without RBAC 28;
- a hidden race combined with GM invisibility;
- more than 49 legal rows;
- O1 own-name search;
- IP disabled and `ProgressionLimit` 1–7.

## 6. What this branch does not do

No C++ hook, no conf key, no loader line. No core, IP or Playerbots
change. No SQL or DBC. No claim of in-game or client behaviour.

— CosmicScript03
