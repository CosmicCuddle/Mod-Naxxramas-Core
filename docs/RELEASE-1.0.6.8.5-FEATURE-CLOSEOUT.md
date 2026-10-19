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

## Completion-first delivery checkpoint — 19 October 2026

**Planning only: no merge, installation, configuration activation or release approved.** The quickest proposed route is to finish **independently built** features individually, not wait for functional Golemagg movement, Hunter Pet autocast ON/OFF persistence or NT1 changed-build talent application. Those three functional problems remain separate **unimplemented/blocked** outcomes, even though their diagnostic/partial candidates build.

| Pilot order | Exact draft head and independent full Worldserver S4 proof | Gate preventing S5–S7 |
| --- | --- | --- |
| 1 — controlled Hunter Ammo | [PR #32](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/32) `84a3da6a3a2192dd56c93a4e9cfd441de7cfe518`, [build 18/18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39269109936) | Actual installed source/era/projectile templates unknown; restore-proven full characters DB and one-Hunter inventory acceptance absent |
| 2 — narrow Quest Loot | [PR #25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/25) `e3e1bf339c8b1aba07ab065d50dbcc3fafbf0e51`, [build 18/18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39270992658) | Actual packet paths, restorable data and **QL-01–QL-15** controlled group-loot acceptance unverified |
| 3 — Eastern Plaguelands announcement | [PR #24](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/24) `8946f8f3bdbb980393922b9226a3cbe211609308`, [build 18/18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39269122346) | Active `outdoorpvp_template(TypeId=6)` binding, source installation, world-state restore, four-tower/two-faction message acceptance all unknown |

**Do not confuse independent builds with a combined release:** [combined PR #33](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/33) and newer [PR #41](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/41) successfully build **Golemagg read-only observer + Hunter Ammo + Hunter Pet read-only audit** together. They do **not** include Quest Loot or EP Announcements. Before selecting an actual multi-feature package, verify exact selected source provenance, config/loader conflicts, full combined pinned Worldserver link, final registrations and default-OFF behavior. No standalone S4 result can certify an untested combination.

### One-pass evidence package before any staged pilot

1. **S5 installed-state inventory (read only):** privately record the *actual* AzerothCore / IP / Playerbots / Naxx module HEAD SHAs, tracked local changes, effective config, real running Worldserver binary and relevant SQL handler/item templates. The optional [read-only source preflight draft #34](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/34) is **not installed**; its source check alone cannot prove running-binary provenance.
2. **S5 restoration rehearsal:** verify known-good source, Worldserver binary, effective configuration and **complete characters database** restore on approved disposable staging. Include world SQL/state and client/DBC backups where relevant. A backup file existing without a verified restore is not enough.
3. **S6 one OFF-baseline feature test at a time, only after fresh owner approval:** for ammo, verify actual item before/after counts, arrows vs bullets, no-pet, no-weapon, full-bags, repeat and relog; for Quest Loot use QL-01–QL-15 including legitimate owner pickup; for EP check each tower, both factions, only one signed 100% notice and restart/lock behavior. Record **PASS/FAIL/NOT RUN**, installed SHA, logs stored privately, any rollback and regressions. Abort on duplication/loss/unlootable loot/incorrect messages.
4. **S7 final selected-release sign-off:** separately approve exact integration candidate, per-feature inclusion, installation/enablement and merge; record final in-game evidence and monitoring. Never flip `include_in_release`, `owner_approved`, `release_approved` or installed/backup proof from GitHub CI alone.

**Minimum next owner involvement, when invited:** authorization for a read-only installed-source inventory and restore-safe staging preflight **only**, not installation or gameplay. No action is requested from the owner now; all ten release manifest inclusions remain `false`. Record progress only in [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), not another master checklist.

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

The isolated [Python model tests](../tests/test_naxx_release_feature_gates.py) explicitly exercise duplicate/missing workstreams, accidental cross-feature inclusion, a fully built but unaccepted Hunter ammo grant, and a **pet observer misrepresented as a persistence fix**. They also enforce **stage/evidence consistency**: unimplemented fixes cannot be marked delivered, an unmerged draft cannot be marked S7, S4 needs a verified full build, S5 needs proven restorable backups, and S6 needs actual accepted gameplay. A checked synthetic model test is still **not** a live acceptance result. They also use disposable fictional fully-approved fixtures to verify the validator can pass an actually satisfied policy; those fictional fixtures **do not change our current release status**.

**Next operator action (later, with approval):** identify installed source SHAs and privately verify **restorable** source/binary/config/full characters DB backups before any feature-specific staging. There is **no operator command or server change requested now**.


## Combined candidate's own source and full-build release gates (19 October)

The combined PR #33 is **not automatically validated for release** merely because its individual feature drafts each have a separate pinned C++ / Worldserver PASS. An earlier version of the fail-closed checker required combined **owner approval**, but did not independently check its already-declared `combined_candidate.source_built` and `combined_candidate.full_worldserver_built` fields when a combined feature was selected.

The current release-gate proposal corrects that: an included combined feature requires **all three** combined candidate gates—verified source build, verified full Worldserver link, and owner approval—*in addition* to the separate per-feature S4/S6, restorable backups and installed-source approvals. A contradictory manifest claiming combined `full_worldserver_built=true` while `source_built=false` is rejected even in read-only report mode. Two new synthetic regression cases ensure a fully fictionally approved release cannot pass if either combined build flag is false.

**Evidence limit:** GitHub current combined PR #33 `c1e0ed6` has a separate exact-head pinned full Worldserver build [#39235253197](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39235253197), which justifies the two current build booleans. The independent 10-file Git blob comparison recorded in [PR #33's review discussion](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/33#issuecomment-6271136856) confirms selected current #30/#32/#26 source/test file identity; it is not proof of every config/loader source or a new runtime. A **new** Golemagg empty-tail candidate [PR #40](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/40) is **not** integrated into that combined binary. No automated merge, release, source or live-server mutation is authorised. All release flags stay false.
