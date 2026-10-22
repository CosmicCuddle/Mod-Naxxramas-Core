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

Vendor fallback when nothing is selected: Rough/Sharp/Razor/Jagged arrows (2512/2515/3030/11285) and Light/Heavy/Solid/Accurate shot (2516/2519/3033/11284). Unselected Thorium is never the fallback. Unknown, quest, reputation, PvP, or expansion selections are left unchanged.

## Known caveats

- **Selection cleared when the stack runs out.** Pinned Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`, `src/server/game/Spells/Spell.cpp` lines 8013-8016: if the ranged attack has no remaining count of `PLAYER_AMMO_ID`, core sets `PLAYER_AMMO_ID` to 0 and returns `SPELL_FAILED_NO_AMMO`. The next preparation then takes the unselected path (`AddedVendorAmmoNeedsSelection`): bags get a vendor fallback, which is not selected, and a Hunter who ran out of Thorium can be downgraded to Jagged Arrow or Accurate Slugs. Inventory delivery does not equip that ammo.
- **Free refill.** Each authorised preparation fills the shortfall back up to the target. The only bound is the existing consumables profile cooldown, bag space, and the 1..1000 clamp. Spent ammo is replaced at no cost. That is an economy effect for controlled Altbots, not a gold or vendor transaction.
- **Live rows and Altbot identity are unknown here.** Whether the installed world's `item_template` rows for the ten catalog IDs match these assumptions, and what the installed Playerbots build means by `IsAltBot()`, was not checked against a running realm.
- **A level 70+ Hunter still receives Classic-tier ammo.** The level cap is 60, so the vendor fallback stops at Jagged Arrow / Accurate Slugs. Thorium stays selected-only and default-deny.

## Not in this draft

No SQL, no DBC, no core/Playerbots/Individual Progression edits, and no claim that a source test or a linked Worldserver proves inventory or combat behaviour. Leave the switch at 0 until a separate owner-approved pilot. Rollback is that same switch plus a restart; minted stacks would need the character backup from that pilot, not a schema rollback.
