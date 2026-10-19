# Eastern Plaguelands — Full-Capture Zone Announcement (14 October 2026)

**Status (19 October 2026):** **DRAFT/UNMERGED, NOT INSTALLED.** Previous exact PR head `7c826ae2dcb159ebf75d6a3a65e89ae0842ab801` passed [pinned C++ translation unit, full Worldserver and handler registration CI #39220814150](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39220814150) (**18/18 steps**), including the one-notice-after-persisted-lock source regression. This documentation-only update does not change the handler/SQL/Worldserver. Build success **does not** prove in-zone receipt, cross-faction text, restart/lock correctness or activation. The owner's earlier installed binary is not assumed to contain this proposal.

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

## Verified build versus still-open gameplay gates

- **S3/S4 complete for previous exact source head `7c826ae`:** source regressions, real C++ compilation, complete pinned Worldserver link and final `outdoorpvp_naxxramas_ep_lock` registration passed in #39220814150. This is an isolated **build result**, not a live report.
- **S5 not complete:** the existing merged tower-lock source, actual server version, effective `outdoorpvp_template(TypeId=6)` binding, restorable source/binary/config/affected world-state backups and rollback must be inspected in an **approved** staging window. Do not run SQL on the realm just to satisfy the documentation.
- **S6 not complete:** owner-approved test must distinguish stock threshold capture announcements from the new custom **100% lock confirmation**. Confirm each of four tower names, Alliance/Horde wording, receiver elsewhere in Eastern Plaguelands, single announcement, repeated locked ticks, neutral reset and restart behavior. Record both *observed* text and expected text, not only screenshots of the attacker.
- **S7 not approved:** no merge, build/install, restart, manual SQL activation or release without separate owner decisions.

## Deployment and acceptance

The unique `outdoorpvp_naxxramas_ep_lock` handler remains **default-off** as long as `acore_world.outdoorpvp_template(TypeId=6)` names `outdoorpvp_ep`. This PR must NOT apply the separate binding or restart the owner's production Worldserver.

1. Preserve the already verified previous exact-source C++/full-link CI evidence; require a fresh head-specific result after any subsequent source change. This is **not** proof of in-game delivery.
2. Owner reviews/merges PR and chooses a later maintenance window for normal module `git pull`, incremental build, installation and clean restart after backups.
3. Confirm original zone handler selection before any manual activation. The existing forward/reverse scripts under `docs/install/` and `docs/rollback/` remain the only explicit activation/unbinding paths.
4. With separate owner approval to activate, observe **both factions**, all four tower names, exactly one custom notice at 100% (not at earlier threshold), and no duplicate during 90-minute lock/restart/reset. Test zone reception from a character away from the objective.
5. Preserve existing rollback/backups. Do not force-crash the live server.

**Note on localization:** Unlike the core's `LANG_OPVP_EP_CAPTURE_*` messages, the new custom strings are presently English-only. Supporting custom localized copies would require a separately reviewed localization data design.
