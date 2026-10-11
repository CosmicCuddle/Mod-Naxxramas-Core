# NT1 Alt Bot Talent Repair — Controlled Normalisation Proposal

**Decision recorded:** 11 October 2026. **Review status:** DESIGN ONLY; NO destructive repair implementation, migration, server activation, or merge. The administrator has clarified that the affected Priest characters are **Alt Bots** and supports **wiping illegal/current-tier-incompatible talents from the selected active spec and rebuilding the requested, fully valid NT1 talent allocation**, rather than permanently blocking all talent changes when previous Playerbots assignments are illegal.

This is **not** consent to delete any other character data, equipped/unequipped items, off-spec talents, unrelated class/trainer spells, bags, wealth or professions. No silently triggered repair on group joins, login, class/spec menu changes or Playerbots maintenance. Do not modify AzerothCore, mod-playerbots or Individual Progression.

## Why existing Apply fails safely

The current module builds an `EncodeExisting(bot, requested.Progression)` snapshot of the bot's **current active spec**, then validates it with the same `ParseCode` used for the requested target NT1. A later-era talent in an otherwise level-60 Vanilla bot makes the *existing snapshot* fail the Vanilla row/capstone filter. This happens **before reset**, hence the observed `No changes made.` messages.

Live user evidence at 16:05–16:08:
- Existing Talent.dbc ID **1768**: Priest **Holy Concentration**, Holy row **6**, column **0**. Vanilla limits row 6 to the centre-column capstone; this talent is not permissible under the current Vanilla rule.
- Existing Talent.dbc ID **1202**: Priest **Borrowed Time**, Discipline row **9**, column **1** (WotLK tree depth), beyond Vanilla's permitted row ceiling.
- The user's three replacement Priest `NT1:vanilla:priest:` codes have **51/51 points** each (two Discipline 32/Holy 19; one Discipline 14/Holy 37). Their IDs/ranks/dependencies/Vanilla-era rows appear valid against the published DBC snapshot (CosmicCuddle/Naxxramas-Resource-Hub, `talents/data/server-talents-v1.gz.b64`, blob `9a11c998850b3069ca15d42f5c6c24b124e5ec21`, dated 8 October). This does **not** prove every actual server DBC entry or the game's learning path, and this test did not successfully Apply talents.
- Reason for denial: old-build rollback requirements, **not** the requested target build. Rejecting Apply until a proper controlled repair path exists is correct.

## Critical AzerothCore API discovery

Review of upstream `azerothcore/azerothcore-wotlk/src/server/game/Entities/Player/Player.cpp::Player::resetTalents(bool)` reveals:

1. `resetTalents(true)` enumerates talents and removes only those whose `specMask` includes `GetActiveSpecMask()`; **the other specialization is not intentionally reset**.
2. The reset may `RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true)`, remove talent-granted spells/auras, remove Titan Grip / Dual Wield state and call **`AutoUnequipOffhandIfNeed()`**. Consequently, even a normal talent reset can indirectly change equipped/offhand item position for Warriors or Shamans. An assertion that `resetTalents` “never touches Alt Bot equipment” is **incorrect** without additional guards. The future repair procedure must fail closed for offhand/equipment-dependent cases unless actual pre/post GUID-safe equipment and inventory invariants can be enforced without consuming bag space; do not re-equip or move gear silently.
3. `resetTalents(true)` bypasses reset-money cost, but invokes Player reset hooks; verify pet/spell/aura/dual-spec side effects against the actual server module set.
4. Current `character_talent` uses `(guid,spell,specMask)` (primary key `guid,spell`); `character_spell` also tracks `(guid,spell,specMask)`; `character_glyphs` records `talentGroup` and six glyph slots. The full backup/rollback scope **cannot be reduced to just `character_talent`**. Verify target core schema at deployment; never write directly to these tables while an affected bot is online.

## User-approved intent versus implementation restrictions

### Desired target outcome
- An explicitly commanded, individually named, **eligible account-controlled Alt Bot** with illegal old Vanilla talents should be able to discard that **selected spec's** original incompatible talent allocation and receive the **fully validated new era-correct NT1** build.
- Character issuing the command must be on `NaxxramasCore.BotTalentImport.AltBotAllowedPlayers` (distributed default empty, **even GM cannot bypass**), plus existing `AccessMode`, non-GM ownership / bot-master and Individual Progression human-era checks.
- No automatic change to items/equipment/inventory, unrelated trained spells, the inactive specialization, professions or the user account's other characters.
- Only the issuing human's **actual Individual Progression stage** determines unlocked era: stages 0–7 Vanilla, 8–12 TBC, 13+ WotLK, respecting `IndividualProgression.ProgressionLimit`. A bot's level, class and rank/tier requirements are additional stricter gates; a player may not transfer later-era talents back into Vanilla.
- Target must be online, alive, out of combat, and the new plan must spend **all** `CalculateTalentsPoints()` points. Never clear existing talents on an invalid new plan.

