# NT1 Playerbot Talent Safety — Development Handover
**Date:** 12 October 2026
**Repository:** https://github.com/CosmicCuddle/Mod-Naxxramas-Core
**Current feature branch:** `feature/nt1-crossclass-readonly-risk-audit`
**Current review PR:** https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/16
**PR status:** OPEN, DRAFT, **UNMERGED** (base `main`)
**Purpose:** preserve engineering status, operational safeguards, current feature work, evidence and next steps for another development session.

> **Operational boundary:** The user has explicitly requested **bulk changes** when useful, but DOES NOT want frequent unnecessary recompilation. Research and development can proceed in the user's GitHub repository on a **draft** branch. Do not merge or deploy PR #16, edit their live Linux server, touch the character database, relax gear/pet guards, or perform destructive talent tests without first confirming the user's approval for those specific steps. Keep old game source and database recoverable. Explain steps clearly and simply.

## 1. Background and concrete user test

The user runs a WotLK 3.3.5a AzerothCore server with Playerbots, Individual Progression and Naxxramas Core. Their bot-talents UI is built around `NT1:<era>:<class>:...` website presets. Custom NT1 module code is **only** in this repository, not upstream AzerothCore/Playerbots/IP.

The original issue: Priest **Rakari** (level 60, Vanilla progression) could preview a **51/51** valid Vanilla Priest target, but ordinary `.naxxbot talents apply` failed **BEFORE reset** with:

`Alt Bot NT1 Apply blocked: an offhand item is equipped. Talent reset could move or MAIL it.`

The user also tried a second valid-looking Priest NT1:
`NT1:vanilla:priest:9k-2.9n-3.9o-1.9s-3.a1-3.b5-5.b6-5.b8-5.ba-3.bc-3.be-2.bh-2.ca-1.wt-5.17d-1.19f-2.1gq-5`
This was blocked on the same offhand safety condition, not proven invalid due to its allocation. The first proposed 51-point Priest test code was:
`NT1:vanilla:priest:8y-1.9h-3.9j-3.9k-2.9n-3.9o-1.9r-1.9s-3.a1-3.b5-5.ba-3.be-2.ca-1.wt-5.xd-5.1d7-2.1d8-3.1gq-5`.

**Observed Rakari diagnostic:** 0 detected out-of-Vanilla talents in the CURRENT active spec; active spec 1/2, 17 rank-spell records in spec 1 and 0 in spec 2; 18/19 equipment slots occupied, offhand YES, active pet NO. The older `repairpreview` inspected only active-spec out-of-era ranks. These observations do NOT prove the other Priest Alt Bots are legal, nor that the 51-point targets are universally safe to apply.

User asked to **consider every class and specialization** for comparable issues: 10 WotLK classes (Warrior, Paladin, Hunter, Rogue, Priest, Death Knight, Shaman, Mage, Warlock, Druid), rather than removing Rakari's offhand or adding a Priest-only exception.

## 2. Actual AzerothCore behaviour and non-negotiable guards

Public AzerothCore `Player::resetTalents(bool)` may trigger `OnPlayerTalentsReset`, `RemovePet(..., PET_SAVE_NOT_IN_SLOT, true)`, talent and triggered spell/aura removal, Titan's Grip/dual-wield invalidation, then `AutoUnequipOffhandIfNeed()`. When offhand incompatible, core can transfer original offhand item to inventory or **MAIL it** when bags are full. `ActivateSpec()` is a DIFFERENT, mutating operation: saves/loads action bars, removes pets/totems, affects glyph/other auras and again assesses offhand. Never switch spec to perform a diagnostic.

Additional risk: `NaxxramasCore.BotTalentCompletion.Enabled = 1` in the user's config, so Playerbots talent completion hooks can operate around reset, spec changes and subsequent ticks. The NT1 scoped importer handles its own interactions but requires controlled runtime verification.

Current Alt Bot ordinary NT1 `apply` has **two fail-closed equipment/pet cases**: ANY occupied offhand, ANY active pet. These are intentional and remain unchanged on PR #16. Do not silently unequip/re-equip, mail, replace equipment, change item-instance GUIDs, auto-generate gear, change inactive spec, delete talent ranks or bypass rollback checks. **There is no implemented `repairapply` command or fully verified transactional character restore**. Out-of-era original Priest talents such as IDs 1768/1202 were seen on OTHER previously discussed Priest Alt Bots and can block old-build recovery; the system must not reset those talents without independently verified full recovery.

**Backup requirement before any destructive experiment:** consistent, stopped-Worldserver `characters` database dump, tested isolated restoration, ability to compare/restore both specs (talents, learned spells, glyphs, action bars), pets (including inactive/stabled), original `item_instance` identities, bag/bank/mail mappings, equipment, auras/related persisted character state. Existing offline backup auditor verifies format/required tables; **it does NOT verify an actual DB restore**. A checksum from the online diagnostic is NOT a backup.

