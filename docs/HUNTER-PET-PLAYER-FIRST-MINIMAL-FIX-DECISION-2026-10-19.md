# Player-controlled Hunter Pet Autocast — minimum safe fix decision

**19 October 2026 · RESEARCH / REVIEW ONLY · not a runtime fix.**

**Owner scope correction:** This feature primarily concerns a **real player controlling their own Hunter pet**, not Hunter Playerbots. Playerbots have their own AI autocast policy and must remain untouched. The previous bot-producer/AI-precedence research remains available as historical work; it is **NOT a gate to the player's first release**. Keep all changes in Naxxramas Core unless the owner separately authorizes a *specific* upstream change.

## Findings from exact pinned source — not a live-bug diagnosis

| Layer | Exact pinned source evidence | Consequence |
| --- | --- | --- |
| AzerothCore pet native storage | `Pet::_LoadSpells` reads the `active` field, `Pet::_SaveSpells` writes spell and `active`; character DB prepared statements operate on **`pet_spell`** (not `character_pet_spell`) | Native settings can already survive reloads if the saved spell record survives |
| Pet autocast toggle | `Pet::ToggleAutocast` maintains native `ACT_ENABLED`/`ACT_DISABLED` and marks an existing spell changed | No new database table is justified until we demonstrate a scenario not covered by the native state |
| Native rank replacement | `Pet::addSpell` explicitly copies `petSpell.active` when replacing a *known lower rank* with a higher rank via the ordinary upgrade path | A simple rank upgrade need **not** lose the state |
| **Individual Progression** reconciliation | `checkHunterPetSpells` excludes configured bot accounts, selects permitted spell ID from the player's IP dummy training spells, then **unlearns non-retained IDs before learning missing keepId** | This particular remove-before-add route can erase the old per-spell state and teach a new autocastable spell with **default OFF** |
| Pet load and IP event | Core loads native spell rows in an **asynchronous pet load callback after AddToWorld**. IP schedules a delayed pet event with ten loading retries and later calls the void `checkHunterPetSpells` | A PetScript AddToWorld observer cannot safely assume native spell preferences were loaded; a later scheduled timer cannot prove IP reconciliation completed |
| PetScript hooks | Pinned `PetScript.h` provides AddToWorld/InitStats/talent gates, **no before-unlearn, after-learn or post-IP reconciliation completion callback** | Current available module hooks do not provide an authoritative atomic preference handoff across the IP remove/relearn operation |

**This is a source-backed candidate cause, not an in-game verified root cause.** It cannot explain a lost toggle when the same rank remained known and no spell was removed; that case must be investigated separately.

Pinned sources: [core Pet.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp), [core CharacterDatabase.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/database/Database/Implementation/CharacterDatabase.cpp), [core PetScript.h](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Scripting/ScriptDefines/PetScript.h), [IP IndividualProgressionSpells.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp).

## Repeat-summon source sequence: another testable mechanism

The exact pinned AzerothCore `Pet::LoadPetFromDB` async callback first calls
`_LoadSpells` (reloading saved `pet_spell.active`), then
`InitLevelupSpellsForLevel`. That routine calls `learnSpell` for eligible
family-level and template-default spells. A **native direct higher-rank**
`addSpell` can carry the previously known rank's active flag, but the new
spell book may differ from what Individual Progression currently permits.

Individual Progression separately schedules a one-pet delayed event from
pet level initialization/AddToWorld (with loading retries) and then calls
`checkHunterPetSpells`, which may **unlearn an unwanted rank first and
relearn the legal keepId**. Thus repeated summoning can, in principle,
recreate an old-rank/new-rank cycle: native saved spell ON -> native
level-based initialization -> IP legal-rank pruning -> new spell defaults OFF.
Whether a specific pet hits this sequence depends on its actual family,
saved known ranks, IP dummy spells, progression stage and current core
level-up spell set. **No deployed pet trace yet confirms the hypothesis.**

This makes the initial reproduction especially important:
- Inspect **the same stored PetNumber** and saved spell ID/active values
  after a normal save, then after a summon **without advancing IP training**.
- Compare current in-memory known legal rank with the native and IP expected
  ranks; do not assume every summon itself changed the rank.
- Observe both a manually ON and manually OFF ability; an OFF default after
  relearning is ambiguous and must not be treated as proof the user turned OFF.
- Preserve semantics for all eligible abilities (not just Lightning Breath)
  and fail closed for any missing/forbidden spell, stable swap or newly tamed
  pet.

The pinned source-check guard additionally verifies this **load ->
level-based initialization -> delayed IP reconcile** sequence. This is
stronger static evidence for a potential repeat-summon reset, still **not**
a real-player reproduction or authorization to patch IP.

