# Naxxramas Core — Project Roadmap & Development Status

**Project:** [CosmicCuddle / Mod-Naxxramas-Core](https://github.com/CosmicCuddle/Mod-Naxxramas-Core)  
**Platform:** AzerothCore, World of Warcraft 3.3.5a  
**Roadmap snapshot:** 10 October 2026  
**Established release baseline:** 1.0.6.8.4  
**Current development line:** **1.0.6.8.5**  
**Primary active workstream:** Naxxramas Talent Calculator `NT1` → Playerbots integration

> This is the central project-status and forward-development roadmap. It describes the repository's implemented systems, known risks, development milestones, release boundaries and verification requirements. It is **not** a claim that every commit on `main` has been compiled, installed or tested on the running server.

## 1. Project direction

Naxxramas Core is the home for server-specific systems, custom class and racial mechanics, seasonal event behaviour, Individual Progression integrations and Playerbot extensions. The objective is to preserve a maintainable AzerothCore WotLK 3.3.5a foundation while offering stage-appropriate Vanilla → TBC → WotLK experiences.

### Architectural principles

1. **Changes belong to Naxxramas Core.** Prefer documented hooks, existing public interfaces, self-contained C++ systems, separately reviewed SQL and matching client/server DBC assets where necessary.
2. **Playerbots is upstream-owned and read-only.** No Playerbots edits, fork patches, replacement files or reapplication after `git pull`. This is an absolute requirement for the NT1 talent-import project. Playerbots may be inspected and called through compatible existing interfaces.
3. **Avoid AzerothCore core-file changes.** Existing AzerothCore hooks/`CommandScript`/`PlayerScript` interfaces are preferred. A system requiring an upstream patch should be presented as a limitation, not installed silently.
4. **Individual Progression remains separately maintained.** Naxxramas Core can respect its stages, limits and configuration without replacing its own logic or modifying its repository.
5. **Every consequential change is reversible.** Back up source, active configuration, affected database rows/tables and known-working DBC files before migration. Include installation prerequisites, verification and rollback instructions for new systems.
6. **Source, compiled, installed, enabled and in-game-tested are separate statuses.** No feature is considered released because its code is on GitHub.
7. **Protect existing gameplay.** Check possible conflicts with Playerbots, IP, client DBCs, SQL, existing custom spells and normal AzerothCore functionality. Avoid unrelated reward, character, or progression changes.
8. **Preserve original interfaces.** Custom extensions should not break existing Playerbots whisper commands or other original functionality.

## 2. Release management

The baseline documentation covers **1.0.6.8.4**. New work remains part of **1.0.6.8.5** until the administrator explicitly starts a different version.

| Release document | Scope |
| --- | --- |
| **Patch Notes 1.0.6.8.5** | Primarily DBC modifications, new/altered spells, talent-data changes, and matching client patch requirements |
| **Change Notes 1.0.6.8.5** | Naxxramas Core C++, configurations, SQL, events, Playerbot systems, compatibility work and server-side fixes |
| **Both documents** | Features that have independent server implementation and DBC/client changes; distinguish those changes instead of duplicating the same description |

The repository's `CHANGELOG.md` is a source-development record; a source entry does not establish successful deployment. Entries labelled *unreleased* remain unreleased unless a separate release decision is made.

**For 1.0.6.8.5 so far:** the new NT1 Playerbot integration, its C++ coordination changes and optional characters SQL belong to the **Change Notes**. The latest Warlock/Shaman capstone corrections change server import validation only; no accompanying DBC edit has been made in this workstream. DBC-focused changes, if introduced later, must be recorded separately in Patch Notes.

### Status vocabulary

- **Source present** — committed implementation exists; current deployment/compilation may be unknown.
- **Previously tested** — a specific earlier version/test is documented; this is not certification of the latest source.
- **Build/test pending** — latest relevant source has not been confirmed compiled and tested on the server.
- **Experimental / off by default** — code exists behind a configuration gate and must not be treated as ready for production.
- **Paused** — explicitly on hold; not a hidden active assignment.
- **Cancelled** — no longer in scope.

## 3. Current repository map

`src/NaxxramasCore_loader.cpp` is the registration point for the module's script systems. Major source ownership:

| Area | Primary locations | Purpose |
| --- | --- | --- |
| Classes | `src/Class/Warrior/`, `src/Class/Warlock/`, `src/Class/Shaman/`, `src/Class/Mage/` | Rend Flurry, Improved Rend, Wrack, Rockbiter, Arcane Momentum |
| Racials | `src/Racials/{Orc,Troll,BloodElf,Forsaken}/` | Blood Fury, Berserking, Arcane Torrent, Touch of the Grave |
| Events | `src/Events/` | Brewfest, Hallow's End and monthly Elemental Invasions |
| Items | `src/Items/` | Green Whelp Armor and item spell behaviour |
| Core systems | `src/Systems/` | Honor, PvP, mail, Playerbot consumables/talents, Meeting Stones, Battleground queues |
| Config | `conf/mod_naxxramas_core.conf.dist` | Distributed defaults; active installed config must be checked independently |
| SQL | `data/sql/db-world/` and `data/sql/db-characters/` | Separate world/characters migrations and required DB state |
| DBC specification | `docs/DBC-CHANGES.md` | Spell, Talent and SkillLineAbility IDs plus backup checks; raw DBCs are not stored in this repository |
| Feature acceptance | `docs/*.md` | Per-feature implementation, testing, limitations and rollback details |

**External related projects** (independent ownership):

- [Naxxramas Resource Hub / Talent Calculator](https://github.com/CosmicCuddle/Naxxramas-Resource-Hub) — [live talent calculator](https://cosmiccuddle.github.io/Naxxramas-Resource-Hub/talents/).
- [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots) — upstream read-only dependency; never patch it for NT1 imports.
- Individual Progression — separate AzerothCore module; keep its native progression rules authoritative.
- [N Classic Battlegrounds](https://github.com/CosmicCuddle/N-ClassicBattlegrounds) — standalone client addon; the copy in this module's `addons/` directory is a **historical backup**.
- **MultiBot fork** — potential user interface for the NT1 apply command once the server feature is stable; specific fork repository link is not recorded in this repo roadmap.

## 4. Feature inventory and verification position

The table records **repository state**, not assumed production installation. Detailed behaviour remains documented in `README.md` and each feature's linked guide.

| System | Existing scope | Current release / verification position |
| --- | --- | --- |
| Warrior custom talents | Rend Flurry (Talent 3000 / Spell 90054), Rend Flurry Strike (90055), shared ICD (90056), Improved Rend rank 3 (90057), Improved Heroic Strike (12282) | Source present; requires matching server/client DBC. Review `docs/DBC-CHANGES.md` and prior migration issues before changing live data |
| Warlock custom abilities | Wrack and bot support in `src/Class/Warlock/` | Source present; talent mechanics, eligibility and bot usage require regression tests alongside future DBC changes |
| Shaman | Rockbiter restoration/system in `src/Class/Shaman/` | Source and world SQL present; confirm exact spells in active client/server data |
| Mage | Arcane Momentum directional Blink with per-character preference | Source and two SQL migrations present; check build, SQL installation and map/collision cases before claiming deployment |
| Racial systems | Orc Blood Fury, Troll Berserking, Blood Elf Mana Tap/Arcane Torrent, Forsaken Touch of the Grave and related DBC work | Source/SQL and DBC-dependent entries present; preserve spell IDs and run race/class tests after DBC updates |
| Honor / PvP | Honor Overflow, fortnightly Honor Reset, forced PvP in Silithus and Eastern Plaguelands | Existing systems in source; live schedules, config and test state must be read from the server |
| Same-account mail | Alt mail delivery delay | Existing source; preserve current functionality |
| Events | Brewfest Dark Iron attack timing and sober gossip; Hallow's End Shade event | Existing source/SQL where applicable; event-specific tests required |
| Items | Green Whelp Armor proc behaviour | Existing source; regress item proc limits |
| Playerbot consumables | Raid and dungeon preparation, level-scaled profiles, instance boundaries, cooldowns, status/cleanup | Extensive existing implementation; see `README.md`, preserve all command and safety behaviour |
| Playerbot talent row limits | Level-based Vanilla/TBC row restrictions | Source present; must remain compatible with the calculator's capstones and ordinary bot talent allocation |
| Playerbot talent completion | Template matching, bot-only delayed finishing and exact chat-plan guard | An earlier version had a successful level-60 Frost Mage test; newer chat-plan/NT1 coordination changes require recompilation and regression tests |
| Classic Meeting Stones | Vanilla interaction restricted, normal summon functionality from IP TBC onward | Source present; **latest build and live tests pending**. Distributed config enables it, but active installed value is unknown |
| Battlemaster-only BG queues | Stage-13 WotLK remote queue unlock; battlemaster access below it | **Experimental/off by default;** C++ build and live validation pending. Separate addon visual state is independent |
| Monthly Elemental Invasions | Calendar-based event 13: first of month for five calendar days | **Experimental/off by default;** special world-event SQL and server tests needed |
| NT1 Playerbot talent importer | Read-only preview, separately gated experimental apply, exact rank checks and recovery attempt | **Active 1.0.6.8.5 development; not yet compiled or tested.** Full bot maintenance protection is unfinished |

### Configuration and data cautions

- A value in `.conf.dist` is **not evidence of the active server value**. Not every existing system defaults to 0; audit the actual installed `mod_naxxramas_core.conf` before restarting.
- The fortnightly honor schedule uses an anchor **2026-10-07 at 06:00 server-local**, interval two weeks, Wednesday. Recheck live state and characters DB marker rather than assume the reset has occurred.
- Monthly invasions rely on `game_event.eventEntry=13` with `world_event=5`, and the configured server-local timezone; website countdown clock and server clock must agree.
- DBC custom data must be kept consistent across server `dbc` and client patch distribution. DBC files themselves are not committed here. Read `docs/DBC-CHANGES.md` before changes to talent spell positions, ordering or rank mapping.
- SQL under `db-world` and `db-characters` targets **different databases**. Do not assume adding a file to GitHub means it was applied to production.

## 5. Priority workstream — NT1 Talent Calculator → Playerbots (1.0.6.8.5)

### 5.1 User-facing objective

A player builds a class spec in the Resource Hub's custom Vanilla/TBC/WotLK talent calculator, copies its `NT1` code and applies **exactly that build** to an eligible Playerbot. **Only builds spending the bot's entire server-computed talent-point budget are eligible for NT1 apply**; under-allocated codes can be previewed but must be rejected before resetting anything. Talent resets and rollback are experimental; random-bot builds are session-scoped and may be replaced by normal Playerbots maintenance.

Desired server commands:

```text
.naxxbot talents preview <online-botname> <NT1-code>
.naxxbot talents apply <online-botname> <NT1-code>
```

**Preferred final interface:** a convenient control in the user's **MultiBot fork**, after server-side acceptance. MultiBot must not be changed as a substitute for unfinished server safeguards. GM commands remain supported and require an online recognized bot. A single **NT1 AccessMode** setting and per-bot ownership checks are staged in Naxxramas Core but are **not yet compiled or tested**. MultiBot addon integration remains a future task.

### 5.2 Format and data contract

- `NT1:era:class:talentID-rank.talentID-rank...`, with **Talent.dbc IDs encoded in base 36**, not server spell rank IDs and not Playerbots' positional talent format.
- Class and era come from the code; the `level=` URL query is **separate**. Available talent points are calculated from the bot's actual level/server rules.
- `vanilla` uses a level-60 cap; `tbc` level 70; `wotlk` level 80; Death Knights are WotLK-only.
- Talent eligibility follows actual loaded `Talent.dbc`, `TalentTab.dbc` and `Spell.dbc`, including custom talents and dependencies. The website is based on a previous live-server snapshot, so a future DBC revision requires compatibility verification.
- The supplied sample **level-60 Warrior** code contains 16 selections totaling **49 points**, leaving **2 unspent** out of the normal 51. This is now an explicit **preview-only negative test:** apply must refuse it without modifying the bot.

**Corrected Vanilla capstones (confirmed in the current calculator and importer):**

| Tree | Correct Vanilla final-row talent | Side talent excluded from Vanilla |
| --- | --- | --- |
| Shaman Enhancement, TalentTab 263 | **Dual Wield**, Talent **1690** | Stormstrike, Talent **901** (available from TBC) |
| Warlock Affliction, TalentTab 302 | **Contagion**, Talent **1669** | Dark Pact, Talent **1022** (available from TBC) |

The sole **TBC off-centre capstone exception** is Paladin Holy **Divine Illumination**, Talent **1747** on TalentTab **382**. Previously generated Vanilla codes selecting Stormstrike or Dark Pact should **fail validation**, not be silently remapped. The `NT1` wire format itself does not change.

### 5.3 Source already staged

- `src/Systems/BotTalentImport.cpp`: parser, base-36 conversion, DBC/rank/class/era/point validation, simulation of purchase order, read-only `preview`, and experimental `apply` whenever AccessMode 1 or 2 is enabled.
- `src/Systems/BotTalentExpansionLimits.cpp`: importer-scoped exception for the **single** off-centre TBC talent; other Playerbots commands retain original row limits.
- `src/Systems/BotTalentCompletion.cpp`: importer-scoped coordination to avoid unwanted completion effects during a full NT1 import and to preserve restoration of older bot snapshots, which might legitimately be incomplete.
- `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`: **optional additive characters table** (`mod_naxxramas_bot_talent_import`) for code per character GUID/spec; not proof of automatic restoration.
- `docs/PLAYERBOT-NT1-TALENT-IMPORT.md`: feature design, test matrix, operational constraints, rollback and known limitations.
- `conf/mod_naxxramas_core.conf.dist`: **one setting** for the whole NT1 system:

```ini
# 0 = Disabled
# 1 = GM accounts only (preview and experimental apply)
# 2 = All players (preview and experimental apply)
NaxxramasCore.BotTalentImport.AccessMode = 0
```

Modes 1 and 2 allow talent resets when authorised callers use `apply`. Mode 0 is the only disabled mode; there is deliberately no preview-only configuration. Non-GMs in mode 2 must control the target bot. The importer attempts to restore the previous build after failure, but **this is not an atomic database transaction**. Keep mode 0 until full database backup and recovery steps are verified.

### 5.4 Current limitations / risks

| Issue | Consequence | Resolution required |
| --- | --- | --- |
| Latest code not yet compiled/tested | Source and in-game behaviour could disagree | Compile and validate in a backed-up test environment; start with first genuine C++ compiler error |
| Playerbots automated allocation/maintenance | Can change or reset approved builds later | Define and test module-only protection and repair policy; do not modify upstream Playerbots |
| AzerothCore `OnPlayerTalentsReset` hook cannot veto reset | Absolute zero-transient-reset guarantee is not proven | Detect/reconcile when safe; disclose any unavoidable timing limitation |
| Experimental apply recovery is best-effort | A failed learn, exception, or crash can leave incomplete state | Full characters DB backup, isolated disposable bot, forced-failure/relog tests, explicit fail-closed behaviour |
| SQL stores desired code only | Stored code is not active enforcement or restoration | Implement verified module-only reapply/consistency checks and stale-row cleanup |
| Random Playerbots | Full randomisation may replace talents, including in an active party | **New source-only, untested:** guarded apply for a random bot grouped with the invoking human master or group leader (when no master); no persistent NT1 profile, no automatic maintenance protection |
| Era checks are currently level-based in relevant Playerbot safeguards | An IP stage may differ from a bot's level | Define expected IP-tier policy and test across mismatched level/stage scenarios without guessing |
| Custom active abilities | Learned talents may not have AI rotations | Separate spell-use and AI integration audit after import is stable |
| Normal-player and MultiBot permissions | Source now requires AccessMode 1 (GMs) or 2 (authorised players) for both commands, plus a same-account/current AI-master check for non-GMs; not yet runtime-tested | Compile, test authorisation-denial matrix and preserve server-side checks before addon integration |

### 5.5 Milestones and exit criteria

**M0 — Build and baseline, next immediate milestone — NOT VERIFIED**

- [ ] Back up current module revision, live config and characters DB before any destructive test.
- [ ] Pull reviewed `main` on the live server only after preserving the installed revision; record Naxxramas Core, AzerothCore and Playerbots commit SHAs.
- [ ] Resolve actual compiler errors, if any, within **Naxxramas Core only**.
- [ ] Restart Worldserver with `NaxxramasCore.BotTalentImport.AccessMode=0`; verify startup/module dependency logs before considering experimental mode 1.
- [ ] Preserve ordinary Playerbots `talents spec`, `talents apply` and existing manual row rules.
- [ ] Record actual outcomes and build evidence; no claims of success until then.

**M1 — NT1 validation — TWO FIELD CHECKS PASSED; FURTHER TESTS PENDING**

- [ ] Live realm only: keep `AccessMode=0` until a verified characters DB backup and disposable-bot recovery procedure are ready. Then test `AccessMode=1` GM preview before any explicitly approved apply attempt.
- [ ] Verify the supplied Warrior 49/51 build against the server's current DBC.
- [ ] Test correct Vanilla Dual Wield and Contagion, and rejection of Vanilla Stormstrike/Dark Pact; verify TBC versions remain available.
- [ ] Test missing/wrong class, invalid format/version, duplicate IDs, incorrect ranks, incomplete prerequisites, excess point budget, and malformed input.
- [ ] Confirm zero character changes from `preview` and denied/invalid requests. `apply` can alter talents in either active mode.

**M2 — Safely replace an existing bot build — EXPERIMENTAL SOURCE; NOT APPROVED FOR LIVE**

- [ ] Review pre-reset validation and current-build snapshot/restore for all classes and both spec slots.
- [ ] Check and review the additive SQL table on the **backed-up live characters DB**; verify restore procedures before any destructive test.
- [ ] Test full apply on disposable **non-random** bots, requiring **0 unspent points**; separately test that an under-allocated code is rejected before reset.
- [ ] Compare all final talent ranks, old talent removal, learned spells, passive auras, trained skills and pet-related changes where relevant.
- [ ] Force runtime learning failures; verify rollback both in memory and after relog. Define handling for unrecoverable restoration failures.
- [ ] Because this project has no isolated test realm, limit any expressly approved experimental application to a disposable non-random bot with a known recoverable backup; never equate that trial with production readiness.

**M3 — Persistence and normal Playerbots maintenance — NOT IMPLEMENTED**

- [ ] Reload desired profiles on bot relog and server restart without overwriting unrelated specs.
- [ ] Differentiate deliberate user respec, level-up, planned import and unwanted automated maintenance.
- [ ] Prevent or safely reconcile free-point auto-fill, unwanted template replacement and maintenance resets; test ordinary and random bots distinctly.
- [ ] Document any unavoidable reset timing limitation under the strict no-Playerbots-modification requirement.
- [ ] Verify normal Playerbots update/`git pull` does not require restoration patches.

**M4 — Player-facing MultiBot integration — WAITING ON STABLE SERVER API**

- [ ] Identify the actual MultiBot fork repository and current UI command/permission model.
- [ ] Implement the **single primary apply action** for a chosen bot and copied NT1 code, with clear validation/results.
- [ ] Verify the new opt-in normal-player config and server-side bot ownership/master checks in-game; no addon command may bypass server RBAC or character ownership restrictions.
- [ ] Keep Playerbots untouched, and release addon-side changes through the MultiBot fork only.

**M5 — Custom talent combat AI — SEPARATE FOLLOW-ON WORK**

- [ ] Audit custom active talents, modified existing abilities, passive effects and talent-dependent rotations.
- [ ] Determine whether module-only hooks support missing bot decisions. Do not presume a learned spell is automatically selected by AI.
- [ ] Publish explicit supported/unsupported abilities; do not patch Playerbots as a shortcut.

**M6 — 1.0.6.8.5 release readiness — NOT COMPLETE**

- [ ] All desired changes classified into Patch Notes vs Change Notes.
- [ ] Exact database/DBC compatibility matrix and rollback steps documented.
- [ ] Build, deployment and game tests recorded against specific revisions.
- [ ] Release candidate reviewed; no disabled experiment advertised as enabled gameplay.
- [ ] Preserve an exact pre-release source/config/DB/DBC backup for rollback.

## 6. Other active or pending verification tracks

These are **separate from NT1**. Do not imply that importing talents is a prerequisite for their normal operation.

### Era-authenticity and Individual Progression

- **Classic Battlemaster queue enforcement:** currently off by default. Test real Battlemaster access, remote queue blocking, mixed-IP parties, GM/Playerbot exemptions, and TBC/WotLK transitions. See [Classic Battlemaster Queues](docs/CLASSIC-BATTLEMASTER-QUEUES.md).
- **Meeting Stones:** source registered; test Vanilla-disabled/TBC-enabled behaviour with mixed player levels and IP stages. The distributed config currently has ClassicMode enabled; check live config separately.
- **N Classic Battlegrounds addon:** now maintained in its own repository; test Arena visibility before stage 8, Wintergrasp visibility before stage 13, and Battleground UI/access without mistaking cosmetic hiding for server enforcement.
- **Monthly Elemental Invasions:** module source + optional SQL present, schedule 1st through start of 6th (five calendar days). Recheck server-local timezone against the Resource Hub countdown; test start/end/restart and other-event isolation. See [Elemental Invasions](docs/ELEMENTAL-INVASIONS.md).

### Existing module regressions after recompilation

- Playerbot talent completion/template guard at level 60 and 70, including the exact Wrack hybrid scenario described in [Playerbot Talent Completion Tests](docs/PLAYERBOT-TALENT-COMPLETION-TESTS.md).
- Playerbot consumables scoped to the correct instance, grouped eligible bots, cooldown and cleanup; especially `.bot consumables mc` and `.bot consumables status`.
- Warrior Rend Flurry and Improved Rend effects, rank mappings, cooldowns, spell tooltips and talent tab ordering.
- Mage Arcane Momentum persistence and movement/collision; Shaman Rockbiter; Warlock Wrack bot support.
- Custom racials, Honor Overflow, fortnightly Honor Reset and forced PvP restore semantics.
- Seasonal event overrides, custom item proc restrictions, mail behaviour and world/characters SQL prerequisites.

Tests in older documentation describe past work or intended behaviour; they are not a blanket sign-off on current `main`.

## 7. Deliberately paused or cancelled

| Initiative | Decision | Current requirement |
| --- | --- | --- |
| Era-dependent mount summoning (3 s Vanilla/TBC, 1.5 s WotLK) | **Cancelled** | Prototype and optional core patch removed. Leave original AzerothCore behaviour. Git history preserves old experimentation only |
| 40-player passage through BRD into Molten Core | **Paused** | Core instance-cap limits prevent a safe simple PlayerScript workaround. No implementation approved; existing BRD-first-entry/attunement behaviour unchanged |
| Other UI/quality-of-life era restrictions | **Not selected** | Do not alter Hearthstone, mail, achievements, calendar, Equipment Manager, dungeon maps, quest-map conveniences, quest scrolling or talent preview merely as part of the era-authenticity initiative |

See [Era Authenticity Decisions](docs/ERA-AUTHENTICITY-ROADMAP.md) for the original decision context. Paused work is **not** part of the current NT1 milestone sequence.

## 8. Backup, deployment and rollback model

**Before any test or production change:**

1. Record current module commit, AzerothCore revision and Playerbots revision; preserve the current installed configuration.
2. Back up the **characters** database (especially talents) and the **world** database rows affected by SQL. Test restore procedures with copies.
3. Back up all known-working server and client DBC files and associated MPQ/client patches where relevant.
4. Review the migration under the correct `data/sql/` database; use HeidiSQL exports or a tested dump before applying it.
5. Compile and inspect the **first real compiler error** rather than relying only on a final `make` failure line.
6. Run narrow tests first, then regression tests, and distinguish “loaded” from “functioned correctly.”
7. If rollback is required, disable the feature in the **active** config; restore SQL/DBC/character data from the correct backup when necessary. A Git revert does not undo a deployed SQL edit or restore altered character talents.
8. Avoid broad `git reset --hard` or deleting build directories as a routine rollback method.

For NT1 specifically, installing `mod_naxxramas_bot_talent_import` is a separate characters SQL decision, **not** an automatic byproduct of `git pull`. Turning off import application also does **not** undo any talents that might already have been applied.

## 9. Open decisions / information still requiring confirmation

- Exact current live deployment: compiled module revision, installed config values, database migrations and running DBC versions cannot be inferred from GitHub alone.
- Whether the live server currently uses only level-based talent limits for bots or needs a future IP-stage-aware policy.
- Which specific bot types should receive persistent custom NT1 builds and whether their natural full randomisation should remain authoritative.
- The user-facing permissions model and GitHub location of the actual MultiBot fork.
- Runtime build/test results for new NT1 importer and other unverified features.
- Whether client/server DBC changes are being introduced separately for **Patch Notes 1.0.6.8.5**.

## 10. Reference index

| Topic | Source of detail |
| --- | --- |
| Full module feature descriptions and install baseline | [README](README.md) |
| Release/source changes | [CHANGELOG](CHANGELOG.md) |
| NT1 source/format, tests, rollback and future MultiBot plan | [NT1 Talent Import](docs/PLAYERBOT-NT1-TALENT-IMPORT.md) |
| Playerbot manual completion regressions | [Talent Completion Tests](docs/PLAYERBOT-TALENT-COMPLETION-TESTS.md) |
| Client/server DBC requirements and spell IDs | [DBC Changes](docs/DBC-CHANGES.md) |
| Monthly invasions world SQL and calendar behaviour | [Elemental Invasions](docs/ELEMENTAL-INVASIONS.md) |
| Battlemaster validation and addon | [Classic Battlemaster Queues](docs/CLASSIC-BATTLEMASTER-QUEUES.md) |
| Cancelled and paused era ideas | [Era Authenticity Roadmap](docs/ERA-AUTHENTICITY-ROADMAP.md) |
| Obsolete talent-rank migration / runtime issues | [Troubleshooting](docs/TROUBLESHOOTING.md) |

---

#### Field verification — 10 October 2026: first NT1 in-game preview (earlier revision)

- **Reported deployment evidence:** administrator pulled and recompiled the module, restarted Worldserver, and supplied an in-game screenshot showing the new `.naxxbot talents preview` command running. The compiler output, exact installed commit SHA and Worldserver startup log have **not** been independently reviewed, so M0 is only **partially evidenced**, not fully signed off.
- **M1 positive test PASS (one sample):** online Playerbot **Catarea (level 60 Mage)**, code `NT1:vanilla:mage:11-5.12-2.1p-3.1q-3.1r-2.1s-2.1u-3.1v-3.1w-3.1x-1.1z-1.20-1.21-3.22-2.23-5.24-3.2d-1.kl-2.19t-3.1f9-3`. Worldserver responded `NT1 valid`, `51 planned / 51 available`, `0 deliberately unspent`, `Talent trees (server tab order): 14 / 0 / 37; 20 talent entries`, and `Read-only validation: no talents have been reset or applied`.
- **Scope of evidence:** establishes command invocation and successful read-only DBC-based validation for **this Mage code only**. No talent-application attempt or persistent-talent check was performed; status of unrelated Playerbots commands, other classes, malformed-code rejection, intentionally unused points, real talent side effects and runtime failure recovery remains **unverified**.
- **Remaining validation cases (next compiled revision):** wrong class, malformed code, invalid rank/era, deliberately unspent points, valid 49/51 Warrior, and corrected Vanilla Shaman/Warlock capstones. `AccessMode=0` denies all NT1 commands. With mode 1/2 enabled, `preview` is read-only but `apply` is **not** disabled. Perform these tests only under the current live-realm backup and disposable-bot safeguards described below.
- **No changes in this verification step:** server source files, DBC, SQL, or client patches; this is a documentation-only status record based on the supplied game screenshot.

#### Historical checkpoint — 10 October 2026: permission drafts (superseded)

- Initial drafts separated master activation, non-GM permission and experimental application into three configuration toggles; a later draft combined some permissions. Those drafts were **never compiled or tested** and their configuration instructions must not be used.
- The requested final design superseded them all: `NaxxramasCore.BotTalentImport.AccessMode` is the **only** active NT1 setting. Mode 0 disables the feature; mode 1 grants GMs preview and experimental apply; mode 2 grants authorised players preview and experimental apply.
- Security decisions retained from the drafts: ordinary players require control of the bot by same account or its current Playerbots master, not just group membership. Destructive apply still rejects random bots.
- Permission and ownership regression cases remain untested against the new source: deny when mode 0, GM-only in mode 1, same-account/master access in mode 2, other-account denial, invalid command arguments and random-bot apply rejection.

#### Field verification — 10 October 2026: wrong-class rejection and usage-message fix (earlier revision)

- **M1 negative test PASS (one sample):** The administrator submitted `.naxxbot talents preview Catarea NT1:vanilla:warrior:11-5` to the online level-60 Mage. The server responded `NT1 rejected: Talent code class does not match the bot's class.` It correctly refused the Warrior code. No character change was requested.
- **Observed usability issue:** AzerothCore followed the intended rejection with `### USAGE: naxxbot talents preview ...` and `There is no detailed usage information...`. This was caused by Naxxramas Core's handlers returning `false` after already presenting the informative rejection message; it was **not** a failed validation guard.
- **Source fix staged for next build:** Both `preview` and `apply` handlers now return a handled result after reporting request validation failures. The `apply` handler also does so after reporting aborted application or malformed second-pass arguments. No validators, config defaults, permissions, DBC/SQL data, talent reset operations, or recovery logic were modified. **The updated source has not yet been pulled, compiled or retested in-game.**
- **Next regression test:** After deploying the new source, repeat the wrong-class preview to confirm a single clear NT1 rejection with no generic command-help spam. Enable mode 1 solely under approved backup/recovery test conditions; mode 0 blocks all commands. The prior read-only test occurred on an older revision.
- **Status:** Read-only valid Mage preview PASSED; wrong-class rejection PASSED; cosmetic command-response cleanup SOURCE ONLY / NOT YET TESTED; all other M1/M2/M3 acceptance cases remain outstanding.

#### Operational constraint — 10 October 2026: live-realm-only NT1 testing

- The administrator **cannot use a separate test realm** and intends to test on disposable bots in the existing live realm. This changes the planned test environment, **not** the acceptance criteria or the experimental status of talent application.
- Do **not** set `NaxxramasCore.BotTalentImport.AccessMode=1` or `2` merely because the earlier read-only preview succeeded. Both expose experimental `apply`; `ApplyValidated` invokes `resetTalents(true)` and recovery is not transactional or proven for live state.
- Prepare a **verified recoverable full backup** of the live characters database and active module config before any manual characters SQL migration or destructive test. Do not confuse the additive `mod_naxxramas_bot_talent_import` table (stores desired code) with backups of the pre-existing talents and derived spell effects.
- The SQL migration `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql` can be installed into an existing characters database; a second realm is not intrinsically required for its schema. Check first whether the table already exists. Do not apply it before the backup is confirmed. Installing the table alone is not an approval to enable apply.
- Use **only a newly made disposable, non-random account Playerbot**, with a deliberate pre-test record of character GUID, active/secondary spec and talent/spell state; normal/random bots, valued characters and public use are excluded from first destructive tests. No unsafe `DROP` or bulk character SQL is part of this plan.
- First pull/recompile/restart with `AccessMode=0` and check startup. Review real recovery/rollback details and obtain explicit approval for the residual risk **before** any live mode-1 trial with a disposable bot. Mode 2 remains for later ownership regression testing. Relog/restart, dual specs and Playerbots automatic retalenting remain unverified.
- The previously specified isolated-test acceptance step **has not been satisfied** and cannot be silently marked as passed. If restore capability or any prerequisite is absent, keep `AccessMode=0` and defer NT1 testing that could invoke `apply`.
- No SQL, DBC, server configuration or live talent changes were made by recording this handover constraint.

#### Latest configuration decision — 10 October 2026: one NT1 AccessMode

- **Final requested design:** exactly one setting `NaxxramasCore.BotTalentImport.AccessMode` with `0` disabled, `1` GM accounts, `2` all players. No preview-only mode. Both enabled modes permit the read-only `preview` command and experimental character-mutating `apply` command.
- **Replaces three obsolete settings:** `NaxxramasCore.BotTalentImport.Enabled`, `NaxxramasCore.BotTalentImport.AllowNonGMPlayers`, and `NaxxramasCore.BotTalentImport.ApplyEnabled`. The latest C++ no longer reads them; remove stale lines from the active `.conf` during deployment. The distributed `.conf.dist` now has only `AccessMode=0`.
- **Safety:** mode 0 rejects both commands; out-of-range values fail closed. Mode 1 requires GM security for both commands. Mode 2 additionally allows non-GMs who control the online Playerbot through same account or direct AI master. Random bots remain rejected by experimental apply; SQL table and validated old-build snapshot are still required.
- **Live-only deployment limitation:** no separate test realm. **Do not enable modes 1 or 2 on the live realm before confirming a recoverable characters backup and a disposable-bot recovery plan**, since both allow destructive talent resets. Preview-only testing is no longer possible through configuration with apply inaccessible.
- **Historical note (superseded by the newer field result below):** at the time this decision was documented, the new AccessMode source had not been compiled or game-tested. Subsequently the administrator reported a successful recompile/restart and demonstrated Mage preview again. Full rollback, normal-player permission matrix and automatic Playerbots maintenance protection remain incomplete.
- **Next actions:** back up characters DB and active config; stage additive SQL only after backup and table-check; deploy/recompile with mode 0; confirm denial/no startup failures, then decide on narrowly scoped mode-1 GM testing with disposable bot. Keep mode 2 for later ownership/auth testing. Update the roadmap after every test result.

#### Field verification — 10 October 2026: NT1 Mage preview after recompilation

- **Post-rebuild read-only test PASS (reported and screenshot-observed):** the administrator reports a successful compilation and Worldserver restart and ran `.naxxbot talents preview` against online level-60 Mage Playerbot **Catarea**. Chat returned `NT1 valid for Catarea (level 60 mage, era vanilla)`, `51 planned / 51 available; 0 deliberately unspent`, `14 / 0 / 37; 20 talent entries`, and `Read-only validation: no talents have been reset or applied`. This reproduces the positive M1 result on the later deployment.
- **Configuration context:** administrator planned `NaxxramasCore.BotTalentImport.AccessMode=1` (GM access), but the installed config, precise source SHA, build log and Worldserver startup log were not directly examined. This screenshot proves GM command invocation and validation, **not** full config/permission-matrix correctness.
- **Not yet tested:** destructive `apply`, characters-table presence, verified database restore, talent replacement/recovery, relog/restart preservation, Playerbots maintenance, normal-player permissions and rejection-message cleanup on this rebuilt revision.
- **Next safe action:** In HeidiSQL, run the read-only `SHOW TABLES LIKE 'mod_naxxramas_bot_talent_import';` against the characters database, and confirm that a full **restorable** characters backup is available before any SQL migration or experimental application. Do not use `.naxxbot talents apply` on Catarea or other valuable bots. Live realm only; use a newly created disposable non-random account bot for any later expressly approved M2 trial.
- **This note changes documentation only;** it does not install SQL, change character talents, modify any configuration, or prove acceptance of the experimental importer.

#### Field verification — 10 October 2026: NT1 characters-table discovery

- **Read-only HeidiSQL check PASS (administrator-reported):** on live database `acore_characters`, `SHOW TABLES LIKE 'mod_naxxramas_bot_talent_import';` returned `mod_naxxramas_bot_talent_import`. The required table name **exists** in the active characters database; no need to re-run the `CREATE TABLE` migration merely to create it.
- **Scope:** this proves **table existence only**, not schema/column conformity, permissions to write to it, persistence behaviour, full characters-database backup status, backup restorability, or successful application. No SQL insert/alter/drop or talent changes were carried out.
- **Next safe steps:** verify a restorable full `acore_characters` backup; optionally inspect `SHOW CREATE TABLE mod_naxxramas_bot_talent_import;` or `DESCRIBE mod_naxxramas_bot_talent_import;` against the checked-in migration. Identify a new disposable, **non-random** account Playerbot and record its GUID, old talents/spec before any destructive test.
- **Do not run `.naxxbot talents apply` yet.** Mode 1/2 exposes non-transactional, experimental changes; a live-only trial requires the backup and recovery plan before explicit approval.

#### NT1 characters-backup checkpoint — 10 October 2026

- **Administrator-reported backup:** user confirms that a backup of live `acore_characters` has been made, following the verified presence of `mod_naxxramas_bot_talent_import`. This establishes that an export or backup was created **but does not yet establish that it is complete, current or restorable**. Do not mark destructive-testing backup acceptance as passed until recovery/restore procedure is confirmed.
- **Next step (non-destructive):** run `DESCRIBE mod_naxxramas_bot_talent_import;` in HeidiSQL and compare columns with `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`: unsigned `guid`, unsigned `spec`, `code` varchar(2048), `updated_at` timestamp, composite primary key (`guid`, `spec`). If a primary-key check is needed, use `SHOW CREATE TABLE mod_naxxramas_bot_talent_import;` (also read-only).
- **Before first apply:** independently record the disposable, non-random account bot's GUID, active spec and old talents/spell state; confirm a backup restore path; agree on residual risk of a nontransactional reset on the live realm. Do not use valuable Mage Catarea as initial destructive target.
- **Status:** NT1 full-DB backup existence REPORTED, restore verification PENDING; table existence PASS; table schema and first experimental apply PENDING. No new SQL modifications or talent changes were carried out in this checkpoint.

#### NT1 table schema verification — 10 October 2026

- **HeidiSQL `DESCRIBE mod_naxxramas_bot_talent_import;` result (administrator-provided):** `guid` int unsigned NOT NULL PRI; `spec` tinyint unsigned NOT NULL PRI; `code` varchar(2048) NOT NULL; `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP. All four expected column names, declared data types, nullability and timestamp update behavior match the optional migration's intended definition.
- **Result: column-structure PASS.** `guid` and `spec` both display `PRI`, consistent with the intended composite key. The full `SHOW CREATE TABLE` output has not been inspected, so exact key order, `code` character set/collation, engine and migration parity are not independently verified.
- **Prior verification:** table existence in live `acore_characters` PASS, Mage read-only NT1 preview PASS on latest reported rebuild, administrator confirms characters backup **created**. Backup restore verification remains pending.
- **Next controlled stage:** determine a new disposable, non-random Playerbot on a normal bot account (bot name, class, level, GUID, current active spec), record its original talents/related spells and plan for recovery if `resetTalents(true)` is interrupted. Do not use valuable Mage Catarea for initial mutation tests.
- **Never mark M2 apply/persistence/rollback passed from a schema check.** `AccessMode=1/2` enables experimental `apply`; keep live risk explicit. No SQL/DBC/config modifications or talent changes occurred here.

#### NT1 initial application candidate — Ido (administrator selection)

- The administrator selected **Ido**, reported as a **level-60 Mage**, as the proposed first NT1 apply-test bot on the existing live realm. This is **candidate selection only**; no application is authorised by it.
- **Pending confirmation:** verify Ido is an online **non-random, account-controlled** Playerbot and not a valued character. The experimental importer rejects random bots when attempting to apply.
- **Immediate non-destructive action:** GM runs `.naxxbot talents preview Ido NT1:vanilla:mage:11-5.12-2.1p-3.1q-3.1r-2.1s-2.1u-3.1v-3.1w-3.1x-1.1z-1.20-1.21-3.22-2.23-5.24-3.2d-1.kl-2.19t-3.1f9-3`; expected 51 planned/51 available and 14/0/37. Do not claim this preview passed until an in-game result is supplied.
- **Before any destructive command:** record Ido's DB GUID, active spec, existing talents/spells and whether dual spec exists; validate that the administrator's reported full characters backup can actually be restored. The custom-profile table exists and `DESCRIBE` column data matched, but these facts alone do not validate character recovery.
- **Test discipline:** keep experimental `.naxxbot talents apply` unused until these prerequisites, the risk of a non-transactional reset, and an explicit test go-ahead are established. Record the first result here.

#### Field verification — 10 October 2026: Ido level-60 Mage read-only preview PASS

- **Screenshot-observed PASS:** administrator ran the NT1 `preview` command for **Ido**, an online **level-60 Mage** on the live realm. Server reported `NT1 valid for Ido (level 60 mage, era vanilla)`, `51 planned / 51 available; 0 deliberately unspent`, `14 / 0 / 37; 20 talent entries`, and `Read-only validation: no talents have been reset or applied`.
- **Scope:** Ido's Mage NT1 code passes validation on the reported post-recompile server. This does not demonstrate that `apply` works, overwrites the right spec, preserves spells/talents, survives relog/restart or can be rolled back. It also does **not** prove that Ido is a non-random account-controlled Playerbot.
- **Outstanding prerequisites before any destructive command:** confirm whether Ido is an account-controlled (non-random) bot, record its character GUID and active spec plus original talent/spell state, verify the reported full `acore_characters` backup has a real restore procedure, and explicitly accept the nontransactional recovery risk. Existing imported-profile table was found and its four columns inspected successfully.
- **No mutation in this step:** do not run `.naxxbot talents apply` yet; no SQL, DBC or config edits are part of this recorded result.

#### NT1 applicability discovery — Ido is a random Playerbot

- **User-confirmed 10 October 2026:** Ido (level-60 Mage), which successfully passed the full NT1 51/51 read-only preview, is a **randomly generated Playerbot**, not an account-controlled alt. The earlier roadmap item listed Ido as a possible first application candidate; **that candidate is not eligible under the current experimental importer**.
- **Existing source behaviour:** `ApplyValidated` rejects `sRandomPlayerbotMgr.IsRandomBot(bot)` before any reset or learning, with an explanatory error. Do **not** remove this safeguard just to force a first import; it prevents a false-positive result that Playerbots full randomisation could later overwrite.
- **Open decision:** either (a) select a disposable, non-random account-controlled bot for the first isolated apply/recovery trial or (b) intentionally extend the Naxxramas Core module to support random bots **after** designing and testing durable imported-profile ownership, maintenance reconciliation, restart/relog and manual-respec policies. Neither path has been authorised or tested yet.
- **For random-bot support:** audit actual Playerbots maintenance/reroll entry points and whether Naxxramas Core hooks can reliably preserve/reapply build intent without editing Playerbots or AzerothCore. SQL `mod_naxxramas_bot_talent_import` alone stores a code but does not provide maintenance enforcement. Define fail-closed handling, removal/restore of import locks, dual specs, level changes, random bot re-creation and intended user override, and reproducible negative tests before enabling random-bot mutations.
- **No destructive test has been run:** Ido's latest result is **preview PASS only**; importing onto a random Playerbot remains blocked and unverified. Keep the restorable characters backup, and use a non-random disposable bot only if the administrator chooses the existing experimental apply test plan.

#### Design direction — 10 October 2026: Temporary NT1 builds for grouped random Playerbots

- **User preference:** Permanent NT1 talent persistence on random Playerbots is **not required** if the player can apply the desired talent build while the random bot is grouped with them and use that build for the session. Returning to normal Playerbots talent allocation after the group ends, bot reroll, or a later reload is acceptable, provided the expected behaviour is explained and verified. This is an **implementation direction**, not proof that such a feature exists.
- **Current gate:** `src/Systems/BotTalentImport.cpp::ApplyValidated` still rejects `sRandomPlayerbotMgr.IsRandomBot(bot)` before reset. Do not advise trying `.naxxbot talents apply Ido ...` and expecting success. The user's successful Ido preview remains read-only.
- **Upstream source inspection:** In mod-playerbots, `RandomPlayerbotMgr::ProcessBot` can request `Randomize(bot)` when a bot becomes idle and its randomize event expires; `PlayerbotFactory::Randomize` contains `resetTalents(true)` and `InitTalentsTree()` paths subject to `EquipAndSpecPersistence`, level and incremental/full randomisation flags. Whether a user's party suppresses all relevant randomisation on their actual build/config is **not verified**; never promise no overwrite during a party without testing.
- **Important current persistence detail:** successful importer application uses `CharacterDatabase.DirectExecute` to save the NT1 code and `bot->SaveToDB(false, false)`. A temporary random-bot feature must explicitly define whether it stores any code and whether talent changes remain in the normal character DB after group leave. Merely leaving a party **does not itself restore previous talents**.
- **Proposed bounded module-only implementation (requires user agreement and review):** maintain the current existing random-bot deny guard until a safe new branch is developed; permit a random bot only if an actual online human player currently controls it as master and shares its group, check valid era/class/build and combat/out-of-combat preflight, then apply after snapshotting/validating original spec. Define protection or detection of any mid-group Playerbots rerandomisation, and a clearly documented group-exit/logout policy; avoid modifying mod-playerbots or AzerothCore. If temporary session intent is chosen, do not leave a permanent NT1 lock that will unexpectedly affect later random bot owners/sessions.
- **Acceptance:** GM versus non-GM authorisation, ability to apply valid code to an eligible grouped random Mage, exact resulting talent ranks/free points, talent-derived learned spells/AI availability, rejection of ungrouped/foreign-controlled random bot, group exit, owner change, death, restart/relog and expired randomisation events, failure restore path, and interactions with normal randomisation. Use a disposable random bot, current restorable `acore_characters` backup and explicit risk acceptance. This is an isolated future M2 variant, **not** already accepted.
- **Next question:** confirm whether the user expects the bot's talents to **remain intact throughout the party** even if its randomisation timer fires, and whether it's acceptable for them to **remain in saved character data until Playerbots naturally replaces them** after leaving (versus proactively restoring the old build at group exit). Do not implement persistence or auto-reapply without settling this distinction.

#### Field test — 10 October 2026: random Playerbot apply correctly rejected

- **User-supplied screenshot confirms PASS:** After a successful 51/51 Mage preview for Ido, administrator tried `.naxxbot talents apply Ido <valid Mage NT1 code>`. Server responded `NT1 apply aborted: Applying to random bots is disabled until automatic full-randomization behaviour has been verified.`
- This validates the **explicit random-bot fail-closed guard** for this playerbot and demonstrates clear handled error output without the previous generic command-usage spam. No successful talent replacement or random-bot maintenance compatibility was shown; this rejection occurs before the importer invokes `resetTalents`.
- **Follow-up design question from administrator:** Will NT1 apply to an account-controlled **Alt Bot**? Current C++ explicitly rejects `sRandomPlayerbotMgr.IsRandomBot(bot)`, so non-random Alt Bots are not excluded by this particular guard. Remaining requirements (online Playerbot, valid code, in-combat and alive checks, level-based era, existing talent snapshot validity, character table and save/recovery path) must still pass. Alt Bot apply is **source-supported but untested** and not certified safe.
- **Next controlled test:** if user elects, identify a disposable non-random account-controlled Alt Bot (name, level, class, prior talent state, current spec, GUID) with a verified restorable backup and run preview first; only then conduct an expressly approved live experimental application. Do not use valuable alt characters or interpret the random rejection as a general apply pass.
- **No change to source, SQL, DBC, configuration or character talents** was performed by this documentation entry.

#### Implementation checkpoint — 10 October 2026: grouped random Playerbot NT1 apply

- **Administrator request:** extend the importer so temporary NT1 talent builds can be applied to **random Playerbots**, not just account-controlled Alt Bots. Losing the imported build later when Playerbots rerandomises is acceptable; full permanent random-bot talent persistence is not required. Keep the existing single `NaxxramasCore.BotTalentImport.AccessMode` setting (0 disabled, 1 GMs, 2 authorised players); no new config switches.
- **Source changes committed, not yet compiled/deployed/tested:** `src/Systems/BotTalentImport.cpp` replaces the blanket `IsRandomBot` rejection with an explicit **live human in the same party or raid** check. Caller and bot must both be members of the same Group; the bot's current AI master must equal the caller, or if no master is assigned the caller must be the actual group leader. Other-human masters are rejected even for GM callers, and the existing non-GM per-bot access gate still applies.
- **Unchanged destructive-apply safeguards:** bot online/recognised, alive and out of combat, NT1 parsed and validated against class/era/DBC, current-build snapshot independently restorable, module SQL table existence checked before reset, exact post-learn audit with old-build restore attempt on failure. Random bots can still fail snapshot validation; never bypass this just to make an import appear successful.
- **Temporary profile policy:** on successful random-bot import, **no entry is written** to `mod_naxxramas_bot_talent_import` (unlike the Alt Bot path). The normal player character talents **are saved** with `SaveToDB`; leaving a group does **not** instantly restore the old spec. Future randomisation may overwrite the build **even during the group**, because automatic protection/reapply is not implemented. The confirmation message warns about this.
- **Upstream evidence:** `mod-playerbots/src/Bot/RandomPlayerbotMgr.cpp::ProcessBot` schedules `Randomize(bot)` for idle bots when the event expires, and `PlayerbotFactory::Randomize` may call `resetTalents(true)` and `InitTalentsTree()` depending on persistence settings and incremental/full rerolls. The new importer deliberately does **not** patch upstream Playerbots or guarantee a party-long build lock.
- **Status:** existing Ido level-60 Mage preview PASS and old blanket random-apply rejection PASS were observed on a previous compiled version. **This new random-bot application path has NOT been compiled, run in-game, or proven to work.** Normal Alt Bot code stays available but also lacks destructive-apply field acceptance.
- **Next controlled test:** refetch source SHA and `git status` on live server, back up active module config/source and verify the full `acore_characters` backup is recoverable, pull with `git pull --ff-only`, compile and restart. Test `preview Ido` first, then attempt `apply Ido` only with Ido grouped to the issuing human GM and recognised as master (or human group leader when AI master is null). Record exact command/error, original and resulting talent ranks, spells, behavior after randomization, party exit, relog/restart, and recovery. Stop if first compiler error, snapshot failure, unrelated reset or unexpected change; do not use valued characters.
- **Open follow-on task:** if party-time randomisation replaces builds too soon, design separately reviewed module-only drift detection/reconciliation and automatic expiry on departure. No hidden permanent lock or unconditional random-bot override.

#### Field verification — 10 October 2026: Husapze Mage preview after grouped-random-bot rebuild

- **Administrator screenshot — read-only preview PASS:** after reporting a successful pull/recompile and restart of the grouped random-bot NT1 source, administrator ran preview for **Husapze** (not Ido). Server reported `NT1 valid for Husapze (level 60 mage, era vanilla)`, `51 planned / 51 available; 0 deliberately unspent`, `14 / 0 / 37; 20 talent entries`, and `Read-only validation: no talents have been reset or applied.`
- **Interpretation:** this demonstrates that read-only NT1 validation still runs on the newer deployed version; exact installed source SHA and compiler logs were not independently reviewed. It does **not** verify random-bot eligibility, group/master authorization or destructive apply. The bot's random/alt classification has not been supplied in this turn.
- **Next safe step:** confirm whether Husapze is a random Playerbot and intended apply target, capture a read-only snapshot of Husapze's current GUID, active spec, talents and relevant known spells in HeidiSQL, and confirm recoverability of the user's full `acore_characters` backup. For a random bot, verify the human GM and bot are in the same group with appropriate AI master/group-leader authority. Only then attempt experimental `apply` with an explicit understanding that existing talents may change and Playerbots may rerandomise them.
- **No source, SQL or config changes were performed by this verification note.**

#### Field verification — 10 October 2026: Husapze identified as random Playerbot

- The administrator confirmed that **Husapze**, whose level-60 Mage NT1 read-only preview passed at 51/51 points and distribution 14/0/37 after the new grouped-random-bot source was reportedly rebuilt, is a **random Playerbot**.
- **Candidate selection:** Husapze replaces Ido as the current planned random-bot application candidate. No talent mutation has been reported; full backup existence is reported, restore path is still unverified.
- **Next step:** inspect `SELECT guid, name, class, level FROM characters WHERE name='Husapze';` in live `acore_characters`, then export/record the current talent and relevant spell rows by GUID and active spec before any destructive attempt. Keep Husapze alive, out of combat, grouped with the human issuing the command and actively mastered by that player (or allow the group-leader fallback only if the AI master is null).
- **Safety:** latest random-bot grouped apply is source-committed and user-reported rebuilt but has not yet demonstrated actual application, restoration or persistent session behavior. Do not mark random-bot M2 acceptance as passed.

#### Pre-apply identity and baseline queries — 10 October 2026: Husapze GUID 73209

- **HeidiSQL result provided by administrator:** on live `acore_characters`, `SELECT guid, name, class, level FROM characters WHERE name='Husapze';` returned `73209 | Husapze | 8 | 60`. Class 8 is **Mage**. Earlier user confirmed Husapze is a **random Playerbot**; full 51/51, 14/0/37 NT1 preview passed.
- **Before attempting application:** record `characters.activeTalentGroup` and `characters.talentGroupsCount`, both spec masks and existing talent rank spell IDs from `character_talent`, and learned spells from `character_spell`; preserve a separate export of Husapze's current rows (full characters backup was made but **restorability has not been verified**). Do not write directly to any character table.
- **Read-only SQL:**

```sql
SELECT guid, name, class, level, talentGroupsCount, activeTalentGroup
FROM characters WHERE guid=73209;

SELECT guid, spell, specMask
FROM character_talent WHERE guid=73209 ORDER BY specMask, spell;

SELECT guid, spell, specMask
FROM character_spell WHERE guid=73209 ORDER BY spell;
```

- **AzerothCore base-schema verification:** `data/sql/base/db_characters/characters.sql` defines `talentGroupsCount` and `activeTalentGroup`; `character_talent.sql` defines `guid, spell, specMask`; `character_spell.sql` defines `guid, spell, specMask`. Actual live custom schema may differ, so stop and inspect if a read-only query fails.
- **Experimental-scope caution:** the `apply` operation uses `resetTalents(true)` and `SaveToDB`, and random bot talent sets can be replaced by automatic Playerbots maintenance. A party/master check and read-only success are not proof of safe rollback. No actual apply yet verified.

#### Pre-apply baseline — 10 October 2026: Husapze GUID 73209 baseline talent rows confirmed

- **Read-only live HeidiSQL response from administrator:** `characters` row `guid=73209`, `name=Husapze`, `class=8` Mage, `level=60`, `talentGroupsCount=1`, `activeTalentGroup=0`. These were read from `acore_characters` for the random Playerbot selected for the first grouped-import test.
- **Saved-character talent baseline:** 21 rows returned by `SELECT guid, spell, specMask FROM character_talent WHERE guid=73209 ORDER BY specMask,spell;`. All have `specMask=1`, representing the first talent group. The spell IDs, in ascending order, are: 11426, 11958, 12469, 12472, 12488, 12577, 12592, 12606, 12840, 12953, 12983, 15047, 16758, 16766, 18462, 28593, 29440, 29444, 44397, 54646, 55094. These are **talent-rank spell IDs**, not Talent.dbc entry IDs, and do not imply 21 talent points.
- **Limit of this baseline:** SQL reflects database-persisted character data, not guaranteed to equal the currently online bot's full in-memory state. Imported talent source's preflight must independently verify its own restorable in-memory snapshot; a previously invalid/legacy talent layout may be rejected before any reset.
- **Next non-destructive query:** `SELECT guid, spell, specMask FROM character_spell WHERE guid=73209 ORDER BY spell;` and ideally export both `character_talent` and `character_spell` result sets to a dated local file via HeidiSQL. If the spell result is lengthy, attach the exported CSV rather than typing every line. No DELETE/UPDATE/INSERT is needed.
- **Destructive acceptance not reached:** full `acore_characters` backup reported by administrator, but restore process is unverified; no observed result yet from grouped random-bot `apply`, and normal Playerbots randomisation may overwrite the requested build even within a party. Do not claim apply succeeded.

#### Field test — 10 October 2026: Zevon random Playerbot apply SUCCESS (first live positive result)

- **User-supplied screenshot and confirmation:** the administrator tried the deployed `.naxxbot talents apply Zevon NT1:vanilla:mage:11-5.12-2.1p-3.1q-3.1r-2.1s-2.1u-3.1v-3.1w-3.1x-1.1z-1.20-1.21-3.22-2.23-5.24-3.2d-1.kl-2.19t-3.1f9-3` on **Zevon**, reported as a newly found eligible random Mage Playerbot after Husapze logged out.
- **Actual game chat confirms:** `NT1 build applied to Zevon: 51 spent / 0 unspent.` It then prints `Random Playerbot: session-scoped build only. Playerbots may replace talents during randomization; no permanent NT1 profile was saved.` The administrator explicitly confirmed **"Yes it worked"**.
- **M2 field result:** the guarded **random-bot application path has passed its first live command-level success** following user-reported pull, compilation and restart. The code only emits this success after `LearnValidated` verifies rank spell state/free talent points in memory; it does **not** prove a separate visual talent window inspection, persistent behavior, learned spell/rotation correctness, no drift during a party, relog/restart or full rollback.
- **Target note:** earlier in this session Husapze (random Mage) passed read-only preview (51/51, 14/0/37) and had a DB-baseline captured at GUID 73209. Husapze logged out before application. **The successful target was Zevon, not Husapze.** Zevon's GUID and pre-apply DB rows were not supplied. Do not conflate their baseline data.
- **Original intended effects:** account-controlled Alt Bot behavior remains unchanged; a random bot does **not** insert a persistent profile into `mod_naxxramas_bot_talent_import`, although normal saved character talents can be updated. It is still possible for Playerbots to rerandomise the bot even while grouped. `AccessMode` access controls and owner/group safety remain mandatory.
- **Next lightweight user-side check:** if Zevon is still present, inspect Zevon's talent window or a read-only in-game talent link to confirm the intended **14/0/37** distribution and expected Mage talents; do not make the user redo extended SQL backup inspections just for this happy-path check.
- **Remaining acceptance work:** failure/snapshot restore, non-GM AccessMode 2, attempts against a non-master/ungrouped random bot, normal Alt Bot apply, cross-class/capstone tests, unspent points, bot spell and AI usage, natural rerandomisation after group leave and while grouped. The feature is still **experimental**, not a fully accepted release.
- **No new code, SQL, DBC or config changes are needed based solely on this successful command response.** Keep work isolated to the module and documentation.

#### Follow-up visual confirmation — 10 October 2026: Zevon 14/0/37 talents verified

- Administrator subsequently **confirmed that Zevon's actual talent build shows the intended 14/0/37 distribution** following `.naxxbot talents apply Zevon ...`, supplementing the previous success message `51 spent / 0 unspent`.
- **Status raised from command-level-only to command-level + user-reported visual distribution PASS**, but no independently supplied talent-window screenshot or spell/rotation audit; cross-class behavior, non-GM authorization, persistence/rerandomisation and interrupted-reset rollback are **still untested**.
- The administrator also requested a brief Discord how-to covering the calculator URL, copying an NT1 code, bot grouping/control for randoms, `.naxxbot talents apply BotName NT1:...`, AccessMode/GM permissions and random-bot session scope. No additional source, config or SQL edits required.

#### New NT1 safety rule — full talent point allocation required (10 October 2026)

- **Administrator request after Zevon success:** do not let people install partially complete NT1 talent trees on either Random Playerbots or account-controlled Alt Bots. For example, a level-60 bot with a normal budget of 51 must receive a **51/51** build; 49/51 must be rejected. Use the **actual server-calculated** `CalculateTalentsPoints()` for the target bot's current level/config (typically 51 at 60, 61 at 70, 71 at 80); do not hardcode the budgets or trust a share URL.
- **Implemented and committed in `src/Systems/BotTalentImport.cpp`, pending next user pull/recompile/restart:** in `ApplyValidated`, after permission/party checks and **before** any `resetTalents`, immediately reject `requested.Spent < requested.Available`. Error gives the available, spent and unspent values with `No talents changed.` Existing `ParseCode` still rejects overspending.
- **Preview remains read-only and informative:** a partial but otherwise valid code still decodes, shows the point count and a prominent `NT1 APPLY BLOCKED` message explaining that every available point must be spent. This allows users to fix their talent calculator selection before attempting apply, without touching the bot.
- **Critical rollback protection:** do **not** enforce full-point spending inside `ParseCode` or `LearnValidated`, since those routines also validate/reconstruct the previous in-memory bot talent snapshot, which can legitimately contain unspent points. Only NEW requested `apply` builds require full allocation. Failed-apply recovery and Playerbots original commands are otherwise unchanged.
- **Scope:** applies to **both** Alt Bots and grouped Random Playerbots through NT1. Does not change the website's free-form builder, ordinary player talents, mod-playerbots whispers, automatic bot specs/templates, DBCs or SQL. No new configuration setting or migration.
- **Regression tests after recompile:** (1) `preview` of normal 49/51 Warrior code shows `NT1 APPLY BLOCKED` + 2 unspent; (2) `apply` of that code returns `NT1 apply aborted` and no talent reset; (3) the previously proven Zevon Mage 51/51 code can still be applied to an appropriately controlled random Mage; (4) 51/51 Alt Bot path and existing partially allocated bot snapshot rollback remain valid; (5) level-70/80 budgets, DBC class/era checks and non-GM permissions retain original safeguards.
- **Status:** feature **source/docs committed only**, not compiled/restarted/game-tested in this revision. The earlier Zevon success was on the preceding revision; do not record the new full-point rejection as field-tested until runtime evidence is received. Continue to maintain a recoverable characters DB backup before live talent changes.

### Current checkpoint

**Main development focus:** NT1 importer 1.0.6.8.5. **New safety source awaiting pull/recompile:** all NT1 `apply` requests now require full talent allocation (`Spent == Available`, using target bot's `CalculateTalentsPoints()`), and incomplete previews show an explicit warning. **Previous live success retained:** Zevon, grouped random level-60 Mage, `51 spent / 0 unspent`, with user-confirmed **14/0/37** talent distribution. The full-points-only change has **not yet been compiled or field-tested**. Random-bot import remains session-scoped; real-player AccessMode 2 permissions, Alt Bot apply, unusual specs, failure/rollback and rerandomisation still need separate testing. The reported full characters DB backup has not been proven restorable; the feature remains experimental/unreleased.
