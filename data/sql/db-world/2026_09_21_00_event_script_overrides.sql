/*
 * Naxxramas Core
 *
 * Event script overrides
 *
 * These entries redirect the affected event NPCs away from
 * AzerothCore's stock AI names and onto the Naxxramas Core
 * replacement scripts.
 */

-- =========================================================
-- Brewfest - Dark Iron Attack Generator
-- =========================================================

UPDATE `creature_template`
SET `ScriptName` = 'npc_naxxramas_dark_iron_attack_generator'
WHERE `entry` = 23703;


-- =========================================================
-- Hallow's End - Shade of the Horseman
-- =========================================================

UPDATE `creature_template`
SET `ScriptName` = 'npc_naxxramas_hallows_end_soh'
WHERE `entry` = 23543;