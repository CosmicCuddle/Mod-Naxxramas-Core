# First combined build — collision-safe loader/config source preflight (S1 only)

**Review-only source/test preparation, NOT an integration and NOT a first in-game candidate.** No production C++, config or loader file changes in this PR; it adds reusable checks and synthetic negative tests for a future approved integration stage. The authoritative master work remains [Issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), with team coordination in [Issue #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48).

## Source-proven collisions

Exact GitHub source read: main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` and four separately main-based draft refs:

| Draft | Reviewed head | Additional function declared and registered |
|---|---|---|
| #120 P0/B10 | `599d1cbb211e6f108a2a6ff9fec78242ffe7a37c` | `AddBotGolemaggReachGuardScripts` |
| #125 F12 Scarlet | `04367fb0f21da75f47af2bb3519c8a023df3b7eb` | `AddScarletMonasteryExitScripts` |
| #127 F13 Atiesh | `d7fdfc44cd47a75b098818f58adeff82b0fe1373` | `AddAtieshKarazhanPortalScripts` |
| #130 A02 Hunter | `c4e861029ad6ca5d9d8155f5ac9c10247f6f03da` | `AddHunterPetAutocastScripts` |

Every loader contains all **29 historical main declarations and 29 historical registrations**, plus its own one new symbol. Copying any one whole loader to combine the drafts loses the others. A04 candidate #129 has **no added loader symbol** and is **not accepted** as the reported human quest-loot functional fix.

## What the tests enforce

The new `tests/test_first_combined_loader_preflight_s1.py` is deliberately a **model**, now with **28 tests**. It checks all 29 baseline declarations/registrations, the four required additions exactly once in declaration and call, detects duplicate/missing functions and dropped historical Golemagg auditing, and verifies no duplicate or accidentally enabled selected config keys. Config requirements are original legacy quest-loot OFF, GFPP one-shot OFF, and Golemagg reach guard, Scarlet, Atiesh, Hunter optional switches independently OFF. These are synthetic witnesses, not a combined implementation.

**New collision check:** the future real-tree mode now also requires the actual four production C++ translation units, not just declarations in the common loader. The separately reviewed exact-head source files are `src/Systems/BotGolemaggReachGuard.cpp` (#120), `src/Systems/ScarletMonasteryExits.cpp` (#125), `src/Systems/AtieshKarazhanPortal.cpp` (#127) and `src/Systems/HunterPetAutocast.cpp` (#130). Each must contain precisely one matching `void Add...Scripts()` definition. Three additional synthetic tests catch missing files or a wrong function body when all four loader entries are still present. This is still *not* CMake or linker evidence: the integrated build must compile and link those functions on its own exact SHA.

Run source-model regression:

```bash
python3 -m unittest discover -s tests -p 'test_first_combined_loader_preflight_s1.py' -v
```

Once a **genuinely working, independently reviewed future union** is assembled on a *new review-only* branch, reuse this explicit live-source check there:

```bash
python3 tests/test_first_combined_loader_preflight_s1.py --check-tree
```

**The real-tree command intentionally FAILS today** on main and this S1 branch because the source/config has not been integrated. Do not mark that negative result as a development regression; this tool exists to gate the later actual union.

The GitHub Actions workflow **executes that expected failure on this isolated source-only PR** and checks both the exact exit code 1 and explicit diagnostic lines for the missing #120 Golemagg, #125 Scarlet, #127 Atiesh and #130 Hunter registrations. A Python crash or unrelated failure is not accepted as an expected negative. Its successful negative test means **the current incomplete tree is correctly rejected**, not that the eventual integrated tree has been verified.

## Hard limitations

Passing model tests **does not prove** the eventual real tree has all CMake translation units, loader symbols in a linked executable, active/unique runtime hooks, good threading under `MapUpdate.Threads=8`, correct GFPP 120 seconds, actual functional A02 Hunter or A04 human-friend quest-loot, no bot regression, or owner-specific Playerbots compatibility (`e88cc409` plus two uncommitted changes). Each needs its own exact-head source/native/full pinned Worldserver/independent review and later owner-approved backup/test gates.

Integration is **HOLD** until actual A04 and A02 fixes work, F12/F13 have exact-head builds/reviews, proper merger of full production files/config/CMake is done, and the owner approves safe backed-up staging. Never merge, install, publish binaries, enable flags, rewrite private SQL/DBC or touch owner core/IP/Playerbots/live server without express approval. This branch cannot substitute for one integrated downloadable first test build.

CS01 owns this test source (20% engineering and full PM); CS03 Claude owns 60% implementation, and CS02 Grok owns 20% engineering/Hunter and reciprocal reviews. All historical nonpriority Issue #28 work remains retained.


## Peer review corrections — both fixed at source-model level

CS03's [review #6388922172](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/131#issuecomment-6388922172) and CS02's [review #6389100498](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/131#issuecomment-6389100498) independently identified two real gaps in the previous S1 gate; these are **not** considered passed until the new exact-head CI is green:

1. **Idempotence on a preassembled loader:** Previously `setUpClass` appended the four draft declarations and calls *again* if the test was reused on an integrated source tree. The model now calls `strip_draft_loader_extras` to synthesize a historical baseline by removing only the four exact declaration/call lines. This is strictly **for synthetic test fixture construction**. `--check-tree` inspects the original unmodified checked-out loader and still rejects missing/duplicated symbols. A new regression builds a model union, strips it again and confirms it reassembles to the same list of declarations/registrations.
2. **Additional safety config:** required single default-OFF/empty keys now include `NaxxramasCore.ScarletExits.RouteDungeonFinderExits=0` (owner means **physical dungeon portals, NOT Dungeon Finder exits**), `NaxxramasCore.BotConsumables.CrossMapAuraSafety=0`, `NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug=0`, and `NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName=""` (no bot is affected until explicitly selected). The config checker rejects duplicate, missing or non-default assignments. Added synthetic negative tests for unexpected Dungeon Finder enablement and populated Golemagg bot name.

**GFPP preservation:** the eventual real-tree gate now additionally requires exactly one `NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};` in `src/Systems/BotRaidConsumables.cpp`. Prior main source uses **90 seconds**, while the accepted P0/B10 #120 source uses **120 seconds**; an integration which accidentally copies main's older consumable implementation must fail. The new model catches 90-second and duplicated 120-second witnesses. This is a source-literal assertion **only**, not a substitute for actual compiled/native/time-behavior tests.

**Developer integration feasibility only:** Claude privately assembled and compiled/linked a local five-way source union of main + #120 + #125 + #127 + #130 (reported [#6388942516](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/131#issuecomment-6388942516)). That work is unpushed and not the accepted first gameplay build: functional human Hunter A02 is still fail-closed, A04 loot incident unresolved, and #129/#132 were excluded. Its existence does not authorize a server binary/release.

**Current gate limitation:** These tests are reusable QA source contracts for a future proper integration, **not** a standalone working combined build. Individual component S3/S4 evidence, real pinned integration CMake/full Worldserver link, peer review, owner restorable backups and S5/S6 in-game proof all remain necessary.

## Conditionally included A04 experimental ordinary-loot flag (S1 gate)

Actual current heads [#129 `a571363`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/129) and [#132 `6d86ab3`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/132) both modify `src/Systems/QuestLootProtection.cpp` **independently** on a main-based branch; they are **not yet reconciled**, and **neither** is an accepted first-gameplay A04 fix. The former adds the separately default-OFF `NaxxramasCore.QuestLootProtection.RestrictHiddenOrdinarySlots = 0` and retains the old legacy global owner lookup; the latter substitutes a map-scoped lookup for the legacy branch and does not add the ordinary-slot switch. Applying both requires independent semantic/source review and full native/link evidence, never a blind whole-file copy.

The integration tree source checker therefore **does not require #129 to be present**, but if its production reader OR its config key has been included, then it insists both are present and exactly one config assignment remains `0`. Three new Python witness tests accept a draft without this unproven feature, accept the optional reader + OFF setting, and reject ON, duplicate and half-imported combinations. This is **source/config completeness and OFF-state protection only**, not evidence that either loot theory resolves the owner's real human-to-human pickup. Any actual future combined source must preserve normal WoW group-loot eligibility and be tested with an identified item/quest/source/turn example and the `MapUpdate.Threads=8` races.


## GFPP literal-spoof preflight — latest S1 amendment

Independent CS02 review identified that a naive `source.count("NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};")` could be fooled by a **comment mentioning 120 seconds** while the real timer reverted to 90 seconds. The source checker now strips simple C++ line comments, block comments, and quoted string/character literals before matching an actual `NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};` initializer. It additionally requires that **exactly one** numeric `NaxxramasOneShotTimer Timer{N * IN_MILLISECONDS};` initializer exists. Three new synthetic tests check a comment fake, a quoted-string fake, whitespace variation and duplicate live declarations. This is a source-level preflight, **not a full C++ preprocessor**; conditionally compiled alternatives and runtime behavior still demand independent native/linked review.

The preceding 25-method hosted success is tied to exact head `a865d81` (run `40140874392`). This new **28-method** amendment requires its own exact-head hosted success before acceptance. It remains source-only and **DO NOT MERGE**.

## Addon-assisted A02 preflight — additional default-OFF safety invariant

The owner chose an **addon-assisted** Hunter pet autocast solution. The original standalone writer #130 remains default-OFF and is not a working server message receiver. Module Editor's isolated #134 v1 addon receiver builds successfully but is **not functional/safe for integration** because its single per-player preference slot can be applied to a different stabled pet and its unsequenced clear/relog can replay old packets. Grok's #135 is a **v2 research proposal**, not yet the single accepted wire or compiled receiver. A successful synthetic loader union must not be mistaken for working A02.

The future real-tree source checker now **also requires exactly one**
`NaxxramasCore.HunterPetAutocast.AddonOptIn = 0` setting, separately from the original `RestoreHumanChain = 0` guard. New positive and missing/duplicate/accidentally ON negative unittest witnesses protect that key. The hosted negative-tree witness also requires an explicit absent AddonOptIn diagnostic on this main-based test branch. This cannot prove that C++ code checks both switches, excludes active SelfBots, authenticates addon messages, handles PetNumber/epoch/restarts safely or restores valid ON/OFF states after IP. Those remain release-blocking **functional** gates requiring a revised canonical protocol, actual integration and owner-approved tests.

Source for the as-yet-unsafe option and its OFF default: [PR #134](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/134), exact `2ab30306c884d3af1c92bb5ad7042648b90fd162`. Unfinalised v2 proposal: [PR #135](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/135), exact reviewed `50f0500eb7b1f682d34cf6fcd0542556cf8363a1`, where [CS01 requested a process-restart replay witness](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/135#issuecomment-6396037062). The 28-method suite is source-model only; it must pass exact-head hosted CI before being marked green. No production runtime file or config was changed by #131.
