# Eastern Plaguelands — Fully Captured Tower Lock (90 Minutes)

**Status: isolated review patch; NOT installed, released, merged, or verified in-game.**
**Owner-approved gameplay scope:** each EP tower individually locks only when the **server-side capture bar reaches 100%**; exactly 90 minutes later that tower resets to neutral. Timer state survives server downtime. No new player announcements, countdown display, addon, GM timer commands, or enable/disable configuration switch.

Tracking: [Issue #19](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/19). This patch is **separate from NT1 Alt Bot draft PR #18**.

## Where this patch belongs

The existing `outdoorpvp_ep` handler is part of the Playerbots-compatible **AzerothCore source**, not the standalone Naxxramas Core module. This repository holds an **opt-in, reversible source patch**; simply installing or updating the module DOES NOT enable this feature.

The draft `patches/azerothcore/0001-ep-full-capture-per-tower-90min-lock.patch` applies **only** to:
- `src/server/scripts/OutdoorPvP/OutdoorPvPEP.h`
- `src/server/scripts/OutdoorPvP/OutdoorPvPEP.cpp`

Patch development is pinned against `mod-playerbots/azerothcore-wotlk@b7f06a16ac7120b5abc2e8d3f96a94265a363224`. Never force checkout or overwrite the owner's actual modified core. If source versions differ, **stop and review the differences**; never use a forced patch.

## Server behaviour

- Towers: Eastwall (EWT), Northpass (NPT), Plaguewood (PWT), Crown Guard (CGT).
- **Partial control is not enough:** AzerothCore marks a tower faction-controlled at the `_minValue` capture threshold, which can be well before the `+/-_maxValue` bar endpoint. The draft starts the lock **only** at `_value >= _maxValue` (Alliance) or `_value <= -_maxValue` (Horde).
- While locked, the core's base capture updater is invoked with **zero elapsed milliseconds** only to maintain active-player proximity/UI membership; no capture progression or faction-switch can occur from player counts.
- Expiry uses `GameTime::GetGameTime().count()` UNIX seconds, **not time accumulated in the PvP area**.
- On expiry, `_value = 0.0f`, `_team = TEAM_NEUTRAL`, the objective state resets, and standard per-tower world-state presentation is refreshed.
- Existing neutral cleanup is preserved for the NPT shrine and PWT flight master. The draft explicitly cleans EWT support NPCs and restores the CGT graveyard link to neutral on lock expiry.
- The owner expressly declined additional player announcements and UI countdowns. The patch suppresses capture/quest messages during startup owner restoration and automatic neutral expiration. Vanilla messages triggered by ordinary PvP capture before full lock remain unchanged.
- Zone-wide tower counts and faction buffs recompute after neutral expiration. Each other tower continues on its own capture and timer.

## Restart-safe storage, migration-free but backup-required

The patch reserves **eight** `acore_characters.worldstates` keys (not client-visible UI IDs):

| Tower | Owner-state key | Expiry-state key |
|---|---:|---:|
| EWT | 93420000 | 93420004 |
| NPT | 93420001 | 93420005 |
| PWT | 93420002 | 93420006 |
| CGT | 93420003 | 93420007 |

- Owner-state value: core `TeamId` (Alliance=0, Horde=1, Neutral=2); expiry value: UNIX seconds.
- The two keys must be absent/unused by other modules before deployment. **Collision-check the owner's actual live database and installed source**, not only the pinned public source. Never overwrite unknown rows. The pinned core's `WorldState::setWorldState` persists these keys through the characters DB.
- A valid unexpired owner/expiry pair reloads that tower at its faction's full capture value and preserves the **original** expiry. An expired or corrupt pair clears to neutral. If a write is interrupted, mismatched values fail closed to neutral at startup.
- The existing `worldstates` table is reused: **no new SQL schema/table or configuration** is required. This is nevertheless a characters DB write and must be backed up and restored in staging before owner-approved installation.

## Backups and safety gates (NOT instructions to install now)

1. Confirm the owner's **actual AzerothCore fork commit and any existing edits** to both EP files. The pinned upstream source is not proof that the live server matches.
2. Back up the **known-good source, binaries, and the full characters database**, including `worldstates`. Prove offline restore first.
3. Check the reserved keys are unused with a **read-only query**:
   ```sql
   SELECT entry, value
   FROM worldstates
   WHERE entry BETWEEN 93420000 AND 93420007
   ORDER BY entry;
   ```
   **Any unexpected row on initial installation is a stop condition.**
4. On a **disposable restored staging server only**, review both patched files, check the exact source revision, use `git apply --check` without `--3way`/`--reject`/`--force`, then apply and rebuild the AzerothCore `worldserver`.
5. Test the four towers with real Horde/Alliance actors before accepting it for production: partial owner without lock, 100% full capture, 90-minute absolute duration, opposite-faction attacks while locked, map unload/reload, full server restart, expiry while offline, crash/recovery, original benefits and NPC/quest UI.
6. Verify ordinary non-EP OutdoorPvP, Playerbots, IP and NT1 functionality on the same staging build. No assumption that synthetic tests prove live gameplay.

## Uninstall/rollback — planned, not yet operator-approved

1. Schedule downtime and back up the **current** characters DB/worldstates and patched Worldserver first.
2. Review `git apply --reverse --check patches/azerothcore/0001-ep-full-capture-per-tower-90min-lock.patch` in the *exact source tree where the patch was applied*. If reverse check fails due to subsequent modifications, do **not** force reverse; reconcile changes manually.
3. Restore original source via reviewed reverse patch and rebuild/reinstall the **backed-up known-good binary** if required.
4. After verifying no other code uses the eight keys and exporting their previous/current values, a separate owner-approved SQL cleanup may delete the eight patch-owned keys. **Do not blindly delete unknown data**.
5. Test on staging that all four towers again follow default AzerothCore capture rules. Production rollout/uninstall always requires separate owner approval.

## Test status and known limitations

- `tests/test_ep_tower_lock_patch.py` contains synthetic edge-case and patch-source assertions. The separate CI job checks **pinned-core `git apply --check` and clean reverse**, not real-world behaviour.
- A **full linked Worldserver compile and gameplay acceptance test have NOT yet been run or passed** for this patch. Therefore it is not ready to merge or deploy.
- The 2-key owner/expiry persistence is designed to reject inconsistent pairs on restart; a truly atomic combined DB record is not implemented. A more robust journal/transaction may be needed after fault-injection testing.
- Core spawn-side effects on cold start and graveyard/buff state must be verified in a disposable restored integration server. A passing source check alone is insufficient.

**Next release gate:** pinned patch applicability + C++ compile/link + owner-approved staging tests + verified rollback, before any PR can be promoted from draft.
