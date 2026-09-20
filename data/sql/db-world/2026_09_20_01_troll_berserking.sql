-- Naxxramas Core
-- Troll - Berserking
--
-- Keeps the WotLK 20% haste baseline and restores
-- health-based scaling up to 30% at low health.

DELETE FROM `spell_script_names`
WHERE `spell_id` = 26297
  AND `ScriptName` = 'spell_custom_troll_berserking';

INSERT INTO `spell_script_names`
    (`spell_id`, `ScriptName`)
VALUES
    (26297, 'spell_custom_troll_berserking');