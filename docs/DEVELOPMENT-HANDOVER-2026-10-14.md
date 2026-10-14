# Naxxramas Core — Development Handover (14 October 2026)

**Status:** PR #21 merged; owner has pulled the new source to the existing production AzerothCore checkout. Worldserver has **NOT** yet been recompiled/installed/restarted, and the optional tower lock has **NOT** been activated. **ALE update is in progress; success not yet confirmed.**

**Repository:** https://github.com/CosmicCuddle/Mod-Naxxramas-Core
**Most recent tower implementation:** https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/21 (merged)
**Merged GitHub commit:** `fad58f8115a8bf57bf9dbb4fc20bb964285fd9f4`
**Feature candidate previously built:** `9e7e1373cc3fe5897d6ef20e5445c8fd33f59f5b`
**Do not confuse this completed merge with runtime installation or in-game acceptance.**

## 1. Immediate next task — finish upstream ALE update

The owner updated Naxxramas Core successfully using:
```bash
cd /root/azerothcore-wotlk/modules/mod-naxxramas-core
git branch --show-current
git pull --ff-only origin main
```
The console showed `main` and a successful fast-forward from `69a91be` to `fad58f8` (14 added files). The source is present but the actual running Worldserver remains the old build until a separately planned rebuild/install/restart.

The owner also tried to update `/root/azerothcore-wotlk/modules/mod-ale` from upstream `azerothcore/mod-ale` `master`. The pull **ABORTED CLEANLY** because local edits to:
`src/LuaEngine/methods/PlayerMethods.h`
would be overwritten. There is no evidence of a partial merge.

The owner-supplied `git diff` shows a manual compatibility patch that:
- adds `PlayerbotAI.h` and `PlayerbotMgr.h` under `MOD_PLAYERBOTS`;
- changes ALE's Lua `IsBot()` from the old `player->GetSession()->IsBot()` to `player && sPlayerbotsMgr.GetPlayerbotAI(player) != nullptr`.

Upstream `azerothcore/mod-ale` at `84b85cc55980dbf67d596f3d5cb34ded10c59102` now uses `player->GetSession()->IsHeadless()` instead, which is declared in the owner's exact Grimfeather core revision. The upstream update also fixes ALE quest-completion logic and renames two Playerbots config member uses to `SightDistance`/`ReactDistance`. It does **not** reproduce the custom AI-object detection semantics exactly; check bot behaviour after the update and rebuild.

**Explicit owner decision:** They wish to discard the one old ALE file modification without making another copy. The last advice was:
```bash
cd /root/azerothcore-wotlk/modules/mod-ale
git restore -- src/LuaEngine/methods/PlayerMethods.h
git pull --ff-only origin master
```
**IMPORTANT:** The owner has **NOT** yet provided output proving those two commands were executed. The new session should ask whether they were run and request their output. Do not claim ALE has been updated; do not suggest deleting the whole module, force-resetting the repository, or updating other modules by default. If the pull reports other local modifications, investigate each separately. Source changes do not affect the currently running Worldserver until compilation and deployment.

## 2. Owner's exact Linux environment

- Source root: `/root/azerothcore-wotlk/`.
- Module: `/root/azerothcore-wotlk/modules/mod-naxxramas-core/` (`main`, successful source fast-forward).
- ALE: `/root/azerothcore-wotlk/modules/mod-ale/`.
- Build directory appeared as `/root/azerothcore-wotlk/build/`; **do not assume** its CMake cache, build flags or install destination without checking.
- Live Worldserver executable: `/root/cosmic_core/bin/worldserver` (observed from process listing). The historical process PID must **not** be reused; identify the running PID afresh as necessary.
- Runtime configs: `/root/cosmic_core/etc/`; module configs under `etc/modules/`.
- Only one live host; owner does not have the time to create a separate staging server. Owner has opted for carefully controlled testing on the existing server. Treat this as a production-risk exception to the earlier isolated-staging checklist, **not** as evidence that runtime acceptance has passed.

**Owner's pre-merge source checkout SHAs:**
- Grimfeather AzerothCore: `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7`.
- Playerbots: `037c01418b5d01506917a3db9b44fd56ac5f965c`.
- Grimfeather Individual Progression: `4ff4b5fcc1480348f058c632573143e62d4e3a41`.
- Naxxramas Core before merge: `69a91be2ded62f6cdccf7ca6e7119ebdcc45e81b`; now pulled `main` through `fad58f8`.

## 3. Backups and database read-only checks already done

Owner reports full backups taken of `acore_world`, `acore_characters`, and the existing Naxxramas Core module. These were **user-confirmed** but restoration was **not** independently tested in this conversation. Verify archive location/restore integrity before risky runtime steps.

