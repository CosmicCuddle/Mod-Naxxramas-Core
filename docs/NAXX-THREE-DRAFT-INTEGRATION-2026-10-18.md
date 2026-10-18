# Naxxramas Core — Three-Draft Source Integration (18 October 2026)

**This is a temporary build-validation branch, not a release or an authorised merge.**

Sources are copied by exact Git blob SHA into a tree whose sole ancestor is
`main` `1f5f317c3991bbac66cc92a7112bbde3c929c232`:

| Independent draft | Exact source SHA | Scope |
| --- | --- | --- |
| [Golemagg #30](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/30) | `ff77debc454ef9d0d8e44939e52127cf0250d92d` | Read-only exact one-bot bounded MC action trace; **no movement fix** |
| [Hunter Ammo #32](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/32) | `082a03d773b0b96a8f2beaefe6fb0433b5f138e3` | Controlled Altbot arrow/bullet inventory top-up, **OFF by default**; no auto-equip |
| [Hunter Pet Autocast #26](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/26) | `1b8b1871fae7b5120f2c59ae3e7425111173f215` | Read-only pet audit and standalone contract models, **NOT autocast preference restoration** |

## Exact merge method, not a Git merge to main

Source compatibility work only. From the exact three Git tree comparisons,
74 non-conflicting changed/added files were copied by their existing exact
blob hashes. The only overlapping files are:

1. `conf/mod_naxxramas_core.conf.dist`: each draft appends its own standalone
   configuration block to the *same identical* `main` file. Integrated text
   keeps all three complete appended sections, never replacing another's keys.
2. `src/NaxxramasCore_loader.cpp`: Golemagg and Hunter pet drafts independently
   register one read-only diagnostic. Both declarations and calls were
   combined **once**; existing module registration calls remain intact.

Independent `src/Systems/` files do **not** overlap. The resulting
integration commit must never be cherry-picked to a feature PR or `main`
without a separate review and owner's explicit approval.

## Combined-source acceptance gates

- [x] No deletion/rename, no nontrivial file overlap, source revisions fixed.
- [x] Golemagg `Enabled=0` and blank `AllowedBotName` fail-closed.
- [x] Hunter Ammo `Enabled=0` and `AllowSelectedNonVendor=0` fail-closed.
- [x] Hunter Pet Autocast `AuditEnabled=0` fail-closed.
- [x] Both diagnostic loader declarations and calls occur exactly once.
- [ ] Exact-head GitHub Actions source checks for **all three feature families**.
- [ ] Standalone pure C++ policy/handoff tests for all three features in one job.
- [ ] Full Worldserver compilation **once** from the combined pinned
  AzerothCore `a66f1bd`, Playerbots `037c014`, IP `4ff4b5f` and Naxx
  integration head, no Worldserver launch.
- [ ] Final **same binary** must contain defined `TopUpHunterAmmo` and both
  diagnostic registration markers. Merely linking a library is insufficient.
- [ ] Confirm all existing NT1 and other module contracts remain passing.
- [ ] Confirm actual installed source SHAs, feature flags and progression
  restrictions; **not verified by this GitHub source build**.
- [ ] Separately approved, verified-restorable Worldserver/config/characters
  DB backup and staged user-authorised feature-specific gameplay tests.
- [ ] Separate explicit owner approval for merging any source, release,
  server install/restart, enabling flags, SQL/DBC edits or inventory mutation.

## CI cost and scope

The integration-specific `.github/workflows/naxx-three-draft-integration.yml`
performs one comprehensive pinned full Worldserver build plus source and
C++ models for all three draft features. The three **isolated pinned full-build
workflows** are conditionally skipped only when the PR source branch begins
`integration/`; they remain unchanged for their own PRs. This prevents
redundantly compiling an identical 1,885-object Worldserver three extra times.
Other source-safety and NT1 workflows may still run independently.

**Important:** Even if the combined C++/full-link workflow passes, it proves
only source/build compatibility on pinned forks, *not* Golemagg gameplay,
Hunter ammunition inventory behavior, or Hunter pet autocast persistence.

Tracking: [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28)
and the independent feature issues [#27](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/27),
[#31](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/31).
