# Naxxramas Talent Calculator -> Playerbots (NT1)
## Change Notes 1.0.6.8.5 — Phase 1 preview and experimental Phase 2 apply

**Development status:** A level-60 Mage NT1 read-only preview and wrong-class rejection passed in-game testing on an earlier revision as of 10 October 2026. Experimental application is not acceptance-tested. The new single-setting AccessMode design is source-only, pending compilation and permission/rollback tests. Keep AccessMode=0 on the live realm until backups and a disposable-bot recovery procedure are verified.

**Absolute rule:** No modification to `mod-playerbots`, AzerothCore or Individual Progression source files. MultiBot addon integration is postponed until the server command actually works and has passed tests.

## Safe and reversible scope

- Source: `src/Systems/BotTalentImport.cpp` (new CommandScript)
- Loader: `src/NaxxramasCore_loader.cpp`
- Only NT1 configuration key: `NaxxramasCore.BotTalentImport.AccessMode = 0` (disabled by default).
- **NO SQL/DBC installation or character update** during Phase 1. Phase 2 includes an **optional additive characters SQL migration** at `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`, which must not be installed without a database backup and explicit test planning.
- The entire NT1 command system is governed by one mode: `0` disabled, `1` GMs, `2` all players with per-bot ownership checks. The command table permits SEC_PLAYER, but the handler enforces the selected mode and same-account/direct Playerbots-master control for non-GMs. Both commands require an online recognised Playerbot. Original Playerbots whispers are unchanged.
- `preview` is always read-only. `apply` can **modify character talents** in either enabled mode (`1` or `2`). There is deliberately no preview-only access mode. Never enable an active mode on the live realm until the SQL, character backup, preflight and recovery requirements are reviewed.

### Available commands (Phase 1)

```text
.naxxbot talents preview <online-botname> <NT1-code>
.naxxbot talents apply <online-botname> <NT1-code>
```

An active mode always exposes both commands: preview validates without changes; apply calls the experimental mutation code after its usual database, non-random-bot and restorable-snapshot checks. **AccessMode 0 is the only no-application configuration.** This is intentional to keep the configuration concise; it also means live read-only testing should be completed before switching modes.

### Single access setting (source updated; compile and in-game tests pending)

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
- Both active modes permit actual talent modification. Use them **only after a verified characters database backup and an agreed disposable-bot test and recovery procedure**. The importer still rejects random bots from destructive application.
- Out-of-range configuration values are treated as mode 0.
- The older `BotTalentImport.Enabled`, `BotTalentImport.AllowNonGMPlayers` and `BotTalentImport.ApplyEnabled` settings are **obsolete and ignored** by this revision. Remove them from the active config to avoid confusion.
- Test modes 0/1/2, bot ownership, forbidden targets, unexpected command-help output, and successful read-only preview. Test real application only when the remaining M2 criteria are satisfied.

### Why use a separate command?

Playerbots' original whispered `talents apply <positional link>` format does not accept the calculator's `NT1` format. The new command is managed wholly by Naxxramas Core's built-in CommandScript API. The eventual MultiBot fork can call it, with permission checks remaining server-side.

## NT1 wire format

Example:

```text
NT1:vanilla:warrior:3g-1.3m-5.3u-5.3w-5.3x-3.40-3.43-2.44-1.45-2.48-1.49-1.4d-5.ji-5.18h-5.19y-2.1qi-3
```

The prefix is `NT1`, followed by era `vanilla|tbc|wotlk`, class and dot-separated `<base36 Talent.dbc ID>-<rank>` entries. These are **Talent.dbc IDs, not rank spell IDs**.

The example decodes to 16 talents, 49 spent points, and 2 unspent points for a normal level-60, 51-point Warrior. This point count is verified algebraically; the source still needs an in-game match with the actual live DBC.

The website also supplies `?level=` separately in share links; that level is not included in the NT1 code. This importer checks the real bot level and real AzerothCore talent point budget, not a claimed URL level.

### Validation