Backup directory (owner renamed it): `/root/Backup Files Pre Towers/`.
- Known-good compiled binary copied from `/root/cosmic_core/bin/worldserver` to `worldserver_2026-10-14_14-11-06`. Original and copy both had identical SHA-256 `44b05f677fc7ff1d8262d1530440feb6b4f6f4ac178e62222add8e5dd1a94ae0`; ~624 MB. Running Worldserver was **not** restarted by this copy.
- `etc_2026-10-14_14-31-23.tar.gz`, ~425 KB, created with restricted permissions, validated by `tar -tzf` and SHA-256 `361a7ce261dc34d581f7b522161601f8f54fb97e89f904d5aef3f8330af0c703`. A readable archive is not a verified restore. Config files may contain secrets — never paste their contents or commit them to GitHub.
- Strongly recommend securely retaining important backups away from the original server/storage.

Owner's **read-only HeidiSQL checks passed**:
- `acore_world.outdoorpvp_template`: exactly one row `TypeId=6, ScriptName=outdoorpvp_ep`.
- `acore_characters.worldstates` keys `93420020` through `93420023`: **zero rows returned**.

## 4. Eastern Plaguelands feature and verified CI

Expected behaviour: Eastwall, Northpass, Plaguewood and Crown Guard towers each independently lock for **90 wall-clock minutes** only on full faction capture at 100% or -100%; blocked opposing capture during lock; expiry to neutral with original NPC, shrine, flight master, graveyard, tower count, buff and flag behaviour. Unexpired locks survive clean restart, and time offline counts against the fixed expiry. No new timer UI, announcement, configuration option or Terokkar alteration. Hard-crash durability is **not** proved.

Implementation remains only in the Naxxramas Core module, not original core source:
- `src/Systems/EasternPlaguelandsTowerLock.cpp`, module loader registration.
- The custom handler `outdoorpvp_naxxramas_ep_lock` is registered but is **DEFAULT-OFF** while the database keeps `outdoorpvp_ep`.
- Optional activation SQL lives deliberately in `docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql` **outside** the automatic module SQL updater. Rollback SQL is `docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql`.
- No activation SQL has been run. It must not be applied until **after** the new Worldserver binary is built/installed in a scheduled maintenance window, required backups are verified, the original handler still matches, and owner separately approves activation.
- A source pull alone does **NOT** require SQL and does **NOT** activate the feature.

**GitHub CI verified (at the candidate SHA before merge):**
- Owner exact Grimfeather/Playerbots/IP full Worldserver compile+link: **SUCCESS** https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38549816427; all **35** regression/source tests PASS; unique handler included; linked test binary SHA-256 `09c6afe807167d530c518518a9d773c4665b96fb56aafe0e8a4146a1d27fe141`. This is a **GitHub-built** binary, not the one installed on the server.
- Pinned source tests and translation-unit compilation: **SUCCESS** https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38549816023.
- Earlier pinned full Worldserver link: **SUCCESS** https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38545796923 (earlier SHA, 34 tests).
- PR #21 merged to `main` by owner request, allowing ordinary `git pull`: https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/21.
- All real **in-game** four-tower, both-faction, restart, outage and rollback acceptance is STILL PENDING.

## 5. Safe sequence for the next chat

1. Confirm the ALE `git restore` and `git pull --ff-only origin master` result; do not assume it completed.
2. Confirm current ALE revision and any remaining local changes if necessary, and check ALE's compatibility with the owner's exact Playerbots configuration.
3. **Before recompiling**, ask how the existing server is normally compiled/installed and inspect only the necessary CMake cache/build commands; avoid guessing a `cmake --install` prefix or overwriting a running binary. Do not needlessly update AzerothCore, Playerbots, or Individual Progression.
4. Owner has existing binary/config/database/module backups, but full database restore proof remains pending. Coordinate a maintenance window and permissions before installing or restarting production Worldserver. Rebuilds might be CPU/RAM intensive, and old live process/binary must not be replaced without checking deployment safety.
5. After compiling and deploying, verify Worldserver starts, ALE and existing game functions work, stock `outdoorpvp_ep` is still selected (**default-off negative check**), and only then separately ask owner to authorise manual binding activation against `acore_world`.
6. On explicit authorisation, use the narrow forward SQL, verify only `TypeId=6` switched, then conduct supervised live EP capture tests and record timestamps. Do **not** perform forced hard crashes on the live server.
7. Preserve the known-good executable, SQL rollback, backups and a clear stop/restore plan. Record actual observations; do not mark CI results as in-game proof.

**Core principle:** one step at a time, simple MobaXterm/HeidiSQL commands, always explain why; preserve the owner's other modules, bot gear/talents, characters, configs and customisations. The owner prefers normal Git pull and minimal unnecessary preflight, but still requires protection against irreversible loss.

## Reference documents

- [Earlier historical handover](DEVELOPMENT-HANDOVER-2026-10-13.md) — earlier sections say PR is draft; superseded by this file for current status.
- [Tower design](EASTERN-PLAGUELANDS-TOWERS-MODULE-ONLY.md).
- [Acceptance checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md) (written for isolated staging; adapt consciously with owner consent for single live server).
- [Blank test evidence record](EP-TOWER-STAGING-EVIDENCE-RECORD.md).
