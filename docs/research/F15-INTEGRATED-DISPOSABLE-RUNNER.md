# F15 — integrated disposable console-archive runner (synthetic only)

**Status: DRAFT test fixture. Not a collector, not deployable, not operational F15.**

Parent: #252 `test/cs01-f15-durable-journal-fixture-20261030` at `90e269d`
(nesting #249 → #250 → #251 → #252). Assigned by CS01 on #143 (6543633527);
claimed in 6544138504. CS01 owns F15 integration; this is one coding slice.

Everything runs inside the runner's own `tempfile.TemporaryDirectory`. There
is no command-line entry point, no live path, no scheduler, and no PM2, tmux,
launcher, SQL, database, owner file or server process. The runner refuses any
directory that is not its own disposable workspace.

## What it does, end to end

Three fake source files stand in for **World PM2 stdout**, **World PM2 stderr**
and the **Authserver native log**. For each one the runner:

1. **Polls** by inode and offset. The first look at a file skips its existing
   bytes (no historical backfill) and records that it did.
2. **Publishes** each newly read span as an immutable journal record, then
   advances one checksummed checkpoint. Both steps are atomic (write, `fsync`,
   link or rename, directory `fsync`).
3. **Seals** each whole UTC day into a plain `.txt` archive holding exactly the
   bytes observed that day, plus a JSON provenance sidecar.
4. **Expires** only manifest-owned, sealed, unchanged archives that closed more
   than 30×24 hours ago.

## Why this is one chain with one authority

Information warned (6543576195) that running #250's `ingest` and #252's
`poll` side by side gives two checkpoints that can disagree after a crash.
This runner has a single source of truth:

- **Journal records** are numbered per stream (1, 2, 3, …). A record is either
  a byte segment or a note (`bootstrap-skip`, `replaced`, `truncated`,
  `incomplete-utf8-tail`). The file name holds the stream, sequence number,
  source inode and byte range, the **UTC observation day** and the full
  SHA-256 of the content.
- **The checkpoint** only says how far the journal has been adopted. A record
  published just before a stop is adopted on restart, so it is never copied
  twice. A record that was never published is simply read again, and takes the
  day of the poll that finally publishes it.
- **Daily archives** are built only from validated records: the sequence must
  have no gaps, segments must continue each other byte for byte, and every
  hash must match. Sealing never reads the source and never uses a second
  offset.

#252's own fixture is not chained in: its 64-byte, day-less segments cannot
say which day a byte belongs to once a crash intervenes. Its tests, and those
of #249–#251, still run unchanged in this workflow as regression.

**Reused from #249 directly (imported, not copied):** `archive_filename` and
`parsed_filename` (archive names), `plan_increment` (classifying each
observation as bootstrap, append, unchanged, replaced or truncated), and
`ArchiveRecord` with `retention_candidates` (the 30×24h retention plan).

## Information's six source/time/encoding requirements

| Requirement | How it is handled | Test |
|---|---|---|
| No invented cross-stream order | One archive per stream per day; no merged file | `test_streams_stay_separate_and_labelled` |
| Split UTF-8 across polls or midnight | A segment never ends inside a codepoint; an incomplete tail is held until the next poll | `test_split_utf8_across_polls`, `test_split_utf8_across_midnight` |
| Idle UTC midnight, delayed append | Idle days close with an `idle` manifest entry and no file; late bytes go to the day they were first observed | `test_idle_day_closes_and_delayed_append_goes_to_observation_day` |
| UTC clock changes | Backwards time fails closed (durable across restarts); forward jumps seal idle days; a jump over 62 days fails closed | `test_clock_moving_backwards_fails_closed`, `test_clock_forward_jump_...` |
| Role-specific sources | Only World out, World err and Auth native; Auth is labelled "NOT a PTY console transcript"; World err is labelled "not a crash diagnosis" | `test_only_world_out_err_and_auth_native` |
| Explicit bootstrap skip | Existing bytes are skipped and the count is recorded | `test_bootstrap_skips_history_and_says_so` |

Timestamps in the archives are **observation days, not event times**. An
archive's bytes are the source bytes unchanged. **The runner does not promise
that every `.txt` is valid UTF-8**: it promises the raw source bytes are kept
and that invalid UTF-8 is visibly flagged. A `.txt` is valid UTF-8 only when
its entry says `utf8_valid: true`. If a source ends inside a UTF-8 sequence and
does not grow, the bytes are kept as they are and flagged (`utf8_valid: false`,
an `incomplete-utf8-tail` note and the `encoding` label); they are never
repaired, replaced or rewritten. Whether a production collector should instead
hold back or quarantine such bytes is an open design decision.

## Failure points tested (each resumes with no lost and no duplicated byte)

| Stop point | Test |
|---|---|
| Before a journal record is published | `test_stop_before_record_publish` |
| After the record, before the checkpoint | `test_stop_after_record_publish_before_checkpoint` |
| Checkpoint written but not published | `test_stop_before_checkpoint_publish` |
| After the checkpoint | `test_stop_after_checkpoint` |
| During the very first (bootstrap) poll | `test_stop_during_bootstrap` |
| **Between publication and daily sealing** | `test_stop_between_publication_and_daily_sealing`, `test_seal_before_adoption_still_archives_each_byte_once` |
| Before the archive file is published | `test_stop_before_archive_publish` |
| After the archive, before the manifest | `test_stop_after_archive_publish_before_manifest` |
| During retention, after unlink | `test_interrupted_retention_resumes_without_touching_anything_else` |
| Full disk while writing (injected `ENOSPC`) | `test_injected_full_disk_fails_visibly_and_loses_nothing` |

## Fails closed, or shows a visible gap

- **Fails closed:** symlinked source; source with more than one hard link;
  unsafe source names (`../`, absolute, hidden, nested); two streams mapped to
  the same source file; unreadable source;
  a second runner on the same workspace (lock); a root that is not the
  runner's own disposable workspace; a corrupt or missing journal record; a
  tampered checkpoint.
- **Visible gap:** a replaced source (new inode) or a truncated source is
  recorded as a note in that day's provenance, saying the old unread tail may
  be missing.
- **Startup cleanup:** a restart removes only this runner's own unpublished
  `*.pending` files; any other file is left alone.

## Retention

Retention only looks at names listed in the signed manifest and acts only when
#249's planner agrees. Each archive is re-checked first, opened relative to
the archive directory without following links: same device and inode, a
regular file, one hard link, and unchanged SHA-256. **The provenance sidecar
gets the same check** (its device, inode and SHA-256 are recorded at sealing).
A file at the sidecar's name that is not the one this runner wrote is left in
place and noted (`sidecar_kept`), including across an interrupted retention
run. A check-then-unlink race remains; a real host adapter would need more
than this synthetic fixture provides. Proven untouched:
`Crash-History.txt`, crash reports, user `.txt` files, a look-alike archive
name that is not in the manifest, the source logs, an archive edited in
place, an archive replaced by a symlink, a hard-linked archive, a manifest
entry pointing outside the archive directory, and a foreign file (replaced or
edited in place) at a sidecar's name. An archive exactly 30×24h old is kept.

## Release blockers (tests pass by showing the gap is NOT solved)

| Blocker | Test |
|---|---|
| A same-inode, same-size rewrite is not detected | `test_BLOCKER_same_inode_same_size_rewrite_is_not_detected` |
| Truncate-then-regrow past the old offset before a poll reads the wrong bytes with no gap noted | `test_BLOCKER_truncate_then_regrow_...` |
| No Authserver PTY capture; native log only | `test_BLOCKER_no_auth_pty_capture` |
| Unread tail of a rotated (old) inode is lost | `test_BLOCKER_unread_old_inode_tail_is_lost_after_rotation` |

Also not covered by any test here: real PM2 or tmux capture, real disk quota
(only `ENOSPC` is injected), power loss and real `fsync` guarantees,
multi-host or network filesystems, cooperation with PM2 log rotation, bytes a
producer never flushed, and any authenticated crash or exit-reason diagnosis.
Stream text is never treated as proof of a crash, an exit code or a shutdown
reason.

## Files

- `tests/f15_integrated_disposable_runner.py`: the runner (test fixture).
- `tests/test_f15_integrated_disposable_runner.py`: 48 end-to-end tests.
- `tests/f15_integrated_runner_mutants.py`: 12 must-fail mutants.
- `.github/workflows/naxx-f15-integrated-disposable-20261031.yml`: runs the
  inherited 38 + 29 + 10 + 24 tests, the 48 new tests (no skips on the
  non-root runner) and the mutants, and checks the added-path scope.

Synthetic success is not operational F15. Exact-head CI, source review,
failure-point coverage, rollback and backups, and separate owner acceptance
are all required before even proposing a controlled host test. The owner's
gate for any game or host pilot remains P1 Warlock, P2 Hunter ammo, P3 F15
and P4 human loot, all ready together.

## Review revision (31 Oct 2026)

- Information (#256, 6544412290): retention deleted any regular single-link
  file at a sidecar's name. The sidecar's identity is now recorded and checked
  like the archive's; a foreign file is kept. Tests:
  `test_foreign_file_at_the_sidecar_name_is_kept`,
  `test_foreign_sidecar_survives_interrupted_retention`.
- CS01 (#143, 6544357951): source names must be distinct
  (`test_two_streams_cannot_share_one_source_file`), and the UTF-8 wording now
  says "raw bytes kept, invalid UTF-8 flagged", not "every `.txt` is valid
  UTF-8".
- Two new must-fail mutants cover both fixes.