1. Require exact `NT1` prefix, four colon-separated sections, recognized era and class.
2. Decode base-36 IDs with overflow protection; reject duplicate IDs, empty fragments, malformed ranks and oversized codes.
3. Resolve actual loaded server `Talent.dbc` ID, class's `TalentTab.dbc` mask, rank `Spell.dbc` IDs, and each spell's `SpellInfo`.
4. Enforce the selected era's level cap: Vanilla <= 60, TBC <= 70, WotLK <= 80, and a minimum level of 10. Death Knights require WotLK.
5. Enforce website row/position rules: Vanilla first six full rows plus final capstone, TBC first eight full rows plus capstone, WotLK all rows. Handle the sole off-centre exception: TBC Divine Illumination (tab 382/talent 1747). In Vanilla, Shaman Enhancement uses centre-column **Dual Wield** (Talent.dbc ID 1690, tab 263), not **Stormstrike** (901). Warlock Affliction uses centre-column **Contagion** (Talent.dbc ID 1669, tab 302), not **Dark Pact** (1022). Both Stormstrike and Dark Pact are side talents unavailable in Vanilla but available from TBC.
6. Reject unknown or unsatisfied DBC talent prerequisites (zero-based DependsOnRank).
7. Check total spent points against the bot's **real** `CalculateTalentsPoints()` (not a hardcoded 51).
8. Find a legal learning sequence using prerequisite dependencies and five earlier-tree-row points per unlocked row. This is a pure preflight: the validator never learns anything.
9. Preview prints server tab distributions and deliberately unspent talent point count.

## Key limitation discovered in existing Naxxramas Core

`src/Systems/BotTalentExpansionLimits.cpp` mirrors Playerbots' level-based row restriction and generally allows only **column 1** on final rows. That conflicts with the single off-centre TBC capstone listed above. It must be reconciled **inside Naxxramas Core only** before activating the actual apply feature, without globally relaxing the old guard for unrelated Playerbots builds.

`src/Systems/BotTalentCompletion.cpp` can spend leftover talent points after Playerbots rescpecs when `NaxxramasCore.BotTalentCompletion.Enabled=1`. An exact 49/51 NT1 build must **not** be filled to 51/51. The importer needs a module-owned explicit-intent/lock shared with the completion script before applying.

## Phase 2 — Experimental code staged, NOT approved for activation

The opt-in application source is now committed and remains **off by default**. It:
- Rejects mismatched level-based eras and random bots until their full-maintenance behaviour is proven safe.
- Refuses to reset an invalid existing talent configuration if that configuration cannot be recreated through AzerothCore's public talent API.
- Checks whether the Naxxramas-owned persistence table exists **before** a reset.
- Uses `Player::resetTalents(true)` and `Player::LearnTalent(talentId, rank - 1)` with an importer-only scope marker.
- Checks exact final class talent ranks and the intentionally unspent points, and attempts to restore the original snapshot if a runtime talent learn unexpectedly fails.
- Persists a successfully applied NT1 code separately for future protection. Normal character talents are saved using `Player::SaveToDB(false, false)`.
- Coordinates with `BotTalentExpansionLimits.cpp` so only the exact website capstone exceptions are permitted during importer-owned application, not normal Playerbots workflows.
- Coordinates with `BotTalentCompletion.cpp` so that explicit NT1 imports do not trigger delayed automatic filling of unspent points.

**Critical:** The snapshot restore is NOT a database transaction. If the fallback restoration fails or Worldserver crashes between reset and verification, some state might be lost. A SQL row containing the desired profile also does **not** yet guarantee protection from a future Playerbots full randomisation, which can trigger a reset before the importer's maintenance protection code exists. The later phase below is needed before calling this production-ready.

### Installation (not approved yet)

1. Take a full and **verified restorable** backup of the characters DB and active config before database changes or any talent application.
2. Check whether the optional table exists. Review and manually apply `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql` only with a confirmed backup. A separate test realm is preferred but not available for this project.
3. Pull, compile and restart the latest Naxxramas Core module with `AccessMode=0`.
4. Record current bot GUID, existing active spec, saved talents and related spell state for a **new, disposable, non-random account bot**.
5. Only once destructive-apply risks are accepted and a recovery procedure is available, enable `AccessMode=1` (GM-only test) for that bot.
6. Verify the preview, apply result, after-relog character state and rollback recovery. Defer public `AccessMode=2` until owner/permission and full persistence tests pass.

