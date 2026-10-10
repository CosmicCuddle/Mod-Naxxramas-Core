# Naxxramas Talent Calculator -> Playerbots (NT1)
## Change Notes 1.0.6.8.5 — Phase 1: read-only validation

**Development status:** source committed; **NOT YET COMPILED, RUN OR VERIFIED ON THE LIVE SERVER**.

**Absolute rule:** No modification to `mod-playerbots`, AzerothCore or Individual Progression source files. MultiBot addon integration is postponed until the server command actually works and has passed tests.

## Safe and reversible scope

- Source: `src/Systems/BotTalentImport.cpp` (new CommandScript)
- Loader: `src/NaxxramasCore_loader.cpp`
- Config default: `NaxxramasCore.BotTalentImport.Enabled = 0`
- **NO SQL/DBC installation or character update** during Phase 1.
- GM-only; target must be an online Playerbot. Normal Playerbots commands remain unchanged.
- **The `apply` command is RESERVED and CURRENTLY READ-ONLY**. It calls the same decoder and preview, then reports that apply is not implemented; it does **not** call `resetTalents`, `LearnTalent`, or `SaveToDB`.

### Available commands (Phase 1)

```text
.naxxbot talents preview <online-botname> <NT1-code>
.naxxbot talents apply <online-botname> <NT1-code>
```

The second command never changes talents until a later, separately tested implementation. This is a safety property, not an installation mistake.

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

## Phase 2 — Not implemented or approved for activation

- Add full preflight simulation against current talent trees and module policies, and a diff preview versus current active spec.
- Snapshot the bot's exact active spec and dependent spells before reset. Backup characters database before any live test.
- Implement a normal AzerothCore `resetTalents(true)` and `LearnTalent(talentId, rank-1)` application **only after full validation**.
- Verify every resulting selected rank and absence of old active-spec talent ranks; if a runtime failure occurs, attempt restoration from snapshot and report incomplete recovery prominently. There is **no built-in atomic reset+apply transaction**.
- Persist approved custom build in a **new, clearly named Naxxramas Core characters DB table** (additive SQL migration, rollback instructions, no Playerbots schema modifications) keyed by bot GUID + spec slot.
- Coordinate bot talent completion so explicitly unspent points are preserved.
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
