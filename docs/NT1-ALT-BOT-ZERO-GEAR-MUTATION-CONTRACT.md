# NT1 Alt Bot — Zero Gear Mutation Contract

**Status: OWNER-PROPOSED SAFETY REQUIREMENT; NOT YET IMPLEMENTED OR RUNTIME-VERIFIED.**

This is the required safety rule for future Alt Bot talent-import development. It is not a statement that PR #18 already makes changing an equipped Alt Bot's talents safe. The current **offhand/pet Apply blocks remain active**.

## Non-negotiable behaviour

**An NT1 talent-change operation on an Alt Bot must not manipulate any item of equipment. No exceptions.**

During the entire NT1 operation, including success, error handling, any talent reset, hooks, delayed bot tasks and recovery, NT1 must never cause:

- Unequipping, swapping, equipping, moving, mailing, deleting, destroying, recreating, enchanting, modifying or replacing equipment.
- Moving an original equipped item to inventory, bags, bank or mail, even if its unique GUID still exists.
- Automatic role/gearing changes when a bot switches talents, e.g. Shadow/Holy Priest, Balance/Feral Druid, DPS/Tank Warrior or Elemental/Enhancement Shaman.
- A "best effort" recovery that modifies equipment or uses newly generated item instances in place of original ones.
- Exceptions for GMs, administrators, offhand type, item quality, class, bot level, available bag space or a supposedly harmless item relocation.

This contract is scoped to **talent operations**; it does not prohibit normal, separately requested inventory/equipment management outside talent import. If role-dependent gearing is ever built, it must be a **separate, explicitly authorised, independently reversible command** and must not piggyback on talent import.

## Fail before mutation, not after

The behaviour must be **safe-or-reject**:

1. Perform the ordinary server-side human issuer, Alt Bot allowlist, ownership, IP-era, class, talent legality, level and config AccessMode checks first.
2. Verify requested ranks against the **entire active specialisation**. For a proven identical build, a future expressly reviewed **no-op** path may return success with no reset or gear action. The PR #18 inspector is **diagnostic only**, not yet an Apply no-op.
3. For a different build, prove the proposed method cannot reach any gear-changing core/Playerbots/other-module hook, automatic equipment routine or queued bot AI action; preserve original equipment item-instance GUIDs, slots and original item metadata. Do not assume a caster held-in-offhand is harmless merely because `AutoUnequipOffhandIfNeed` has no immediate trigger.
4. If the build depends on abilities removed by a reset (Dual Wield, Titan's Grip, some offhand configurations), or a hook/source path is unknown, **deny the talent change before the first state mutation**. Gear must remain exactly as it was.
5. Never attempt to satisfy the request by temporarily unequipping the item, mailing it to the bot, or auto-gearing it afterward.
6. Error handling must preserve gear too: a failure and the rollback attempt are part of the **same no-equipment-mutation guarantee**. A post-hoc snapshot, inventory checksum or replacement item is insufficient prevention.
7. If other Playerbots background activity could manipulate gear during or immediately after the transaction, source-prove an effective prevention/coordination mechanism or reject the operation. A read-only before/after check alone cannot prevent a mid-operation move or crash.

A guarantee covering unrelated, uncontrolled actions of third-party modules cannot be asserted from NT1 alone. Where this cannot be demonstrated, return **BLOCKED: GEAR PRESERVATION CANNOT BE GUARANTEED**, rather than promising success.

## Why an offhand exception is not the solution

Current AzerothCore's `Player::resetTalents(true)` may invoke script hooks, remove a pet, remove talent-granted abilities and call `Player::AutoUnequipOffhandIfNeed()`. That helper can relocate or **mail** equipment. The NT1 importer currently invokes a reset and may invoke a **second** reset when attempting recovery.

Therefore, allowing caster offhands, shields, or any specific item template through the existing guard without addressing the reset/hook path does **not** satisfy this contract.

**Arndor's example:** main-hand template **11923**, held-in-offhand template **22319**. The target is to apply a valid different Holy Priest raid build **without moving either original item instance at all**. Until this is proven, retain the guard and leave Arndor untouched.

## Acceptance matrix before permitting any different-build Apply

| Scenario | Required result |
|---|---|
| Already exact active-spec ranks | Authorised no-op, no reset and zero gear actions; still obey normal issuer/config restrictions |
| Legal different Holy Priest build, one-hand + caster held-in-offhand | Talent change permitted **only when the entire source and hook path is proven gear-inert**; original equip instance GUIDs/slots unchanged |
| Shield, offhand weapon, staff/polearm, lost Dual Wield/Titan's Grip | Reject **before any mutation** if gear inertia cannot be proven |
| Warrior/Druid/Priest/Shaman role change | Talents only; never auto-equip a role preset |
| Hunter/Warlock/Mage/DK with summoned or stabled pets | No unrelated pet loss; unverified pet path remains blocked separately |
| Talent-learning error or rollback error | No item mutations of any kind; zero "mail and recover later" actions |
| Module callbacks, delayed Playerbots AI, addon-triggered actions | No NT1-caused gear change even asynchronously; reject unverified paths |
| Crash/persistence boundary | Original equipment state and unique item-instance GUIDs survive; restore proof required before any destructive test |

Review pinned core, Playerbots and other installed module sources; include injected-failure tests, a full linked Worldserver build, and **disposable, isolated database backup/restore trials** before enabling new Apply behaviour. Do not test this on earned-character gear, including Arndor and Rakari. Consult [the disposable equipment evidence procedure](NT1-DISPOSABLE-ALTBOT-EVIDENCE-PROCEDURE.md) for read-only GUID/slot/mail validation. No client/DB/Git merge changes are authorised by this design document.

## Release and MultiBot contract

- PR #18 remains **draft and unmerged**; its existing read-only talent match, tests and documentation do not satisfy the new different-build mutation invariant.
- Do not replace the universal offhand guard with item-type exceptions.
- Do not introduce automatic equipment handling to MultiBot. The server alone decides if a talent change can occur, and should report **BLOCKED** if gear safety is unproven.
- On completion, give the owner the **mandatory copy-and-paste-ready final Naxxramas Core → N-MultiBot-Chatless handover**, with actual verified server behaviour, updated messages and any necessary addon UI changes.
