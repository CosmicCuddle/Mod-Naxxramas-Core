-- Naxxramas Core: calendar-based Elemental Invasions (game_event 13).
-- IMPORTANT: Back up the complete original game_event row (eventEntry=13)
-- before applying this migration. See docs/ELEMENTAL-INVASIONS.md.
--
-- GAMEEVENT_INTERNAL (5) prevents the built-in minute-based event scheduler
-- from switching event 13 off between module-controlled calendar checks.
-- The WorldScript starts and stops the original event using GameEventMgr.
-- All other game events and their existing recurrence values are unchanged.
--
-- This is intentionally guarded: it only alters the stock Elemental
-- Invasions row in its normal (0) state. Custom event IDs are not overwritten.
UPDATE `game_event`
SET `world_event` = 5
WHERE `eventEntry` = 13
  AND `world_event` = 0
  AND `description` = 'Elemental Invasions';
