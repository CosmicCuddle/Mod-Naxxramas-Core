# Three mature feature integration — source-only delivery candidate

**19 October 2026 — DRAFT, UNMERGED, default-OFF, NO RELEASE APPROVAL.**

This is a dedicated **completion-first** candidate, separated from [combined PR #33](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/33) and [PR #41](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/41). It aims to establish whether **three individually S4-built features** also compile and link together, without including the unfinished Golemagg movement fix, Hunter Pet autocast persistence or NT1 different-build talent change.

| Workstream | Exact original source head | Independent full Worldserver |
| --- | --- | --- |
| Hunter Ammo | [PR #32](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/32) `84a3da6a3a2192dd56c93a4e9cfd441de7cfe518` | [18/18 source-specific CI](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39269109936) |
| Quest Loot | [PR #25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/25) `e3e1bf339c8b1aba07ab065d50dbcc3fafbf0e51` | [18/18 source-specific CI](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39270992658) |
| EP full-capture announcements | [PR #24](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/24) `8946f8f3bdbb980393922b9226a3cbe211609308` | [18/18 source-specific CI](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39269122346) |

### Source assembly rules

- Base on exact original `main` commit `1f5f317c3991bbac66cc92a7112bbde3c929c232`, preserving existing module features.
- Copy original feature changed-file Git blobs unchanged **except** `conf/mod_naxxramas_core.conf.dist`, whose Quest Loot and Hunter Ammo **append-only** chunks are composed after confirming both branches share the exact original base config. Preserve each separate disabled setting once.
- Original three feature-specific expensive Actions workflows remain with their individual PRs; this integration uses **one** new pinned combined workflow and runs all three source test suites, actual three module C++ translation units, a full Worldserver link and same-binary symbol/registration checks. A started job is **not** S4 until the entire run and binary checks are confirmed success.
- EP announcements change the existing already-merged tower lock source; actual world `outdoorpvp_template(TypeId=6)` binding still must be explicitly verified before gameplay, and is not changed here.

### S5–S7 release blockers

- Installed AzerothCore/IP/Playerbots/Naxx revisions, local edits, effective config and actual running binary unknown.
- Mandatory restorable binary/config/**full characters DB** backups and relevant EP world SQL/state rollback not tested.
- Approved Hunter Ammo inventory/edge-case, Quest Loot QL-01–QL-15 and EP four-tower/two-faction client acceptance have **not** been run.
- This integrated draft does **not** grant feature inclusion, merge, install, Worldserver restart, item addition, loot protection, zone announcements or release approval. Both inventory-altering features stay **OFF by default** and the EP handler remains SQL-binding gated.
- Source-level combined success is not proof of in-game behavior, human Hunter pet preference persistence or Golemagg movement repair.

Track all decisions in the **single master [issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28)**, not a competing checklist. The release manifest in [PR #39](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/39) keeps all inclusion and owner approval flags false until separately authorised.
