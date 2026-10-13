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
- `data/sql/db-world/2026_10_13_00_ep_tower_lock_module_bind.sql`: targeted world DB `outdoorpvp_template.TypeId=6` script-name migration from stock `outdoorpvp_ep` to module handler **only when the existing name exactly matches**.
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
