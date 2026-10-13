# NT1 Alt Bot — Evidence and Recovery Gate (Disposable Characters Only)

**Status:** Planning and **read-only** inspection tools. No permission to run a destructive test, change equipment or skip `CheckApplyReadiness`.  
**Source baseline:** mod-playerbots-compatible AzerothCore `b7f06a16ac7120b5abc2e8d3f96a94265a363224`, Playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c`, Naxxramas Core `69a91be2ded62f6cdccf7ca6e7119ebdcc45e81b`.  
**Companion:** [scripts/nt1_altbot_evidence_readonly.sql](../scripts/nt1_altbot_evidence_readonly.sql).

## Purpose

The reported Arndor NT1 Preview contains **item template IDs** 11923 and 22319. A template ID identifies an *item type*, not the unique item instance. To prove original equipment survived, future isolated tests must compare the **same original `item_instance.guid`**, owner and equip position, with mail and bag/bank records. Merely finding another copy of item #22319 equipped afterwards is **not a pass**.

This procedure records evidence only. It does **not** assert that a normal reset is harmless for an equipped held-in-offhand and does not recommend doing one on Arndor or Rakari.

## Preparation — required before even considering an isolated mutation test

1. **Do nothing to production.** Do not test Apply, reset or gear changes on Arndor/Rakari. Keep the draft PR unmerged until reviewed.
2. Record the **exact actual worldserver binary**, module commits, Playerbots fork commit, effective `mod_naxxramas_core.conf`, custom DBC hashes, other enabled module/Playerbots config. A GitHub commit alone cannot prove a running binary's contents.
3. Make a **consistent entire `acore_characters` backup** with an appropriate server/DB maintenance window. The evidence SQL script cannot replace a backup.
4. **Demonstrate a successful restore into a separate, disconnected database**. Verify relevant character, `item_instance`, `character_inventory`, `mail_items`, `character_talent`, `character_spell`, `character_pet`, `pet_spell`, `character_glyphs` and `character_action` tables. Never replace the live database with the test copy.
5. Create a **disposable, isolated Alt Bot** with known equipment and talent states; do not use the owner's earned progression characters. An eventual destructive experiment needs its **own separate explicit approval**.

## Evidence collection — permitted read-only, on isolated restored data

1. With the isolated Worldserver **stopped** and the disposable character's state saved, open the **restored database** in HeidiSQL; confirm it is not the production connection.
2. Open [`scripts/nt1_altbot_evidence_readonly.sql`](../scripts/nt1_altbot_evidence_readonly.sql). Replace the zero-valued `@NT1_TEST_BOT_GUID` with the disposable character's GUID (not name). Set `@NT1_ORIGINAL_OFFHAND_INSTANCE_GUID` to the **unique item instance GUID**, never the item template #22319. Obtain the item GUID from the inventory query on the offline copy.
3. Run the **SELECT-only** queries. Export results with clear `BEFORE` filenames and retain a copy of the exact SQL and revisions. The two `SET @...` statements change session variables only, not database rows.
4. On a future **separately approved** isolated test, collect identically structured `AFTER` evidence **only after the disposable bot is fully saved and the isolated Worldserver is stopped again**. Comparing a saved `BEFORE` to an unsaved in-memory `AFTER` can produce false conclusions.
5. Compare every original item instance GUID/owner and exact bag/slot, mail attachment locations, talent rank spells and spec masks, spell records, glyphs, action bars, pet IDs/spells/stable slots and unexpected aura changes. A correct new talent allocation does **not** excuse unrelated lost/relocated gear.
6. Any missing item, new item copy masquerading as the original, unexpected mailbox row, item owner change, non-consensual equipment position change, unexpectedly changed inactive spec/pet state, or failed talent rollback **fails** the preservation gate. Quarantine that test copy and diagnose; do not retry on production.

## Evidence matrix (design only; not tests already performed)

| Case | What must be proven in a disposable, isolated environment |
|---|---|
| Already identical rank-for-rank active build | The future **no-op** truly leaves all item GUIDs and state untouched; read-only `EXACT` report does not itself authorize Apply |
| Zero talent points spent | A hypothetical direct-learn path handles failed rank learning **without** destructive rollback; no pet/gear effects |
| Priest main-hand #11923 type 21 + held-in-offhand #22319 type 23 | Exact **original offhand instance GUID and slot** survive both success and injected failure paths |
| Shield and caster focus across class/role changes | No forced unequip or mail even if reset changes talent-granted abilities |
| Offhand weapon, Dual Wield and Titan's Grip | Lost abilities cannot silently move equipment; unsafe cases remain blocked |
| Pet and stable slots, including Hunter/Warlock/Mage/DK | Original pets/spells/slots survive; `GetPet()==nullptr` alone is not proof |
| Inactive specialization, glyphs and action bars | No spec switch, stale rank, glyph removal or action bar replacement |
| Explicit role change (e.g., Shadow → Holy) | Talent import never invokes automatic gearing; any future gear action must be separately confirmed and reversible |
| Mid-apply LearnTalent rejection, rollback rejection or crash | No partial talents, pet loss, mailed/destroyed items or stale NT1 DB intent after recovery; demonstrate actual restore |

## Limits of these queries

- SQL is verified against the **pinned upstream base schema**. Your installed schema may differ after migrations/custom modules. Review `SHOW CREATE TABLE` offline if queries fail; never guess columns and never attempt schema changes for a read-only audit.
- A stopped-server DB snapshot does **not** expose all active auras, queued AI actions, active pets, unsaved talents, in-memory `PlayerTalentMap`, or hooks. Combine it with in-game *read-only* diagnostics and independently validated C++/integration tests.
- An isolated before/after match can support preservation *for that tested scenario only*; it cannot prove every item combination/hook is harmless or justify weakening the existing Alt Bot offhand and pet blocks globally.
- Capture the original item in **every** possible persistence location (inventory, item instance, mail). A report counting equal template IDs cannot prove GUID identity.
- The `mod_naxxramas_bot_talent_import` intent table may persist a requested profile; any future test must check whether its row is appropriate and consistent. The SQL script intentionally avoids promising a generic schema for custom module state.

## Release and addon coordination

Once C++ compilation and in-game read-only acceptance are confirmed, proceed by owner-approved stages only. **No new Apply behaviour** is currently implemented. Existing `preview`, `repairpreview`, `safetypreview` and `apply` interfaces are unchanged. The final Naxxramas Core → [N-MultiBot-Chatless](https://github.com/CosmicCuddle/N-MultiBot-Chatless) handover is a **mandatory deliverable** when this workstream is complete; it must explain new read-only `EXACT / DIFFERENT / CANNOT VERIFY` lines, final server state, and whether addon changes are actually necessary.
