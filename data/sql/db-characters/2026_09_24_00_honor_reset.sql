CREATE TABLE IF NOT EXISTS `mod_naxxramas_honor_reset` (
    `id` TINYINT UNSIGNED NOT NULL DEFAULT 1,
    `last_reset` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO `mod_naxxramas_honor_reset`
(`id`, `last_reset`)
VALUES
(1, 0);