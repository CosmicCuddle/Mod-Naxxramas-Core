# NT1 read-only exact talent match — pre-merge/release review

**PR:** [#18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/18)  
**Reviewed gameplay-code HEAD:** `ec5dc971bdea6a913e61e84fa390ee3260279d3e` (later documentation-only commits require latest CI re-verification)  
**Base `main`:** `69a91be2ded62f6cdccf7ca6e7119ebdcc45e81b`  
**Status:** Pre-merge review prepared. **NOT MERGED, NOT INSTALLED, NOT IN-GAME TESTED.** The full-link test succeeded on isolated pinned sources only.

## 1. What is safe to release in this PR

The source comparison from base to reviewed gameplay-code revision reports one gameplay C++ file changed:

- `src/Systems/BotTalentImport.cpp`: **202 additive lines**, no removed C++ lines.
- Adds an active-spec `EXACT` / `DIFFERENT` / `CANNOT VERIFY` talent rank and free-points inspector.
- Calls the inspector only from **existing read-only** `preview` and `repairpreview` reporting. No new bot/chat command or addon protocol.
- No change to `CheckApplyReadiness`, `ApplyValidated`, either `bot->resetTalents(true)`, `LearnValidated`, `CanApplyToAltBot`, any SQL migration, config defaults or equipment API calls.
- Preview of the protected **Alt Bot** exact-rank report requires that the **human issuing character** appears in `NaxxramasCore.BotTalentImport.AltBotAllowedPlayers` even if GM. Repair Preview already requires this. Other access and ownership/era gates remain in place.
- An `EXACT` message **DOES NOT** mark Apply safe. The active-pet and any-equipped-offhand Alt Bot blocks remain in place, including Arndor's held-in-offhand #22319.
- No talent or gear rollback, no direct learn/no-reset mode and **no automatic role-dependent equipment changes** have been added.

**This release milestone is diagnostics only, not the originally requested offhand exemption.** Keep the unsafe-reset investigation separate and tracked after this milestone.

## 2. Verified checks at the reviewed commit

| Gate | Evidence | Result |
|---|---|---|
| Python source/regression suite | [combined action run #38394659511](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38394659511) | **255 tests pass** |
| Exact read-only C++ function fixture | Same combined run | **15 cases pass** |
| Pinned fork C++ entire NT1 translation unit | [#38394659493](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38394659493) | **PASS** |
| Full AzerothCore/Playerbots/IP static-module Worldserver build and link | [#38394659644](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38394659644) | **PASS** |
| Built executable contains the new exact-match output and pre-existing offhand refusal | Same full-link build, post-link binary-string verification | **PASS** |
| Other read-only, recovery and NT1L1 projection source suites | Other actions on same commit | **PASS** |

These are **CI results from a disposable GitHub runner** using these exact sources:
- AzerothCore `mod-playerbots/azerothcore-wotlk`: `b7f06a16ac7120b5abc2e8d3f96a94265a363224`
- Playerbots `mod-playerbots/mod-playerbots`: `037c01418b5d01506917a3db9b44fd56ac5f965c`
- Individual Progression `ZhengPeiRu21/mod-individual-progression`: `283abe12774801e5671da746ea8bf535cc0252e0`

Do **not** assume a user's actual source patches, module combinations, config, custom DBC or production binary match these public commits.

## 3. Remaining approval gates: stop rather than guessing

1. **Owner authorises PR merge separately.** Do not merge or mark deployed from this review document alone. Update this review if the PR HEAD changes and verify latest Actions again.
2. **Before local update** the owner checks the actual installed module path, current branch and any uncommitted custom edits using **read-only** `git status --short` and `git branch --show-current`. No forced checkout or reset. A simple `git pull` on `main` does **not** fetch the draft PR yet.
3. **Safeguard the current production installation:** independently back up actual module source, effective module configuration, local patches/DBC and the **known-good** Worldserver binary before rebuild or restart. Keep the earlier known-good version available for binary rollback.
4. Since the active server may have local changes or extra modules, build in a **separate worktree/test checkout** first if possible, compare actual pinned revisions, and confirm the NT1-only source differences; fail on unexpected build errors.
5. For any production change, record a **consistent whole `acore_characters` backup and a verified isolated restore**. The read-only SQL evidence template is **not a backup**.
6. **Owner-approved read-only acceptance only:** test an appropriately controlled disposable Alt Bot with normal `.naxxbot talents preview <botname> <NT1-code>` and `.naxxbot talents repairpreview <botname> <NT1-code>`; confirm expected `EXACT`, `DIFFERENT`, `CANNOT VERIFY` as safely reproducible, and the continued `NT1 PREFLIGHT BLOCKED` for occupied offhand/pet. **Do not use `.naxxbot talents apply`** to test diagnostics.
7. Confirm AccessMode 3/4 still prevents Apply; human allowlist, IP-era rejection, normal non-GM ownership and MultiBot two-step confirmation remain unchanged.
8. After logout/restart, review logs and verify **no item instance GUID moved, no talents or equipment altered by read-only commands**, and no addon user-interface regression.
9. If anything fails, **stop testing** and restore only by the owner's independently rehearsed server/database procedure; do not improvise item recreation, reset SQL or fresh GUIDs.

## 4. Final owner-to-MultiBot handover — required, NOT delivered yet

Once the *entire* Naxxramas Core talent/offhand workstream is finalised, prepare a concise copy-and-paste-ready note for the N-MultiBot-Chatless developer chat and draft PR #5 covering:

- Exact merged/deployed server commit and whether the new server reports are visible.
- The three new read-only chat messages: `NT1 ACTIVE TALENT MATCH: EXACT`, `DIFFERENT`, `CANNOT VERIFY`, plus the `NT1 ACTIVE MATCH LIMIT` disclaimer.
- The unchanged `preview`, `repairpreview`, `safetypreview`, `apply` syntax and server authority. **No client-side reinterpretation of `EXACT` as Apply-ready** and no automatic gear changes.
- Required addon UI tweaks only if empirically needed after in-game tests. Server-only diagnostics should not force an addon release without an observed compatibility issue.
- Preserved offhand/pet blocks and actual outcomes of tests/rollback validation. Do not infer item safety solely from the passing C++ build.

## 5. Merge decision for this milestone

**Technically built and source-tested; in-game diagnostics acceptance not yet verified.** The diagnostics-only release can be considered for explicit owner-approved merge once the owner accepts those proof limits, reviews custom compatibility and has a backup/rollback plan. This PR **must not be represented as completing the separate offhand-preservation/transactional-Apply goal**. Keep that open as a distinct next milestone rather than bypassing the guard.
