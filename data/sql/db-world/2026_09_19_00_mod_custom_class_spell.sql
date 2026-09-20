-- Rend Flurry
-- Attach the custom Rend Flurry script to every rank of Rend.
-- Negative spell_id means the entire spell rank chain.

DELETE FROM `spell_script_names`
WHERE `spell_id` = -772
  AND `ScriptName` = 'spell_custom_warr_rend_flurry';

INSERT INTO `spell_script_names`
    (`spell_id`, `ScriptName`)
VALUES
    (-772, 'spell_custom_warr_rend_flurry');