# Naxxramas Talent Calculator -> Playerbots (NT1)
## Change Notes 1.0.6.8.5 — Phase 1 preview and experimental Phase 2 apply

**Development status:** A level-60 Mage NT1 read-only preview and wrong-class rejection have passed in-game testing as of 10 October 2026. Experimental Phase 2 apply has **not** passed acceptance testing. New player permissions and command-message cleanup are source-only and must be compiled/tested before being treated as deployed. Keep actual talent application disabled on live realms.

**Absolute rule:** No modification to `mod-playerbots`, AzerothCore or Individual Progression source files. MultiBot addon integration is postponed until the server command actually works and has passed tests.

## Safe and reversible scope

- Source: `src/Systems/BotTalentImport.cpp` (new CommandScript)
- Loader: `src/NaxxramasCore_loader.cpp`
- Config default: `NaxxramasCore.BotTalentImport.Enabled = 0`
- **NO SQL/DBC installation or character update** during Phase 1. Phase 2 includes an **optional additive characters SQL migration** at `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`, which must not be installed without a database backup and explicit test planning.
- GM commands remain available to GMs. **Regular-player NT1 preview and apply access** is opt-in using the single `AllowPlayers=0` default. The command table permits SEC_PLAYER, but the handler enforces both config permission and a same-account/direct Playerbots-master ownership check. Other players' bots cannot be targeted by name alone. Preview and apply require an online recognized Playerbot. Normal Playerbots whisper commands remain unchanged.
- **With `ApplyEnabled=0` (default), the `apply` command remains strictly READ-ONLY.** Experimental application code now exists behind `NaxxramasCore.BotTalentImport.ApplyEnabled = 1`, which is **not approved for live deployment** before compilation and comprehensive rollback tests. With the switch off it never calls `resetTalents`, `LearnTalent`, or `SaveToDB`.

### Available commands (Phase 1)

```text
.naxxbot talents preview <online-botname> <NT1-code>
.naxxbot talents apply <online-botname> <NT1-code>
```

By default the second command never changes talents. In Phase 2 experimental testing, it could modify talents **only if both** the top-level enabled flag and the separate `ApplyEnabled` flag are turned on, the bot passes complete validation, the persistence table exists, and a restorable current talent snapshot can be captured. For **non-GM accounts**, `AllowPlayers=1` and the ownership/master check are required for either command. Actual application still requires the separate global `ApplyEnabled=1` safeguard. **Keep `ApplyEnabled=0` for now.**

### Regular-player permissions (new source; build and test pending)

```ini
# Master switch for the NT1 commands; required for all actors.
NaxxramasCore.BotTalentImport.Enabled = 1

# Optional: permit non-GMs to use preview and apply for authorised bots.
# 0 = GM only; 1 = regular players and GMs.
NaxxramasCore.BotTalentImport.AllowPlayers = 0

# Actual talent mutation is a separate global experiment. Keep OFF.
NaxxramasCore.BotTalentImport.ApplyEnabled = 0
```

- **Default behaviour:** ordinary accounts are denied both new commands with a clear reason; existing GM permissions remain as before.
- To let ordinary players preview their bots, set `AllowPlayers=1` and leave `ApplyEnabled=0`. The `apply` command remains validation-only with that safety switch off.
- A normal player may target their **same-account online bot** or an online Playerbot whose current AI `GetMaster()` is that player. Group membership alone, name knowledge, and another player's mastership confer no access.
- Even when `AllowPlayers=1`, normal M2 safeguards still apply: actual application is separately gated by `ApplyEnabled=1`, rejects random bots, refuses invalid requests and must pass snapshot/schema preflight.
- The safe `SEC_PLAYER` registration is deliberate: the handler must be reachable so it can enforce the configuration and ownership checks at runtime. Never remove the per-request checks while keeping `SEC_PLAYER`.
- Check GM access, player access disabled, own-account player preview, directly mastered player preview, other-account/master denial, random-bot rejection from apply, and configuration combinations; confirm no change to original Playerbots whispers or to other accounts.
- **Do not enable `ApplyEnabled=1` on a live realm before full destructive-testing acceptance.** `AllowPlayers=1` by itself never changes talents. The current snapshot restoration is best-effort, not transactional.
- The command-message cleanup now avoids AzerothCore's extra generic `### USAGE` output on handled NT1 errors. It is also source-only pending compilation.

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

