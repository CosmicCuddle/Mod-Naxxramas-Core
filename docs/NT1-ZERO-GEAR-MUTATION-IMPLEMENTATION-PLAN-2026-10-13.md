# NT1 Alt Bots — Safe Talent-Change Implementation Plan

**Development date:** 13 October 2026; **owner explicitly ratified the zero-gear rule on 14 October 2026**  
**Owner decision:** Keep `NaxxramasCore.BotTalentImport.AltBotAllowedPlayers` (human-character authorisation) and enforce the universal Alt Bot [zero gear mutation contract](NT1-ALT-BOT-ZERO-GEAR-MUTATION-CONTRACT.md) **without a disabling configuration setting**.  
**Status:** Source review, regression protections and an **unreleased draft early-return for a proven exact-match Alt Bot**. **No different-build Apply/gear functionality implemented**, no in-game tests. PR #18 remains draft, unmerged, and uninstalled.

## Exact source evidence (pinned public stack)

Source SHAs:
- `mod-playerbots/azerothcore-wotlk` `b7f06a16ac7120b5abc2e8d3f96a94265a363224`
- `mod-playerbots/mod-playerbots` `037c01418b5d01506917a3db9b44fd56ac5f965c`
- `ZhengPeiRu21/mod-individual-progression` `283abe12774801e5671da746ea8bf535cc0252e0`

| Source | Observed behaviour | Why it matters |
|---|---|---|
| AzerothCore `src/server/game/Entities/Player/Player.cpp:3876-3968` | `resetTalents(bool)` calls `sScriptMgr->OnPlayerTalentsReset` **before** its early return; then pet removal, talent/aura/spell changes, Titan's Grip/Dual Wield removal and **`AutoUnequipOffhandIfNeed()` at line 3953** | Calling the public reset API is not guaranteed gear-inert, even for a caster. A zero-points early return does not prevent the reset hook. |
| Same file `:12743-12791` | `AutoUnequipOffhandIfNeed` may remove offhand and store it in inventory, or transfer it into **mail** if storage fails | Any temporary relocation violates the owner's invariant, even if the instance GUID survives. |
| Same file `:14281-14395` | `LearnTalent` invokes `OnPlayerCanLearnTalent` and has point, dependency and tier checks | A new talent engine must handle rejected ranks without invoking unsafe rollback operations. |
| Same file `:15674-15681` | Switching active specialisation also calls `AutoUnequipOffhandIfNeed` | Never use spec switching to dodge/reset requirements. |
| Naxxramas Core `src/Systems/BotTalentImport.cpp`: `ApplyValidated` | Calls `CheckApplyReadiness`, then **`resetTalents(true)`**, then `LearnValidated`, then another **`resetTalents(true)`** if learning fails; persists the profile on successful Alt Bot Apply | Current best-effort recovery is not a gear/pet-transaction guarantee. |
| Naxxramas Core `src/Systems/BotTalentCompletion.cpp:720-763` | `OnPlayerTalentsReset` sees `ImportScope` and clears pending talent intents, without direct gear handling | One hook is understood, but this is not a complete inventory of the owner's installed hooks/modules. |
| Pinned Playerbots `src/Bot/PlayerbotAI.cpp:6303-6311` | Equipment helper can call `AutoUnequipOffhandIfNeed(true)` | Not necessarily called by NT1, but background/equipment actions must not be confused with a safe talent-operation guarantee. |
| Pinned Playerbots `src/Bot/Factory/PlayerbotFactory.cpp:2592-2602` | Factory explicitly equips an item and then calls offhand relocation | Do not invoke the factory as part of an Alt Bot talent-change path. |
| Pinned Playerbots `src/Ai/Base/Actions/TrainerAction.cpp:515-525` | Trainer item path can destroy a paired-ring/trinket item, equip a new item and invoke offhand relocation | Explicitly disallow talent operations from triggering gear/trainer automation. |

**Specific Arndor result:** Template 11923 main-hand + 22319 held-in-offhand had no *immediate ordinary relocation condition* in earlier read-only inspection, but **that is not sufficient** to clear the full reset, hook, asynchronous AI and recovery path. The current refusal is correct.

## Phase 1 — Lock in the agreed policy (this draft work)

- Preserve `AccessMode`, the **human-character** `AltBotAllowedPlayers` security allowlist and current IP-era/ownership preflight.
- Preserve the existing occupied offhand **and** active pet block until replaced by source-proven protections. Current C++ still has two resets; do not claim it is zero-gear-mutation compliant.
- Add a CI regression test that fails if the allowlist, conservative guard or no-gear-command discipline is casually removed.
- Keep equipment/role changes out of MultiBot talent actions, including Shadow-to-Holy or DPS-to-Tank transitions.

