-- Naxxramas Core 1.0.6.8.5: NT1 Playerbot talent import (opt-in).
-- Apply manually ONLY after backing up the characters database.
-- This does not alter Playerbots tables, talent tables, or AzerothCore source.
-- Desired NT1 profiles are written only after successful exact post-validation.
-- NOTE: automatic Playerbots maintenance restore is NOT yet implemented.

CREATE TABLE IF NOT EXISTS `mod_naxxramas_bot_talent_import` (
    `guid` INT UNSIGNED NOT NULL,
    `spec` TINYINT UNSIGNED NOT NULL,
    `code` VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`guid`, `spec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rollback ONLY if you intentionally want to discard stored NT1 profiles:
-- DROP TABLE IF EXISTS `mod_naxxramas_bot_talent_import`;
-- The normal character_talent data is not modified by CREATE TABLE.
