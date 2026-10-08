-- Naxxramas Core: attach optional directional Blink script to regular Mage Blink (1953).
-- Leaves existing spell_script_names rows and regular spell data untouched.

DELETE FROM `spell_script_names`
WHERE `spell_id` = 1953
  AND `ScriptName` = 'spell_naxxramas_arcane_momentum';

INSERT INTO `spell_script_names` (`spell_id`, `ScriptName`)
VALUES (1953, 'spell_naxxramas_arcane_momentum');
