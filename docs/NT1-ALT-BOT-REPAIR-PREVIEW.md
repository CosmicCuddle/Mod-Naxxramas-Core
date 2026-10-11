# Alt Bot NT1 Repair Inspection — read-only diagnostic (draft)

**Status:** Added to the separate draft branch \`feature/nt1-altbot-repair-readonly-diagnostics\` stacked on the unmerged PR #7 shared preflight. **No talent repair/reset/apply feature is added or authorised by this branch.** No production deployment, migrations, DBC modifications or Playerbots/Individual Progression changes.

## Why

Two live Priest Alt Bot attempts failed safely before resetting any talents:

\`\`\`text
NT1 apply aborted: Existing talents cannot be safely restored:
Talent ID 1768 is outside the allowed rows for vanilla. No changes made.

NT1 apply aborted: Existing talents cannot be safely restored:
Talent ID 1202 is outside the allowed rows for vanilla. No changes made.
\`\`\`

These are talents in the **bot's existing active specialization**, NOT invalid IDs in the requested replacement. The 8 October 2026 Resource Hub server-DBC snapshot identifies:

| Talent.dbc ID | Priest talent | Position (zero-based) | Vanilla reason |
| --- | --- | --- | --- |
| 1768 | Holy Concentration (Holy) | row 6, col 0 | Vanilla's permitted row-6 capstone is in the centre column |
| 1202 | Borrowed Time (Discipline) | row 9, col 1 | Vanilla limits rows to 0–6 |

The new inspection reports ALL detectable existing out-of-era talents (chat display capped at the first 12 plus remaining count) without changing them. It **does not delete them** and is not proof the pre-existing spec is restorable.

## Read-only command, once a reviewed C++ build is installed

\`\`\`text
.naxxbot talents repairpreview <online-altbot-name> <full NT1-code>
\`\`\`

Example command format, using the user's previously supplied first 51-point Vanilla Priest build:

\`\`\`text
.naxxbot talents repairpreview BotName NT1:vanilla:priest:8y-1.9h-3.9j-3.9k-2.9n-3.9o-1.9r-1.9s-3.a1-3.b5-5.ba-3.be-2.ca-1.wt-5.xd-5.1d7-2.1d8-3.1gq-5
\`\`\`

**Do not run this on the production server today; it only exists in the draft code.** It must first pass C++ compilation and in-game read-only tests on an approved development build.

### Illustrative reply (not claimed to have occurred in game)

\`\`\`text
NT1 ALT BOT REPAIR INSPECTION: <BotName> (level 60, active spec 0).
Requested vanilla build: 51 / 51 points.
Existing active-spec talents outside vanilla policy: 2.
Existing invalid Talent.dbc ID 1202: rank <actual>, tree 0, row 9, column 1 (zero-based).
Existing invalid Talent.dbc ID 1768: rank <actual>, tree 1, row 6, column 0 (zero-based).
NT1 ALT REPAIR DIAGNOSTIC BLOCKED: Existing talents cannot be safely restored: ...
NT1 ALT REPAIR DISABLED: no repair Apply command exists. Normal reset may affect offhand gear; recovery is unverified.
READ ONLY: no talents, spells, equipment, bags or database records have been changed by this inspection.
\`\`\`

### Permissions

The handler reuses existing \`ValidateRequest\`, so it honours \`AccessMode\` (distributed default \`0\`), issuer identity, normal Playerbot control requirements, bot class, DBC/legal new target, current level and **issuer's** exact IP expansion (hidden quests 66001–66018 and configured progression limit).

After validation, the handler additionally requires:
- A real, online human issuing player (not a bot).
- A non-Random Playerbot target. **Random Playerbots cannot use this Alt Bot repair diagnostic.**
- The human issuing character's exact name in \`AltBotAllowedPlayers\`, even for GMs; the list's distributed default remains \`""\` (deny). Existing GM/master controls do not expand.

This diagnostic does **not** change or override the allowlist, grant any right to edit equipment or silently approve a later destructive action.

### What it reports

- Requested valid NT1 era, bot identity/level/active specialization, current requested point budget.
- Every existing, active-spec Talent.dbc rank that fails the **same server-side \`AvailableInEra\` row/capstone rule** as an NT1 request.
- \`CheckApplyReadiness\` result from PR #7 and **the actual blocker** (for the affected Priests, the existing build is not safely restorable). A legal proposed NT1 is not an Apply guarantee.
- Explicit **repair disabled/read-only** warning and offhand side-effect caution.

The inspection deliberately **does not** alter talent rows, learn spells, reset pets, touch other specializations, save to DB or touch bags/equipment. It does not inspect non-talent, separately learned class spells, original talent spell effects/auras, complete SQL snapshots, or comprehensive spec/glyph/pet recovery. The lack of these checks prevents destructive repair from being considered safe.

## Next approval gates (separate future PRs)

1. **Compile and read-only field test:** after approval and a reviewable combined PR #7 + diagnostics build, test a single affected level-60 Priest Alt Bot with a 51/51 Vanilla NT1. Confirm both IDs display and that no talents/inventory change. Test allowlisted vs unlisted characters, other-account bot permissions, Random Bot refusal, wrong era and disabled mode. No Apply.
2. **Verified recovery plan:** offline/consistent characters DB backup, per-GUID selected-spec snapshot, original \`character_talent\`/\`character_spell\`/\`character_glyphs\` preservation, full dual-spec and player-spell/auras/pet effect checks; rehearse full restore with bot offline. No direct SQL edits to an online player.
3. **Item invariant:** \`Player::resetTalents(true)\` in current AzerothCore may invoke \`AutoUnequipOffhandIfNeed()\`. Do not promise unchanged Alt Bot equipment merely by calling reset. Before a later repair, prove GUID-level equipment/inventory safeguards can prevent or reject mutation without bag-space consumption. Alt Bot equipment must never be intentionally replaced.
4. **Explicit, separate, disabled-by-default repair Apply:** proposed future \`NaxxramasCore.BotTalentImport.AltBotRepair.Enabled = 0\` is **NOT implemented by this PR**. It will require the existing name allowlist, real ownership/GM policy, verified backups and active-spec recovery, fixed era/class/point budget, independent explicit confirmation, revalidation, and failed-repair recovery evidence before any enabling.

**Source testing only:** \`tests/test_nt1_altbot_repair_preview.py\` checks read-only call sites and fail-closed permission flow. Passing Python source-contract tests **do not constitute compilation or real-game safety proof**.
