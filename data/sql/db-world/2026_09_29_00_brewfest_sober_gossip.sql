-- Naxxramas Core
-- Brewfest Accessibility
--
-- Adds an optional sober-up gossip choice to:
--   Goldark Snipehunter (Alliance) - gossip menu 10603
--   Glodrak Huntsniper  (Horde)    - gossip menu 10604
--
-- OptionID 2 is custom and does not replace the existing
-- Synthebrew Goggles or dialogue options.

DELETE FROM `gossip_menu_option`
WHERE `MenuID` IN (10603, 10604)
  AND `OptionID` = 2;

INSERT INTO `gossip_menu_option`
(
    `MenuID`,
    `OptionID`,
    `OptionIcon`,
    `OptionText`,
    `OptionBroadcastTextID`,
    `OptionType`,
    `OptionNpcFlag`,
    `ActionMenuID`,
    `ActionPoiID`,
    `BoxCoded`,
    `BoxMoney`,
    `BoxText`,
    `BoxBroadcastTextID`,
    `VerifiedBuild`
)
VALUES
(
    10603,
    2,
    0,
    'The drinking effects are making me feel unwell. Could you sober me up?',
    0,
    7,
    1,
    0,
    0,
    0,
    0,
    '',
    0,
    0
),
(
    10604,
    2,
    0,
    'The drinking effects are making me feel unwell. Could you sober me up?',
    0,
    7,
    1,
    0,
    0,
    0,
    0,
    '',
    0,
    0
);
