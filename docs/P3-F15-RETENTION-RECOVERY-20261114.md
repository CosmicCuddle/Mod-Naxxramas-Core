# F15 unified retention recovery hardening — 2026-11-14

**Owner:** CosmicCuddle  
**State:** source-only child of DRAFT #315.  
**Parent:** #315 sidecar-history-lock head `c096d9b13692d95d2c90136519a5bc2ca5f94a0b`.

## Purpose

Make 30-day retention interruption-safe and diagnosable across all F15-owned evidence domains without automatically deleting uncertain evidence or clearing an unfinished intent.

Covered domains:
- pre-overwrite snapshot archive;
- detailed crash reports + Crash-History;
- raw crash-evidence bundles.

## New retention-intent contract

New deletion intents use **version 2** and persist target identity before deletion.

Snapshot intent records:
- snapshot/manifest names;
- dev/inode/size/mtime;
- SHA-256 for both files.

Crash-report intent records:
- report name;
- dev/inode/size/mtime;
- SHA-256.

Raw-evidence intent records:
- bundle directory dev/inode;
- incident id;
- every artifact + manifest name;
- dev/inode/size/mtime/SHA-256 for every target.

After the intent is durably published, retention revalidates the full persisted identity/hash immediately before unlink. A changed/replaced target is refused and the intent/evidence remain for review.

Intent publication uses unique private temporary files rather than the old fixed `.pending` filename, so a killed writer cannot permanently wedge later intent creation. Old fixed pending debris is treated as foreign evidence and is not silently removed.

## Unified read-only recovery classifier

`scripts/f15_retention_recovery.py` classifies but never mutates.

Examples:
- `PRE_DELETE_TARGETS_INTACT`;
- `PARTIAL_DELETE`;
- `TARGETS_ALREADY_ABSENT`;
- `REPORT_ALREADY_ABSENT_AFTER_INTENT`;
- `BUNDLE_ALREADY_ABSENT_AFTER_INTENT`;
- `IDENTITY_MISMATCH_OR_FOREIGN`;
- `LEGACY_IDENTITY_UNPROVEN`;
- `MALFORMED_INTENT`;
- `UNSAFE_INTENT`;
- `PARTIAL_BUNDLE_WITHOUT_RETENTION_INTENT`;
- `ROOT_ABSENT`.

Legacy v1/name-only intents are never guessed safe because they lack persisted target fingerprints.

A partial raw bundle from a failed evidence write with **no retention intent** is distinguished from interrupted retention.

No classifier path unlinks, renames, repairs, recreates or clears evidence/intent state.

## Operational CLI

New read-only mode:

`recovery-status --archive-root ... --crash-root ...`

`retain-once` now runs the unified classifier **before the first deletion in any root**.

All retention is blocked when:
- any snapshot/crash/raw retention intent exists; or
- raw evidence contains a partial/unverified bundle with no retention intent.

This prevents archive deletion from occurring before a later raw/crash root exposes an unresolved interruption.

## Crash-History composition

This child is based on #315 and uses the exact same persistent sidecar:
`Crash-History.txt.lock`.

Crash-report retention acquires that sidecar **before deleting any expired report**, holds it through report deletion and history pruning, and atomically replaces history while still holding the stable lock.

Therefore:
- renderer append and retention rewrite cannot race through different history inodes;
- an unsafe/insecure sidecar is discovered before destructive crash-report retention;
- locking the replaceable history inode itself is not used as the serialization contract.

## 30-day policy preserved

The retention boundary is unchanged:
- exactly 30 days old survives;
- only `now > created + 30 days` expires.

Active source logs remain outside retention ownership. Foreign/unknown root files and unknown history lines remain preserved.

## Tests added/extended

Committed focused tests cover:
- v2 snapshot/crash/raw intent contents;
- interruption immediately after intent publication;
- full identity/hash presence;
- old fixed pending debris not wedging new intent writes;
- shared history-lock refusal before report deletion;
- read-only classification for intact/partial/absent/replaced targets;
- legacy, malformed, foreign and unsafe intents;
- raw partial bundle with no retention intent;
- target filename grammar;
- absent roots without creation;
- classifier non-mutation;
- global retain-once preflight preserving an expired archive snapshot when raw evidence is partial;
- operational CLI recovery mode.

These tests are committed but **not claimed executed on an exact local checkout in this environment**. No hosted Actions were requested.

## Remaining operator-recovery boundary

The classifier deliberately does **not** provide an automatic “clear intent” command. Human/operator review is still required to decide whether surviving/missing evidence matches the interrupted deletion and whether an intent may be removed.

A future documented manual resolution procedure must preserve this rule:
- never auto-delete uncertain evidence;
- never treat replacement/foreign objects as deletion progress;
- legacy intents remain identity-unproven.

## Custom Modifications Register — F15-RETENTION-RECOVERY-20261114

- **Owner:** CosmicCuddle.
- **Owning component:** Mod-Naxxramas-Core F15 operational tooling.
- **Parent:** DRAFT #315 at `c096d9b13692d95d2c90136519a5bc2ca5f94a0b`.
- **Affected files:** retention helpers, raw-evidence helper, operational CLI, new recovery classifier, focused tests, this document.
- **Config/SQL/DBC/client:** none.
- **Known risks:** intentional fail-closed states require operator review; legacy intents cannot prove target identity; no automatic cleanup of recovery debris.
- **Tests:** focused tests committed; current exact-head execution UNKNOWN here; no hosted Actions.
- **Live status:** DRAFT only, uninstalled/not invoked on owner host.
- **Rollback:** abandon/revert this child; no live state exists.
