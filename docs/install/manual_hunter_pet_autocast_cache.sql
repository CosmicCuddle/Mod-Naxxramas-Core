-- Naxxramas Core: hunter pet autocast cache.
-- MANUAL INSTALL ONLY. DO NOT APPLY this file from CI, from this module,
-- or from a worldserver start.
--
-- This file is intentionally outside data/sql. At both pinned cores the
-- character updater discovers modules/<name>/data/sql/* directories whose
-- names contain "characters" and FillFileListRecursively walks them to
-- depth 10. A copy under any data/sql/*characters* path would be eligible
-- for ApplyUpdateFile when Updates.Character is on. Do not move it there.
--
-- The owner must approve it and back up the characters database before install.
-- Installing it does not read or rewrite pet_spell, and it does not turn any
-- existing pet ability on. There is no one-time migration.
--
-- This replaces the first draft shape (owner_guid, pet_number, spell_first,
-- active). Do not apply that shape. The module probes information_schema for
-- these seven columns and, if the probe fails or they are absent, does not
-- default-on and does not write.
--
-- AzerothCore stores the saved book in characters.pet_spell (guid = pet
-- number, spell, active). Ownership is characters.character_pet.owner and
-- character_pet.id. pet_spell has no owner column. There is no table named
-- character_pet_spell.
--
-- Identity is the player, the charm pet number, the creature entry, and the
-- create spell, plus the character_pet.savetime last bound by this module.
-- Pet::_SaveSpells says pet numbers are recycled. GeneratePetNumber on these
-- pins is MAX(id)+1 then increment, so a live process does not hand an old
-- id out again. Abandon deletes the character_pet row and this module's
-- orphan delete drops cache rows whose number is gone. A number that comes
-- back with a different entry or create spell deletes the old cache. A
-- matching entry with a different savetime is not applied. A same-entry
-- recycle whose savetime was rebound to the new row cannot be told apart.

CREATE TABLE IF NOT EXISTS `mod_naxxramas_hunter_pet_autocast` (
    `owner_guid` INT UNSIGNED NOT NULL COMMENT 'Player GUID counter, character_pet.owner',
    `pet_number` INT UNSIGNED NOT NULL COMMENT 'character_pet.id / CharmInfo::GetPetNumber',
    `creature_entry` INT UNSIGNED NOT NULL COMMENT 'character_pet.entry',
    `created_by_spell` INT UNSIGNED NOT NULL COMMENT 'character_pet.CreatedBySpell',
    `seen_savetime` INT UNSIGNED NOT NULL COMMENT 'character_pet.savetime last bound',
    `spell_first` INT UNSIGNED NOT NULL COMMENT 'First rank spell id',
    `active` TINYINT UNSIGNED NOT NULL COMMENT '1 autocast on, 0 off',
    PRIMARY KEY (`owner_guid`, `pet_number`, `spell_first`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Rollback ONLY after a backup, and only if this cache should be discarded:
-- DROP TABLE IF EXISTS `mod_naxxramas_hunter_pet_autocast`;
-- pet_spell is not modified by CREATE TABLE or by that DROP.
