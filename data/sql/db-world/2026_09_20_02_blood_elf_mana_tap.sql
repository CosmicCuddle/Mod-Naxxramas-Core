-- Naxxramas Core
-- Blood Elf - Mana Tap
--
-- Restores Mana Tap as a starting Blood Elf racial ability.

DELETE FROM `playercreateinfo_spell_custom`
WHERE `racemask` = 512
  AND `Spell` = 28734;

INSERT INTO `playercreateinfo_spell_custom`
    (`racemask`, `classmask`, `Spell`, `Note`)
VALUES
    (512, 414, 28734, 'Mana Tap - Blood Elf racial');