### Phase 3 — Persistent protection and other work still not implemented

- Prove snapshot and restored talent spell/auras are correct after a full respec, including spells learned indirectly and dual-spec class state. Preflight currently checks talent ranks, not every derived aura/spell side effect.
- Verify SQL persistence with the full Playerbot lifecycle across relogs and restarts, and handle deletion/stale rows.
- Existing `OnPlayerTalentsReset` does **not** veto a Playerbots reset, so automated maintenance can temporarily change talents. Investigate module-hook learning guard + delayed post-maintenance reconciliation; prove online/relog/restart and random-bot behaviour before making guarantees.
- Introduce safe error messages and explicit confirmation only after acceptance tests.
- Preserve normal Playerbots whispers and existing spec actions; no upsteam Playerbots patch.
- Audit active abilities and AI rotations **after** import is stable, in a separately scoped phase.

### Acceptance tests and no-deployment conditions

Do not enable application merely because preview has passed. Since a separate test realm is not available, any experimental application must use a disposable, non-random online bot on the backed-up live realm with explicit risk acknowledgement and a recovery procedure:

- Valid 49-point level-60 Warrior NT1 code; 2 points remain when application is eventually enabled.
- All available classes and deliberately unspent points, and the one off-centre TBC capstone, Vanilla Dual Wield (1690) and Contagion (1669), and rejection of Vanilla Stormstrike (901) and Dark Pact (1022).
- Custom talent 3000 (Rend Flurry), other modified trees/rank spells, empty and missing-rank data.
- Wrong class, malformed/version mismatch, duplicate talent IDs, impossible ranks, missing dependencies, too many points, level/era mismatch: **no resets**.
- Existing build -> replacement; pre-existing dependent spells properly removed.
- Dual specs; relog; server restart; Playerbots AutoPickTalents; Playerbots incremental and full randomization; Playerbots upstream update.
- Manual original `talents apply`/ `talents spec` remain unchanged.

**Rollback:** Set `NaxxramasCore.BotTalentImport.AccessMode = 0` in the active config, then restart Worldserver. This stops further NT1 command use; it **does not revert talents already applied**. Restoring previous character talents still requires an independently recoverable database backup. The additive `mod_naxxramas_bot_talent_import` table can be removed only after backing it up and deciding that stored profiles are no longer wanted. Removing it does not undo character talent changes. Avoid `git reset --hard`.

## Operating steps after compilation (one-setting edition)

1. Back up live characters DB and active configs; deploy source using `git pull --ff-only`, recompile and restart with `AccessMode=0`.
2. Keep mode 0 until recovery is prepared, and check Worldserver logs for module startup errors.
3. Once backup/rollback prerequisites are met, choose `AccessMode=1` for a tightly controlled GM-only trial with a disposable, non-random account bot; restart Worldserver.
4. Use `.naxxbot talents preview` first and confirm the build is valid. Preview remains read-only.
5. Run `.naxxbot talents apply` **only after explicit acceptance of the experimental reset risk**, then inspect active talent ranks, unspent points, learned spells, relog and bot maintenance.
6. Keep `AccessMode=2` deferred until non-GM ownership checks and persistence are verified in-game. Restore `AccessMode=0` to disable further NT1 commands if anything fails.

## Future MultiBot fork work

After the real apply operation works and persists, add UI support **only to the user's MultiBot fork**. The module now contains optional server-side non-GM permission and ownership checks, but their runtime operation is not yet validated and addon integration must not bypass them. Confirm security/permission behaviour: GM-dot commands are **not** the same as bot whispers, and an addon cannot bypass server permissions. Display user-friendly validation errors and character name/build status in MultiBot. Do not edit MultiBot while backend commands are experimental.
