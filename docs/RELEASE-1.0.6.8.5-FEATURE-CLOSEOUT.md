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

**New isolated completion-first build candidate:** [DRAFT PR #46](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/46) at `4734e4a0ccb2d457420f9995c21bee14826d2a9a` combines **Hunter Ammo + Quest Loot + EP Announcements only**. All 17 copied source/test/documentation Git blobs were independently verified identical to their exact standalone draft heads; the shared config was safely composed from two append-only changes and leaves both inventory-sensitive features disabled. [Exact-head pinned three-feature workflow #39301290987](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39301290987) has verified dependency revisions, source/model tests, default-OFF config, and all three real C++ translation-unit compilations. **The full pinned Worldserver link and final executable checks COMPLETED SUCCESS; combined S4 is independently verified for this exact draft head (job #118226850410).** This does not supersede the older #33/#41 candidate or grant any release inclusion, merge, installed-server verification, restore acceptance or owner approval. The initial run #39300932569 failed a test-only declaration-versus-registration counting assertion before C++ compilation; the corrected run was prepared by changing that workflow assertion only.

### One-pass evidence package before any staged pilot

1. **S5 installed-state inventory (read only):** privately record the *actual* AzerothCore / IP / Playerbots / Naxx module HEAD SHAs, tracked local changes, effective config, real running Worldserver binary and relevant SQL handler/item templates. The optional [read-only source preflight draft #34](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/34) is **not installed**; its separately authorised `--worldserver-pid` probe can identify/hash an existing Linux process executable, but source checks alone still cannot prove installed-binary provenance.
2. **S5 restoration rehearsal:** verify known-good source, Worldserver binary, effective configuration and **complete characters database** restore on approved disposable staging. Include world SQL/state and client/DBC backups where relevant. A backup file existing without a verified restore is not enough.
3. **S6 one OFF-baseline feature test at a time, only after fresh owner approval:** for ammo, verify actual item before/after counts, arrows vs bullets, no-pet, no-weapon, full-bags, repeat and relog; for Quest Loot use QL-01–QL-15 including legitimate owner pickup; for EP check each tower, both factions, only one signed 100% notice and restart/lock behavior. Record **PASS/FAIL/NOT RUN**, installed SHA, logs stored privately, any rollback and regressions. Abort on duplication/loss/unlootable loot/incorrect messages.
4. **S7 final selected-release sign-off:** separately approve exact integration candidate, per-feature inclusion, installation/enablement and merge; record final in-game evidence and monitoring. Never flip `include_in_release`, `owner_approved`, `release_approved` or installed/backup proof from GitHub CI alone.

**Minimum next owner involvement, when invited:** authorization for a read-only installed-source inventory and restore-safe staging preflight **only**, not installation or gameplay. No action is requested from the owner now; all ten release manifest inclusions remain `false`. Record progress only in [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), not another master checklist.

## S5/S6 owner-controlled evidence handoff — prepared, **NOT RUN**

This is an **empty evidence worksheet**, **not** a second feature tracker. Keep the authoritative stage state in [issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28). Do **not** paste private absolute home paths, credentials, DSNs, full Worldserver configurations, account IDs, or identifiable character logs into public GitHub issues or this document. Review this record privately with the owner only **after** separate staging authorization.

| Gate and evidence | Current result | Acceptance / STOP rule |
| --- | --- | --- |
| Candidate revision and integration CI | #46 exact `4734e4a0ccb2d457420f9995c21bee14826d2a9a`; source tests + native C++ units + **complete same-binary Worldserver link / final symbols PASSED** in #39301290987; SHA-256 `52724e832aa3747a7914fee542f4c0346648edee1b02b11733959f257b14ea86` | **Combined S4 CONFIRMED**; still requires actual installed-source/process, restorable backups, feature-specific staged gameplay and distinct owner approval for S5–S7 |
| Actual installed Grimfeather core SHA and tracked differences | **NOT COLLECTED** | Capture actual SHA and local modifications; pinned CI source SHA is not an assertion about the owner server |
| Installed Playerbots, Individual Progression and Naxx Core SHAs | **NOT COLLECTED** | Capture all three **separate** repositories, not the parent Git SHA for nested modules; do not force-reset a mismatching install |
| Running Worldserver process/binary provenance | **NOT COLLECTED** | Identify service execution path and resolved process executable privately. Optional [draft PR #34](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/34) read-only `--worldserver-pid` hashes the existing `/proc/PID/exe`; comparing that SHA-256 with an on-disk executable is stronger identity evidence but does not prove compiled source/configuration |
| Actual config and EP world handler (TypeId=6) | **NOT COLLECTED** | Private review of feature toggles, IP/Playerbots settings, world DB handler binding; **no SQL UPDATE**, feature activation or restart just to inspect |
| Restore rehearsal: binary + source + effective config | **NOT RUN** | Prove a known-good restoration on approved disposable staging and record result before proposing feature installation |
| Restore rehearsal: **complete characters DB** | **NOT RUN** | Verify the full DB can be restored on disposable staging, **not** just that an export file exists; inventory/quest loot change persistent data |
| EP-specific world state + SQL binding rollback | **NOT RUN** | Prove relevant world-state restore and exact guarded forward/reverse handler row behavior, including independent lock preservation |
| Hunter ammo owner-approved pilot | **NOT AUTHORIZED / NOT RUN** | First OFF baseline, then single controlled Hunter; bows/crossbows vs gun, selected vs missing ammo, full bag, no-pet, no-weapon, repeat/relog, quantity before/after |
| Quest Loot owner-approved pilot | **NOT AUTHORIZED / NOT RUN** | QL-01 through QL-15 in [feature guide](QUEST-LOOT-PROTECTION.md), especially owner pickup, released turn, bot packet path and no stranded loot |
| Eastern Plaguelands owner-approved pilot | **NOT AUTHORIZED / NOT RUN** | All four named towers, both factions, zone-wide notice at full 100% persisted lock only, restart and reset without duplicate announcements |
| Cross-feature defaults and regression pilot | **NOT AUTHORIZED / NOT RUN** | First combined OFF baseline; validate existing classes, consumables, PvP and progression without simultaneously enabling unaccepted features |
| Separate owner decisions: include/merge/install/enable/release | **NONE GRANTED** | Specific signed-off candidate, staged test result, backup proof and reviewed manifest required; approval of one gate never implies another |

The independently tested source-check helper [draft PR #34](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/34) is **not installed** on the owner's realm. If separately authorised and made available from a reviewed source, it can inspect Git repository roots/SHA/dirty tracked files **read only**; it does not inspect untracked files, service-manager configuration, SQL, private settings, run backups or certify restore. The new optional `--worldserver-pid` identifies an existing running executable through read-only Linux procfs **only when separately authorised**; no process, credentials or live server have been inspected. Any mismatch is a **STOP / investigate** condition, not an instruction to overwrite installed files.

**Short operator result format, for private use when authorised:** `Date/time + selected candidate SHA | installed core/IP/Playerbots/Naxx SHAs and dirty/clean summary | binary identity | config/binding verified? | binary/config/source restore PASS/FAIL | full characters DB restore PASS/FAIL | EP world-state restore PASS/FAIL | specific S6 case IDs and observed PASS/FAIL | rollback PASS/FAIL | owner approvals by action`. Start every field as **NOT RUN**. Only update the corresponding master issue gate with sanitised evidence *after* the real test; never promote a not-yet-run field because a CI build passes.

### Exact combined S4 evidence confirmed — 19 October 2026

Completion-first [draft PR #46](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/46) at `4734e4a0ccb2d457420f9995c21bee14826d2a9a` passed [full pinned Worldserver CI #39301290987](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39301290987): all 3 actual C++ module units compiled, Ninja built the full `worldserver` target through **1886/1886** tasks, then `nm` verified a **defined** Hunter Ammo `TopUpHunterAmmo` symbol in both the archive and final executable; binary checks verified Quest Loot registration marker and EP handler marker in that **same** executable. SHA-256 of the linked test binary: `52724e832aa3747a7914fee542f4c0346648edee1b02b11733959f257b14ea86`. This is a tested CI artifact, **not** the owner's installed or running Worldserver. All S5/S6 worksheet fields remain **NOT COLLECTED/NOT RUN**; the two inventory-affecting features remain default-OFF; no EP SQL applied. The updated manifest captures **combined full_worldserver_built=true** only. All 10 `include_in_release=false`, all owner approvals and installed/restore gates false. Next work is controlled S5 staging with consent, **not automatic deployment**.

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


## Integration release gate — exact selected feature mix (19 October)

The checker now guards **two different, overlapping source families**, not merely the original PR #33:
- **Historical diagnostic family:** Golemagg read-only diagnostic + Hunter Ammo + Hunter Pet read-only observer, built in [draft PR #33](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/33). A selected set of **two or more** members of this exact family needs PR #33's own verified source/full link and separate owner approval.
- **Completion-first family:** Hunter Ammo + Quest Loot + EP full-capture announcements, assembled in [draft PR #46](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/46), exact `4734e4a0ccb2d457420f9995c21bee14826d2a9a`. The new `mature_three_candidate` manifest records **source_built=true, full_worldserver_built=true, owner_approved=false**, reflecting the completed successful pinned [combined CI #39301290987](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39301290987). Actual running-server and owner approval remain separately unverified. Selecting **two or more** of those family members requires this candidate's own gates.
- **Unsupported cross-family selection:** any selected two or more experimental workstreams that fit **neither** single source family (such as Quest Loot + the Hunter Pet observer, or NT1 + Hunter Ammo) remain **BLOCKED** regardless of individually successful Worldserver builds. Those mixes have no verified same-binary candidate.
- **Single-feature release:** selecting just one eligible experimental feature does *not* unnecessarily require an unrelated combined candidate; it still requires that feature's own S4, verified S5 restoration, actual S6 acceptance, merge and owner release approval. This is about accurate evidence, not permission to release an untested feature.

[Exact-head fail-closed release CI #39306462386](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39306462386) **COMPLETED SUCCESS, 24/24 synthetic gate tests and 8/8 job steps** for the exact checker/manifest commit `0067fd64be184f9b7727f3a83066fe383ae3e45e`. That test run uses fictional approved fixtures to prove blocking rules; it is **not** owner acceptance. The real authored manifest remains **0/10 selected, all owner approvals false, no installed source/backup/real gameplay proof**, so **RELEASE GATE: BLOCKED** is the expected safe result.

