# Bot Consumables — Hunter Ammunition Auto-Detection (V1 DRAFT)

**Tracked at:** [master #28 (B02a)](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) · [issue #31](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/31)

**Status (19 October 2026):** Module-only, default-OFF **DRAFT PR #32**. The last verified documentation-only PR head before this guide refresh was `3504cde54e731732e2e6c26eafdf514162647d19`. Its exact-head [full pinned C++ / Worldserver / defined ammo-function CI #39172979749](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39172979749), [ammo policy #39172979690](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39172979690) and [NT1 #39172979688](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39172979688) **ALL PASSED**. The runtime ammunition implementation remains the prior `082a03d` source; this update changes only this Markdown guide. **NO** installed-server evidence, inventory acceptance, item grant, merge or configuration enablement.

## Owner's request and observed gap

When running `.bot consumables mc` and the level/named dungeon preparation commands, Hunter Altbots should also receive appropriate **real inventory ammunition**, automatically detecting the equipped ranged weapon and any currently selected ammo. Previously `PrepareHunter` supplied consumables and Hunter pet Juju but *no ammo*. This works regardless of whether a Hunter's pet is active.

Pinned core facts: `PLAYER_AMMO_ID` stores current ammo selection; `GetWeaponForAttack(RANGED_ATTACK)` returns the ranged weapon; native `CheckAmmoCompatibility` requires arrows for **bows/crossbows** and bullets for **guns**. `CanUseAmmo` and `ItemTemplate` validate native level/item restrictions. Thrown weapons/wands do not accept ammo. The core `Player::AddItem` may partially store on low bag capacity; this feature checks native storage capacity **before** attempting the addition and records **only the observed item-count increase** afterward.

## Scope and settings

```ini
NaxxramasCore.BotConsumables.HunterAmmo.Enabled = 0
NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor = 0
NaxxramasCore.BotConsumables.HunterAmmo.TargetCount = 600
```

The feature is **OFF by default**, and the target quantity is clamped to **1–1000 items per eligible Hunter** (not 1000 extra each time). No automated per-tick refills; the existing `.bot consumables` permission, cooldown, instance and party scope apply. Stage-1 implementation covers **controlled Altbots only**, not global Random Bots or real players.

The Hunter's real/effective dungeon level is also clamped to Vanilla's level **60**. Native ammo templates must be actual `ITEM_CLASS_PROJECTILE`, `INVTYPE_AMMO`, the appropriate arrow/bullet subclass, usable by the bot and its ranged weapon, required level at/below the effective stage, item level at/below **60**, and quality at/below **uncommon**.

## Selection rules (fail closed)

1. If a Hunter **already has an ammo type selected**, that specific ID must be in the small Classic catalog and compatible with its equipped weapon and effective level. If valid, supply the **shortfall of that same exact item ID** without changing selection.
2. **Thorium Headed Arrow (18042)** comes from a repeatable **quest exchange** and **Thorium Shells (15997)** are engineer-crafted. Simply finding either type selected must **NOT** mean they may be duplicated. Their replenishment requires *both* `Enabled=1` and the independent `AllowSelectedNonVendor=1` operator opt-in, and they must already be selected and native-compatible. Both controls are **OFF by default**. No Thorium fallback for an unselected Hunter. Existing unfamiliar, raid, PvP, reputation or higher-era selections are **never silently substituted or minted**. An exact installed-world/IP policy remains a separate review gate.
3. If **nothing is selected** (`PLAYER_AMMO_ID = 0`), select a conservative *vendor ammunition item for inventory only*, appropriate to the current bow/crossbow/gun and effective level. The owner/AI must manually select these items later. **No `SetAmmo`, equip or weapon swap.**
4. If no compatible ranged weapon (including broken, wand or thrown), no item template, the bot is a human/Random Bot, native use check fails or inventory cannot fit the entire top-up, skip rather than mutate unexpected items.
5. Verify existing bag amount, do **not** count bank stock as available, and add at most `TargetCount - current`; repeated command executions won't keep adding beyond target. No SQL schema changes, but **inventory grants are persistent character DB changes**.

### Explicit catalog (Classic IDs)

| Eligible level | Bow / crossbow | Gun | Fallback? |
| --- | --- | --- | --- |
| 1+ | Rough Arrow **2512** | Light Shot **2516** | yes |
| 10+ | Sharp Arrow **2515** | Heavy Shot **2519** | yes |
| 25+ | Razor Arrow **3030** | Solid Shot **3033** | yes |
| 40+ | Jagged Arrow **11285** | Accurate Slugs **11284** | yes |
| 52+ | Thorium Headed Arrow **18042** | Thorium Shells **15997** | **selected AND separately permitted (default deny)** |

The code checks the live database's actual item template against these assumptions. Other notable rarer ammo (Doomshot, AV ammunition, expansion ammunition) is **not** minted by this draft.

## Additional numeric safety regression (included in draft PR #32)

The feature now separates quota arithmetic into three pure C++ functions in `HunterAmmoSelection.h`: `TargetCount` strictly applies the **1–1000 ceiling** and any lower positive item template limit; `Shortfall` returns zero for sufficient existing ammunition; and `ObservedAdded` limits reporting to the *actual* before/after inventory increase, never exceeding the attempted quantity. The standalone policy test includes **17 additional edge-case assertions**, covering malformed configured targets, repeated runs, one missing round, insufficient capacity/partial additions, and impossible/negative stock deltas.

The corresponding source contract and tests are **already included in the current draft PR #32** at exact SHA `082a03d773b0b96a8f2beaefe6fb0433b5f138e3`. The [source and C++ policy CI #39135564447](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39135564447), [NT1 #39135564621](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39135564621) and [pinned real C++/full Worldserver build #39135564348](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39135564348) all **COMPLETED SUCCESS** on that **previous source/test-exact head**. The pinned build verified that the actual defined `NaxxramasHunterAmmo::TopUpHunterAmmo` symbol survives both module archive and linked Worldserver. This is **not live inventory/Playerbots acceptance** and does not authorise installation or opt-in.

## Test and acceptance matrix

- [x] Implement isolated selection policy and a real C++ test, `tests/hunter_ammo_selection.cpp`.
- [x] Wire `src/Systems/HunterAmmoProvision.cpp` to existing MC/dungeon command and stats; source only, disabled unless config explicit.
- [x] Maintain class/pet separation: `PrepareHunter` top-up occurs **before** missing-pet early return.
- [x] Include source-check contract `tests/test_hunter_ammo_consumables.py`.
- [x] **Hunter runtime source `082a03d` (retained by docs-only successors):** independent `AllowSelectedNonVendor = 0` gate and selected-Thorium default-deny source tests are included. Earlier `feature/hunter-ammo-source-safety-prepared-2026-10-18` is a historical preparation branch, not the live PR head.
- [x] Exact source revision `082a03d`: standalone C++ model/policy and source checks **PASS** — [#39135564447](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39135564447).
- [x] Exact source revision `082a03d`: actual C++ translation unit, full pinned AzerothCore/Playerbots/IP Worldserver link, and **defined `TopUpHunterAmmo` function presence in archive AND final executable** **PASS** — [#39135564348](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39135564348). No in-game ammo use inferred.
- [x] **Documentation/CI synchronization before this new guide revision:** PR #32 previous head `3504cde` passed exact-head full C++/Worldserver/retained-function #39172979749, policy #39172979690 and NT1 #39172979688. Any newer documentation-only commit needs its **own** head/run recorded; prior build results cannot be silently re-labelled.
- [ ] Verify operator's actual installed source and current world `item_template` match the test pin; investigate IP's additional item gating, especially Hunter stage shifts.
- [ ] Back up known-good Worldserver, active config and **full characters database**, and **prove the restore procedure** before any proposed inventory test.
- [ ] Approved one-Hunter MC pilot: selected vendor arrows, gun bullets, crossbow arrows; manual fallbacks without a selected ammo; crafted Thorium already selected; unusual/quest ammo denied; broken/missing weapon, level cap, no pet, full inventory, retry, relog, ammo consumption, character restore.
- [ ] Verify debug and summary messages accurately count ammo added, skipped, and needing manual selection. Test item count before/after across a partial bag constraint; verify no partial mutation.
- [ ] After real client/bot evidence, consider (with explicit owner approval) whether *optional* auto-selection of vendor fallback is appropriate; **not implemented here**.
- [ ] Separate owner approval for merge/install/config enablement and clear release/rollback notes.

### Rollback

In a reviewed maintenance window: restore `NaxxramasCore.BotConsumables.HunterAmmo.Enabled = 0` in the active module conf and restart Worldserver as approved; restore known-good binary/source if there is a problem. No SQL schema rollback or DBC change. If ammo was minted during an approved test, coordinate character inventory reversal using the recorded counts and original character DB backup rather than deleting inventory indiscriminately.

**IMPORTANT:** A source test or full pinned Worldserver link is *not proof* this is running or working on the owner's actual server. Keep the PR DRAFT and UNMERGED until separately approved.
