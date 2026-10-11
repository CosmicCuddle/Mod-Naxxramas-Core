# Naxxramas Talent Calculator -> Playerbots (NT1)
## Change Notes 1.0.6.8.5 — Phase 1 preview and experimental Phase 2 apply

**Development status (10 October 2026):** Read-only Mage previews passed in-game, and the former random-bot rejection was verified on Ido. The administrator then **pulled, compiled and restarted** the guarded grouped-random-bot implementation and supplied a screenshot showing its **first successful experimental application** to random Playerbot **Zevon**: `NT1 build applied to Zevon: 51 spent / 0 unspent.` The system also displayed the intended warning that the random bot has **no permanent NT1 profile**. This confirms a narrow live happy path, **not** a production-ready feature: independent talent-window inspection, learned spells, randomisation behavior, non-GM authorization and rollback remain unverified. Retain restorable `acore_characters` backups.

**Absolute rule:** No modification to `mod-playerbots`, AzerothCore or Individual Progression source files. MultiBot addon integration is postponed until the server command actually works and has passed tests.

## Safe and reversible scope

- Source: `src/Systems/BotTalentImport.cpp` (new CommandScript)
- Loader: `src/NaxxramasCore_loader.cpp`
- NT1 config uses `NaxxramasCore.BotTalentImport.AccessMode = 0` (disabled by default), plus **`NaxxramasCore.BotTalentImport.AltBotAllowedPlayers = ""`** (deny all Alt Bot talent applications by default).
- **NO SQL/DBC installation or character update** during Phase 1. Phase 2 includes an **optional additive characters SQL migration** at `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`, which must not be installed without a database backup and explicit test planning.
- The entire NT1 command system is governed by one mode: `0` disabled, `1` GMs, `2` all players with per-bot ownership checks. The command table permits SEC_PLAYER, but the handler enforces the selected mode and same-account/direct Playerbots-master control for non-GMs. Both commands require an online recognised Playerbot. Original Playerbots whispers are unchanged.
- `preview` is always read-only. `apply` can **modify character talents** in either enabled mode (`1` or `2`). There is deliberately no preview-only access mode. Never enable an active mode on the live realm until the SQL, character backup, preflight and recovery requirements are reviewed.

### Available commands (Phase 1)

```text
.naxxbot talents preview <online-botname> <NT1-code>
.naxxbot talents apply <online-botname> <NT1-code>
```

An active mode always exposes both commands: preview validates without changes; apply calls the experimental mutation code after its database, **random-bot party/master eligibility**, and restorable-snapshot checks. **AccessMode 0 is the only no-application configuration.** This is intentional to keep the configuration concise; it also means live read-only testing should be completed before switching modes.

### Single access setting (GM apply tested; broader permissions still pending)

```ini
# 0 = Disabled
# 1 = GM accounts only (preview and experimental apply)
# 2 = All players (preview and experimental apply)
# Default: 0
NaxxramasCore.BotTalentImport.AccessMode = 0
```

- **Mode 0 (default):** both commands are disabled for GMs and ordinary players. It is the safe rollback setting, but does not undo previously changed character talents.
- **Mode 1:** GMs may preview and apply NT1 codes to eligible online Playerbots. Non-GMs cannot use either command.
- **Mode 2:** GMs and non-GMs may preview and apply. Non-GMs must control the bot through the same account or be its current Playerbots AI master; group membership or knowing the bot name does not grant permission.
- Both active modes permit actual talent modification. Use them **only after a verified characters database backup and an agreed disposable-bot test and recovery procedure**. Grouped random bots are additionally restricted to the invoking real player who currently controls them. This path passed its first live happy-path test on Zevon, but permissions, maintenance and rollback remain unverified.
- Out-of-range configuration values are treated as mode 0.
- The older `BotTalentImport.Enabled`, `BotTalentImport.AllowNonGMPlayers` and `BotTalentImport.ApplyEnabled` settings are **obsolete and ignored** by this revision. Remove them from the active config to avoid confusion.
- Test modes 0/1/2, bot ownership, forbidden targets, unexpected command-help output, and read-only preview. One fully allocated Random Playerbot application passed on Zevon; incomplete-point refusal and broader M2 cases remain to be tested after the next compile.

### Alt Bot invalid-talent repair inspection (separate draft; read-only)

