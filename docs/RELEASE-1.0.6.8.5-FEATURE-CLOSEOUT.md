# Version 1.0.6.8.5 — module-wide feature closeout and release gate

**19 October 2026 · DRAFT REVIEW / NO RELEASE APPROVED.** This is the next step after the owner's request to cover **all Mod-Naxxramas-Core workstreams**, not just Hunter Pet Autocast. The permanent history and owner scope live in [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28); this note is a cross-feature **release decision aid**, not a replacement for the issue. Nothing here merges a PR, enables defaults, restarts Worldserver, touches DB/DBC/client files or edits Playerbots/Individual Progression.

## One firm rule: successful CI is not an accepted feature

- **S0–S1:** requested/researched; code might not exist.
- **S2:** source exists, possibly as an **unmerged DRAFT**.
- **S3–S4:** source tests, C++ or complete pinned Worldserver link. **This is not actual gameplay evidence.**
- **S5:** actual installed dependencies checked and **full characters DB + configuration + binary backups proven restorable** in an authorized staging setup.
- **S6:** owner-approved game scenarios and regression cases passed on a specific exact build.
- **S7:** separate explicit merge, release, install/restart and enablement decisions with rollback/monitoring.

The release-gate inventory in [`docs/release-gates/1.0.6.8.5.json`](release-gates/1.0.6.8.5.json) is deliberately **fail-closed**. All ten tracked components are currently **excluded** from a new release, **not** because existing main code has been disabled, but because the owner has **not selected/approved a release scope**. Features already on `main` remain historically present and are not undone by this manifest. The manifest makes **no claim** about currently installed binaries or live server settings.

## What the combined candidate actually contains

[Draft integration PR #33](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/33) exact `c1e0ed607a53ceaafdd27da32360f38bca6235cd` has a **successful full pinned Worldserver build** [#39235253197](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39235253197) of just these three new workstreams:
- [Golemagg #30](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/30): OFF-by-default **read-only one-Altbot diagnostic**, not movement fix.
- [Hunter Ammunition #32](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/32): OFF-by-default command-only controlled Altbot inventory top-up; **persistent item additions after explicit opt-in**, requires owner pilot.
- [Hunter Pet audit #26](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/26): OFF-by-default human Hunter **read-only observation**, not persistence restoration.

**These are not in combined #33:** [Quest Loot Protection #25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/25), [Eastern Plaguelands full-capture announcements #24](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/24), [NT1 Altbot safety draft #18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/18). The main Eastern Plaguelands 90-minute lock is already **merged** but not verified as enabled/deployed. Legacy class/racial/consumable/event/DBC features are not automatically revalidated by the three-feature compile.

**Recent Hunter research #36–#38 is also not a functioning module-only runtime fix.** [Draft #38](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/38) briefly modifies an **ephemeral** IP checkout in CI to test a proposed upstream-dependent correction; even if that Worldserver links, a permanent IP modification **does not satisfy** the owner's **module-only** delivery requirement.

## Recommended closeout sequence

1. **Release scope freeze first (no install):** select which current draft features might belong in 1.0.6.8.5. Explicitly classify diagnostics as diagnostics and exclude unimplemented Golemagg movement and human Hunter autocast functionality. Keep all three combined feature flags default-OFF.
2. **Small controlled acceptance first:** consider Hunter ammunition **one named Altbot** and Quest Loot **one quest/drop/group scenario** in separately authorized restorable staging runs, not simultaneous with other new features. These change persistent inventory/loot and must never be enabled just because CI passes.
3. **Eastern Plaguelands:** verify the already-merged tower-lock source is actually installed/bound and correctly restores 90-minute tower states. Test faction-zone messages separately for the additional draft; do not assume a merged source means an active SQL binding.
4. **Harder functional blockers remain separately tracked:** Golemagg actual melee oscillation (requires approved one-Grau trace), NT1 safe changed-build Altbot Apply (currently denied), and player-controlled Hunter pet autocast ON/OFF (safe **module-only** handoff still unproven).
5. **Cross-feature regressions and per-feature signoff:** compare installed exact AzerothCore/IP/Playerbots/Naxx SHAs, test backup restore, DBC/SQL compatibility, expected disabled baseline, authorized in-game scenarios, release Change Notes and rollback. Approve merge/release/install/enablement **individually**.

## Read-only command

```bash
python3 scripts/check_naxx_release_feature_gates.py --mode report
# Prints all components, current authored evidence, missing release-wide approvals.
# Exit 0: reporting succeeded; NOT "safe to release."

python3 scripts/check_naxx_release_feature_gates.py --mode release-gate
# Exit 2: expected BLOCKED for current unapproved release.
# Exit 0: only after a future separately reviewed manifest records all
# owner, build, backup, installed-version and in-game acceptance gates.
```

The isolated [Python model tests](../tests/test_naxx_release_feature_gates.py) explicitly exercise duplicate/missing workstreams, accidental cross-feature inclusion, a fully built but unaccepted Hunter ammo grant, and a **pet observer misrepresented as a persistence fix**. They also use disposable fictional fully-approved fixtures to verify the validator can pass an actually satisfied policy; those fictional fixtures **do not change our current release status**.

**Next operator action (later, with approval):** identify installed source SHAs and privately verify **restorable** source/binary/config/full characters DB backups before any feature-specific staging. There is **no operator command or server change requested now**.
