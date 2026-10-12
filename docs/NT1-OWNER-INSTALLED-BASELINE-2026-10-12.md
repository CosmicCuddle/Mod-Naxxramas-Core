# NT1 Owner Installation Baseline — 12 October 2026

**Status:** Operator-provided read-only Git evidence reviewed against public GitHub source. Draft PR #16 only; the running Worldserver binary was not inspected. No server actions or changes were performed by this project review.

## Actual source observations

The operator supplied MobaXterm terminal screenshots captured in the AzerothCore source directory. These commands were run on the operator's Linux host by the operator: `git rev-parse HEAD`, `git status --short`, and `ls -1 modules` for the core, plus `rev-parse` and `status --short` for each relevant module.

| Source folder on host | Full reported HEAD | Git status |
|---|---|---|
| `/root/azerothcore-wotlk` | `b7f06a16ac7120b5abc2e8d3f96a94265a363224` | Empty `git status --short` output (clean observed) |
| `/root/azerothcore-wotlk/modules/mod-playerbots` | `037c01418b5d01506917a3db9b44fd56ac5f965c` | Empty `git status --short` output |
| `/root/azerothcore-wotlk/modules/mod-individual-progression` | `283abe12774801e5671da746ea8bf535cc0252e0` | Empty `git status --short` output |
| `/root/azerothcore-wotlk/modules/mod-naxxramas-core` | `969f0429b4f02d8ba64ee83ecf4c91323e474bdd` | Empty `git status --short` output |

Git SHA and clean working tree **are source observations**; they do not establish where `worldserver` binaries came from, custom build flags, linked modules, runtime config, effective DBC content, or a verified rollback. The operator was **not** asked to pull, compile or stop the server.

The module directory listing included all three needed module folders. Additional `.rar`/`.zip` files in the directory were not read, extracted, modified or chosen as source.

## Public GitHub compatibility review against those exact commits

- AzerothCore core commit `b7f06a16...` is visible in [mod-playerbots/azerothcore-wotlk](https://github.com/mod-playerbots/azerothcore-wotlk/commit/b7f06a16ac7120b5abc2e8d3f96a94265a363224). Its actual `Player.h` includes per-spec `HasTalent`, const `GetTalentMap`/`GetSpellMap`, spec count/current spec, active glyphs, `GetItemByPos`, `GetQuestStatus`, `CanTitanGrip` and `PlayerTalent::specMask/talentID/State`. In actual `Player.cpp`, `resetTalents` calls a talent-reset script hook, can dismiss a pet, disables class-dependent offhand capabilities, and invokes `AutoUnequipOffhandIfNeed`. The latter has a mail fallback. These core methods must **not** be invoked by the new read-only inspection.
- Playerbots commit `037c01418b5d01506917a3db9b44fd56ac5f965c` is visible at [mod-playerbots/mod-playerbots](https://github.com/mod-playerbots/mod-playerbots/commit/037c01418b5d01506917a3db9b44fd56ac5f965c). Its `PlayerbotAI.h` exposes `GetMaster()`, `PlayerbotMgr.h` exposes `GetPlayerbotAI(Player*)`, and `RandomPlayerbotMgr.h` exposes `IsRandomBot(Player*)`.
- Individual Progression commit `283abe12774801e5671da746ea8bf535cc0252e0` is reachable from [ZhengPeiRu21/mod-individual-progression](https://github.com/ZhengPeiRu21/mod-individual-progression/commit/283abe12774801e5671da746ea8bf535cc0252e0). In `src/IndividualProgression.cpp`, `GetPlayerProgressionFromQuests` scans `66000 + stage` rewarded quests; the source reads `IndividualProgression.ProgressionLimit` from config. Its `src/IndividualProgression.h` enumerates Vanilla stages 1–7, TBC starting at stage 8 and WotLK starting at stage 13. This validates the NT1 issuer-stage *source concept*, **not** the bot's own IP stage, configured enablement, database state or current issuer stage. A matching commit in public GitHub does not prove which remote URL the operator configured; no `git remote` command was requested.
- Naxxramas Core installed commit `969f0429b4f02d8ba64ee83ecf4c91323e474bdd` is reachable at [CosmicCuddle/Mod-Naxxramas-Core](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/969f0429b4f02d8ba64ee83ecf4c91323e474bdd), the earlier integration of the read-only mode 3 work.

**Lineage / expected update boundary:** GitHub's commit comparison shows that the owner's Naxxramas Core installed commit is **one commit behind** the draft PR's base `main` (`86bf82d33137296820fe93d6747c31c0b64e83ba`). Draft PR #16 currently has **31 commits beyond that main baseline** (review checkpoint `1fbd3e207511e688d7857435906397475f589321`). A normal `git pull` on the owner's current `main` will therefore **not** bring in the PR #16 diagnostics.

## What has and has not been demonstrated

**Established in source review:** required basic API signatures are present in the public repositories at the exact reported core/Playerbots/IP commits; the IP rewarded-quest stages are consistent with the new read-only logic; the draft NT1 source continues to protect against talent reset with occupied offhand/active pet. The legacy installed module is behind the proposed read-only source.

**Still unknown:** the actual live binary SHA/build timestamp and build source provenance; any effective build-specific C++ compile errors or other module hooks; all in-game class scenarios and inactive glyph behaviour; exact live configuration; whether any custom DBC patch is present; and a successfully restored isolated character DB backup. `git status --short` and matching GitHub commits cannot establish these.

**No additional checker run is necessary merely to record Git revisions.** The operator has completed the narrow revision-gathering checkpoint, which is distinct from actual compilation and runtime acceptance.

## Decision gate — no deployment permission

1. Finish source review of PR #16 and confirm all source/synthetic tests. Keep the PR draft until review is accepted.
2. **Ask the owner for approval before merging PR #16, any Git pull, compilation, module replacement, worldserver restart or config change.** No such permission was granted while collecting revisions.
3. Before the approved single bundled compile: preserve backups of the existing module source and configuration, currently deployed binary and any custom patches. Use the existing working tree and dependency revisions, **not** an automatic switch to a public fork.
4. After a successful approved compile: begin with a controlled **read-only** configuration and in-game tests for all classes, including issuer allowlist and non-Random Bot controls, active/inactive specs, pet/offhand refusal and readable chat reports.
5. Any reset/Apply/repair that may alter real characters still requires separate approval plus consistent offline characters-DB backup and a successfully tested **isolated restoration**. Source review, compilation and read-only tests do not grant that approval.

Supporting documents: [Dependency Revision Checkpoint](NT1-DEPENDENCY-REVISION-CHECKPOINT.md), [Talent Map Integrity](NT1-TALENT-MAP-INTEGRITY.md), [Cross-class Talent Safety Audit](NT1-CROSSCLASS-TALENT-SAFETY-AUDIT.md), [Public Playerbots API Baseline](NT1-PUBLIC-PLAYERBOTS-FORK-API-BASELINE.md).


## Prepared acceptance plan (not yet executed)

A single-build, all-class read-only [release acceptance matrix](NT1-READONLY-RELEASE-ACCEPTANCE.md) now covers operator backups, actual binary provenance, Mode 4 issuer permission checks, protected-state checksums, ten classes, chat readability and no talent or equipment changes. Git checkout evidence is sufficient for the source-version checkpoint; **do not ask the operator to rerun Git commands or the optional Python preflight merely to duplicate the same SHAs**. Compilation, server restart and configured Mode 4 usage still require distinct approval.