## Minimal correction candidates (NOT implemented)

**Option A — module-only, first choice if a reliable interception point exists.** Capture the *actual, previously loaded* native legal spell's `PetSpell.active` for a verified real human Hunter's **same current pet** before IP removes it. Transfer only that explicit state to the **correct newly legal rank after IP finishes**. Preserve ON **and OFF**, never generate a spell, never force-enable absent/untrained abilities, and never infer user intent from the default disabled state. **Blocking problem:** the pinned public PetScript/PlayerScript surfaces lack a reliable before-and-after IP reconciliation callback. Pet AddToWorld can run before async `_LoadSpells`, and a scheduled delay/poll does not prove IP completed. Do not implement a fragile timer or fake a module-only fix.

**Option B — narrowly scoped IP change, requiring SEPARATE express owner approval.** Within IP's existing per-family `reconcile` path, capture the previous native active state **while the old legal spell still exists**, then perform its existing entitlement-preserving unlearn/relearn sequence, and only if a new legal autocastable keep-rank is actually known, apply the captured **ON or OFF** to that retained rank using existing native `Pet::ToggleAutocast`. This reuses native `pet_spell` storage, avoids a second preference schema, and keeps IP as the source of legal ranks. It must be atomic with the same pet and same call: no deferred lookup of `player->GetPet()` to a different pet, no Playerbots changes, and no inferred success after a void return.

### Proposed IP review pseudocode — *not compiled or submitted upstream*

```text
guard: real Hunter player / not configured bot / valid current hunter pet
for each existing IP-reconciled legal pet ability family:
    inspect currently known member ranks BEFORE IP unlearn
    if exactly one previously known, native-autocastable rank:
        capture its ACT_ENABLED or ACT_DISABLED as a candidate
    else:
        no candidate (do not guess preference)
    run the EXISTING legitimate IP wipe/keep reconciliation unchanged
    if an actual replacement happened AND candidate exists AND
       the same pet still owns the new, current legal/autocastable keepId:
        use native ToggleAutocast(keepId, candidate state)
        verify native spell record/autospell/action-bar consistency
    otherwise:
        no toggle; leave IP/native behavior unchanged
```

**Important caveats before any real implementation:** distinguish default disabled from deliberate OFF; native rank upgrade semantics may already preserve state, so avoid rewriting if the valid rank never changed. Do not enable untrained or era-illegal ranks, misinterpret species/family spells, restore a deleted pet's old choices, overwrite stable-swapped pets, or touch Playerbots. Review whether matching the full rank-family is sufficient and whether the actionbar must be refreshed through existing core methods. The proposal is intentionally not a ready-to-paste patch because the installed versions and actual failing sequence are not yet verified.

## Focused, staged human-player test — after explicit approval only

Do **not** modify the owner's live characters database to perform this test. Before installation or a real test, back up the exact executable/config/modules and **full characters DB**, and verify a disposable restore.

1. On a staging copy of a **real player's Hunter**, record core/IP/module Git SHAs, IP enabled/VanillaHunterPets flag, actual legal training stage, pet number, family and the current `pet_spell` rows. Keep all personal/realm names and configuration private.
2. Set one eligible autocast ability **ON**, and a different eligible ability **OFF** manually. Compare in-game UI and the native active state (ACT_ENABLED/ACT_DISABLED) after a normal save.
3. Dismiss/re-summon and log out/in **without changing IP rank entitlement**. If an already known legal rank changes state, the cause cannot be attributed to the rank-removal mechanism alone.
4. In a separate, restore-testable staging scenario **legitimately changing a taught rank**, compare saved spell ID/active **before IP** and visible state **after IP** for the *same pet*. Native higher-rank upgrade versus IP replacement are different paths.
5. Repeat both ON and OFF cases for more than one autocast-capable family. Stable swap/new pet must never inherit the previous pet's setting. Check death/revive and restart once the basic scenario works.
6. Use the module's existing **OFF-by-default read-only Hunter pet audit** only with explicit separate authorization; its sampled post-event view **does not** prove the origin of unlearn/relearn. Correlate observations with manually recorded legal spell IDs and active state.

**Exit criteria:** Identify the actual reset point on a real player's pet, confirm the smallest safe intervention with correct hook/ordering, then write source tests and compile the real patched code on the exact intended revisions. No live or player-facing fix, new SQL, upstream patch, Worldserver restart, or released feature is claimed by this review.

## Out of scope, intentionally deferred

Playerbots master chat command origin, Playerbot AI precedence and automated bot pet toggles; previous test-only bridge contracts; and all unrelated Golemagg, Hunter Ammunition, NT1, Quest Loot, and Eastern Plaguelands projects. Their separate master issue #28 milestones stay intact.
