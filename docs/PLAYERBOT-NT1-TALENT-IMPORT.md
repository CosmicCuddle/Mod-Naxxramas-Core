# Naxxramas Talent Calculator -> Playerbots (NT1)
## Change Notes 1.0.6.8.5 — Phase 1: read-only validation

**Development status:** Phase 1 preview plus experimental Phase 2 apply source committed; **NOT YET COMPILED, RUN OR VERIFIED ON THE LIVE SERVER**. Both are disabled by default, with separate configuration switches. The actual apply routine has not passed acceptance testing. Do not enable apply on your live realm yet.

**Absolute rule:** No modification to `mod-playerbots`, AzerothCore or Individual Progression source files. MultiBot addon integration is postponed until the server command actually works and has passed tests.

## Safe and reversible scope

- Source: `src/Systems/BotTalentImport.cpp` (new CommandScript)
- Loader: `src/NaxxramasCore_loader.cpp`
- Config default: `NaxxramasCore.BotTalentImport.Enabled = 0`
- **NO SQL/DBC installation or character update** during Phase 1. Phase 2 includes an **optional additive characters SQL migration** at `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql`, which must not be installed without a database backup and explicit test planning.
- GM-only; target must be an online Playerbot. Normal Playerbots commands remain unchanged.
- **With `ApplyEnabled=0` (default), the `apply` command remains strictly READ-ONLY.** Experimental application code now exists behind `NaxxramasCore.BotTalentImport.ApplyEnabled = 1`, which is **not approved for live deployment** before compilation and comprehensive rollback tests. With the switch off it never calls `resetTalents`, `LearnTalent`, or `SaveToDB`.

### Available commands (Phase 1)

```text
.naxxbot talents preview <online-botname> <NT1-code>
.naxxbot talents apply <online-botname> <NT1-code>
```

By default the second command never changes talents. In Phase 2 experimental testing, it could modify talents **only if both** the top-level enabled flag and the separate `ApplyEnabled` flag are turned on, the bot passes complete validation, the persistence table exists, and a restorable current talent snapshot can be captured. **Keep `ApplyEnabled=0` for now.**

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
5. Enforce website row/position rules: Vanilla first six full rows plus final capstone, TBC first eight full rows plus capstone, WotLK all rows. Handle exact off-centre capstones: Vanilla Stormstrike (tab 263/talent 901), Vanilla Dark Pact (tab 302/talent 1022), TBC Divine Illumination (tab 382/talent 1747).
6. Reject unknown or unsatisfied DBC talent prerequisites (zero-based DependsOnRank).
7. Check total spent points against the bot's **real** `CalculateTalentsPoints()` (not a hardcoded 51).
8. Find a legal learning sequence using prerequisite dependencies and five earlier-tree-row points per unlocked row. This is a pure preflight: the validator never learns anything.
9. Preview prints server tab distributions and deliberately unspent talent point count.

## Key limitation discovered in existing Naxxramas Core

`src/Systems/BotTalentExpansionLimits.cpp` mirrors Playerbots' level-based row restriction and generally allows only **column 1** on final rows. That conflicts with the three off-centre calculator capstones listed above. It must be reconciled **inside Naxxramas Core only** before activating the actual apply feature, without globally relaxing the old guard for unrelated Playerbots builds.

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

Do not enable application merely because Phase 1 compiles. Test on disposable online bots in a test realm:

- Valid 49-point level-60 Warrior NT1 code; 2 points remain when application is eventually enabled.
- All available classes and deliberately unspent points, and the three off-centre capstones.
- Custom talent 3000 (Rend Flurry), other modified trees/rank spells, empty and missing-rank data.
- Wrong class, malformed/version mismatch, duplicate talent IDs, impossible ranks, missing dependencies, too many points, level/era mismatch: **no resets**.
- Existing build -> replacement; pre-existing dependent spells properly removed.
- Dual specs; relog; server restart; Playerbots AutoPickTalents; Playerbots incremental and full randomization; Playerbots upstream update.
- Manual original `talents apply`/ `talents spec` remain unchanged.

**Rollback (Phase 1 only):** set `NaxxramasCore.BotTalentImport.Enabled = 0` in active server config and restart Worldserver. For complete source rollback, revert only the importer commits using Git after first backing up local work. Do not use `git reset --hard`. No talent DB rows exist for this phase.

## Operating steps (after initial compilation succeeds)

1. Back up active configs; ensure module repo has updated with `git pull --ff-only` and compile/test the source.
2. Set **only** `NaxxramasCore.BotTalentImport.Enabled = 1` in your active `mod_naxxramas_core.conf`, then restart Worldserver.
3. Summon/invite your test Warrior Playerbot so it is **online**.
4. In a **GM account** issue the preview command with the entire sample NT1 code.
5. Verify server reports a valid 49-point plan with 2 unspent. The bot's talents must be unchanged.
6. Try the `apply` command: **it should say APPLY NOT ENABLED** and must still leave talents unchanged.
7. Re-test malformed codes: none should change characters.
8. Set `Enabled=0` after testing, until Phase 2 is approved and built.

## Future MultiBot fork work

After the real apply operation works and persists, add UI support **only to the user's MultiBot fork**. Confirm security/permission behaviour: GM-dot commands are **not** the same as bot whispers, and an addon cannot bypass server permissions. Display user-friendly validation errors and character name/build status in MultiBot. Do not edit MultiBot while backend commands are experimental.
