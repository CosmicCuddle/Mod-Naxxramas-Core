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

## Single-session Hunter test card — PROPOSED / NOT RUN

**Use only after separate owner authorisation, a source-matched installed build, verified restore points and a disposable Hunter Altbot inside the actual chosen dungeon/raid profile.** The existing `.bot consumables` preparation also grants other configured consumables; it is **not an ammo-only command**. The game's cooldown/profile checks still apply; do not create extra inventory, economic or character-state effects on a real unbacked-up character. `Enabled` stays 0 until an approved pilot.

| Test | Source-backed preparation | Pass criteria |
| --- | --- | --- |
| Positive arrow pickup | A **verified Altbot** Hunter, alive, has a working bow/crossbow and **Jagged Arrow (11285) already selected**; suitable effective level at least 40; inventory has space, fewer than 600 of that item. In a permitted dungeon or MC profile, invoke the normal approved `.bot consumables <profile>` path once. | Real bag count increases by **no more than the shortfall to TargetCount** (default 600, subject to native MaxCount), **PLAYER_AMMO_ID remains 11285**; fire several ranged attacks and verify actual arrow consumption. Spell animations and a 'supplied' status message alone are NOT proof. |
| Positive bullet | Equivalent controlled Altbot Hunter with a working gun and allowed selected **Accurate Slugs (11284)** at suitable level. | Adds only the allowed compatible bullets; gun actually fires/consumes them; does not switch to arrows. |
| No selected ammo | Compatible working weapon, no current selected ammo ID. | The code can add level-appropriate vendor fallback arrows/shot to bags but **does not equip or select** them; readiness message must instruct manual selection. No false claim that the Hunter can fire without selecting ammo. |
| Rare ammo preserve | A Hunter whose **Doomshot (12654)** was legitimately selected, for example while using Bloodseeker crossbow 19107. `AllowSelectedNonVendor=0`. | Correct behavior is **no free Doomshot, no silent replacement** with Jagged Arrow and no forced ammo-ID change. Source catalog does not contain Doomshot. Owner's earlier skip is an expected safety result, NOT a positive test failure. |
| Exclusion and capacity | Human Hunter, unowned/random Playerbot Hunter, missing/broken ranged weapon, incompatible/expansion ammo, low-level or insufficient bag capacity. | No unauthorised grant to humans/rndbots; no partial bag-space top-up; reported skip is appropriately differentiated. Existing gold/quest/rarity inventory preserved. |
| Repeat/rollback | Repeat only after the **existing approved** consumables cooldown in a disposable test. Save before/after selected ammo, item quantity, actual shots and profile output. | Only source-authorised profile actions occur, not continuous auto-refills; cap never bypasses 60. Rollback means restoring dated character state if items were minted: flipping the enable switch back to 0 does **not** remove already granted stacks. |

**Exact user-facing source commands for a future approved test (do not run now):** `.bot consumables ubrs` runs the permitted UBRS profile while inside the relevant instance. `.bot consumables debug ubrs` captures one preparation's debug messages; `.bot consumables status` displays state. The command is master/instance scoped; do not treat this as permission to issue it on a production bot. Recheck command/runtime behavior against the owner's installed binary before relying on it. [Combined historical grouping/Warlock/Hunter native link SUCCESS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41138075456) only proves link coexistence; **no real ammunition was granted or fired by this CI**.

## Not in this draft

No SQL, no DBC, no core/Playerbots/Individual Progression edits, and no claim that a source test or a linked Worldserver proves inventory or combat behaviour. Leave the switch at 0 until a separate owner-approved pilot. Rollback is that same switch plus a restart; minted stacks would need the character backup from that pilot, not a schema rollback.
