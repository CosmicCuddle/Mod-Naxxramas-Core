-- Naxxramas Core: hunter pet autocast cache.
-- DO NOT APPLY this file from CI, from this module, or from a worldserver start.
-- The owner must approve it and back up the characters database before install.
-- Installing it does not read or rewrite pet_spell, and it does not turn any
-- existing pet ability on. There is no one-time migration.
--
-- AzerothCore stores the saved book in characters.pet_spell (guid = pet number,
-- spell, active). This table is the module's own pre-IP choice, keyed by the
-- player and the charm pet number plus the first rank. Pet numbers are recycled
-- by the core (Pet.cpp _SaveSpells). owner_guid keeps one player's rows off
-- another player's pet. A recycled number on the same account can still collide
-- until the next verified write replaces that pet's rows.

CREATE TABLE IF NOT EXISTS `mod_naxxramas_hunter_pet_autocast` (
    `owner_guid` INT UNSIGNED NOT NULL COMMENT 'Player GUID counter',
    `pet_number` INT UNSIGNED NOT NULL COMMENT 'CharmInfo::GetPetNumber',
    `spell_first` INT UNSIGNED NOT NULL COMMENT 'First rank spell id',
    `active` TINYINT UNSIGNED NOT NULL COMMENT '1 autocast on, 0 off',
    PRIMARY KEY (`owner_guid`, `pet_number`, `spell_first`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Rollback ONLY after a backup, and only if this cache should be discarded:
-- DROP TABLE IF EXISTS `mod_naxxramas_hunter_pet_autocast`;
-- pet_spell is not modified by CREATE TABLE or by that DROP.
