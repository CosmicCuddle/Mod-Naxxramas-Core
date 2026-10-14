# NT1 Offhand Preservation — Source Review and Safe Design Proposal

**Review date:** 13 October 2026  
**Status:** source-only investigation, separate draft PR; **no runtime patch, new equipment exception, or deployment**.  
**Trigger:** Arndor, level-60 Holy Priest Alt Bot; reviewed against merged PR #16 at commit `69a91be2ded62f6cdccf7ca6e7119ebdcc45e81b`.

## Summary of the actual observation

- Arndor received a valid read-only Holy Priest Raid NT1 Preview: Vanilla **51/51 points**, allocation **14 / 37 / 0**.
- Equipment report: main-hand item **11923**, `InventoryType=21` (main-hand); offhand item **22319**, `InventoryType=23` (held-in-offhand); `CanDualWield=NO` and `CanTitanGrip=NO`.
- Safety Inspection reports **no current core relocation trigger for a non-weapon offhand**, but still says **STILL BLOCKED** because hooks and post-reset state are unverified.
- Preview correctly reports `NT1 PREFLIGHT BLOCKED` because the **existing fail-closed guard disallows every occupied offhand on Alt Bots**. Neither Preview nor Safety Inspection performs Apply. The report is not contradictory: one message classifies known core inputs; the other enforces the stronger end-to-end policy.
- No change in talents or gear was observed/reported for Arndor. **Do not conduct an Apply or equipment test on Arndor.**

