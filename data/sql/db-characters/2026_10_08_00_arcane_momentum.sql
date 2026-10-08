-- Naxxramas Core: Mage Arcane Momentum preference (per character).
-- Having a row = movement-direction Blink enabled; no row = normal Blink.
-- This is additive and does not alter existing character or spell data.

CREATE TABLE IF NOT EXISTS `mod_naxxramas_arcane_momentum` (
    `guid` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`guid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
