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
| Known risks | Incorrect host topology/path assumptions; wrong overwrite hook; insufficient storage; accidental retention ownership broadening. F15 read/write roots reject symlink ancestors; crash reports publish atomically and retry validation is inode-bound; history operations use coordinated locks/recovery backup. |
| Tests | Focused source tests cover operation separation, lexical/real path boundaries including ancestor symlinks, recovery state, report evidence, atomic publication/inode retry, ownership, private-root/FIFO refusal and history locking/recovery; no current claim of full World/Auth/live validation. |
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


## F15-REPORT-PRIVACY-20261121

| Field | Record |
| --- | --- |
| Intended behaviour | Prevent known credential tails and history-row injection in human-readable crash reports; keep newest redacted context within 32768 UTF-8 bytes. |
| Owning component | CosmicCuddle; F15 renderer. |
| Source ref/version | Child of frozen #336 at `64e06361e1daaf5db6cfcfd2b07bc7375650c675`; exact child HEAD recorded in PR/review queue. |
| Affected files | `scripts/f15_crash_report_renderer.py`, `tests/test_f15_report_privacy.py`, bounded Linux workflow and accompanying privacy note. |
| Config/SQL/DBC/client dependencies | Python standard library; Linux/POSIX required for inherited storage tests. No SQL/config/DBC/client dependency. |
| Known risks | Conservative redaction can omit diagnostic text; unknown secret formats are not guaranteed scrubbed. Existing report retry mismatches fail closed. Raw forensic evidence retains inherited private handling. |
| Tests | 15 pure-renderer tests PASS locally; actual frozen-parent leak reproduction; unchanged storage AST guard. Full Linux suite outcome must be taken from exact-head CI evidence. |
| Live status | Not installed; source only; no deployment, service action or live-log access. |
| Decisions | Preserve frozen #336, storage/locking/retention and raw evidence. Do not interpret pure projection as Linux storage or PM2/tmux evidence. |
| Rollback requirements | Revert/abandon source child; preserve existing reports/history/raw evidence. |


### Supervised-report composition increment (2026-11-21)

CosmicCuddle owns this F15 extension. Draft PR341 is a child of PR340
`c460787efb0600ff5ca6617c78c40e522429f7e0`; exact implementation head is recorded
in the PR. Files: `scripts/f15_supervised_incident.py`, its executable fixture
tests and source note. Requires explicit execute=True for a new child, never
attaches to or restarts existing services. No config/SQL/DBC/client dependency.
Risk: report failure requires manual reconciliation; oversized console is omitted
from rendered input with a gap while originals remain private. No installed
PM2/tmux adapter or deployment. Test results belong to exact-head CI records.
Source only, not installed. Rollback: abandon/revert child, preserve evidence.


### Supervised report recovery increment (2026-11-21)

Source child of PR341 at cf875236e34fc85a2c3644051a331167e7424d5e.
`recover_report` uses a completed verified raw bundle and original timestamp;
it never launches a process. Descriptor-read report input is hash checked against
the verified manifest. Missing/altered/ambiguous evidence is refused. Existing
report/history idempotence remains inherited; no evidence is rewritten.
Executable tests inject report/history failures, verify retry/no respawn,
idempotence and tampered/missing evidence refusal. Exact Linux results are in
the draft PR/review queue. Failures before complete bundle publication and
pending partial report files still require inspection. No new live/config/SQL/
DBC/client dependency; uninstalled. Rollback: revert child, preserve evidence.


### Explicit incident CLI (2026-11-21)

Source child of PR342 at cd2ec28c356b1b66fd294beb2191e9c173b267c4.
`f15_supervised_incident.py supervise` requires --execute and an explicit command;
`recover` only publishes from verified completed evidence. Existing observation
CLI is untouched. Arguments are passed as a vector with no shell interpolation.
Normal operational failures emit generic messages without exception/path details.
Diagnostic status is 0 for clean complete supervision or successful recovery,
2 for nonzero/signaled child, capture failure or refusal. It is not a transparent
PM2/tmux launcher replacement; original child status remains in private evidence.
Tests use disposable Python children, default-off no-side-effects, literal shell
metacharacters, nonzero status/report retention and recovery. Exact Linux results
are recorded in PR/queue. No SQL/config/DBC/client changes, uninstalled. Rollback:
revert child, preserve evidence. No authority to install or change live services.
