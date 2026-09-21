/*
 * Naxxramas Core
 *
 * Forsaken - Touch of the Grave
 *
 * 90052 = Passive proc aura
 * 90053 = Damage / health leech spell
 */

-- =========================================================
-- Spell Script
-- =========================================================

DELETE FROM `spell_script_names`
WHERE `spell_id` = 90053;

INSERT INTO `spell_script_names`
(
    `spell_id`,
    `ScriptName`
)
VALUES
(
    90053,
    'spell_naxxramas_touch_of_the_grave'
);


-- =========================================================
-- Proc Configuration
-- =========================================================

DELETE FROM `spell_proc`
WHERE `SpellId` = 90052;

INSERT INTO `spell_proc`
(
    `SpellId`,
    `SchoolMask`,
    `SpellFamilyName`,
    `SpellFamilyMask0`,
    `SpellFamilyMask1`,
    `SpellFamilyMask2`,
    `ProcFlags`,
    `SpellTypeMask`,
    `SpellPhaseMask`,
    `HitMask`,
    `AttributesMask`,
    `DisableEffectsMask`,
    `ProcsPerMinute`,
    `Chance`,
    `Cooldown`,
    `Charges`
)
VALUES
(
    90052,
    0,
    0,
    0,
    0,
    0,
    12915028,
    1,
    2,
    3,
    0,
    0,
    0,
    5,
    0,
    0
);