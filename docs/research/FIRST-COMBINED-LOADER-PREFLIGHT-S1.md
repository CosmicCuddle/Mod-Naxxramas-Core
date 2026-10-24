# First combined build — collision-safe loader/config source preflight (S1 only)

**Review-only source/test preparation, NOT an integration and NOT a first in-game candidate.** No production C++, config or loader file changes in this PR; it adds reusable checks and synthetic negative tests for a future approved integration stage. The authoritative master work remains [Issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), with team coordination in [Issue #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48).

## Source-proven collisions

Exact GitHub source read: main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` and four separately main-based draft refs:

| Draft | Reviewed head | Additional function declared and registered |
|---|---|---|
| #120 P0/B10 | `599d1cbb211e6f108a2a6ff9fec78242ffe7a37c` | `AddBotGolemaggReachGuardScripts` |
| #125 F12 Scarlet | `04367fb0f21da75f47af2bb3519c8a023df3b7eb` | `AddScarletMonasteryExitScripts` |
| #127 F13 Atiesh | `d7fdfc44cd47a75b098818f58adeff82b0fe1373` | `AddAtieshKarazhanPortalScripts` |
| #130 A02 Hunter | `d3c5a1d57268cc45fd3f1b1589667ebd97dfac17` | `AddHunterPetAutocastScripts` |

Every loader contains all **29 historical main declarations and 29 historical registrations**, plus its own one new symbol. Copying any one whole loader to combine the drafts loses the others. A04 candidate #129 has **no added loader symbol** and is **not accepted** as the reported human quest-loot functional fix.

## What the tests enforce

The new `tests/test_first_combined_loader_preflight_s1.py` is deliberately a **model**, with 11 tests. It checks all 29 baseline declarations/registrations, the four required additions exactly once in declaration and call, detects duplicate/missing functions and dropped historical Golemagg auditing, and verifies no duplicate or accidentally enabled selected config keys. Config requirements are original legacy quest-loot OFF, GFPP one-shot OFF, and Golemagg reach guard, Scarlet, Atiesh, Hunter optional switches independently OFF. These are synthetic witnesses, not a combined implementation.

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