## 3. GitHub status and installed-version distinction

**Merged `main`:**
- [PR #14](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/14) combined NT1 `preview`, `project`, `repairpreview`, preliminary safety checks, existing experimental `apply`.
- [PR #15](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/15) added **AccessMode 4** = normal-player **read-only** Preview/Project/Repair Preview; early `apply` refusal. Distributed default remains mode 0 disabled. Mode 3 = GM read-only; mode 2 = ordinary players with **experimental destructive Apply**, therefore unsafe for routine read-only testing.
- At handover, repository `main` ref previously verified `86bf82d33137296820fe93d6747c31c0b64e83ba`, but always re-check before future edits.

**Unmerged draft under development:**
- [PR #16](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/16), `feature/nt1-crossclass-readonly-risk-audit`, base main, source and docs/tests. It was still OPEN/DRAFT/unmerged at handover. Re-fetch current head rather than assuming a SHA, since handover/docs commits may update it.
- **Do not tell the user `git pull origin main` includes PR #16** until it is explicitly reviewed and merged.

**Actual user's live server:** The user finished a compilation of the earlier combined NT1 integration and restarted Worldserver, then successfully ran `repairpreview` and `preview` on Rakari. Later PR #15 was merged, but the user explicitly wished to **avoid immediate recompile**; their active config shared in-chat was `NaxxramasCore.BotTalentImport.AccessMode = 2`, `NaxxramasCore.BotTalentImport.AltBotAllowedPlayers = "Takali, Drakka, Sequoia"`, `NaxxramasCore.BotTalentCompletion.Enabled = 1`. **Do not assume the running binary includes mode 4 or PR #16**; do not ask them to configure mode 4 until compiled from a version that implements it. They should avoid the destructive Apply command/addon confirmation in mode 2.

Linux module path `/root/azerothcore-wotlk/modules/mod-naxxramas-core`; build path used `/root/azerothcore-wotlk/build`. Their Git branch may differ. Never run unverified git commands against dirty local files without checking `git status`; take module/config backups before switching or deploying.

## 4. Work completed on PR #16

**C++:** `src/Systems/BotTalentImport.cpp`
- New `PrintAltBotCrossClassSafetyAudit`: examines current mainhand/offhand item entry IDs and InventoryType, observes Dual Wield and Titan's Grip, heuristically identifies AzerothCore offhand movement risk, distinguishes caster focus/shield versus offhand weapon/2H, reports class-specific issue categories for every one of the 10 classes. Titan's Grip is cleared BEFORE core offhand recheck, so a 2H mainhand must still be flagged even if presently dual-wielded. These diagnostics explicitly **never authorize** a reset.
- Reports active pet presence and unknown stabled/unslotted/guardian state, other spec/glyph/action bar risks, `BotTalentCompletion.Enabled` status and need for offline recovery.
- Existing `repairpreview` now checks out-of-era Talent.dbc ranks in **both** owned specializations with `Player::HasTalent(talentRankSpell, spec)` and `AvailableInEra`. Active-spec detail remains; inactive-spec reports count plus up to **6** individual offending IDs per spec; no `ActivateSpec`/other state changes.
- New **`.naxxbot talents safetypreview <online-altbotname>`** needs NO NT1 build. Calls the protected-state report and cross-class risk report. Still enforces enabled mode, real online human issuer, online recognised Playerbot, non-GM account/master rights, non-Random Alt Bot and the exact issuing human character's `AltBotAllowedPlayers`, **even for GM**. It never calls talent reset, pet removal, spec switch or item/DB mutation.
- Shared invalid-argument usage text no longer incorrectly claims every command is `preview`.
- Absolutely NO new destructive repair, unlock of Apply, access-mode default alteration, SQL/DBC migration, upstream core/Playerbots/IP edits or live bot actions.

**Tests:**
- `tests/test_nt1_crossclass_safety_audit.py`: 21 ten-class, dangerous-call, synthetic offhand/Titan's Grip scenarios.
- `tests/test_nt1_inactive_spec_era_audit.py`: 13 dual-spec era/legal talent diagnostics tests, synthetic invalid ranks 1202 and 1768.
- `tests/test_nt1_altbot_safetypreview.py`: 13 command-level source contracts (permissions, exact allowlist, no mutation).
- Other existing tests remain and pass.

**Docs:**
- `docs/NT1-CROSSCLASS-TALENT-SAFETY-AUDIT.md` (audit design, 10-class risk matrix, new command and detailed preservation checklist).
- `docs/PLAYERBOT-NT1-TALENT-IMPORT.md`, `conf/mod_naxxramas_core.conf.dist`, `ROADMAP.md`, `CHANGELOG.md` updated with no-code command, both specs and operator caveats.
- THIS dated handover document for continuation.

## 5. CI evidence — actual GitHub Actions, NOT a compile

Last completely verified CI runs on the PR #16 branch before this documentation-only handover:
- [Combined NT1 regression workflow](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38247248403): **139/139 PASS**.
- [Alt Bot recovery/backup contracts](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38247248427): **65/65 PASS**.
- [Alt Bot read-only diagnostic contracts](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38247248434): **12/12 PASS**.
- [Pinned NT1L1 Mage projection](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38247248379): **25/25 PASS**.

These suites **overlap** (139 combined already includes much of the above). They are Python/static/synthetic tests **only**: no C++ compilation against the user's local AzerothCore, no in-game test of new command, no actual DB backup or isolated restoration. The user should NOT recompile now unless they want to test the reviewed draft after a future approved merge.

## 6. Next work, in priority order

1. **Review PR #16 C++ compilation viability and API accuracy.** Verify against user's exact AzerothCore and Playerbots revisions, not just upstream master. Check `Item::GetTemplate()`, `Item::GetEntry()`, ClassName, enum constants, `Player::CanDualWield()`, `HasSpell(674)`, `CanTitanGrip()`, `PSendSysMessage` formatting, class enums, active/inactive spec mask logic and chat output length. Decide whether the heuristic really should use LIVE spell 674 (it reports conservative risk only). Keep blocker intact.
2. **Potential improvements**: break diagnostics into manageable chat lines instead of spamming; maybe add `safetypreview` on several bots, but never allow targeted Random bot or unauthorized human. Validate new code doesn't accidentally print sensitive records for non-owners or create side effects.
3. **CI and docs**: add meaningful code-level regression/synthetic tests for edge scenarios (missing mainhand, unknown template, 2H after Titan's Grip reset, talent-derived Dual Wield, inactive illegal ID, stabled pet unknown). Existing tests are static rather than C++ unit/runtime; never conflate them. Update draft PR #16 and handover if more changes.
4. **Only after user approval**, merge PR #16 to main as a **bundled** update, back up module/active config, `git pull --ff-only origin main`, compile, set `AccessMode = 4` in active config and restart Worldserver. Current user's mode 2 means avoid `apply` during tests.
5. In-game on a normal (non-GM) allowlisted character: `.naxxbot talents safetypreview Rakari` (NO NT1 code), and `.naxxbot talents repairpreview Rakari NT1:vanilla:priest:...` to see both-spec illegal talents. Then sample all 10 classes/3 specs using disposable bots and read-only commands; confirm equipment GUID/pet state unchanged. Do not switch specs merely for diagnosis.
6. **Longer-term separate work**, not in PR #16: transactional-style protected rollback/isolated DB restoration, original out-of-era Priest talents, and safe repair implementation. Do not bypass current offhand/pet guard on a caster focus until actual safe recovery is proven.

## 7. Clear next-chat operating instructions

- User is dyslexic: write **short, clearly ordered guidance**, explain what each server command does, avoid large one-shot shell scripts, and encourage backup before important operations.
- The user likes substantial, professionally organised GitHub feature work with **bulk commits/one compilation after review**, not constant small-change/recompile loops.
- Work exclusively on **Mod-Naxxramas-Core** for this task; avoid upstream code modifications and unrelated N-MultiBot-Chatless addon work unless requested.
- Before each edit re-fetch current PR/branch/commit, keep main unmodified. **NO silent merge** of PR #16; no live server/DB action.
- Do not claim static CI equals successful AzerothCore compilation, proper pet handling or complete rollback.
- Maintain `ROADMAP.md`, `CHANGELOG.md`, the audit design and a handover in the repo so this work can continue if another chat reaches its limit.
- Follow project-wide directives to avoid patronising phrasing, be specific about backups, test results, current access mode, Git status and what the user must do next.

**Suggested handoff continuation:** “Read this ENTIRE handover and `docs/NT1-CROSSCLASS-TALENT-SAFETY-AUDIT.md` plus the current draft PR #16 and code/tests. Continue reviewing/refining the ten-class read-only NT1 safety audit. Keep PR draft and do not merge/recompile/deploy until the user approves a bundled test update.”


## 8. Continuation checkpoint — second source/API review (12 October 2026)

**Scope:** One batched draft-source refinement, regression additions, and docs. No live realm/DB action, no merge, no Worldserver compilation.

- Confirmed public upstream AzerothCore signatures for item templates/entries, equipment, `HasTalent(spell,spec)`, glyphs, quest status, Dual Wield, Titan's Grip, `HasSpell`, and formatted chat. **This is NOT exact-local-source or C++ build validation.** The user's exact core, Playerbots and IP revision SHAs have not been supplied.
- No-code `safetypreview` reports the issuing **HUMAN character's** effective capped IP stage and Vanilla/TBC/WotLK era through a read-only helper shared with the existing NT1 era gate. IP-disabled is explicitly reported. This does not validate the bot build or reveal an inactive spec's glyphs.
- Unknown-template warnings print observed item entry IDs but remain **BLOCKED**. Unknown class text uses a non-null fallback. The Alt Bot offhand/active-pet guards and read-only mode 3/4 Apply denials have **not** been altered.
- New Python source/synthetic regression cases cover permit checks before the human IP report, shared era policy, disabled-IP, missing mainhand, unknown templates and unknown class text.
- PR #16 stays **DRAFT and UNMERGED**. CI must be rechecked on this new commit; older 139/139, 65/65, 12/12 and 25/25 results do **not** certify this update. No user-side Git pull/recompile is required merely because code was pushed.

**Next engineering gate:** inspect exact installed dependency revisions, complete updated static CI, seek approval for a **single bundled C++ compile** after review, then test the new commands read-only with protected-state comparison and 3.3.5a chat readability. Any destructive repair remains blocked until a verified isolated `characters` database restore, covering pets, item GUIDs, action bars, glyphs and both specs, is demonstrated.

### Verified post-refinement CI (commit `a9849977b15d883d3e60dc8fe34a60f3c9555809`)

GitHub Actions source/synthetic workflows completed successfully on the **new code commit**: [combined 147/147](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38250538734), [Alt recovery 70/70](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38250539122), [read-only diagnostic 12/12](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38250538540), [Mage projection 25/25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38250538905). Counts overlap. No C++ compilation, live-game test or isolated DB restore was performed. PR #16 remains draft/unmerged. Exact deployed core/Playerbots/IP revisions and controlled read-only inspection remain the next engineering gates.

## 9. Next draft addition — no-code, both-spec issuer-era comparison (12 October 2026)

### Draft extension — no-code issuer-era rank screening (not full validation)

When Individual Progression is enabled, allowlisted `.naxxbot talents safetypreview <online-altbotname>` now performs a **bounded, read-only DBC era-policy comparison in EACH owned specialization** against the **issuing HUMAN character's** effective capped Vanilla/TBC/WotLK era. The existing `GetOutOfEraTalents(bot, era, spec)` scans Talent.dbc rank spells via `HasTalent(spell, spec)`, without changing spec. Each spec displays a total plus at most three sample Talent.dbc ID/rank pairs. A missing or ineligible row is flagged even when there is no NT1 preset yet, making all-ten-class inspection more useful.

The issuer's current era **is not proof of the bot's own Individual Progression stage**. A zero count is **not** proof the complete build is legal, that prerequisites/point allocation are correct, or that a reset is safe. Glyphs, pets, original item GUID recovery and any anomalies outside DBC era ranks remain separate audits. If IP is **disabled**, the no-code era comparison is **not performed**; level-based restrictions continue, and a specific NT1 `repairpreview` is needed to inspect a selected target era. No automated repair, full talent validation, permissions change, offhand or pet exemption is introduced. This adds at most four short chat messages for the DBC era comparison even on dual-spec characters.

New source/synthetic checks cover both-spec boundaries, issuer allowlist ordering before output, IP-disabled exclusion, three-example cap, zero-count caveats and no dangerous C++ calls. Exact installed core/Playerbots/IP revisions, 3.3.5a chat readability and real compiled behaviour are **not yet verified**.

**Next:** rerun all source/synthetic workflows on the NEW code SHA; attach links and counts in PR #16. Leave the PR draft and unmerged. Do not compile or change live mode 2 without permission. A build check against the user's exact dependency SHAs and read-only in-game testing remain outstanding. No database changes or Talent.dbc edits have been made.


### Latest source CI and exact-dependency checkpoint

Source commit `41de01db0ebc12538c64a77a371b971cc6c176db` passed [combined 152/152](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334648), [recovery 75/75](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334657), [diagnostics 12/12](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334631), [Mage 25/25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334751). Counts overlap. No AzerothCore C++ compilation, actual in-game class test or isolated DB restore has been done. The read-only operator/source-SHA discovery protocol is in [NT1 Dependency Revision Checkpoint](NT1-DEPENDENCY-REVISION-CHECKPOINT.md). **Next work: identify exact installed AzerothCore/Playerbots/IP source revisions from operator evidence before an approved bundled build.** Keep PR #16 draft/unmerged, existing offhand/active pet guards unchanged, and no live server/database changes.
