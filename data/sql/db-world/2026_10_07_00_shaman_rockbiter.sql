-- Naxxramas Core
-- Shaman - Rockbiter Weapon restoration
--
-- Restores the Rockbiter rank chain through Rank 7,
-- adds Ranks 5-7 to both AzerothCore Shaman trainer paths,
-- and binds the hidden server-side Rockbiter threat aura.
--
-- Spell.dbc IDs used by the module:
--   90059 = hidden Rockbiter threat proc aura
--   90060-90066 = hidden AP scaler spells (Ranks 1-7)

-- ---------------------------------------------------------
-- Hidden Rockbiter threat aura script
-- ---------------------------------------------------------

DELETE FROM `spell_script_names`
WHERE `spell_id` = 90059
  AND `ScriptName` = 'spell_custom_sha_rockbiter_threat';

INSERT INTO `spell_script_names`
    (`spell_id`, `ScriptName`)
VALUES
    (90059, 'spell_custom_sha_rockbiter_threat');

-- ---------------------------------------------------------
-- Rockbiter spell rank chain
-- ---------------------------------------------------------

DELETE FROM `spell_ranks`
WHERE (`first_spell_id` = 8017 AND `rank` BETWEEN 5 AND 7)
   OR `spell_id` IN (16314, 16315, 16316);

INSERT INTO `spell_ranks`
    (`first_spell_id`, `spell_id`, `rank`)
VALUES
    (8017, 16314, 5),
    (8017, 16315, 6),
    (8017, 16316, 7);

-- ---------------------------------------------------------
-- Shaman class trainer (TrainerId 14)
-- ---------------------------------------------------------

DELETE FROM `trainer_spell`
WHERE `TrainerId` = 14
  AND `SpellId` IN (16314, 16315, 16316);

INSERT INTO `trainer_spell`
    (`TrainerId`, `SpellId`, `MoneyCost`, `ReqSkillLine`,
     `ReqSkillRank`, `ReqAbility1`, `ReqAbility2`,
     `ReqAbility3`, `ReqLevel`, `VerifiedBuild`)
VALUES
    (14, 16314,  9000, 0, 0, 10399, 0, 0, 34, 0),
    (14, 16315, 18000, 0, 0, 16314, 0, 0, 44, 0),
    (14, 16316, 29000, 0, 0, 16315, 0, 0, 54, 0);

-- ---------------------------------------------------------
-- Shared AzerothCore Shaman trainer template (ID 200018)
--
-- AzerothCore still has NPCs that reference this shared template.
-- Existing Rockbiter Ranks 2-4 are present here, so restore 5-7 too.
-- ---------------------------------------------------------

DELETE FROM `npc_trainer`
WHERE `ID` = 200018
  AND `SpellID` IN (16314, 16315, 16316);

INSERT INTO `npc_trainer`
    (`ID`, `SpellID`, `MoneyCost`, `ReqSkillLine`,
     `ReqSkillRank`, `ReqLevel`, `ReqSpell`)
VALUES
    (200018, 16314,  9000, 0, 0, 34, 0),
    (200018, 16315, 18000, 0, 0, 44, 0),
    (200018, 16316, 29000, 0, 0, 54, 0);
