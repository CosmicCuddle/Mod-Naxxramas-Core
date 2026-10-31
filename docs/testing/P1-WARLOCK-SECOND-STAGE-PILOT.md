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

Use **four distinct grouped characters total**, never two or three: a level-eligible **Vanilla Warlock (W)**, two nearby helper players **A** and **B**, and a separate **distant eligible raid member T** who will accept the summon. For deterministic results, all four must be legitimate distinct characters in the same group/raid, not an alternate use of the same player as a second helper. Only perform this in an owner-approved, backed-up staging session after the actual source/binary and config have been verified. The following is an **acceptance specification, not a performed in-game test**.

| Checkpoint | Exact action and observation | Pass / fail meaning |
| --- | --- | --- |
| 1 — first ritual | W selects or prepares a legitimate distant T and casts **698**. W's first green GO **194108, type18**, is present. Two distinct nearby helpers **A and B** complete the first-stage channel with W. | First ritual succeeds and **GO194097/type23**, created by **61993**, appears. Merely spawning GO194097 is NOT a successful remote summon. |
| 2 — second portal | Helper **A** (not W or T) explicitly selects distant **T** as current target, then clicks GO **194097** while GO194097 has a valid owner GUID and creation spell 61993. Preserve T as A's target through the next stage; do not assume selection persists without observing it. | The opt-in hook attempts **normal nontriggered 61994**, never native type23 **23598**. Check that spell61994 is actually cast/channelled, not only requested. This code path has not been owner-tested. |
| 3 — final ritual | Check whether spell61994 creates final GO **179944, type18**, owned by the second portal activator **A**. Nearby helper **B** (a *different* character from A and not distant target T) completes the last required participation/channel for that GO. | Final GO's native type18 completion is expected to invoke **7720** and issue T's summon request. The appearance of GO179944 alone is still NOT proof. |
| 4 — distant completion | Distant target **T** sees a real summon confirmation, accepts, and actually appears at the Warlock group's intended location. Record each outcome separately, including who was selected and which player arrived. | **Only actual target acceptance + arrival** closes Warlock P1 gameplay acceptance. A cast, GO creation, channel animation or summon prompt alone is not sufficient. |
| Negative/control cases | With pilot ON, try invalid/self/out-of-group or underlevel T, wrong origin/static GO194097, and repeated rapid clicks. With pilot OFF confirm exact previous behavior. Test a real ordinary dungeon Meeting Stone in Vanilla with ClassicMode ON and then an eligible TBC/WotLK control. | No unearned target summon, no duplicate cast, no reclassification of genuine dungeon Meeting Stones, and no change to the first GO194108 path. The pilot may run before native GO cooldown/mounted checks: these remain mandatory review points. |

The **first** smoke configuration from #247 keeps both this pilot and ClassicMode OFF and is **NOT** evidence of these Vanilla-specific tests.

**Safety holds:** R7 HonorOverflow race release HOLD and owner economic choices unselected; F14 Blood Elf/Draenei concealment OFF/unmerged; K1 and N-Core NoWrite relay OFF, D18 pet A→B HARD NO-GO; `MapUpdate.Threads=8` MUST remain 8. No merge, deploy, owner server/Worldserver restart, DB/SQL/DBC/client or core/IP/Playerbots/N-Core changes. Current P1 owner gameplay acceptance remains **FAILED** until actually retested.


**Separate same-binary historic compile milestone (not a gameplay pass):** [Combined full Worldserver CI 41138075456](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41138075456) completed successfully with this P1 C++ source, the current IP grouping draft, protected Hunter ammo, and quest-loot/EP module sources. Full native link and expected Warlock GO handler/vtable are present in the disposable linked binary. Owner's newer Core/Playerbots source and effective installed version are still not fingerprinted; normal pilot remains **OFF**. Neither a GitHub link nor this revised document authorizes a production test or deployment.
