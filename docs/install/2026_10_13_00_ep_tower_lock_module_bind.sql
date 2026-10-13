-- MANUAL, OWNER-APPROVED INSTALL ONLY: this file is deliberately OUTSIDE
-- data/sql/db-world to avoid AzerothCore's automatic module SQL updater.
-- Stop the isolated staging Worldserver, verify backups and read-only SQL
-- preflight, then apply exactly once as an explicit owner-approved action.
-- Naxxramas Core — Eastern Plaguelands lock handler (optional).
-- Run only after backing up acore_world.outdoorpvp_template TypeId=6
-- AND installing a tested Worldserver with the Naxxramas module handler.
-- Does not touch the built-in AzerothCore source or any other zone.
--
-- Fail-closed: never override a different/custom outdoor PvP script.
-- Affected rows: exactly one when vanilla ScriptName is outdoorpvp_ep.
UPDATE `outdoorpvp_template`
SET `ScriptName` = 'outdoorpvp_naxxramas_ep_lock'
WHERE `TypeId` = 6
  AND `ScriptName` = 'outdoorpvp_ep';
