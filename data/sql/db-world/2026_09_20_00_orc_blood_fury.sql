-- Naxxramas Core
-- Orc - Blood Fury
--
-- Keeps the WotLK offensive Blood Fury bonuses while restoring
-- the older 50% healing-received penalty for 25 seconds.

DELETE FROM `spell_script_names`
WHERE `spell_id` IN (20572, 33697, 33702)
  AND `ScriptName` = 'spell_custom_orc_blood_fury_healing_reduction';

INSERT INTO `spell_script_names`
    (`spell_id`, `ScriptName`)
VALUES
    (20572, 'spell_custom_orc_blood_fury_healing_reduction'),
    (33697, 'spell_custom_orc_blood_fury_healing_reduction'),
    (33702, 'spell_custom_orc_blood_fury_healing_reduction');