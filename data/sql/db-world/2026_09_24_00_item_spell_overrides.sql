-- Green Whelp Armor
-- Replace AzerothCore's default level-50 proc restriction
-- with Naxxramas Server's level-63 version.

DELETE FROM `spell_script_names`
WHERE `spell_id` = 9160
AND `ScriptName` = 'spell_item_green_whelp_armor';

DELETE FROM `spell_script_names`
WHERE `spell_id` = 9160
AND `ScriptName` = 'spell_naxx_green_whelp_armor';

INSERT INTO `spell_script_names`
(`spell_id`, `ScriptName`)
VALUES
(9160, 'spell_naxx_green_whelp_armor');