# F15 Custom Modifications Register

**Scope:** F15 crash/log preservation and operational tooling only.  
**Owner:** CosmicCuddle.  
**Authority:** This is a component register, not a claim that all server customisations are catalogued here.

## F15-OPERATIONAL-CLI-20261113

| Field | Record |
| --- | --- |
| Intended behaviour | Provide separated `observe-once`, `snapshot-before-overwrite`, and `retain-once` operational modes for F15 diagnostics/log preservation, with captured process-identity evidence rendered into human-readable crash reports. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Source ref/version | DRAFT #309, exact accepted source head `827f5618c991611c483941cabb0ba910fee09180`. |
| Affected files | `scripts/f15_operational_cli.py`, `tests/test_f15_operational_cli.py`, `docs/P3-F15-OPERATIONAL-CLI-20261113.md`. |
| Config/SQL/DBC/client dependencies | None in source candidate. |
| Host dependencies | Actual PM2/tmux topology, log paths, overwrite/rotation owner, permissions, free space, scheduling and build/source fingerprint evidence remain host-specific. |
| Known risks | Incorrect host topology/path assumptions; wrong overwrite hook; insufficient storage; accidental retention ownership broadening. Snapshot sources are regular/single-link only. Crash retention requires explicit ownership proof, and Crash-History pruning shares the renderer's exclusive file lock so concurrent incident appends are not overwritten. |
| Tests | Focused source tests cover operation separation, path boundaries, recovery state, report evidence, crash-retention ownership, FIFO refusal and exclusive Crash-History rewrite locking; no current claim of full World/Auth/live validation. |
| Live status | Not installed / not scheduled / not invoked on owner host by CS01. |
| Decisions | Active logs are never retention-owned; copy before approved overwrite/rotation/truncation; F15-owned archive/crash/raw evidence retained 30 days. |
| Rollback requirements | If later staged, disable schedules/hooks first, restore replaced files from verified backup, preserve diagnostic evidence, and verify original World/Auth topology. |

## F15-STAGING-PREFLIGHT-20261113

| Field | Record |
| --- | --- |
| Intended behaviour | Offline assessment of whether the evidence required for safe F15 staging is complete. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Parent | DRAFT #309 head `827f5618c991611c483941cabb0ba910fee09180`. |
| Source ref/version | DRAFT #310 preflight line with NUL-hardening child DRAFT #318, current source head `1140c462a96d69880f0d0e4676c1781ed42da2ca`. |
| Affected files | `scripts/f15_staging_preflight.py`, `tests/test_f15_staging_preflight.py`, `examples/f15_staging_manifest.example.json`, `docs/P3-F15-STAGING-PREFLIGHT-20261113.md`, `docs/P3-F15-STAGING-EVIDENCE-COLLECTION-20261113.md`. |
| Config/SQL/DBC/client dependencies | None. |
| Host dependencies | Operator-supplied provenance-bearing evidence only; tool does not probe host. |
| Known risks | Bad supplied evidence could misclassify readiness; schema therefore requires explicit status/value/source, strict path/type checks, UNKNOWN preservation and self-authorization blocking. |
| Tests | 13/13 focused local tests passed on prior head `044fde67...`. Later heads added canonical-path/root checks and embedded-NUL rejection; current `1140c462...` contains 20 focused test methods. CS01 independently checked source ordering/focused path behavior, but a full exact-head 20-test execution is not yet claimed. No hosted Actions. |
| Live status | Uninstalled / not invoked on owner host. |
| Decisions | Host facts must be VERIFIED; only scheduling-plan fields may be PROPOSED; READY_FOR_OWNER_REVIEW is not deployment approval. |
| Rollback requirements | Abandon/revert branch/PR; no live state exists. |

## F15-STAGING-BACKUP-ROLLBACK-20261113

| Field | Record |
| --- | --- |
| Intended behaviour | Define the backup, rollback, phased staging and stop-condition template that must exist before any F15 live installation/scheduling. |
| Owning component | Mod-Naxxramas-Core F15 operational planning. |
| Parent | DRAFT #318 current head `1140c462a96d69880f0d0e4676c1781ed42da2ca` on the #310 preflight line. |
| Source ref/version | Clean replacement child of #318; exact moving head is tracked in PR metadata/master board rather than self-embedded in this file. Supersedes stale-parent DRAFT #312 and older #311 without rewriting either history. |
| Affected files | `docs/P3-F15-STAGING-BACKUP-ROLLBACK-TEMPLATE-20261113.md`, this register. |
| Config/SQL/DBC/client dependencies | None. |
| Host dependencies | Requires a VERIFIED current #310/#318 evidence manifest plus later owner-approved exact target paths, backup location, scheduler/hook design and runtime ownership. |
| Known risks | Proceeding without exact backup hashes, path ownership or overwrite-owner proof; accidental loss of active logs/evidence; rollback that removes diagnostic evidence. |
| Tests | Document/source review only; no live rehearsal and no hosted Actions. |
| Live status | Planning only; no host operation performed. |
| Decisions | Active logs never deleted by F15; F15 evidence preserved through rollback; staging split into separate approval-gated phases; no live overwrite is used merely to prove snapshot behavior. |
| Rollback requirements | Revert/abandon source-only branch now. Future host rollback order is documented in the staging template and requires schedules/hooks disabled before file restoration. |

## Register maintenance rule

When F15 advances:
1. update the exact source ref/head;
2. preserve prior decisions and rollback requirements;
3. distinguish source-only, compiled, staged, gameplay/live and production states;
4. never mark a later state proven merely because an earlier state passed;
5. do not broaden F15 retention ownership to unrelated server logs or artifacts.