New proposed command: `.naxxbot talents repairpreview <online-altbot-name> <NT1-code>`. This command is **read-only**: it does not attempt any talent reset/rebuild, inventory movement, save, SQL update, or equipment generation. Existing `.naxxbot talents apply` still **denies** the operation when original talents are not safely restorable; **no repair Apply command exists**.

For the user's affected Priest Alt Bots the original builds contained **Talent.dbc ID 1768 (Holy Concentration; Holy row 6, col 0)** and **1202 (Borrowed Time; Discipline row 9, col 1)**. These are in the **existing spec**, not necessarily the requested legal Vanilla NT1. The new diagnostic scans ALL selected active-spec DBC talent ranks, lists those outside the **requested era's actual `AvailableInEra` policy**, and runs the shared `CheckApplyReadiness` to explain the current blocker. It does not claim all possible non-DBC spell effects are covered.

The command requires existing `AccessMode` rights, live human identity and bot control; it **refuses Random Playerbots** and additionally requires the issuing character's name in `AltBotAllowedPlayers`, including GMs. Empty default denies detailed Alt Bot repair inspection. Every source DBC class/rank/prerequisite rule and issuing-human IP-era check still comes from `ValidateRequest`. No new config/default or migration.

**Important:** AzerothCore `Player::resetTalents(true)` may call `AutoUnequipOffhandIfNeed()`; neither ordinary talent Apply nor a hypothetical reset-and-repair automatically guarantees completely unchanged Alt Bot equipment. Future destructive repair must be independently reviewed with reliable character backups, explicit human confirmation, active-spec/inactive-spec and equipment GUID/bag invariants, and a validated offline recovery. No gear-changing repair has been implemented.

