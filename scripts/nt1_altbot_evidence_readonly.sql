-- NT1 DISPOSABLE ALT BOT EVIDENCE (READ-ONLY, OFFLINE RESTORED DB ONLY).
-- Schema verified against pinned mod-playerbots/azerothcore-wotlk
-- b7f06a16ac7120b5abc2e8d3f96a94265a363224.
-- These SELECTs are NOT a backup, NOT a data restore and NOT proof of
-- equipment safety while the worldserver still holds unsaved state in RAM.
-- Do not execute against a changing live characters database.
-- Step 1: Work on a verified RESTORED, isolated acore_characters copy.
-- Step 2: Replace the zeros with DISPOSABLE bot / original item instance GUIDs.
-- Step 3: Run queries in HeidiSQL and export each result before/after
--         a separately approved isolated test, maintaining the same GUIDs.
-- Session variable assignments below do NOT change any database rows.
-- Keep the statements SELECT-only. NO destructive SQL is needed.
SET @NT1_TEST_BOT_GUID = 0;
SET @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID = 0;

-- 01: Bot identity, level and persisted online marker.
SELECT c.guid, c.name, c.level, c.class, c.online, c.at_login
FROM characters AS c
WHERE c.guid = @NT1_TEST_BOT_GUID;

-- 02: Every inventoried item (equipment, bags and bank as persisted).
-- The item's instance GUID is ci.item / ii.guid, NOT the itemEntry template ID.
SELECT ci.guid AS character_guid, ci.bag, ci.slot,
       ci.item AS instance_guid, ii.itemEntry AS item_template_id,
       ii.owner_guid, ii.count, ii.flags, ii.enchantments,
       ii.randomPropertyId, ii.durability
FROM character_inventory AS ci
LEFT JOIN item_instance AS ii ON ii.guid = ci.item
WHERE ci.guid = @NT1_TEST_BOT_GUID
ORDER BY ci.bag, ci.slot, ci.item;

-- 03: All item instances still owned by the disposable bot.
-- Compare instance GUIDs; do NOT assume mail or displaced items still
-- appear in character_inventory.
SELECT ii.guid AS instance_guid, ii.itemEntry AS item_template_id,
       ii.owner_guid, ii.count, ii.flags, ii.enchantments,
       ii.randomPropertyId, ii.durability
FROM item_instance AS ii
WHERE ii.owner_guid = @NT1_TEST_BOT_GUID
ORDER BY ii.guid;

-- 04: The ORIGINAL offhand item, looked up by its unique instance GUID
-- globally even if the owner, container or location changes.
SELECT ii.guid AS instance_guid, ii.itemEntry AS item_template_id,
       ii.owner_guid, ii.count, ii.flags, ii.enchantments,
       ii.randomPropertyId, ii.durability
FROM item_instance AS ii
WHERE ii.guid = @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID;

-- 05: Locate original offhand in ANY character's inventory, not only
-- the bot who initially owned it.
SELECT ci.guid AS character_guid, ci.bag, ci.slot,
       ci.item AS instance_guid
FROM character_inventory AS ci
WHERE ci.item = @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID;

-- 06: Mail holding the original item, if any.
SELECT mi.mail_id, mi.item_guid AS instance_guid, mi.receiver,
       m.sender, m.has_items, m.deliver_time, m.expire_time
FROM mail_items AS mi
LEFT JOIN mail AS m ON m.id = mi.mail_id
WHERE mi.item_guid = @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID;

-- 07: All mail attachments currently received by the disposable bot.
SELECT mi.mail_id, mi.item_guid AS instance_guid, mi.receiver,
       ii.itemEntry AS item_template_id, m.sender
FROM mail_items AS mi
LEFT JOIN item_instance AS ii ON ii.guid = mi.item_guid
LEFT JOIN mail AS m ON m.id = mi.mail_id
WHERE mi.receiver = @NT1_TEST_BOT_GUID
ORDER BY mi.mail_id, mi.item_guid;

-- 08: Talents of BOTH specialisations, with saved spec masks.
SELECT t.guid, t.spell, t.specMask
FROM character_talent AS t
WHERE t.guid = @NT1_TEST_BOT_GUID
ORDER BY t.spell, t.specMask;

-- 09: Saved spells, including talent-granted spells where persisted.
SELECT s.guid, s.spell, s.specMask
FROM character_spell AS s
WHERE s.guid = @NT1_TEST_BOT_GUID
ORDER BY s.spell, s.specMask;

-- 10: Glyphs for both specs, without switching spec in game.
SELECT g.guid, g.talentGroup, g.glyph1, g.glyph2, g.glyph3,
       g.glyph4, g.glyph5, g.glyph6
FROM character_glyphs AS g
WHERE g.guid = @NT1_TEST_BOT_GUID
ORDER BY g.talentGroup;

-- 11: Saved action bars of both specs.
SELECT a.guid, a.spec, a.button, a.action, a.type
FROM character_action AS a
WHERE a.guid = @NT1_TEST_BOT_GUID
ORDER BY a.spec, a.button;

-- 12: Stabled and active pets in saved data. A null GetPet() in game
-- does NOT imply the character has no pets stored here.
SELECT p.id AS pet_id, p.owner, p.entry, p.PetType, p.slot,
       p.level, p.CreatedBySpell, p.name, p.curhealth, p.curmana
FROM character_pet AS p
WHERE p.owner = @NT1_TEST_BOT_GUID
ORDER BY p.slot, p.id;

-- 13: Pet spell records for every owned pet.
SELECT p.id AS pet_id, p.slot, s.spell, s.active
FROM character_pet AS p
LEFT JOIN pet_spell AS s ON s.guid = p.id
WHERE p.owner = @NT1_TEST_BOT_GUID
ORDER BY p.id, s.spell;

-- 14: Aura records persisted for the bot (some temporary auras will not
-- be captured; compare only stable results after a controlled logout).
SELECT a.guid, a.casterGuid, a.itemGuid, a.spell,
       a.effectMask, a.stackCount, a.remainTime
FROM character_aura AS a
WHERE a.guid = @NT1_TEST_BOT_GUID
ORDER BY a.spell, a.casterGuid, a.itemGuid, a.effectMask;

-- Stop here. No database-writing commands are required or supplied.