### Proposed standalone workflow (not implemented)
1. **Read-only inspect/preview.** Identify human issuer, Alt Bot GUID/name/account, active spec, bot level, human IP stage, current talent ranks and illegal talent IDs/names/rows, selected new NT1 code, prerequisite legality, full-point allocation, dual-spec and gear/offhand state. Explain normal Apply refusal and explicitly mark `ALT_BOT_REPAIR_REQUIRED`, **not** ordinary `APPLY_READY`. No writes or resets.
2. **Backup checkpoint outside the bot session.** Administrator must take and *verify recoverability* of a consistent **characters DB backup** before any experimental destructive repair, plus backup of the precise affected character/spec. Snapshot current talent rank spells, `specMask`, `character_spell`, glyphs, relevant pet/talent/spell consequences and character data. An online SQL snapshot without safe consistency is not sufficient. A module-owned recovery journal may assist audit but is not a proven substitute for an offline restore-capable database backup; do not simply claim `SaveToDB` plus SQL rows makes recovery transactional.
3. **Separate, explicit, opt-in repair authorization**, disabled by default even if NT1 `AccessMode` is 1 or 2. Suggested future setting `NaxxramasCore.BotTalentImport.AltBotRepair.Enabled = 0`. Require a deliberate user action targeting a specific bot, spec and NT1 plan, with a fresh issuer/target/security/IP/class/DBC check immediately before any change. No silent “repair if illegal” side effect during normal Apply. Prevent repeated attempts and concurrent maintenance/spec switches.
4. **Gear invariant.** Capture all equipped slot item GUIDs and bag contents; refuse if talent loss could auto-unequip or otherwise move an item (especially Titan Grip/Dual Wield). Do **not** consume bag space, silently destroy an item, mail it, or “restore” gear via a generated replacement. Reject the repair if the invariant cannot be proven. For Priest target cases the risk of talent-dependent offhand removal appears lower, but it still needs a real live test; never generalise without verification.
5. **Selected-spec reset, then validated rebuild** only after all gates are met. Verify `resetTalents(true)` actually completed and current spec identity did not change. Learn exactly selected verified target ranks and check **all** class talent ranks, available points and relevant spell/auras. Reverify equipped-slot GUIDs, offspec talent/spell state and ownership before reporting success; preserve original Alt Bot equipment.
6. **If rebuild fails:** no fabricated success message. Because original talents may be illegal, the ordinary `LearnValidated(snapshot)` rollback **cannot be assumed to work**. Mark `RECOVERY_REQUIRED`, stop further repair attempts, guide the admin to use the tested **offline** restore procedure with Worldserver stopped and the affected character offline. Do not reload an inconsistent online character from backup. A proper hardened recovery implementation is required before real deployment.
7. **Persistence/maintenance:** Verify corrected spec after logout/relog/server restart; check upstream `AiPlayerbot.AltMaintenanceTalentTree` behaviour. Playerbots maintenance must not immediately reintroduce incompatible talents. Avoid modifying upstream modules without explicit discussion; if the permitted module cannot prevent conflicting maintenance reliably, block and explain.

### Review/acceptance tests before enabling
- Failure with missing/unverified DB backup, unlisted issuer (GM included), non-owner in mode 2, random-bot target, blocked era, invalid NT1, underallocated target, bot in combat/dead, spec switched since preview, or unsafe offhand/equipment state: **zero talent reset/item mutation**.
- Live Priest Alt Bot with existing `1768` or `1202` (or both): read-only diagnostics list exact IDs/rows; repair cannot proceed until explicit opt-in, backup and confirmation. After *approved* experiment, verify 51/51 correct requested talents and spell/auras plus identical item GUIDs, inactive-spec talents and original bag state.
- Force learn failure after reset and prove a **tested full offline restoration** returns all affected player data, not just `character_talent`. If this cannot be shown, do not enable repair.
- Restart/relog, dual-spec switching, Playerbots Alt maintenance and ownership changes must not silently reintroduce illegal ranks.
- No SQL migrations, C++ repair commands or configuration additions are approved or implemented in this design-only change.

## Staging plan

Stage A (next separate code PR, read-only): `altrepair preview` or similar explicit diagnostic, integrated with PR #7 shared preflight; report current illegal talents/restore restrictions, target eligibility and unsafe equipment cases, no state writes.

Stage B (separate reviewable patch): recovery snapshot design and backup/restore rehearsal; verify core API side effects and maintenance interactions.

Stage C (explicit owner approval required): default-off, named-Alt-Bot-only selected-spec reset/rebuild, after automated guard coverage, C++ compile, backup evidence and real Worldserver negative tests. No merging/activation until approved.

**Currently available safe action:** do not retry NT1 `apply` on these out-of-era Priest Alt Bots. Existing command has correctly refused without modifying talents. Using a different 51/51 target code does not remove the old-build restoration blocker.