See [read-only repair diagnostic command and acceptance plan](NT1-ALT-BOT-REPAIR-PREVIEW.md) and [repair recovery design on the audit PR #6 branch](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/6).

### Shared read-only Apply preflight (new draft PR — uncompiled)

**Scope:** `src/Systems/BotTalentImport.cpp` now has a `CheckApplyReadiness` routine, shared by the existing `preview` and `apply` handlers. The helper is **read-only**: it reads character state, the current talent snapshot and SQL table metadata; it does not call talent resets, learning, save methods, profile writes, equipment or inventory operations. The only change in the mutation path is that it calls this same helper **again before any reset** and uses its validated old-build snapshot for existing best-effort rollback.

Preview now distinguishes two separate facts:

- **`NT1 valid for ...`** — the submitted code is syntactically/class/DBC/era valid for the target's current level and available points. This alone does not imply Apply eligibility.
- **`NT1 PREFLIGHT READY (current state only)`** — same immediate eligibility checks as Apply passed; **no token, reservation, persistence guarantee or authorization grant is issued**.
- **`NT1 PREFLIGHT BLOCKED: <reason>`** — Apply is currently ineligible, including group/master status, empty or unmatched Alt Bot allowlist, combat/death, missing SQL table, expansion-vs-bot-level restriction, unspent target points, or an invalid/unrecoverable original bot spec. Preview still makes no changes and prints talent totals/tree distribution when the requested plan parses.

Both commands retain `AccessMode` and direct owner/AI-master checks, and the shared helper also enforces these a second time, using the real human issuer and online target. The intended *new* behavior is to reject Apply before reset if a caller, current target, class, level or live budget no longer matches preflight requirements. **Alt Bot gear remains out of scope**. The Individual Progression header exclusion is unchanged, preventing the previously observed conflicting `GENERAL` enum.

**Important limitations remaining:** This is a **current-state readiness report**, not a server-issued short-lived confirmation ticket. Preview and Apply are still separate commands; Apply checks everything again and can still fail if the bot or permissions change. The prior reset/learning and rollback routine remains best-effort and non-atomic, including the pre-existing active-spec-change failure path. The server has not adopted a structured addon protocol; MultiBot must not parse the new human-readable text as a durable authorization or infer success from dispatch.

**Build/test status:** code committed to a separate *draft, unmerged* branch; static read-only/ordering review only, **server compilation and in-game regression tests pending**.

Suggested minimum field tests *after an approved, successfully compiled candidate*:

| Check | Preview expected | Apply expected |
| --- | --- | --- |
| 51/51 level-60 Vanilla Mage, controlled eligible grouped Random Bot | `PREFLIGHT READY` | Existing guarded talent application still works; no permanent random-bot NT1 profile |
| Same Mage, ungrouped or foreign master | `PREFLIGHT BLOCKED` | `NT1 apply aborted` before reset |
| Alt Bot with caller absent from the list (including GM) | `PREFLIGHT BLOCKED` | Denied; no talent or gear changes |
| Allowlisted Alt Bot with valid ownership/security | `PREFLIGHT READY` | Experimental Apply only after recovery checks; no inventory changes |
| 49/51 incomplete level-60 build | `PREFLIGHT BLOCKED` with missing point count | Denied before reset |
| Correct code, bot in combat/dead | `PREFLIGHT BLOCKED` | Denied before reset |
| Missing import table or unrestorable existing talents | `PREFLIGHT BLOCKED` | Denied before reset |
| Wrong class, malformed rank or blocked IP era | `NT1 rejected` (fails parse/issuer-stage gate) | No reset |
| `AccessMode=0` | Command unavailable | Command unavailable |

The next stage requires an explicit reviewed **server-bound, one-use preview/confirmation protocol**, plus better rollback/error reporting; it is **not** implemented by this PR.

### Alt Bot NT1 character-name allowlist (source committed; next build/test pending)

**Alt Bots never participate in NT1 automatic gear generation.** The proposed post-NT1 role-gearing feature is reserved for eligible **Random Playerbots only**. An Alt Bot's existing equipped gear, bags and earned items must not be touched by that feature. This is scoped to **NT1-related automation**; it does not change the behaviour of stock Playerbots equipment commands run separately.

The Alt Bot talent-application permission list is configured with the **names of real player characters using the command**, not the names of the bots being changed:

```ini
NaxxramasCore.BotTalentImport.AltBotAllowedPlayers = "Takali, Drakka, Sequoia"
```

- **The distributed default is `""` — all Alt Bot NT1 applications are blocked unless an administrator adds names to the active config.** GM status does not bypass the list. The names are compared as complete names, case-insensitively for ASCII letters; surrounding spaces and trailing commas are ignored.
- The allowlist **does not grant extra permissions**. `AccessMode=0` blocks both commands, `AccessMode=1` still requires GM security, and `AccessMode=2` retains the ordinary non-GM same-account or bot-master ownership checks. Therefore adding a character name alone does NOT authorize a normal player in mode 1 or grant access to unrelated players' Alt Bots.
- This additional allowlist is checked **only for Alt Bot `apply`**, before any talent reset, profile-table update or character save. **Alt Bot `preview` remains read-only** and requires the ordinary AccessMode and progression checks but not the allowlist.
- **Random Playerbots are unaffected** by `AltBotAllowedPlayers`: they retain their own human master/group eligibility and the existing AccessMode/progression/full-point checks.
- Unlike an account-ID allowlist, character-name authorization may transfer if a name is renamed or reassigned. Administrators must maintain this list accordingly. The module authenticates the current session's actual character name, not a user-supplied command argument.
- **Implementation status:** GitHub source/config committed, not yet recompiled or field-tested. Test the empty list, an allowlisted GM, an unlisted GM, `AccessMode=1` non-GM denial, `AccessMode=2` allowlisted owner vs unauthorized owner, and a Random Playerbot regression. No SQL/DBC changes.
- The future role-gearing system remains **design only**. Do not treat this talent-import allowlist as protection against separate standard Playerbots gear actions.

### Individual Progression era rule (new server-side source, awaiting next recompile)

**An NT1 talent code must use exactly the same expansion as the player issuing the command.** This is enforced in `src/Systems/BotTalentImport.cpp` for **both `preview` and `apply`**, for both GMs and authorised ordinary players, and for both account-controlled Alt Bots and grouped Random Playerbots. The requested talent code's `vanilla`, `tbc` or `wotlk` era is **never trusted to grant an expansion unlock**.

When Individual Progression is enabled, the server reads the **issuing human character's** progression; the random bot's (often exempt) IP state and the bot's or issuer's level are **not substitutes** for that progression. The current hidden-quest Individual Progression release unlocks **TBC at milestone 8** and **WotLK at milestone 13**:

| Human character's Individual Progression | NT1 code era allowed | Rejected |
| --- | --- | --- |
| Vanilla (before stage 8) | `vanilla` | `tbc`, `wotlk` |
| TBC (stages 8–12) | `tbc` | `vanilla`, `wotlk` |
| WotLK (stage 13 onward) | `wotlk` | `vanilla`, `tbc` |

The server honours `IndividualProgression.ProgressionLimit` when determining the permitted stage. **Implementation note / compilation fix (11 October 2026):** `IndividualProgression.h` and Playerbots' `PlayerbotAI.h` both declare a global `GENERAL` enumerator, so including them together caused a real `redefinition of enumerator 'GENERAL'` compiler error. The NT1 importer **no longer includes or references the Individual Progression header**. Instead, it reads the issuing human character's **modern hidden rewarded quests `66001..66018` through `Player::GetQuestStatus`**, using the highest completed stage, as the separate Naxxramas Core Battlemaster progression integration does. This deliberately supports the current hidden-quest IP schema; older player-settings-based IP variants require separate compatibility work and must not be assumed supported. No Individual Progression or Playerbots code was changed. **The corrected source is committed but has not yet been recompiled/tested.**

If `IndividualProgression.Enable=0`, there is no character IP stage to check, so the importer retains its **existing bot-level era restriction and DBC talent-row limits**. The player-era rule cannot bypass those restrictions; a bot still needs the correct level/expansion, class/ranks/prerequisites and **all available talent points allocated**. This era rule adds no new configuration keys; the independent Alt Bot permission allowlist is documented above.

**Wrong-era requests fail with `NT1 rejected: NT1 era blocked by Individual Progression: ... No talents changed.`** Preview remains read-only, and apply is denied before any talent reset. The live result of this rule has **not yet been tested**; it requires the administrator to pull, recompile and restart. **Only Naxxramas Core was changed**: no edits to IP, Playerbots, AzerothCore, addon or website.

**Post-build tests:** Vanilla GM with TBC and WotLK code must get rejected; TBC GM with WotLK code rejected; exact-era Vanilla full-51-point Mage still previews/applies on eligible grouped random Mage (Zevon's prior success is from an earlier revision). Test exact-stage boundary 7→8, 12→13, progression-limit clamp, mode-2 non-GM permission, and deny wrong-era code before any character reset.

### Complete talent allocation rule (new source, awaiting next recompile)

**Every NT1 build applied to any bot must use all talent points available to that bot.** `ApplyValidated` rejects any request with `Spent < Available` **before** a talent reset. `Available` comes from the bot's real `CalculateTalentsPoints()`, not a hardcoded 51/61/71 or the website's level parameter. Examples using normal budgets: level 60 = 51/51, level 70 = 61/61, level 80 = 71/71.

- `preview` still decodes and validates under-allocated builds **read-only**, reporting the missing points and `NT1 APPLY BLOCKED`. This helps the player finish the calculator build without changing the bot.
- `apply` stops with `NT1 apply aborted: Full talent allocation required: ... No talents changed.` on any partial build, whether targeted at an Alt Bot or a grouped Random Playerbot.
- A bot's **previous** spec might have unspent points. Snapshot validation and best-effort rollback **remain allowed to reconstruct that old partial spec**, so this new rule does not accidentally disable recovery.
- Over-allocated, invalid or illegal talent builds remain rejected by existing `ParseCode` checks.
- This change governs the **NT1 importer only**. It does not modify built-in Playerbots whispers, automatic templates, ordinary player talents, or the Resource Hub calculator's freedom to create draft/partial specs.
- **Implementation status:** committed source only; compilation and positive/negative in-game tests pending. The previously observed Zevon full-51-point application is unaffected.

### Grouped random Playerbots (first live apply passed; remaining cases untested)

The NT1 importer has two application cases under the existing `AccessMode` setting. **Alt Bot `apply` additionally requires an explicitly allowlisted issuing character name.** Random Playerbot permissions remain unchanged.

- **Alt Bots:** `.naxxbot talents apply` is allowed only when the HUMAN issuing character's name is in `AltBotAllowedPlayers` **and** the original `AccessMode`/non-GM ownership checks pass. The default empty allowlist denies all Alt Bot NT1 applications, including GMs. On success, only normal talents and the stored NT1 intent are updated; **no equipment generation, gear replacement, item moves, or gear deletion is part of NT1 apply**.
- **Random Playerbots:** may apply only while the issuing **real player** and the bot are **both members of the same active party or raid**. The bot must currently identify that player as its Playerbots AI master. If no master is assigned, only the **actual group leader** may issue the application command. A bot mastered by someone else remains off-limits, even to a GM who merely joins the group.
- The random-bot case runs the **same** NT1 class/era/DBC/rank preflight, existing-build snapshot check, exact talent learning verification and best-effort rollback as the Alt Bot case; it still refuses applications when the bot is dead or in combat.
- Successful random-bot application **does not insert/update the desired NT1 code in the persistent profile table**, so it will not intentionally lock a build into future randomised sessions. The normal character talents are still saved to the characters DB; **leaving the party does not immediately restore the old build**.
- Standard Playerbots background or full randomisation can **still replace the imported talents**, potentially **even while the bot remains in the party**. This release does not suppress randomisation or automatically reapply an overridden build, and no session-long persistence guarantee is claimed.
- `preview` remains available for any eligible online Playerbot and **never changes talents**. After a reported successful pull/compile/restart, the administrator applied a full Mage NT1 build to **Zevon**, a grouped random Playerbot. Game chat reported **51 spent, 0 unspent** and the nonpersistent-profile warning. This is a successful experimental command-level field test; it does not verify persistent talents or every class.
- Test session master binding, a GM applying to its own party's random bot, non-GM ownership restrictions, random bot without the issuer in the group, foreign master, dead/combat/invalid requests, exact learned ranks, spell side effects, mid-party randomisation, group exit, relog/restart and fallback restoration before calling the feature stable.
- The normal `AccessMode=0/1/2` options remain unchanged. The existing full characters database backup and a recoverable copy of the specific test bot's original talents are prerequisites for a live-only trial.

### Why use a separate command?

Playerbots' original whispered `talents apply <positional link>` format does not accept the calculator's `NT1` format. The new command is managed wholly by Naxxramas Core's built-in CommandScript API. The eventual MultiBot fork can call it, with permission checks remaining server-side.

### First live positive application — Zevon (10 October 2026)

The administrator supplied a screenshot confirming `NT1 build applied to Zevon: 51 spent / 0 unspent.`, followed by the explicit message `Random Playerbot: session-scoped build only. Playerbots may replace talents during randomization; no permanent NT1 profile was saved.` Zevon replaced Husapze as a test target after Husapze logged out.

This confirms the **successful command-level grouped random Playerbot apply path** and its calculated full 51-point spend. It is **not** proof that the Mage talent window was separately inspected, that the bot used all intended talent abilities, that group-time rerandomisation is prevented, or that recovery from an interrupted application works. Those remain future acceptance tests. No broad permission change or permanent random-bot profile lock is implied.

## NT1 wire format

Example:

```text
NT1:vanilla:warrior:3g-1.3m-5.3u-5.3w-5.3x-3.40-3.43-2.44-1.45-2.48-1.49-1.4d-5.ji-5.18h-5.19y-2.1qi-3
```

The prefix is `NT1`, followed by era `vanilla|tbc|wotlk`, class and dot-separated `<base36 Talent.dbc ID>-<rank>` entries. These are **Talent.dbc IDs, not rank spell IDs**.

The example decodes to 16 talents, 49 spent points, and 2 unspent points for a normal level-60, 51-point Warrior. This point count is verified algebraically; the source still needs an in-game match with the actual live DBC. **Under the new full-allocation policy, this code may be previewed but MUST be refused by `apply` on a normal level-60, 51-point Warrior.**

The website also supplies `?level=` separately in share links; that level is not included in the NT1 code. This importer checks the real bot level and real AzerothCore talent point budget, not a claimed URL level.

### Validation

1. Require exact `NT1` prefix, four colon-separated sections, recognized era and class.
2. Decode base-36 IDs with overflow protection; reject duplicate IDs, empty fragments, malformed ranks and oversized codes.
3. Resolve actual loaded server `Talent.dbc` ID, class's `TalentTab.dbc` mask, rank `Spell.dbc` IDs, and each spell's `SpellInfo`.
4. Enforce the selected era's level cap: Vanilla <= 60, TBC <= 70, WotLK <= 80, and a minimum level of 10. Death Knights require WotLK.
5. Enforce website row/position rules: Vanilla first six full rows plus final capstone, TBC first eight full rows plus capstone, WotLK all rows. Handle the sole off-centre exception: TBC Divine Illumination (tab 382/talent 1747). In Vanilla, Shaman Enhancement uses centre-column **Dual Wield** (Talent.dbc ID 1690, tab 263), not **Stormstrike** (901). Warlock Affliction uses centre-column **Contagion** (Talent.dbc ID 1669, tab 302), not **Dark Pact** (1022). Both Stormstrike and Dark Pact are side talents unavailable in Vanilla but available from TBC.
6. Reject unknown or unsatisfied DBC talent prerequisites (zero-based DependsOnRank).
7. Check total spent points against the bot's **real** `CalculateTalentsPoints()` (not a hardcoded 51). Overspending is invalid for preview and apply; underspending remains readable in preview but **is forbidden for apply**.
8. Find a legal learning sequence using prerequisite dependencies and five earlier-tree-row points per unlocked row. This is a pure preflight: the validator never learns anything.
9. Preview prints server tab distributions and unspent point count. If any points remain, it displays **`NT1 APPLY BLOCKED`**. Preview does not reset talents.
10. If Individual Progression is enabled, require the NT1 code's expansion to **exactly match the issuing human character's current IP era** (stage 8 TBC, 13 WotLK) for both preview and apply. This is checked before any bot talents are touched.

## Key limitation discovered in existing Naxxramas Core

`src/Systems/BotTalentExpansionLimits.cpp` mirrors Playerbots' level-based row restriction and generally allows only **column 1** on final rows. That conflicts with the single off-centre TBC capstone listed above. It must be reconciled **inside Naxxramas Core only** before activating the actual apply feature, without globally relaxing the old guard for unrelated Playerbots builds.

`src/Systems/BotTalentCompletion.cpp` can spend leftover talent points after Playerbots rescpecs when `NaxxramasCore.BotTalentCompletion.Enabled=1`. **New policy:** a 49/51 NT1 build cannot be applied at all; the player must complete it first. Import scope coordination remains necessary to keep validation/rollback and regular Playerbots completion separate.

## Phase 2 — Experimental code with one successful Random Playerbot apply, NOT production-approved

The opt-in application source is now committed and remains **off by default**. It:
- Rejects mismatched level-based eras; random bots must have a genuine human group controller as above, rather than an unconditional block.
- Refuses to reset an invalid existing talent configuration if that configuration cannot be recreated through AzerothCore's public talent API.
- Checks whether the Naxxramas-owned persistence table exists **before** a reset.
- Uses `Player::resetTalents(true)` and `Player::LearnTalent(talentId, rank - 1)` with an importer-only scope marker.
- Before any reset, **rejects NT1 apply when even one talent point is unspent** (uses `CalculateTalentsPoints()` for the target's real level and server rules), with an explicit count and a `No talents changed` message. The same rule applies to Alt Bots and grouped Random Playerbots. **Do not enforce this during previous-build snapshot parsing**, which must support restoration of an old bot spec with unspent points.
- Checks exact final class talent ranks and zero remaining talent points, and attempts to restore the original snapshot if a runtime talent learn unexpectedly fails.
- Persists a successfully applied NT1 code for **Alt Bots only**. Random-bot imports are session-scoped and do **not** store a persistent NT1 profile. Both use `Player::SaveToDB(false, false)` to save normal character talents, which Playerbots may later overwrite.
- Coordinates with `BotTalentExpansionLimits.cpp` so only the exact website capstone exceptions are permitted during importer-owned application, not normal Playerbots workflows.
- Coordinates with `BotTalentCompletion.cpp` to prevent unintended talent-completion logic during imported changes and snapshot restoration; incomplete NT1 target builds are now rejected before mutation.

**Critical:** The snapshot restore is NOT a database transaction. If the fallback restoration fails or Worldserver crashes between reset and verification, some state might be lost. A SQL row containing the desired profile also does **not** yet guarantee protection from a future Playerbots full randomisation, which can trigger a reset before the importer's maintenance protection code exists. The later phase below is needed before calling this production-ready.

### Installation (not approved yet)

1. Take a full and **verified restorable** backup of the characters DB and active config before database changes or any talent application.
2. Check whether the optional table exists. Review and manually apply `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql` only with a confirmed backup. A separate test realm is preferred but not available for this project.
3. Pull, compile and restart the latest Naxxramas Core module with `AccessMode=0`.
4. Record the bot's GUID, active spec, saved talents and related spell state for a **disposable account bot or a grouped disposable random bot**; for random bots confirm the issuing player's party/master control.
5. Only once destructive-apply risks are accepted and a recovery procedure is available, enable `AccessMode=1` (GM-only test) for that bot.
6. Verify preview, application (only with explicit residual-risk acceptance), precise final ranks, failure recovery and what happens after group exit and Playerbots rerandomisation. Defer public `AccessMode=2` until owner/permission and session behaviour tests pass.

### Phase 3 — Persistent protection and other work still not implemented

- Prove snapshot and restored talent spell/auras are correct after a full respec, including spells learned indirectly and dual-spec class state. Preflight currently checks talent ranks, not every derived aura/spell side effect.
- Verify SQL persistence with the full Playerbot lifecycle across relogs and restarts, and handle deletion/stale rows.
- Existing `OnPlayerTalentsReset` does **not** veto a Playerbots reset, so automated maintenance can temporarily change talents. Investigate module-hook learning guard + delayed post-maintenance reconciliation; prove online/relog/restart and random-bot behaviour before making guarantees.
- Introduce safe error messages and explicit confirmation only after acceptance tests.
- Preserve normal Playerbots whispers and existing spec actions; no upsteam Playerbots patch.
- Audit active abilities and AI rotations **after** import is stable, in a separately scoped phase.

### Acceptance tests and no-deployment conditions

Do not assume experimental application works merely because preview has passed. Since a separate test realm is not available, any experimental application must use a disposable online account bot **or an eligible grouped random bot** on the backed-up live realm with explicit risk acknowledgement and a recovery procedure:

- Incomplete 49/51 level-60 Warrior NT1 code: **preview identifies 2 unspent points and warns that apply is blocked; apply rejects before reset**. Original bot talents and spell records must not change.
- Valid **fully allocated** builds for all available classes and the one off-centre TBC capstone, Vanilla Dual Wield (1690) and Contagion (1669), and rejection of Vanilla Stormstrike (901) and Dark Pact (1022).
- Custom talent 3000 (Rend Flurry), other modified trees/rank spells, empty and missing-rank data.
- Wrong class, malformed/version mismatch, duplicate talent IDs, impossible ranks, missing dependencies, too many points, level/era mismatch: **no resets**.
- Existing build -> replacement; pre-existing dependent spells properly removed.
- Dual specs; relog; server restart; Playerbots AutoPickTalents; Playerbots incremental and full randomization; Playerbots upstream update.
- Manual original `talents apply`/ `talents spec` remain unchanged.

**Rollback:** Set `NaxxramasCore.BotTalentImport.AccessMode = 0` in the active config, then restart Worldserver. This stops further NT1 command use; it **does not revert talents already applied**. Restoring previous character talents still requires an independently recoverable database backup. The additive `mod_naxxramas_bot_talent_import` table can be removed only after backing it up and deciding that stored profiles are no longer wanted. Removing it does not undo character talent changes. Avoid `git reset --hard`.

## Operating steps after compilation (one-setting edition)

1. Back up live characters DB and active configs; deploy source using `git pull --ff-only`, recompile and restart with `AccessMode=0`.
2. Keep mode 0 until recovery is prepared, and check Worldserver logs for module startup errors.
3. Once backup/rollback prerequisites are met, use `AccessMode=1` for a tightly controlled GM-only trial with a disposable account bot **or a disposable random bot in your party for which you are the active master/group leader**; restart Worldserver if changing the mode.
4. Use `.naxxbot talents preview` first and confirm the build is legal **and has 0 unspent points**. Preview remains read-only; incomplete builds show an `NT1 APPLY BLOCKED` warning.
5. Run `.naxxbot talents apply` **only after explicit acceptance of the experimental reset risk**. An under-allocated code is rejected without changing talents. On accepted full allocations, inspect actual ranks, 0 unspent points, learned spells, relog and bot maintenance.
6. Keep `AccessMode=2` deferred until non-GM ownership checks and persistence are verified in-game. Restore `AccessMode=0` to disable further NT1 commands if anything fails.

## Future MultiBot fork work

After the real apply operation works and persists, add UI support **only to the user's MultiBot fork**. The module now contains optional server-side non-GM permission and ownership checks, but their runtime operation is not yet validated and addon integration must not bypass them. Confirm security/permission behaviour: GM-dot commands are **not** the same as bot whispers, and an addon cannot bypass server permissions. Display user-friendly validation errors and character name/build status in MultiBot. Do not edit MultiBot while backend commands are experimental.