1. Take a full backup of your characters DB and active configs.
2. Only on a separate backed-up test realm, apply the optional SQL file `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`.
3. Pull and compile the latest Naxxramas Core module.
4. Keep both switches OFF while first checking a successful compilation.
5. Set `NaxxramasCore.BotTalentImport.Enabled=1` for read-only preview tests; leave `NaxxramasCore.BotTalentImport.ApplyEnabled=0`.
6. Only after the rollback recovery path has been reviewed and tested should a disposable-bot test use `ApplyEnabled=1`.

### Phase 3 — Persistent protection and other work still not implemented

- Prove snapshot and restored talent spell/auras are correct after a full respec, including spells learned indirectly and dual-spec class state. Preflight currently checks talent ranks, not every derived aura/spell side effect.
- Verify SQL persistence with the full Playerbot lifecycle across relogs and restarts, and handle deletion/stale rows.
- Existing `OnPlayerTalentsReset` does **not** veto a Playerbots reset, so automated maintenance can temporarily change talents. Investigate module-hook learning guard + delayed post-maintenance reconciliation; prove online/relog/restart and random-bot behaviour before making guarantees.
- Introduce safe error messages and explicit confirmation only after acceptance tests.
- Preserve normal Playerbots whispers and existing spec actions; no upsteam Playerbots patch.
- Audit active abilities and AI rotations **after** import is stable, in a separately scoped phase.

### Acceptance tests and no-deployment conditions

Do not enable application merely because Phase 1 compiles. Test on disposable online bots in a backed-up test realm:

- Valid 49-point level-60 Warrior NT1 code; 2 points remain when application is eventually enabled.
- All available classes and deliberately unspent points, and the one off-centre TBC capstone, Vanilla Dual Wield (1690) and Contagion (1669), and rejection of Vanilla Stormstrike (901) and Dark Pact (1022).
- Custom talent 3000 (Rend Flurry), other modified trees/rank spells, empty and missing-rank data.
- Wrong class, malformed/version mismatch, duplicate talent IDs, impossible ranks, missing dependencies, too many points, level/era mismatch: **no resets**.
- Existing build -> replacement; pre-existing dependent spells properly removed.
- Dual specs; relog; server restart; Playerbots AutoPickTalents; Playerbots incremental and full randomization; Playerbots upstream update.
- Manual original `talents apply`/ `talents spec` remain unchanged.

**Rollback:** Set `NaxxramasCore.BotTalentImport.ApplyEnabled = 0` (and optionally `NaxxramasCore.BotTalentImport.Enabled = 0`) in the active config, then restart Worldserver. Any already applied character talents remain normal AzerothCore character data: disabling the importer does not revert those talents. Restore individual talents from an independently backed-up character DB if needed. The additive `mod_naxxramas_bot_talent_import` table can be removed after backing it up and only when custom profile records are no longer wanted; doing so does not automatically undo previously applied talents. For complete source rollback, revert only importer-related commits after backing up local work. Never use `git reset --hard`.

## Operating steps (after initial compilation succeeds)

1. Back up active configs; ensure module repo has updated with `git pull --ff-only` and compile/test the source.
2. Set **only** `NaxxramasCore.BotTalentImport.Enabled = 1` in your active `mod_naxxramas_core.conf`, then restart Worldserver.
3. Summon/invite your test Warrior Playerbot so it is **online**.
4. In a **GM account** issue the preview command with the entire sample NT1 code.
5. Verify server reports a valid 49-point plan with 2 unspent. The bot's talents must be unchanged.
6. Try the `apply` command: **it should say APPLY NOT ENABLED** and must still leave talents unchanged.
7. Re-test malformed codes: none should change characters.
8. Keep `ApplyEnabled=0` until the application/rollback tests are successful; then make a separate production release decision.

## Future MultiBot fork work

After the real apply operation works and persists, add UI support **only to the user's MultiBot fork**. The module now contains optional server-side non-GM permission and ownership checks, but their runtime operation is not yet validated and addon integration must not bypass them. Confirm security/permission behaviour: GM-dot commands are **not** the same as bot whispers, and an addon cannot bypass server permissions. Display user-friendly validation errors and character name/build status in MultiBot. Do not edit MultiBot while backend commands are experimental.