The earlier **Rakari** Priest case in [issue #17](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/17) separately demonstrates a zero-spent-talent character that was still blocked until the owner moved equipment manually. Those two observations share the guard but are not the same test.

## Exact source checkpoints inspected

| Repository / component | Source revision / paths |
|---|---|
| Naxxramas Core | `main` at `69a91be2ded62f6cdccf7ca6e7119ebdcc45e81b`; `src/Systems/BotTalentImport.cpp`, `BotTalentCompletion.cpp`, `BotTalentExpansionLimits.cpp` |
| Playerbots-compatible AzerothCore fork | `b7f06a16ac7120b5abc2e8d3f96a94265a363224`; `src/server/game/Entities/Player/Player.cpp`, `Player.h` |
| Playerbots module | `037c01418b5d01506917a3db9b44fd56ac5f965c`; `src/Bot/PlayerbotAI.cpp`, `src/Bot/Factory/PlayerbotFactory.cpp`, `src/Ai/Base/Actions/TrainerAction.cpp` |
| MultiBot draft NT1 integration | `CosmicCuddle/N-MultiBot-Chatless` draft PR #5; `docs/NT1-SERVER-INTEGRATION-CONTRACT.md` |

These are **reviewed repository source versions**, not proof the running Worldserver is compiled with every expected flag or that the operator's external modules/custom hooks are completely covered.

## 1. Core function trace — why a held-in-offhand is different

The **pinned** AzerothCore `Player::AutoUnequipOffhandIfNeed(bool force=false)`:

1. Returns early if no offhand (after an `UpdateTitansGrip` call).
2. Forces relocation if an offhand **weapon** is equipped without `CanDualWield`.
3. Forces relocation if the main-hand item's **weapon subclass** is polearm, staff or fishing pole.
4. Otherwise returns without relocating if Titan's Grip remains available, or if the offhand is not a two-handed weapon and `IsTwoHandUsed()` is false.
5. When relocating, uses `CanStoreItem` + `RemoveItem`/`StoreItem`; if inventory storage fails, it invokes `MoveItemFromInventory` and `MailDraft(...).AddItem(offItem).SendMailTo(...)` (a real original-item relocation, not hypothetical).

For Arndor's stated types **21 main-hand and 23 holdable offhand**, and ordinary one-handed post-reset state, the **function's own relocation condition does not appear to fire**. Lack of Dual Wield is relevant for an offhand **weapon**, not a holdable caster item. `InventoryType` alone cannot certify other state, future changes, custom item templates, or `force=true` from another caller. Even a non-relocating invocation may update Titan's Grip state.

**Do not infer this proves the item will remain equipped across a complete talent reset.**

## 2. Reset and failure path actually reached by NT1

Current `CheckApplyReadiness`:
- Rechecks eligible issuer/bot, current level/class/points, issuer Individual Progression era, role-independent build validity, database table, parseable/restorable original active talent plan, `GetFreeTalentPoints`, Random Bot classification, human Alt Bot allowlist, active pet and offhand.
- **Any occupied Alt Bot offhand** fails, regardless of type (23 holdable, shield, weapon or 2H).
- Access modes 3 and 4 refuse Apply independently. The other parts of Preview/Repair Preview may still show useful diagnostic results.

Current `ApplyValidated`, if called in permissive mode after successful validation:
- Acquires an import scope and **always calls `bot->resetTalents(true)`**, then attempts `LearnValidated`.
- On partial talent learning or post-validation failure, calls **`resetTalents(true)` again** and attempts to restore the old snapshot. This is **best effort, not a transaction**. An equipment-safe *first reset* is insufficient when a second reset may occur after abilities, auras or active talent spells have changed.
- There is no automatic Naxxramas Core **role-based gearing** in this import function; the importer does not directly call `AutoGear`, `EquipNewItem`, `DestroyEquippedGear` or `MailDraft`.
- `Player::resetTalents` calls `sScriptMgr->OnPlayerTalentsReset` **before** its zero-spent-talent early return. A reset that returns false still runs hooks. With actual spent points it may dismiss a pet, revoke Titan's Grip or Dual Wield and call `AutoUnequipOffhandIfNeed`.

For talent changes, equipment must remain independent. No automatic role-change gear transition, mail handling, offhand swapping or item replacement belongs inside NT1.

## 3. Hook review and remaining uncertainty

- Naxxramas Core **BotTalentCompletion** registers `PLAYERHOOK_ON_TALENTS_RESET`. Inside scoped NT1 import it erases **pending completion/intention** records and returns; this inspected branch **does not equip, destroy, move or mail equipment**. It also demonstrates that a reset can have non-equipment side effects. Outside import scope, the same script may queue a respec completion when enabled. Its separate `OnPlayerCanLearnTalent` hook explicitly allows ranks during import. `BotTalentExpansionLimits` preserves the row restrictions, permitting its already-scoped special case.
- The pinned Playerbots `PlayerbotFactory::Randomize` can perform a talent reset and **ClearAllItems** based on its persistence settings. `PlayerbotFactory::DestroyEquippedGear` explicitly calls `DestroyItem`; `AutoGear` and PlayerbotAI/TrainerAction contain equipment handling and can invoke `AutoUnequipOffhandIfNeed` in their own paths. **No direct call from the inspected Naxxramas Core importer to those routines was found.** This does **not** prove they cannot run from a scheduled Playerbots action, addon-driven ordinary command, another hook, or modified server module.
- Other installed AzerothCore modules and external Playerbots scripts/hook registrations, database states, item templates and real-time AI behaviour were **not** exhaustively verified. Their absence of a demonstrated direct call is **not a no-side-effects guarantee**.
- Preview's label `NO CURRENT CORE RELOCATION CONDITION` is **a branch observation** only. The current policy's `STILL BLOCKED` is therefore correct and should not be weakened solely for item #22319.

## 4. Safest staged solution — NOT yet implemented

**Stage A: diagnostic precision without mutation (preferred next C++ feature).**

- Enhance a read-only `repairpreview`/Preview comparison of the proposed NT1 **exact rank spell IDs** against **all** currently active-spec talent records, plus current free points, spec count/slot, exact DBC talent IDs, prerequisites and stale/orphan records. `51/51` and `14/37/0` totals alone are insufficient to establish equivalence.
- Return a clear **already matches exactly / mismatched / inconsistent / indeterminate** report. The report must not call `resetTalents`, learn spells, change active spec, write a profile, move gear or declare Apply safe.
- Preserve both-spec information, active glyph limitations, issuer entitlement and class/era checks before exposing potentially sensitive bot data. Use the existing read-only command interface; do not need a new MultiBot chat protocol for this phase.

**Stage B: server-side idempotent no-op, separate review only.**

- If a bot's *entire* active talent allocation is already identical, **after all issuer AccessMode, Alt Bot allowlist, ownership, Random Bot, class/era and current-bot revalidation**, an explicit no-change result might avoid any reset or learning. It must not bypass mode 3/4: a no-op report is not authority to Apply.
- Do not write an NT1 profile, change Playerbots command intents, update pet/gear, activate a different spec or report that any new talents were learned. Establish which response/state should be returned before changing the Apply path.
- If the match is uncertain for **any** reason, keep the old denial. Prototype and test this independently; do not silently adopt it as a generic shortcut.

**Stage C: genuinely new talent allocations with equipped offhands.**

- Do **not** exempt type 23, shields or any particular class from the guard until the **whole** reset + learn + failure + second-reset + hook + Playerbots update sequence has been experimentally shown to preserve every original item GUID and location, mail/bank inventory records, pets, inactive specialization and trained spells.
- Stronger designs may require a newly reviewed, reset-free or fully reversible talent operation. An initial-reset skip for zero points does not solve **partial LearnValidated failure** or hook effects. Rechecking only `AutoUnequipOffhandIfNeed` is insufficient.
- Any refined policy must be **default off**, limited to proven cases, explicitly deny ambiguous item templates, and never reposition items as an NT1 side effect. No owner authorization for such implementation/testing is recorded here.

**Separate future role-gear work:** a role change may suggest equipment differences, but **must not automatically equip/unequip or destroy earned items**. It would require an explicit separate player confirmation, preview of old/new GUIDs/locations, proven rollback, and new approval. No such feature is part of this PR.

## 5. Verification and rollback gate

**Safe in this draft PR only:** source documentation and Python synthetic/static checks. The checks contain a small model of the pinned AzerothCore core offhand branch; their return value `RETAIN_IN_CORE_MODEL_ONLY` **never means a real import is safe**. They require the current full occupied-offhand/pet guard, double-reset recovery risk, non-mutating diagnostic reports and no auto-gear calls in `ApplyValidated` to remain.

**Before any future real-game mutation, separately approved:**

1. Preserve a copy of current source, effective config, working worldserver binary and key custom patches, and record the actual deployed revision/build.
2. Create a **consistent** `acore_characters` backup and successfully restore it in an **isolated database**, with observed recovery of the complete target character and original item instance GUIDs. Merely making a SQL dump is not enough.
3. Use disposable controlled Alt Bots, not Arndor or other progression characters. Test type-23 held-in-offhand (including #22319 equivalent), shield, offhand weapons, Titan's Grip/2H, talent-dependent Dual Wield, pet, zero-spent-talents, exactly-matching builds, intentionally rejected ranks and post-failure rollback. Include classes and role changes across the actual server's custom DBC data.
4. Independently compare before/after: `item_instance.guid`, equipped inventory placement, mail records, bank/bags, spec masks, talents and talent-granted spells, glyphs, pet/stable, other module hooks, pending Playerbots intents, logouts and restart outcomes.
5. Reject and retain the block on any unexplained item movement, mail delivery, bot spec mutation or partial talent allocation.

## 6. MultiBot contract

N-MultiBot-Chatless remains a client-side request/inspection interface: server permissions and the existing `preview`, `repairpreview`, `safetypreview` and `apply` commands are unchanged by this review. Draft [MultiBot PR #5](https://github.com/CosmicCuddle/N-MultiBot-Chatless/pull/5) and its [server integration contract](https://github.com/CosmicCuddle/N-MultiBot-Chatless/blob/fix/nt1-confirm-class-package-audit/docs/NT1-SERVER-INTEGRATION-CONTRACT.md) should retain deliberate confirmation, safe target binding and the distinction between **command sent**, **valid Preview**, **blocked preflight** and **server-confirmed successful Apply**. No new client-side role auto-gearing or false `APPLY_READY` claim.

## Decision

**Retain the occupied-offhand guard and active-pet guard.** The static core logic offers a plausible basis for a *future* more precise rule, **not a current safety proof**. Prefer detecting **already-identical builds read-only** as the next independently testable feature; do not attempt non-idempotent resets with protected offhands without proven end-to-end recovery.

Related: [issue #17 — zero-talent imports](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/17), [PR #16 — original read-only audit](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/16).


## 7. Stage A implemented IN DRAFT as read-only active-talent comparison (not deployed)

To make the next decision less speculative, the draft now adds `InspectActiveTalentMatch` in `src/Systems/BotTalentImport.cpp` and surfaces `PrintActiveTalentMatch` in the existing **Preview** and Alt Bot **Repair Preview** reports. No new chat command or addon protocol was introduced; read-only diagnostics cannot call `LearnTalent`, `resetTalents`, `SaveToDB` or equip/move/mail items.

The result is **EXACT**, **DIFFERENT**, or **CANNOT VERIFY**:
- **EXACT** demands equality of the full active-spec `PlayerTalentMap` rank IDs *and* free-point budget against the server-validated NT1 code. 51/51 points or 14/37/0 tree totals alone are never enough.
- **DIFFERENT** means known active ranks differ; the report shows counts, not a permission to reset.
- **CANNOT VERIFY** takes precedence for missing or stale `PlayerTalent` records, wrong-class or unmatched custom DBC rank spells, multiple active ranks for one Talent.dbc entry, suspicious spec metadata, changed class/level budget or mismatched observed/free points. This is **not** interpreted as "different but safe."
- The existing `ValidateRequest` first performs server-side class, DBC, era and issuer/ownership checks. The **general Preview** displays protected Alt Bot exact-rank comparison **only** when the issuing human also passes `AltBotAllowedPlayers`, including GMs. Random Playerbots do not receive this Alt-only report. The dedicated `repairpreview` handler already checks the human allowlist before any report.
- Reporting is a volatile inspection of the **active spec only**; it does not cover inactive-spec glyphs, talent-granted auxiliary spells, equipment, pets, mail, bank, bags or recovery. A matched existing build **does not make Apply safe** while an offhand is occupied.

**Important:** the imported NT1 Apply and post-failure recovery paths remain **byte-for-byte unchanged**. Both original reset opportunities, occupied-offhand and active-pet blocks, config AccessMode and role-independent gear policy are preserved. No automatic no-op, exemption, gear movement or role change was implemented.

**Source/synthetic test scope:** `tests/test_nt1_active_talent_exact_match.py` asserts the three-way model for equal-point-but-different builds, mismatched ranks, unknown DBC class/spells, multiple active ranks, free-point corruption, empty and partial allocations; it also enforces the handler allowlist ordering, no diagnostic mutations and original double-reset + gear/pet guards. These tests are *not* a C++ compile or a live-item safety trial.

### Still needed before this change is production-ready

An owner-approved C++ compilation against the pinned AzerothCore/Playerbots source revisions, then test only `.naxxbot talents preview <bot> <code>` or `.naxxbot talents repairpreview <altbot> <code>` in-game. Do **not** issue Apply to validate the report. Confirm three-way output for a disposable known exact build, a different build with equal point totals, and a corrupted/custom DBC case in an isolated test environment. If there is no match report on general Preview, confirm the **issuing human name allowlist**; do not weaken it for a GM.

### Mandatory MultiBot release handover — still pending

**Owner request:** when the Naxxramas Core offhand/talent work is FINISHED, give the owner a concise, copy-paste-ready handover for the separately managed [N-MultiBot-Chatless](https://github.com/CosmicCuddle/N-MultiBot-Chatless) development chat (draft PR #5). Include what actually changed and its merge/deployment state, command syntax, new user-visible messages (EXACT / DIFFERENT / CANNOT VERIFY), server-only permissions, preserved Apply/two-click confirmation/targeting, unaltered offhand and pet blocks, 3.3.5a message length, no automatic role gearing, tests and any addon changes recommended/required. **Do not declare integration complete before final server decisions and in-game validation.** The previous coordination comment is already on MultiBot PR #5; the final owner handover is a separate deliverable.


## 8. Reproducible instance-GUID preservation evidence (read-only tooling)

The source review now includes an **offline-only** evidence template in [`scripts/nt1_altbot_evidence_readonly.sql`](../scripts/nt1_altbot_evidence_readonly.sql) and a [step-by-step gate for disposable characters](NT1-DISPOSABLE-ALTBOT-EVIDENCE-PROCEDURE.md). The SQL selects inventory position, **unique item-instance GUID** (not item template ID), item ownership, mail attachments, both talent spec masks, spells, glyphs, action bars, saved pets/pet spells and persisted auras. It has **no** write or reset commands.

The schema was checked against the exact pinned AzerothCore base definitions for `character_inventory`, `item_instance`, `mail_items`, `mail`, `character_talent`, `character_spell`, `character_glyphs`, `character_action`, `character_pet`, `pet_spell` and `character_aura`. **A source test validates a strict whitelist of SELECT statements and two session-variable assignments.** This is not a database backup; it requires a **verified isolated restore**, server-stopped saved-state comparison and separate owner approval before any destructive future experiments. It does **not** demonstrate that Arndor's item instance 22319 is safe during talent reset.


## 9. Isolated C++ compile-and-execute gate (passed; not full Worldserver)

[The exact active-match function's isolated C++17 contract harness](NT1-EXACT-MATCH-CPP-CONTRACT-2026-10-13.md) was added to the NT1 combined GitHub Action. The source slice itself is compiled and exercised with **15 deterministic synthetic runtime cases** (including invalid requested rank totals and missing planned DBC spell ranks), in addition to the existing **243 Python source/synthetic tests**. The [CI run](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38390259005) succeeded on commit `3765d1668efac0b39c5cb90e83c4776cb9010610`; all other four source-level workflow gates on that revision were green.

**This is NOT a full `BotTalentImport.cpp` compile against actual `Player.h`/`SpellMgr` headers, Worldserver linking, equipped-item experiment or in-game acceptance.** The harness deliberately simulates adjacent APIs, so a passing result only gives stronger evidence about the function's C++ syntax and controlled semantics. Retain the draft/no-merge/no-deploy rule and read-only testing priority. Final owner-to-MultiBot handover remains mandatory after actual completion.
