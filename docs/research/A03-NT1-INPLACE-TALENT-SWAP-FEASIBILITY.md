# A03 P4 — Can a changed-build Alt Bot talent swap be atomic and keep gear and pets?

**Status:** research plus an executable fact checker. **No runtime code, config, SQL or bot data change.** The Alt Bot fail-closed guard (#18, and the offhand/pet guard on main) is untouched.

**Pins:** core Grimfeather `8daffda`, Playerbots `d750b4b`, IP `dd96f2b`.

**Scope:** #62 already proved that sequential `LearnTalent` is not atomic. This note does not repeat that. It asks whether any **other** module-only path exists.

## Verdict

1. **Reset-based Apply (the current path): NO, under any variant.** `Player::resetTalents` has these effects:
   - it dismisses the pet whenever any point is spent (F1);
   - it clears Titan's Grip and dual wield and then auto-unequips, and possibly **mails**, the offhand (F2);
   - its rollback is a second reset followed by a relearn, so it is not transactional.

   No module setting avoids these effects.
2. **Reset-free in-place swap: possible in principle, but only for a restricted subset, and it is NOT implemented here.**
   - The primitives are **public** (F4): `_removeTalent`, `_removeTalentAurasAndSpells`, `addTalent`, `_addTalentAurasAndSpells`, `removeSpell`, `learnSpell`, `SetFreeTalentPoints`.
   - None of these touches the pet slot or equipment.
   - **Atomicity** needs every precondition checked **before** the first change. After that, no step may fail:
     - `addTalent` fails only on static DBC data or an already-present talent (F6);
     - during an import, the only `OnPlayerCanLearnTalent` vetoes are this module's own two hooks, which are deterministic (F7). Playerbots and IP implement **no** talent hooks at the pins.

     A full pre-validation can therefore guarantee an all-or-nothing in-memory swap within one map-thread call.
3. **What a reset-free swap would have to reimplement in the module.** Each item is a correctness risk:
   - **`LearnTalent`'s rule checks and post-steps** (F5):
     - class mask, rank, dependency and tier checks;
     - `learnSpell` for spell-book talents, `SendLearnPacket`, additional talent spells, `SetFreeTalentPoints`;
     - `OnPlayerLearnTalents`, which this module itself uses in `ShamanRockbiter`, `WarlockWrack` and `BotTalentCompletion`.
   - **Capabilities that only `resetTalents` and `ActivateSpec` clear** (F3). Titan's Grip and dual wield would otherwise be left stale. Clearing them correctly requires `AutoUnequipOffhandIfNeed`, which moves gear. So **any swap that changes a Titan's Grip or dual-wield-granting talent must be refused**, not handled.
   - **Pet-affecting talents.** A swap is unsafe while a pet is present if it changes any of:
     - pet auras;
     - Beast Mastery pet talent points or exotic pets;
     - summon talents such as Felguard;
     - DK Master of Ghouls.

     The in-place path must refuse such diffs.
   - **Other `OnPlayerTalentsReset` users** (`WarlockWrack`, `BotTalentCompletion`): their reset-time behaviour would not run and needs separate review.

**Answer to "is safe, atomic changed-build application possible while preserving gear, pets and state?"**
- **Not with the existing reset path.**
- **Conditionally, with a new reset-free swap**, and only for builds whose diff avoids gear-capability and pet-affecting talents, for a bot that is out of combat, alive and not in an instance encounter.
- Building that swap is a new, owner-approved feature with its own S1/S2 review. It is **not** a fix. `changed_build_altbot_apply_safe` stays **false**, and #18 stays fail-closed.

## Executable evidence

- `scripts/check_nt1_inplace_swap_facts.py` checks facts F1–F8 against the pinned sources and this module. Any mismatch exits 1, so a pin bump forces re-review instead of passing silently.
- `tests/test_nt1_inplace_swap_facts.py` has 23 tests:
  - the real pins pass;
  - 21 negatives, each mutating the real pinned text: pet removal made conditional, removed or moved; offhand unequip removed; a new Titan's Grip reset site or one removed from `ActivateSpec`; a primitive made private or removed; `OnPlayerLearnTalents` removed; an exit after `addTalent`; the veto moved after the rule checks; a new `addTalent` failure or hook; a Playerbots or IP talent hook added; a commented hook ignored; the module hook set changed; the module pet or offhand guard removed; Apply no longer resetting;
  - CLI exit codes.
- `.github/workflows/nt1-inplace-swap-facts.yml` runs both against sparse checkouts of the exact pins.

## Not done or not proven

- No swap implementation and no runtime test.
- No proof that hooks registered by modules **outside** these three pins are absent on the owner's server.
- The DBC-side list of pet-affecting and capability talents for a refusal table is not built.
- Mandatory gameplay outcomes remain 0/5.
