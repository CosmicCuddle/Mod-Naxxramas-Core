# Eastern Plaguelands — Full-Capture Zone Announcement (14 October 2026)

**Status:** draft module-only enhancement, pending CI, merge, a future Worldserver rebuild and in-game verification. The owner reported the prior Worldserver build installed/restarted successfully, but this new proposal is **not** in that running binary.

## Owner-requested behaviour

Once a particular Eastwall, Northpass, Plaguewood or Crown Guard Tower reaches **100%** capture, announce that the Horde/Alliance has **secured** it across **Eastern Plaguelands**.

Example zone-defense strings (custom English-only, inspired by the concise Blizzard capture style, not copied official localized strings):

- `The Horde has secured Eastwall Tower!`
- `The Alliance has secured Northpass Tower!`

Other tower names substitute appropriately: Plaguewood Tower and Crown Guard Tower.

## Precise trigger and scope

- Keep **stock AzerothCore's existing zone capture notices** when objective ownership changes at the earlier vanilla threshold.
- Add exactly **one further zone-wide notice** only when the capture value reaches the signed extreme and `PackLock` succeeds, the lock expiry is set, and persistence is queued.
- Use the **same native Map::SendZoneText** mechanism and `EP_GraveyardZone` (Eastern Plaguelands) used by the original core script. The native code sends the zone-defense text to both factions in the zone.
- **No notices** from startup restore, repeated locked ticks, incomplete captures, neutral expiry/reset, or a lock that cannot be represented by the persistence format.
- Four independent tower names, one announcement per completed capture. Another notice becomes possible only if a tower eventually neutralizes and is fully captured again.
- **No UI timer, configuration flag, changed lock duration, additional SQL, new DB rows, global/cross-zone message, addon changes, or core/Playerbots/IP/ALE source edit.**

## Deployment and acceptance

The unique `outdoorpvp_naxxramas_ep_lock` handler remains **default-off** as long as `acore_world.outdoorpvp_template(TypeId=6)` names `outdoorpvp_ep`. This PR must NOT apply the separate binding or restart the owner's production Worldserver.

1. Validate C++ source contract and full-link CMake CI against the pinned compatible source; this is **not** proof of in-game delivery.
2. Owner reviews/merges PR and chooses a later maintenance window for normal module `git pull`, incremental build, installation and clean restart after backups.
3. Confirm original zone handler selection before any manual activation. The existing forward/reverse scripts under `docs/install/` and `docs/rollback/` remain the only explicit activation/unbinding paths.
4. With separate owner approval to activate, observe **both factions**, all four tower names, exactly one custom notice at 100% (not at earlier threshold), and no duplicate during 90-minute lock/restart/reset. Test zone reception from a character away from the objective.
5. Preserve existing rollback/backups. Do not force-crash the live server.

**Note on localization:** Unlike the core's `LANG_OPVP_EP_CAPTURE_*` messages, the new custom strings are presently English-only. Supporting custom localized copies would require a separately reviewed localization data design.
