# P1 Warlock Ritual of Summoning — second-stage portal repair pilot

**30 October 2026 • Source-level DRAFT only. Default OFF. No owner server/DB/DBC/client changes.**

Original owner reproduction: [P1 issue #84](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/84), 23 October 2026. Warlock's first green Ritual of Summoning portal (spell 698, associated GO 194108 type 18) appeared; grouped helpers completed it; **second** Summoning Portal appeared; attempting to use that second portal yielded NaxxramasCore's Vanilla Meeting Stone rejection. Summoning **FAILED**. The owner also supplied read-only `acore_world.gameobject_template` evidence that GO 194097 is a Summoning Portal of type 23. The actual clicked second-stage GO entry was not captured as a live log.

## Confirmed source cause

Original main `src/Systems/MeetingStoneProgression.cpp` checks **GO type 23 only**, so it can intercept GO 194097 as a Vanilla dungeon Meeting Stone. It lacks a GO-entry exception. The historical owner-reported core pin **`mod-playerbots/azerothcore-wotlk@b7f06a16ac7120b5abc2e8d3f96a94265a363224`** has original `src/server/game/Entities/GameObject/GameObject.cpp` blob `c006c59145b3bdd14e7d3f513628bc0a29653835`, which unconditionally selects **23598** in its GO type-23 handler, even for 194097. Existing WotLK TrinityCore 3.3.5 core chooses **61994** for GO194097 (second-stage ritual), separate from a normal dungeon Meeting Stone. Core `SpellEffects::EffectTransmitted` blob `306a7a44e93a9f64b56e7749432762043d292ec0` stores spell ID on newly created GO (including spell61993 -> GO194097 from WotLK spell reference). **This does not establish actual client/DB/SpellInfo runtime compatibility on owner's host.**

Our previously successful first-build [DRAFT #247](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/247) full Worldserver link (run 40922173319) compiled the **unfixed** main behaviour; it was not a Warlock gameplay pass. Existing source-only guard test did not consider type-23 Warlock second-stage, hence it incorrectly suggested ordinary ritual exclusion was sufficient.

## Scoped corrective DRAFT — no core patch

Changes on one isolated source-only pilot DRAFT branched from immutable protected Mod main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`:

1. Add `NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled = 0` to distributed module config. **OFF by default.** Do not silently enable or change owner-installed .conf.
2. Extend the existing `AllGameObjectScript::CanGameObjectGossipHello` only for GO type **23**, entry **194097**, and explicitly enabled pilot. Demand `go->GetOwnerGUID()` (summoned/owned) and `go->GetSpellId() == 61993`; malformed/static fake portals are consumed without a spell. The ordinary first ritual GO type 18 is untouched.
3. Use **synchronous** ObjectAccessor target lookup (as in original core type-23 branch), demand a non-self selected Player target in same raid and preserve native user and target minimum-level checks. If invalid, consume without casting (do not fall through to generic spell 23598). No raw Player pointer is retained across callbacks or queued work.
4. Require registered SpellInfo **61994** then `player->CastSpell(player, 61994, false)` (normal, not fully triggered). Returning true prevents an additional wrong native type-23 cast. Normal dungeon Meeting Stones, regardless of Vanilla/TBC and enabled/disabled ClassicMode, continue the exact original path.
5. This is a **pilot** because `CanGameObjectGossipHello` runs before the native GO cooldown and mounted-behaviour branch. Exact equivalence for cooldown, duplicate clicks, channeling, reagent/class conditions and GO194097 SpellInfo creation **must be proved** before any release claim. The new self-target refusal is stricter than the pinned core's raw same-raid check and aligns with the 3.3.5 TrinityCore branch; real acceptance must verify it does not break legitimate uses.

**Explicit limitations:** The feature doesn't grant summoning without group/target/level requirements. There is no blanket Meeting Stone unlock, GO-type mutation, core change, SQL/DBC edit, hacky template conversion, global race-gating change, or owner-host installation.

## Required tests before offering owner a Warlock gameplay pilot

- Existing `test_meeting_stone_ritual_isolation.py` should continue to prove original Vanilla/IP and loader protections for ordinary Meeting Stones, with the special OFF-by-default pilot permitted.
- New `test_p1_warlock_second_stage_pilot.py` source contract has 15 deliberate negative mutations and a synthetic decision table: only type23 + GO194097 + enabled + valid spawned/owned origin, target, same raid, both minlevels, registered SpellInfo results in **one** nontriggered 61994 cast. All other GOs retain original path. Test **does not execute real C++ or prove an actual portal works**.
- Native source compilation: compile the actual modified `MeetingStoneProgression.cpp` against the historically owner-reported pinned AzerothCore/Playerbots/IP headers using real generated `compile_commands.json`. A full exact-HEAD Worldserver compile and link is required before promoting this DRAFT to a candidate.
- Independent CS02/CS03 review requested, not assumed. Check hook precedence, class restriction, spell61994 target/channel, GO cooldown and repeated clicks. Owner must separately approve any actual first Warlock test after dated backups and successful restoration test.

## Owner gameplay acceptance — AFTER review/approval

With a disposable Vanilla-stage Warlock and two legitimate group helpers, observe each step:

| Step | Expected |
| --- | --- |
| Cast 698 | First green ritual circle appears |
| Two eligible helpers | Ritual completes; second portal appears |
| Inspect spawned second GO ID/type | Expected 194097/type23 created by 61993; capture if possible read-only |
| Valid eligible selected target and helper click | Second portal casts 61994 and leads to successful target summon |
| Invalid target, self, non-group player, underlevel | No unauthorized summon or wrong spell |
| Repeated rapid clicks | No duplicate incorrect portal or uncontrolled cast |
| Normal dungeon Meeting Stone with Vanilla progression and ClassicMode ON | Still blocked with intended message |
| Same dungeon stone with TBC/WotLK progression | Native accepted when group/level requirements satisfied |
| Pilot OFF | Identical original main routing; no new effect |

The **first** smoke configuration from #247 keeps both this pilot and ClassicMode OFF and is **NOT** evidence of these Vanilla-specific tests.

**Safety holds:** R7 HonorOverflow race release HOLD and owner economic choices unselected; F14 Blood Elf/Draenei concealment OFF/unmerged; K1 and N-Core NoWrite relay OFF, D18 pet A→B HARD NO-GO; `MapUpdate.Threads=8` MUST remain 8. No merge, deploy, owner server/Worldserver restart, DB/SQL/DBC/client or core/IP/Playerbots/N-Core changes. Current P1 owner gameplay acceptance remains **FAILED** until actually retested.
