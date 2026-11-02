# Bot Consumables — Hunter ammunition (default OFF)

Draft reconciliation of [PR #32](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/32) (`84a3da6`, base `1f5f317`) onto current `main`. That branch is left untouched. This page describes the new candidate only. It is not installed, not enabled, and not an in-game test. Older CI on `84a3da6` does not certify this head.

Tracked at [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) and [issue #31](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/31).

## What it does

`.bot consumables` Molten Core preparation (`PrepareHunter`) and dungeon preparation (`PrepareDungeonBot`) may top up a controlled Hunter Altbot's bags. Bows and crossbows use arrows; guns use bullets. Thrown weapons, wands, and broken or missing ranged weapons are skipped. A missing pet does not block the top-up. Humans and Random Bots are excluded (`IsAltBot()`). There is no timer, no `SetAmmo`, and no weapon change.

```ini
NaxxramasCore.BotConsumables.HunterAmmo.Enabled = 0
NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor = 0
NaxxramasCore.BotConsumables.HunterAmmo.TargetCount = 600
```

Code fallbacks match those defaults (`HunterAmmoProvision.cpp`). `AllowSelectedNonVendor` denies free copies of quest-exchanged Thorium Headed Arrow (18042) and crafted Thorium Shells (15997) unless that second switch is explicitly on. The catalog is Classic-only. Effective level is `min(bot level, profile level, 60)`. Before any grant the code rechecks `ItemLevel <= 60`, quality at or below Uncommon, `CheckAmmoCompatibility`, and `CanUseAmmo`. The full shortfall must pass `CanStoreNewItem`; the reported amount is the actual before/after count. Target is clamped to 1..1000 and to the item `MaxCount`.

Vendor fallback when nothing is selected: Rough/Sharp/Razor/Jagged arrows (2512/2515/3030/11285) and Light/Heavy/Solid/Accurate shot (2516/2519/3033/11284). Unselected Thorium is never the fallback. Unknown, quest, reputation, PvP, or expansion selections remain selected and unchanged, but if the module cannot safely refill them it instead supplies the highest level-appropriate standard vendor ammunition matching the equipped weapon in the bot's bags. For example, Doomshot (12654) is **never duplicated**, while a level-60 crossbow Hunter can receive Jagged Arrows (11285) as separate backup. No auto-select/equip occurs: the Hunter must select that backup when needed. If the original selected ammo *is* approved and supplyable, the module still refills the preferred ammunition first.

## Known caveats

- **Selection cleared when the stack runs out.** Pinned Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`, `src/server/game/Spells/Spell.cpp` lines 8013-8016: if the ranged attack has no remaining count of `PLAYER_AMMO_ID`, core sets `PLAYER_AMMO_ID` to 0 and returns `SPELL_FAILED_NO_AMMO`. The next preparation then takes the unselected path (`AddedVendorAmmoNeedsSelection`): bags get a vendor fallback, which is not selected, and a Hunter who ran out of Thorium can be downgraded to Jagged Arrow or Accurate Slugs. Inventory delivery does not equip that ammo.
- **Free refill.** Each authorised preparation fills the shortfall back up to the target. The only bound is the existing consumables profile cooldown, bag space, and the 1..1000 clamp. Spent ammo is replaced at no cost. That is an economy effect for controlled Altbots, not a gold or vendor transaction.
- **Live rows and Altbot identity are unknown here.** Whether the installed world's `item_template` rows for the ten catalog IDs match these assumptions, and what the installed Playerbots build means by `IsAltBot()`, was not checked against a running realm.
- **A level 70+ Hunter still receives Classic-tier ammo.** The level cap is 60, so the vendor fallback stops at Jagged Arrow / Accurate Slugs. Thorium stays selected-only and default-deny.

## Not in this draft

No SQL, no DBC, no core/Playerbots/Individual Progression edits, and no claim that a source test or a linked Worldserver proves inventory or combat behaviour. Leave the switch at 0 until a separate owner-approved pilot. Rollback is that same switch plus a restart; minted stacks would need the character backup from that pilot, not a schema rollback.

## 2 Nov 2026 owner-directed Doomshot single-allocation draft (NOT LIVE)

The earlier vendor-only fallback now has a separate **default-OFF**
`NaxxramasCore.BotConsumables.HunterAmmo.AllowOneDoomshotAllocation = 0` option.
When separately enabled, a controlled Hunter Altbot with a bow/crossbow
that **already has and selects** Doomshot ID 12654 and meets level 54+
may receive up to **200 total Doomshot arrows** in bags.
Any already-held Doomshot counts against the 200 allowance.
The remainder of the existing configurable target (e.g. 600-200=400)
is supplied as Jagged Arrow or a lower legal vendor arrow, subject to
item template compatibility and available bag space. Source permits
replenishment of consumed Doomshot on a later eligible preparation;
this is **not a one-time lifetime issuance**. Selected projectile and
rare inventory are never deleted or forcibly replaced. Other rare ammo
and non-vendor Thorium are not granted by this exception.

WotLK item_template may allow a physical stack of 1000 arrows; the
200-allocation is an intentional policy cap so mixed ammunition fits the
owner's requested total. The current Playerbots build's ability to
switch to the backup after selected Doomshot runs out remains unverified.
Verify true live item_template Stackable/MaxCount, AddItem outcomes and
bot use before any protected branch merge or production deployment.

## 2 Nov 2026 — 16-slot Molten Core quiver mode (DRAFT, default OFF)

The owner clarified that Vanilla ammunition is grouped in **200-arrow stacks**
and the actual MC quiver has **16 slots**. A new independent config
`NaxxramasCore.BotConsumables.HunterAmmo.MoltenCore.FillQuiver.Enabled = 0`
allows **only the Molten Core profile, map 409** to fill an equipped
**16-slot matching quiver (bow/crossbow)** or ammo pouch (gun). Other
profiles use the previous TargetCount=600 top-up when enabled.

For a quiver with 16 available slots and genuine item_template stacking
of 200 or above, one selected, owner-authorized Doomshot allocation to at
most **200 total owned** and 15 stacks of approved vendor Jagged Arrows
could give **3,200 arrows maximum in that quiver**. This is an illustration,
not a tested result. Existing ammunition stacks are never moved/deleted;
other occupied slots reduce available fill space. The Doomshot exception
also requires the separate default-OFF permission, an **existing Doomshot
item** and a compatible, eligible level-54+ Hunter.

This mode uses native per-slot CanStoreNewItem and StoreNewItem, never
general AddItem; it intends to put the ammunition **in the actual quiver**
and should not grant thousands to ordinary bags if no correct quiver exists.
Runtime item templates, specialised-bag compatibility, core compile and
actual client inventory **are not yet verified**. A 3,200-arrow free refill
per MC preparation is a significant economy change, not a bag-size-only
cosmetic change. Roll back by leaving this config OFF; record any inventory
grants and restore a test-character backup before any production use.

**Rare already stored elsewhere:** When a selected, eligible 200-arrow
Doomshot allocation is already entirely in another bag and not in the
quiver, the module does not move or duplicate the rare stack. It reserves
one empty quiver slot instead, so the owner/Playerbots can move that
legitimate stack when appropriate. Consequently the quiver may not
immediately display 16 filled slots.