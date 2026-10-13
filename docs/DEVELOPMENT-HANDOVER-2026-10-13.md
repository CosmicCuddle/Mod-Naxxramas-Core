# Naxxramas Core — Development Handover

**Checkpoint:** 13 October 2026
**Project:** [CosmicCuddle/Mod-Naxxramas-Core](https://github.com/CosmicCuddle/Mod-Naxxramas-Core)
**Purpose:** authoritative continuity for the next development session. This file is a checkpoint, not a production release declaration.
**Principle:** preserve backups and reversibility; never merge, deploy, mutate live databases, change characters/items, or run talent Apply without the owner's specific, separate approval.

## 1. Immediate priority: Eastern Plaguelands per-tower locks — MODULE ONLY

- **Approved issue:** [#19](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/19).
- **Correct active development:** [DRAFT PR #21](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/21), branch `feature/ep-tower-lock-module-only`.
- **PAUSED superseded design:** [DRAFT PR #20](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/20). Its patch edits original AzerothCore `OutdoorPvPEP.h/.cpp`. The owner requires **all custom C++ in the Naxxramas Core module**; do not deploy PR #20.
- **Read first:** [Module-only architecture, backups, SQL checks, rollout and rollback](EASTERN-PLAGUELANDS-TOWERS-MODULE-ONLY.md).

### Locked owner decisions

1. **Each of FOUR towers independently** (Eastwall, Northpass, Plaguewood, Crown Guard).
2. Lock for **90 minutes of real-world elapsed time** only after the **server-side capture bar reaches 100%**, i.e., `_value >= _maxValue` or `_value <= -_maxValue` with matching faction. Vanilla faction state can change at `_minValue` before 100%; **do not start a lock there**.
3. While locked, opposition cannot change tower ownership/progress. Other three towers remain capturable.
4. At expiry, that tower must return **completely neutral** including underlying capture meter, flag/world state, owner, buffs and related NPC/graveyard side effects.
5. **Restart protection is mandatory:** store original absolute expiry; downtime consumes remaining time, never adds another 90 minutes. Expired during downtime => neutral on startup.
6. **Do NOT add** new announcements, player-facing countdown displays, or an enable/disable configuration option. Existing normal game behaviour remains intact.
7. Changes to *original AzerothCore source* are not acceptable. The owner **explicitly approved a narrowly scoped reversible SQL migration** supplied by the module.

### PR #21 implementation under validation (NOT release-ready)

- `src/Systems/EasternPlaguelandsTowerLock.cpp`: unique `OutdoorPvPScript("outdoorpvp_naxxramas_ep_lock")`, original four tower classes wrapped via subclasses, `OutdoorPvPEP` extended within the module. No original core files edited.
- `src/NaxxramasCore_loader.cpp`: module registration.
- `docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql`: targeted world DB `outdoorpvp_template.TypeId=6` script-name migration from stock `outdoorpvp_ep` to module handler **only when the existing name exactly matches**.
- **Rollback SQL is intentionally kept OUT of auto-discovered world-update directories**: find the current path and detailed instructions in `docs/EASTERN-PLAGUELANDS-TOWERS-MODULE-ONLY.md`. Never auto-apply the rollback script during normal updates.
- `acore_characters.worldstates` keys **93420020–93420023**: single packed uint32 per tower, encoding faction and Unix expiry offset to avoid torn two-row owner/expiry pairs. Before first installation, check these keys are unclaimed by the actual server; no migration or production DB write has been authorised. `WorldState::setWorldState` is asynchronous; **hard-crash durability remains unproven**.
- `tests/test_ep_tower_module_only.py` and `.github/workflows/ep-module-pinned-compile.yml`, `ep-module-pinned-worldserver-link.yml` implement synthetic/source testing and pinned-stack compile/link.
- **PR #21 snapshot:** as of the last check in this session, head `5c88cea28b4fa4b0a8b87e5ffeba2c31b8bfb76f`. Pinned source compile workflow **SUCCESS** ([run 38427838897](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38427838897)). Pinned **full Worldserver link is still IN PROGRESS** ([run 38427838867](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38427838867)). Recheck latest branch head AND CI rather than trusting this snapshot.

### First steps for the next session

1. Read this handover, issue #19, PR #21, and the module-only design doc. **Fetch latest branch and PR head** before any changes; GitHub branch has already advanced within the development cycle.
2. Check the completed **full Worldserver link** outcome and logs. If errors, fix only PR #21 on its own draft branch, re-run pinned compile/link and tests. No unreviewed changes to upstream core.
3. Source-audit the four vanilla EP tower `ChangeState` side effects (EWT support units, NPT shrine, PWT flight master, CGT graveyard) and original `OutdoorPvPEP` private control-count/buff handling. Verify startup restoration and neutral cleanup avoid duplicate quest credit/announcements.
4. Review `outdoorpvp_template` ScriptMgr startup registration, stock-vs-module OutdoorPvPScript uniqueness and the revised rollback SQL path. Verify normal Naxxramas module auto-update discovery will **not** execute rollback.
5. Check the saved expiry design: 100% detection at exact endpoint, 90-minute wall-clock expiration independent of players; partial-state, team flip, stale values, counter restoration, empty zone, restart and hard-crash behaviour.
6. **Before any installation**: owner-installed fork/source revision audit; backup known-good binaries/module, **full acore_world and acore_characters**, test offline restore, then read-only check `outdoorpvp_template.TypeId=6` and `acore_characters.worldstates` keys 93420020–93420023. Unexpected binding/collision means STOP; never overwrite unknown keys. Owner-approved disposable staging tests only.
7. Keep PR #21 **DRAFT** until all source, full-link, rollback, staging gameplay and explicit approval gates pass. **Never merge automatically.**

### Pinned compatibility stack used for CI (not proof of owner's installed revisions)

- AzerothCore: `mod-playerbots/azerothcore-wotlk@b7f06a16ac7120b5abc2e8d3f96a94265a363224`
- Playerbots: `mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c`
- Individual Progression: `ZhengPeiRu21/mod-individual-progression@283abe12774801e5671da746ea8bf535cc0252e0`

### Current EP staging-validation companion

The [staging acceptance checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md) records the required backup, read-only SQL, four-tower/faction acceptance matrix, clean-restart/downtime cases and safe rollback drill. **This is a plan, not staging authorisation.** On the pinned source the character `worldstates.value` column is `INT UNSIGNED`, compatible with the packed per-tower value. However, `WorldState::setWorldState` skips database persistence on **cross-realm** nodes; such deployments are blocked pending a revised storage design. Async hard-crash durability is still not established.

Recent review checkpoint: EP source compile and the synthetic regressions were successful for `fd1be1f9eb4e9e26330eb15018463c01419c4d81`. Full Worldserver link was still **in progress** at review time, not declared passed; always verify the newest PR head and its own workflow results. No upstream C++ or live SQL was modified.

### EP review: later-loaded tower flag appearance

The pinned AzerothCore `OutdoorPvP::SetMapFromZone` creates map 0 on EP handler setup, avoiding a null base-map pointer, but it does **not guarantee tower grids are loaded**. Stock tower `ChangeState()` sets artkit on only currently loaded GO instances. On restart with an unloaded EP grid, a newly loaded tower flag or capture point could therefore retain neutral artkit despite restored ownership.

- [`d760d39`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/d760d39478db8cec2afdfeba48dd1603d6465b09) adds a module-owned override of `ChangeState()`, calls the unchanged stock method first, and then uses the pinned **public** `GameObject::SetGoArtKit(uint8, GameObject*, ObjectGuid::LowType)` API with a null live GO pointer to synchronize **in-memory spawn metadata** for the proper per-tower capture object and flag. It applies to captures, restart restoration, and neutral expiry. It neither edits original AzerothCore files nor writes GO artkit values to the SQL database. A new source-contract test and unloaded-grid staging test were added.
- The first synthetic source workflow for that commit failed on an **escaped newline in the new test**, *not an established C++ failure*. [`5cc3a11`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/5cc3a11efc7410e7eb0a8759f5ac268ebd0a5256) corrects the test; its exact-head compile and the earlier gameplay-code full-link job were **still in progress** when recorded. Do not claim the new C++ is validated until these pass.
- An older full Worldserver link at `5c88cea` **SUCCEEDED** and confirmed the unique module script name in the linked Worldserver, but that is **before** the flag appearance fix and cannot substitute for the new linked build.

**Latest active PR #21 commit at this checkpoint:** `5cc3a11efc7410e7eb0a8759f5ac268ebd0a5256`. Recheck GitHub for newer commits and CI outcomes before planning installation. Staging approval, backup/restore drill, hard-crash caveat, crossrealm STOP gate, and explicit production permission remain mandatory.

### EP next-session checkpoint — packed-state boundary tests

- Source/CI contract [`4bf1617`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/4bf1617b253c781a0fe35488fcbcd3e41d12897c) confirmed pinned startup ordering, normal async DB pool shutdown and late-grid artkit source interfaces, then **PASSED** ([source check 38439517849](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38439517849)). This is **not** runtime restart proof.
- [`407b952`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/407b9520c786b0e5cd3bc92ddd7fe7bacdd843e8) added two pure synthetic tests for unsigned packed lock expiry max/overflow and invalid factions/epochs; **23 tests in suite**. Pinned [source check 38442334898](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38442334898) was **in progress** when recorded. No gameplay C++ changed after the previous `d760d39` artkit fix.
- The **first build linking the revised artkit C++** is [full Worldserver run 38438203265](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38438203265), **still running** at last observation. Earlier full links passed, including [38433275612](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38433275612), but predate the artkit change. Recheck actual outcome before declaring linked-code success.
- [PR #21 file isolation audit](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/21/files) verified 11 changed paths exclusively in `Mod-Naxxramas-Core`; **zero** changed original AzerothCore or other-module files. Do not promote superseded PR #20.
- Next: confirm the exact gameplay C++ full-link success; compare owner's **actual** installed core/source SHAs with the pinned stack; only after **owner-authorised isolated staging** and full verified backups use the detailed [staging acceptance checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md). Do not conflate graceful restarts with crash durability or crossrealm DB persistence. PR remains draft.

### EP additional gameplay fix — Northpass late-spawn shrine faction

- [`0e7516a`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/0e7516a1b1ca8e7c032d1249ab92bdd2aa0693e0) adds a **module-only** `OutdoorPvP::OnGameObjectCreate` forwarder to the Naxxramas-owned Eastern Plaguelands handler. When a Northpass shrine **spawn ID** appears after an unloaded-grid restart, the handler restores the **original** `GAMEOBJECT_FACTION` (Alliance=84/Horde=83) *for that shrine alone*. During neutral ownership it does nothing; the original neutral state still removes the shrine.
- The pinned core route was audited: `GameObject::Create` calls `SetZoneScript()`, `WorldObject::SetZoneScript` resolves the registered OutdoorPvP handler for EP, and `GameObject::AddToWorld` dispatches `OnGameObjectCreate`. Additional source-contract assertions lock down that routing alongside stock Northpass `SummonGO` faction values.
- [Source compile run 38445137876](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445137876) and [full Worldserver link run 38445137510](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445137510) for the gameplay fix had **started but not passed** at this checkpoint. Do not declare the newest code validated until those checks and the subsequent exact-head source test succeed.
- The older late-grid **flag artkit** fix build [38438203265](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38438203265) is separate; the Northpass shrine fix needs its **own** link to verify.
- The updated [staging checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md) explicitly tests delayed Northpass shrine spawning for both factions. Runtime tests remain **blocked pending explicit owner approval, full backups/restore checks and confirmation of the owner's installed AzerothCore fork**. No production operations took place.

### EP validation update — flag-restoration full link passed

- [Pinned full Worldserver run 38438203265](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38438203265) at gameplay commit `d760d39478db8cec2afdfeba48dd1603d6465b09` **COMPLETED SUCCESS**: actual full-worldserver static C++ compile/link and the unique `outdoorpvp_naxxramas_ep_lock` string check passed. This **does cover** the late-loaded flag artkit restoration fix.
- [Pinned source compile/run 38445399205](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445399205) at newest gameplay source plus the routing-test follow-up `81fd3e16dbd204a2039665b251bf2b2fe739e331` **COMPLETED SUCCESS**, all 25 tests and real EP C++ source compile.
- The newest **Northpass shrine late-spawn fix** `0e7516a1b1ca8e7c032d1249ab92bdd2aa0693e0` **still requires its own full link outcome**: [pinned run 38445137510](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445137510) was **in progress** when checked. Previous successful full links **do not** verify this later commit.
- [PR #21](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/21) remains **draft/unmerged**. No actual gameplay, database restore, manual tower tests, real installed-fork validation, backup/rollback or production activity. Do not replace these gates with source CI success; see [staging checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md).
- **Exact next check**: check run `38445137510`; if PASS, compare owner fork revisions; if FAIL, inspect failed step/log and fix strictly inside the Naxxramas Core PR. Staging requires separate owner authorisation.

### EP migration / rollback safety test checkpoint

- [`d26c11f`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/d26c11f8222683221f369455e25022f44655c22e) extends the **module-only test suite to 27 tests**, with real forward and rollback SQL statements run against an **isolated in-memory SQLite** table. It proves the portable exact `TypeId=6` + script-name-match semantics, repeated-run idempotence, preservation of other zones and refusal to overwrite a third-party EP handler. It **does not** access any live MySQL server or certify the actual world DB installation.
- [Pinned source compile + test run 38453731581](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38453731581) **COMPLETED SUCCESS**, including the SQL tests, synthetic transitions and actual EP translation-unit compilation against pinned AzerothCore/Playerbots/IP sources.
- Most recent **Northpass shrine gameplay-code full link** [38445137510](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445137510) **was still running** at documentation time; do not promote PR based solely on previous successful links. The preceding **flag-artkit gameplay-code full link** [38438203265](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38438203265) passed.
- **STOP before actual database work:** Back up/restore-test `acore_world` and `acore_characters`; preflight exact `TypeId=6` binding and unclaimed character worldstate keys 93420020–93420023; compare owner's installed AzerothCore fork; obtain explicit owner approval for an isolated staging realm, execute full four-tower tests, and rehearse rollback. No live server/database/character action has been authorised.
- PR #21 remains **DRAFT and unmerged**. This checkpoint only changes module tests and documentation. Preserves the independent 90-minute locks, no config switch, no new announcements and untouched original AzerothCore source.

### EP release safety correction — optional world SQL must never auto-run

A source review of the pinned AzerothCore `src/server/database/Updater/UpdateFetcher.cpp` confirms that the updater automatically searches enabled modules' `data/sql/db-world` folders for pending SQL. The former PR #21 location was therefore an inadvertent **auto-activation risk**. The forward EP script-name binding has been **moved to** [`docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql`](install/2026_10_13_00_ep_tower_lock_module_bind.sql), outside the scanned location; the former `data/sql/db-world/2026_10_13_00_ep_tower_lock_module_bind.sql` is **deleted from the PR tree**. Both SQL directions require explicit manual, owner-approved staging steps; neither must be applied to production automatically. Do not restore the old path.

- Added regression guard that the optional EP SQL stays outside module updater discovery. Source compile and full Worldserver CI track both the relocated file and relevant build source. Subsequent code changes must not reintroduce the old `data/sql/` path.
- Staging checklist and module design document were updated with manual-only activation and stock-handler default. **This is a GitHub branch change only**; no staging/production DB was accessed.
- Prior successful [Northpass shrine full Worldserver build 38445137510](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445137510) remains valid for unchanged gameplay C++, but **rerun exact-head CI** for this change and ensure current success before later release discussion. Runtime acceptance/installed-fork verification remain separate gates.

### EP owner-fork compatibility gate — read-only revision instructions

- A new pinned-source test checks that AzerothCore's `UpdateFetcher.cpp` actually traverses enabled modules' `data/sql` directories. This makes the prior safety fix (the manual EP SQL now lives only under `docs/install/`) an enforceable compatibility contract for the pinned source. A successful pinned test does not replace checking the actual installed fork.
- Updated [staging acceptance checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md) with **four explicitly read-only Git commands** that the owner may run in MobaXterm against their source checkout, with an explanation of missing paths and the pinned AzerothCore, Playerbots and Individual Progression SHAs.
- Owner's actual installed fork commit and running binary are **not yet independently verified**; do not claim deployment readiness or assume the owner's checkout matches CI.
- Most recent completed gameplay-code full build [38445137510](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38445137510) **PASSED**. The full pinned build for manual SQL relocation [38454791617](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38454791617) was still running at this prior checkpoint; recheck GitHub before promoting the branch. PR #21 remains draft, module-only and uninstalled.

### EP default-off guarantee and manager binding contract

- A new pinned-core source-contract test checks `OutdoorPvPMgr::InitOutdoorPvP` reads `TypeId, ScriptName` from `outdoorpvp_template` and instantiates exactly the selected script. Merely compiling and registering the unique Naxxramas handler **must not replace** `outdoorpvp_ep` until the owner intentionally applies `docs/install/` SQL.
- The staging checklist now requires a **default-off verification**: on separately owner-authorised isolated staging, after backup and before applying the optional SQL, check that TypeId 6 still selects stock `outdoorpvp_ep`. Unexpected changes are STOP, not an instruction to re-run migrations.
- The earlier empty-zone expiry test at [`cb2f2ee`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/commit/cb2f2ee3e5bda54451cef3207f7b608228f1204a) was **source/test only**, and [CI 38456387483](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38456387483) **passed 30 tests** and actual pinned EP source compile. No module gameplay C++ or database contents changed in the default-off test/documentation update.
- Latest status of [Worldserver link 38454791617](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38454791617) for C++-equivalent `388eea9` was still **in progress** at last observation. Confirm it independently before stating full link of optional-SQL relocation.

## 2. Separate continuing workstream: NT1 Alt Bot talent imports — PR #18

- [DRAFT PR #18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/18), branch `research/nt1-offhand-preservation-review`.
- Latest checked head: `92961f86636ba0dc7ebfaf38c014f8a1a5375012`.
- **All six pinned/test CI workflows were SUCCESS** at last check, including full linked Worldserver. This does **NOT** mean the new different-build operation is equipment-safe or runtime-verified.
- Existing draft added a narrowly scoped **authorised exact active-spec NO-OP**: if an Alt Bot already matches exactly, return `NT1 ALREADY MATCHES — NO CHANGES MADE` before `ImportScope`, resets, talent learning, profile or DB writes. Random Playerbot behaviour remains unchanged.
- **Different-build Alt Bot Apply is NOT fixed.** Guarded offhand and active pet still block unsafe resets. Pinned `Player::resetTalents(true)` invokes `AutoUnequipOffhandIfNeed()`, which can move/maybe mail items; cleanup/rollback hook risks remain. The user specifically wants Holy Priest **Arndor** to switch valid raid builds without changing ANY gear. Do **not** lift the offhand/pet guard until truly verified safe.
- Mandatory **Zero Gear Mutation Rule** for *all* Alt Bots: never unequip, move to bags/mail, replace, delete, recreate, swap, enchant, autogear, or temporarily relocate original equipment, including during failed Apply/recovery. No configurable bypass. Pet preservation separate. **No side-effect-free different-build engine has been implemented.**
- Keep both security controls: `NaxxramasCore.BotTalentImport.AccessMode` and **human-issuer** allowlist `NaxxramasCore.BotTalentImport.AltBotAllowedPlayers`. The owner explicitly agreed to keep the allowlist.
- Read [zero-gear contract](NT1-ALT-BOT-ZERO-GEAR-MUTATION-CONTRACT.md), [implementation plan](NT1-ZERO-GEAR-MUTATION-IMPLEMENTATION-PLAN-2026-10-13.md) and PR #18 review notes. These documents currently live on PR #18's draft branch, so a relative link from this branch may not resolve; open the PR #18 branch directly.
- After **fully verified server work and the owner's release approval**, provide a substantial **Naxxramas Core → N-MultiBot-Chatless addon-team handover**. Do not hand over speculative Apply behaviour or trigger gear role changes.

## 3. Governance and safety

- The GitHub repo stores all the development work, but **PR #20's source patch is NOT module-only**; it is paused. **PR #21** is the module-only alternative.
- No live SQL migration, installation, release, character mutation, talent Apply, Worldserver start, or production test has been authorised or performed here.
- Always explain each step clearly and compactly for readability, recommend backups before significant edits, and maintain explicit rollback steps. Do not modify `main`, merge, deploy or delete private/earned character data without separate owner approval.
- The official issue/PR/docs are the source of truth when moving conversations; **recheck live GitHub state** to catch CI or branch updates that happened after this dated checkpoint.

## 4. Next-chat continuation

> Continue Naxxramas Core development from `docs/DEVELOPMENT-HANDOVER-2026-10-13.md` on the `feature/ep-tower-lock-module-only` branch. First check draft PR #21's pinned full Worldserver link and resolve any failures, then continue source review and safe staging/rollback planning. Keep EP changes module-only plus owner-approved reversible SQL; leave paused PR #20 untouched. Preserve separate draft PR #18 NT1 Zero Gear Mutation requirements, no new gear changes and no Apply to earned characters. Never merge/deploy or modify production databases without explicit permission.
