# Eastern Plaguelands Towers — Naxxramas Core Module-Only Design

**Status: module-only C++ + reversible SQL DRAFT. Unmerged, uninstalled and not yet proved on the owner's live core.**
**Scope confirmed by owner:** all four towers lock **individually** for **90 real-time minutes** when that tower's capture bar reaches **100%**, then become neutral again. Survives clean Worldserver restart and time elapsed during downtime. No added announcements, countdown UI, config flags or Terokkar changes.

Tracking: [Issue #19](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/19). The earlier [core-source patch PR #20](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/20) is **PAUSED and superseded by this module-only design**. NT1 talent research PR #18 remains separate.

## Architecture — no original AzerothCore source edits

AzerothCore's `OutdoorPvPMgr::InitOutdoorPvP` reads the world DB `outdoorpvp_template(TypeId,ScriptName)`. `TypeId=6` is Eastern Plaguelands. The ScriptMgr resolves the selected name to one `OutdoorPvPScript` factory.

The Naxxramas module installs its **own uniquely named** factory `outdoorpvp_naxxramas_ep_lock`. The original `outdoorpvp_ep` source still compiles but is **not selected** for this zone while the reviewed world SQL binding is active. It is **NOT registered under the stock script name**. Reversing the SQL re-selects the untouched stock script on next Worldserver startup.

- Module-owned C++: `src/Systems/EasternPlaguelandsTowerLock.cpp` and registration in `src/NaxxramasCore_loader.cpp`.
- World binding: `data/sql/db-world/2026_10_13_00_ep_tower_lock_module_bind.sql`.
- Unbind: `docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql`.
- The rollback script deliberately lives **outside `data/sql/db-world`** so any module SQL updater cannot accidentally run the uninstall step during a normal installation or upgrade.
- Four wrappers derive from **existing** `OPvPCapturePointEP_EWT`, `_NPT`, `_PWT` and `_CGT` classes and call their normal `ChangeState()` when restoring/canceling ownership. The original `OutdoorPvPEP` remains the parent of the zone wrapper so existing buff/count/quest UI logic stays in charge.

**Pinned implementation assumption:** standard source layout `azerothcore/modules/mod-naxxramas-core/src/Systems` can include the core's original `OutdoorPvPEP.h`. The owner's fork's compile/link and original script class visibility **must be checked**. Do not force-copy or replace AzerothCore headers.

## Capture and neutral reset

The original AzerothCore capture update flags towers as controlled once the captured value exceeds its neutral interval threshold `_minValue`, **before** 100%. The Naxxramas wrapper watches the `_value >= _maxValue` Alliance or `_value <= -_maxValue` Horde endpoint and starts the lock **only once**.

- While locked, invokes base capture update with `diff=0` to keep nearby-player membership and UI presence accurate **without changing capture progress**.
- On expiry, clears saved state, changes the actual capture meter to midpoint `0.0f`, returns owner and objective flags to neutral and triggers the original `ChangeState()` to refresh artkit/UI.
- EWT support NPC despawn and CGT graveyard neutral-link cleanup are explicitly handled (the original neutral branches do not always perform these cleanups).
- Original NPT shrine and PWT flight-master neutral branches are reused. Zone-level counts and buffs recompute after expiry.
- During startup restoration, the original `ChangeState()` restores each captured tower's benefits with `_oldState=_state` to avoid extra capture text. The initial zero-diff refresh recalculates the original zone's private control-count cache.
- **Late-loaded flag appearance:** The original `ChangeState()` updates artkits only on currently loaded map objects. The module wrapper additionally uses the pinned `GameObject::SetGoArtKit(kit, nullptr, spawnId)` API to refresh **in-memory spawn metadata** for both each tower's capture point and its flag, including on restart restoration and neutral expiry. Thus grids loaded later inherit the faction/neutral artkit. This does not edit GameObject C++ or write to the world DB. Actual unloaded-grid behaviour remains a staging acceptance test.
- No new messages or client-side countdowns are introduced.

## Restart-safe characters database state

The pinned AzerothCore `sWorldState->setWorldState` saves one uint32 value per ID in **acore_characters.worldstates**. This module reserves FOUR keys only:

| Tower | Key |
|---|---:|
| Eastwall | 93420020 |
| Northpass | 93420021 |
| Plaguewood | 93420022 |
| Crown Guard | 93420023 |

One packed `uint32` stores (Unix expiry seconds - 2020-01-01 epoch) in the upper 31 bits and **Horde=1 / Alliance=0** in the lowest bit. Zero means neutral/no active lock. It supports second-precise expiry until approximately 2088. A single per-tower database row avoids torn two-row updates. An expired, impossible or inconsistent timestamp is discarded to neutral on startup. Restored locks keep the **original expiry**; time offline counts against the 90 minutes.

**Caveat:** `WorldState::setWorldState` uses the core's asynchronous DB execute path; a hard crash before queued writes flush may lose the latest captured lock. The design guarantees interpretation of persisted state, but **does not promise crash-durable instant writes**. This requires explicit fault-injection tests and/or a reviewed synchronised persistence barrier if stronger durability is required.

## Pre-install backups and read-only checks — do NOT run yet

1. Back up the original `acore_world.outdoorpvp_template` row for `TypeId=6`, including the script name, and the full world and characters databases. Back up your known-good Worldserver binary, module directory, config and current core source revision. Verify off-server restore capability.
2. Check the current bindings with **read-only** SQL in HeidiSQL:
   ```sql
   SELECT TypeId, ScriptName
   FROM outdoorpvp_template
   WHERE TypeId = 6;
   ```
   Expected exactly one row with `ScriptName = 'outdoorpvp_ep'`. Any other result is a STOP condition (existing custom handler, missing entry or duplicate).
3. Check the characters DB for collisions (read-only):
   ```sql
   SELECT entry, value
   FROM worldstates
   WHERE entry BETWEEN 93420020 AND 93420023
   ORDER BY entry;
   ```
   Before initial installation **no rows should exist** for these four reserved keys. Nonempty results are a STOP condition pending manual source/ownership audit.
4. Check the owner's **actual Playerbots-compatible AzerothCore fork**, not only the pinned public source. Confirm the four original EP class definitions, `OutdoorPvPScript` registration flow, worldstate persistence and all module include paths still match.
5. Run the entire integration on an isolated restored test server, **not production**. Build Naxxramas Core with the full Playerbots/IP stack; verify no duplicate outdoor PvP handler registration, then apply the module SQL to the **staging world DB only**.
6. Test Horde/Alliance capture at 60%, 99%, 100%, blocked opposition for 90 minutes, all four staggered, on-time expiry, restart at 10 and 89 minutes, long downtime, associated EWT/NPT/PWT/CGT side effects, IP/Playerbots, default Terokkar and original EP UI.
7. Only after all above pass and the owner separately approves production deployment: stage binaries, apply the SQL to the backed-up world DB, restart Worldserver and verify in-game. Updating this GitHub branch alone does nothing to live data.

## Reversal and uninstall (backup first)

1. Stop Worldserver, retain full database and known-good binary backups. Do not remove module code while the DB still selects its custom handler.
2. In the reviewed world DB, run the **module-supplied rollback SQL** `docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql`, which rebinds only the exact `ScriptName='outdoorpvp_naxxramas_ep_lock'` `TypeId=6` entry to stock `outdoorpvp_ep`. Other custom scripts are untouched.
3. Restart a known-good Worldserver with stock `outdoorpvp_ep` and verify towers return to the default AzerothCore behaviour.
4. The four module-owned `worldstates` values are inert when unbound. **Do not delete them blindly.** With a verified database backup and owner permission, remove only the audited four patch-owned rows if desired. Removing the C++ in a later release is a separate reviewed action.
5. If any part fails, restore the full backed-up databases and known-good binary rather than attempting guessed repairs.

## Validation gates

- `tests/test_ep_tower_module_only.py` is a **synthetic behaviour model and static source contract**, not a gameplay proof.
- CI must compile the original class subclassing against the exact pinned core and then **link full Worldserver** with Playerbots and Individual Progression modules. Compile success does not prove live behaviour.
- Compatibility with the owner's installed fork, safe SQL restore, and EWT/NPT/PWT/CGT runtime validation are required before any merge/deploy.
- PR #20's separate upstream-core patch remains paused; **do not install both approaches simultaneously**.
