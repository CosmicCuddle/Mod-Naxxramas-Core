-- Naxxramas Core
-- Blood Elf - Arcane Torrent
--
-- Keeps the WotLK 2-second silence while restoring
-- the original Mana Tap charge/resource interaction.

DELETE FROM `spell_script_names`
WHERE `spell_id` IN (28730, 25046)
  AND `ScriptName` = 'spell_custom_blood_elf_arcane_torrent';

INSERT INTO `spell_script_names`
    (`spell_id`, `ScriptName`)
VALUES
    (28730, 'spell_custom_blood_elf_arcane_torrent'),
    (25046, 'spell_custom_blood_elf_arcane_torrent');