-- Naxxramas Core — reversible Eastern Plaguelands handler rollback.
-- BACK UP acore_world and acore_characters first.
-- Rebinds only the handler installed by our matching forward migration.
-- Does not delete any worldstates rows or touch other custom scripts.
UPDATE `outdoorpvp_template`
SET `ScriptName` = 'outdoorpvp_ep'
WHERE `TypeId` = 6
  AND `ScriptName` = 'outdoorpvp_naxxramas_ep_lock';