## Phase 2 — Safely avoid unnecessary resets (draft C++ implementation, not deployed)

A small **unreleased exact-match no-op path** now uses the existing full active-spec comparator (`EXACT`, `DIFFERENT`, `CANNOT VERIFY`). A caller requesting a no-op is accepted only after the usual human/allowlist/control/era/full point budget, old-build snapshot, character database table and read-only mode checks. Unlike the still-destructive different-build path, it returns **before ImportScope, reset, LearnTalent, SaveToDB or profile persistence**. This has not yet been tested in the owner's server, and does **not** address different-build imports.

Requirements for any future no-op Apply:
1. The same issuer security, AccessMode 1/2, Alt Bot allowlist, owner/master checks, bot identity, level, class, IP era, legal full point budget and out-of-combat checks apply. Never let a diagnostic `EXACT` bypass these. The exact path still requires the read-only database table and original snapshot check, retaining fail-closed semantics.
2. Recheck the live rank map atomically with the decision. An indeterminate result is **not** success.
3. No `resetTalents`, `LearnTalent`, `SaveToDB`, database intent insert, equip API, packet implying a changed build, bot AI factory, or spec switch.
4. Return a distinctive `ALREADY MATCHES / NO CHANGES MADE` result. The addon must not treat this as a destructive Apply or role-gear request.
5. Test the no-op with an offhand and an active pet **only on disposable bots** after an isolated restore point, once owner permission is given. Until then, no in-game Apply attempts.

This limited improvement does **not** enable switching a bot whose talents differ, including Arndor if his current talent ranks differ from the desired Holy build.

## Phase 3 — Different-build engine: no gear side effects, including failure

**Engineering decision gate**: Directly invoking the pinned `Player::resetTalents(true)` cannot be presented as a universal no-gear-mutation guarantee, because it invokes the reset hook and offhand relocation. Adding a configuration switch, a post-hoc gear snapshot or a Priest/held-in-offhand exception does not solve this.

Before implementing or enabling a different-build Apply path:
1. Audit **all** linked `OnPlayerTalentsReset`, `OnPlayerCanLearnTalent`, equipment/inventory hooks and asynchronous Playerbots actions for the exact owner's installed source tree, not only the pinned example.
2. First investigate a safe implementation **confined to mod-naxxramas-core**. Determine whether the upstream core lacks the necessary gear-inert talent-change primitive. If a core-level patch is truly required, **STOP** and explain that dependency to the owner for a separate decision; do not silently modify, patch, or replace AzerothCore or another module to make this work.
3. Define the transaction/failure model for talent ranks, dependent spells, auras, action bars, dual wield/Titan's Grip, glyphs, pet state, queued actions and persistence. **No equipment move is ever permitted**, even temporarily or in a rollback attempt.
4. Prefer **fail before any mutation** where the entire path cannot be demonstrated safe. No "unequip before reset, put it back later"; no GUID recreation.
5. Identify races with other Playerbots equipment automation: a source-verified exclusion mechanism or safe rejection is needed if NT1 would cause a queued action. Do not claim control of unrelated player-initiated equipment actions.
6. Keep pet-preservation a separate barrier: enforcing no item moves does not prove no pet loss.
7. Build a verified fault-injection matrix: rank-learn rejection, hook rejection, one/two specs, full bags, incompatible two-hand/offhand/talent-granted abilities, active pet, login/logout, reset interruption, failed rollback and DB write error.
8. Require isolated restored `acore_characters` test data. Compare **original `item_instance.guid`**, equipped slots, owner, stack, enchantments and mail attachments, before and after each test. This is **evidence**, never the mechanism enforcing safety.
9. Run all source/unit gates and a **full linked Worldserver** build, then owner-approved disposable-bot tests with a proven restore. Do not run destructive scenarios on Arndor, Rakari or other earned characters.

## Release gates and communication

- The zero-gear requirement itself was approved by the owner on 14 October 2026, **not** any destructive implementation or deployment.
- PR #18 is **draft**. No merging or installation until specific owner approval, source compatibility review and backups.
- A CI PASS for the current read-only diagnostics is **not** approval to lift the offhand restriction.
- `AltBotAllowedPlayers` is retained and **does not provide a bypass** around equipment safety.
- No gear safety override/config flag will be introduced.
- A final **copy-and-paste Naxxramas Core → N-MultiBot-Chatless owner handover** is mandatory after the actual server behaviour has been verified and released. The addon must continue obeying server Apply refusals.

**Next engineering gate:** run full regression tests, pinned real-header compilation and full Worldserver link of the draft exact-match no-op, then review in-game acceptance on an owner-approved disposable test bot with a verified characters DB restoration. It must never be advertised as fixing different-build Arndor until the gear-inert engine and disposable runtime tests pass.
