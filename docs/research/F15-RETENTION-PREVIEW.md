# F15 — read-only 30-day archive expiry preview

**Date:** 1 November 2026. **Status:** separate temporary developer-coverage DRAFT (default OFF, not installed, not production approved).

## Why this exists

CosmicCuddle requested usable Worldserver/Authserver crash-console backups and
automatic 30-day retention, but no original server logs may be deleted without
explicit owner approval. The existing opt-in F15 collector has a real deletion
routine, `f15_archive_retention.retain_once`, that writes a durable intent and
removes **collector-owned** expired archive/journal records, never original
server logs. The operator needs a reliable, non-destructive way to examine
*potential* retention candidates before authorizing any active retention.

`scripts/f15_retention_preview.py` adds a **read-only** command. It shares
the strict journal, UTC cutoff, origin and receipt checks used by the existing
retention implementation. It reads only the private archive root; it does not
query PM2, start/stop programs, alter World/Auth, change access permissions,
write or delete a single file.

## Example — documentation only, NOT a command to run on the owner host yet

```bash
python3 scripts/f15_retention_preview.py \
  --root /path/to/already-approved-private-collector-root \
  --preview
```

No `--preview` means refusal. The root **must already exist** and be private
0700, with an existing collector lock, records and archives. The command
takes the same cooperative lock as capture/deletion. A pending interrupted
retention intent causes a refusal requiring manual review.

Its JSON output contains only the stream label, UTC observation day, checked
journal byte count and record count; it does **not** print original log paths,
packet payloads, command lines, credentials or console contents. It uses the
exact current clock (no fake `--now` CLI flag).

## What this checks

- Valid source-created journal record filename ranges, contiguous offsets,
  nondecreasing observation day, exact byte size and SHA-256.
- One private `records`/ `archives` pair for a known World/Auth stream label.
- No symbolic-link directory components in the selected collector root or its ancestor chain (including aliases to otherwise private directories).
- Valid origin metadata and no unknown, hardlinked, missing or replaced file.
- Matching complete archive bytes plus receipt for each candidate day.
- **Strictly later than** the end of the UTC observation day plus 30 days.
  A day exactly on the boundary is *not* eligible.
- No retention-intent interruption; no competing collector/worker lock.

The eligibility result is a **snapshot**. The destructive routine must check
every condition anew at actual deletion time; a preview is NOT consent to
delete. All testing occurs on disposable fake log paths in CI; the developer
has not run this against CosmicCuddle's host.

## Deliberate limits

- This previews only archive/journal days that the existing `retain_once`
  routine could expire, **not** raw supervisor `stdout.raw` /
  `stderr.raw`, PM2-managed original stdout/stderr, attachments, backups or
  arbitrary disk files. Consequently it does NOT yet solve the entire
  30-day disk-capacity goal.
- Does not attach to Authserver if the owner runs it under tmux rather than
  PM2. Existing PM2 log-inode rotation still refuses safely and requires a
  separate, source-backed handoff. PM2 PID change remains **unclassified**, not
  a proven engine crash.
- Private-path validation is not a comprehensive defense against a hostile
  same-UID actor racing filesystem metadata between `lstat` and `read`.
  The tool is still experimental and should not be installed unattended.
- No owner restore drill, actual daemon inventory, log confidentiality review,
  30-day dry-run approval, native Worldserver link or actual crash evidence
  is established by this script.

## Testing and ownership

`tests/test_f15_retention_preview.py` checks nine disposable scenarios:
no file mutation, exact boundary, newer-day preservation, corrupt/missing
archive refusal, symlink/pending-intent refusal, untrusted root/journal
refusal, nested symlink ancestor refusal, cooperative collector-lock refusal,
and explicit opt-in CLI without leaking source paths/log contents.

The existing [F15 source workflow](../../.github/workflows/naxx-f15-operator-capture-20261101.yml)
will execute this suite and assert the preview program includes no file
delete or process-control calls. **This DRAFT is not a hosted PASS until the
workflow completes on its exact SHA.**

**Handover:** Information temporarily covers this P3 subtask while Claude
takes an owner-reported break. CS01 Maintenance owns combined branch
integration; Claude can resume another unclaimed P3 task upon return.
Do not merge, deploy, enable retention, access host paths or modify live
processes/data without CosmicCuddle's separate approval.
