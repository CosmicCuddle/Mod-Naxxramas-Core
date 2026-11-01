# CosmicCuddle — Naxx P1–P4 + P3/F15 operator tooling integration (1 Nov 2026)

**Owner:** CosmicCuddle. **Status:** isolated CS01 Maintenance DRAFT, unmerged and not installed. **No permission to deploy, delete, rotate, start a service, enable a flag, read the owner host, or alter a database.**

## Why this is one candidate

The earlier [combined P1–P4 + P4-H zero-count DRAFT #278](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/278) contains actual Warlock, Hunter ammunition, World/Auth P3 F15 collector/diagnostics, and human quest-loot development changes, including the malformed zero-count loot guard. Its exact branch head at integration start was `880c7ee52671e94522931b807f2791544b51c1f1`.

Two independently developed, separately reviewable **P3 operator tools** were not yet present in that combined candidate:

1. [Information F15 archive-preview DRAFT #277](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/277) exact `328c7344800d0d05015df3c286b5e88eede86ca3`: explicit `--preview` of **collector-owned** expired archive/journal UTC days, using read-only private-path and cooperative-lock checks. This does **not** delete data or activate 30-day retention.
2. [CS01 P3 raw-storage audit DRAFT #279](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/279) exact `63a05b09e486bfad4cb939e4f0c444caf7f54d28`: reads only metadata and strict existing receipts for completed/incomplete supervised Worldserver/Authserver runs; reports raw bytes and completed runs older than 30 days. This does **not** read raw log contents, rotate/delete files or prove actual engine crashes.

This child integration brings these already-reviewed implementation files and tests together. **These two tools solve different reporting problems. They do NOT make raw logs automatically expire.** The owner-requested automated 30-day archive retention for real installed server logging remains contingent on verified host process ownership, scheduled operation, specific original-vs-owned-log policy and separate approval.

## Custom Modifications Register — NAXX-CS01-F15-P3-TOOLS-COMPOSITION

| Field | Record |
| --- | --- |
| Intended behaviour | Preserve the current P1 Warlock/P2 ammunition/P3 diagnostics/P4 quest-loot code and default-OFF P4-H while adding read-only P3 archive expiry previews and supervised raw capacity reporting. |
| Owning component | `CosmicCuddle/Mod-Naxxramas-Core` development branch `integration/cs01-p1-p4-p3-supervised-tools-20261101`; sourced from #278, #277 and #279, **not** their protected/default branches. |
| Files from #277 | `scripts/f15_retention_preview.py`, `tests/test_f15_retention_preview.py`, `docs/research/F15-RETENTION-PREVIEW.md`, and updated `.github/workflows/naxx-f15-operator-capture-20261101.yml`. The exact Git **blob SHA** of each is checked against #277 before claiming preservation. |
| Files from #279 | `scripts/f15_supervised_storage_audit.py`, `tests/test_f15_supervised_storage_audit.py`, `.github/workflows/f15-supervised-storage-audit-20261101.yml`, `docs/P3-F15-RAW-STORAGE-AUDIT-20261101.md`, byte-identical to the #279 source ref. |
| Shared dependencies | `f15_operator_collector.py`, `f15_archive_retention.py`, `f15_process_supervisor.py` and `f15_supervised_retention.py` were all independently confirmed at the same exact Git blobs on #278/#277/#279 before the copy. They are intentionally **not modified**. No Core C++ runtime, SQL, DBC or owner configuration is changed by this child. |
| CI and tests | Existing preview offline workflow now includes the preview test. The dedicated raw-storage workflow tests the audit and read-only API on disposable temporary subprocesses. New GitHub Actions at the actual child HEAD require verification; copied source hashes and workflow registration alone are **not** executed test evidence. Native Worldserver link, true crash handling, PM2/tmux and 30-day owner-host operation are **not tested**. |
| Risks / limits | Strict path and receipt checks are not a same-UID TOCTOU security boundary; cooperative lock only covers cooperating tools. No original server log is inspected. Unbounded original raw streams remain a storage risk, even if collector-owned archived output follows a 30-day policy. A successful log-size report never authorizes deletion, and no game-safe retention window is assumed. |
| Integration/rollback | Drop this isolated child branch to undo only its additive scripts/docs/tests and preview workflow update. Original #277/#278/#279 refs are preserved; no destructive cleanup is implied by reverting code. Full backed-up staged test, manual human loot acceptance, security and rollback are required before any owner-approved production installation. |

## Next required acceptance

- Confirm exact-head GitHub Actions results for the combined source (no "green" claim from queued runners); compile and link the actual pinned AzerothCore Worldserver/Authserver-compatible module.
- Run both P3 Python test modules on disposable paths; check the preview's 9 negative/positive cases and the raw capacity audit's supervised child-process cases.
- Owner-authorized test environment: verify real World/Auth capture and identify PM2/tmux/systemd process owner without exposing private paths or contents.
- Verify P1 summoning, P2 ammunition and P4 quest loot including multiple real human viewers, then evaluate read-only P3 data and separately approved archive scheduling. **No production deployment until CosmicCuddle explicitly approves.**

## Combined native-link workflow gate (after initial source composition)

The child also updates **only the pull-request paths filter** in `.github/workflows/naxx-p4-h-master-loot-20261101.yml` to include the two new P3 scripts, their disposable tests and the composed CI/docs files. This reuses the existing pinned, non-launched **full Worldserver** compile/link and stock Master Loot harnesses whenever a new combined P3-only child is reviewed. Its implementation jobs, pinned Core `8daffdabe9202c228e45d833c9a1d399597a15cd`, historical Playerbots `037c01418b5d01506917a3db9b44fd56ac5f965c` and upstream IP `4ff4b5fcc1480348f058c632573143e62d4e3a41` are **unchanged**. This test is NOT a compile against the owner's currently installed Core/Playerbots/IP revisions nor proof the separate paid-IP/Character Services forks work together.

At combined head `77a56911bf5e17776a956222588dd218378238b7`, a GitHub comparison against original #278 reported **10 child commits and 10 paths**, comprising seven exact source/test/docs copies, one exact existing F15 preview workflow from #277, one new composition register, and this **one paths-only P4-H workflow update**. There are **no changes to pre-existing C++ runtime files, config, SQL, process launch or defaults**. The new P4-H native-check run and two F15 test runs were **QUEUED**, not completed, at first check. Verify the exact current HEAD before using any CI output. No owner-host deployment approval is implied.
