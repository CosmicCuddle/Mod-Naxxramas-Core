# F15 raw crash-evidence bundle — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; source/tests only; no live host access/deletion.  
**Parent:** F15 owned 30-day retention DRAFT #306 head `3cb8403cca149b284f2daad9a6401f81db698bd3`.

## Purpose

Close the final explicit retention gap in #306 by giving raw crash evidence its
own strict F15-owned bundle format and 30-day expiry policy.

A bundle is stored under a private Raw Evidence root and contains:
- one 0700 incident directory;
- one or more bounded 0600 artifacts;
- one strict 0600 `manifest.json`;
- SHA-256 and size for every artifact;
- incident id, UTC creation time, provenance and `retention_days = 30`.

Example artifact labels are intended for bounded evidence such as:
- PM2 jlist/status snapshot;
- PM2 manager exit excerpt;
- bounded stdout/stderr tail;
- Auth process/tmux snapshot;
- native crash/coredump metadata summary;
- build/source fingerprint facts.

The bundle format does not itself collect these facts; it stores facts supplied
by the future operational composition layer.

## Bounds and ownership

- incident/artifact names are constrained to safe filename characters;
- maximum single artifact = 1 MiB;
- maximum bundle payload = 4 MiB;
- bundle publication is complete only when `manifest.json` exists;
- a partial directory without a manifest is preserved for review and is never
  treated as an owned complete bundle.

Unknown root files are preserved.

## 30-day retention

A bundle is retained through the full 30-day boundary and is eligible only when
current UTC time is later than `created_utc + 30 days`.

Before deletion:
- manifest shape/kind/policy must be exact;
- every declared artifact must be present, private, regular and singly linked;
- size and SHA-256 must match;
- no unexpected extra file may exist inside the bundle;
- an fsynced retention intent is written;
- file identities are rechecked immediately before unlink.

Any mismatch refuses deletion.

After verified deletion of all artifacts and manifest, the now-empty incident
directory is removed. Active server logs and non-bundle files are never targets.

## Test intent

Focused disposable tests cover:
1. private hashed artifacts + strict manifest;
2. exact 30-day boundary retained;
3. expiry after >30 days;
4. tampered artifact refuses retention;
5. unexpected extra file refuses retention;
6. foreign root file is preserved;
7. invalid incident/artifact names refuse;
8. oversized artifact creates no complete manifest;
9. unfinished retention intent blocks deletion.

No hosted Actions are requested.

## Integration contract

The final synthetic composition should use:

`read-only host probe -> topology normalizer -> checkpoint -> raw evidence bundle -> detailed renderer/history`

For one incident, the detailed report's `Raw evidence reference` must point to
the corresponding bundle path. Both the human-readable report and its raw
evidence bundle then share the owner's 30-day retention policy.

## Custom Modifications Register — F15-RAW-EVIDENCE-BUNDLE-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Store bounded, hashed, private raw crash evidence per incident and retain it for 30 days. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_raw_evidence_bundle.py`, `tests/test_f15_raw_evidence_bundle.py`, this note. |
| Parent | #306 head `3cb8403cca149b284f2daad9a6401f81db698bd3`. |
| Dependencies | Future collector/composition supplies normalized bounded evidence. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Bundle does not itself prove provenance of supplied evidence; total payload intentionally bounded; partial bundles require manual review. |
| Tests | Focused disposable tests authored; no hosted Actions/live host test. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; no live state changed. |
