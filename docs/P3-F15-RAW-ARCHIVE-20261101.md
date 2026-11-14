# P3 F15 — opt-in, non-deleting archive of completed supervised World/Auth raw output

**Status: DRAFT development code, OFF unless an operator runs it.** Not merged,
not installed, not scheduled. CS01 assigned it (#143, 6563359476), and I
claimed it in 6563539649. The branch is a child of #280 (`deebd7b`); no
existing F15 script, workflow, C++ source or setting is changed.

## What it does

`scripts/f15_raw_archive.py` copies the raw console output of **completed**
runs started by the existing `f15_process_supervisor.py` into a separate
private archive. Nothing is ever deleted.

- **Dry run by default.** It validates the selected runs and prints a plan:
  service, observed exit kind, raw byte count, whether the run is older than
  30 days, and `would_archive` or `would_verify_existing`. It writes nothing,
  not even the destination's subfolders.
- **Copying is explicit.** `--archive-owned-completed` plus one `--run RUN_ID`
  per run the owner chooses. Every selection is validated before anything is
  copied.
- **What is copied:** `stdout.raw` and `stderr.raw` byte for byte, the
  `start.json` and `exit.json` receipts, and a `manifest.json` with each
  stream's SHA-256, size and source dev/ino, plus the service, exit kind,
  exit code and exit time.

```
<raw-archive-root>/runs/<run-id>/{stdout.raw, stderr.raw, start.json, exit.json, manifest.json}
```

## Safety rules (from the existing receipt layout)

A run is copied only if all of these hold. These are the same checks the
existing retention and storage-audit scripts use:

- the run id matches the supervisor's format, and both the run folder and its
  capture folder are existing private (0700) directories with no symlinked
  ancestors;
- `start.json` and `exit.json` are single-link regular files with the exact
  schema, matching service, paths and capture root;
- `exit.json` says `exit_observed` with `capture: complete_for_observed_run`
  and no capture error. **Unfinished runs and `fail_closed` captures are
  refused;**
- each raw stream is a private (0600) regular single-link file, and its dev and
  inode match the capture's `origin.json`. A replaced, symlinked or hardlinked
  stream is refused.

**Writing:**
1. The destination root must already exist, be private (0700), and be separate
   from (not nested with) the supervisor's output and capture roots. It is
   never created.
2. Each run is built in `.staging/<run-id>-<random>/`.
3. Sources are opened with `O_NOFOLLOW`; the open file must be the validated
   inode.
4. The SHA-256 is computed while copying. The source's size and modification
   time are rechecked after copying, and the copy is re-hashed.
5. The manifest is written and fsynced.
6. One atomic `rename` publishes `runs/<run-id>/`, then both folders are
   fsynced.

Archive files are 0600 and folders 0700.

**Repeats and interruptions:**
- Running it again for an archived run re-verifies the archive: its contents,
  manifest, the copy's digest, the source inode and the live source's digest.
  A match reports `already_archived` and changes nothing; any mismatch is
  refused for manual review.
- An interrupted copy leaves only its staging folder, never a half-published
  run. A rerun uses a new staging folder. Leftovers are counted in
  `stale_staging_entries` and **not removed**.

**Never:**
- delete, truncate, rotate or rewrite originals or receipts;
- touch PM2, tmux or systemd;
- install cron, or change the existing archive retention;
- start or stop any process;
- put log contents in its report;
- treat a nonzero or signaled exit as a proven engine crash.

## Tests

`tests/test_f15_raw_archive.py` has 20 tests. They run in disposable temporary
folders, using real `f15_process_supervisor.supervise` child processes.

| Area | Checked |
|---|---|
| Default dry run | writes nothing; no log text in the report |
| Worldserver clean exit and Authserver nonzero exit | both archived byte for byte; manifest digests and inodes; modes 0600/0700; originals' bytes, inode, mtime and mode unchanged |
| Selection | only the selected runs are copied; empty or duplicate selections, a bad id and a nested destination are refused; a missing destination is refused and not created; a non-private destination is refused |
| Duplicate invocation | `already_archived`; no file is rewritten |
| Interrupted copy, then restart | nothing is published while interrupted; the restart archives; the stale staging is reported, not removed |
| Archive digest mismatch | refused |
| Symlinked or hardlinked archived receipt | refused before any byte is read |
| Forged manifest `exit_code` or `exit_time_utc` | refused |
| Source changed after archiving | refused |
| Symlink, hardlink or replaced-inode stream | refused; nothing published |
| Incomplete run, `fail_closed` capture | refused |
| 30-day boundary | informational flag only; the run is still archived and nothing is deleted |
| CLI | dry run unless `--archive-owned-completed` is given |
| Static check | no unlink, remove, rmtree, truncate, replace, chmod, process calls or `O_TRUNC`; does not import `subprocess`, `shutil` or `signal` |

`tests/f15_raw_archive_mutants.py` has 13 must-fail mutants of the real
script, all caught:
- incomplete run accepted;
- `fail_closed` accepted;
- origin inode not checked;
- archive digest not re-verified;
- live source not compared;
- dry run copies by default;
- wrong 30-day boundary;
- nested destination allowed;
- duplicate selection allowed;
- interrupted staging published;
- manifest `exit_code` not cross-checked;
- manifest `exit_time_utc` not cross-checked;
- archived receipt read following links.

## Custom Modifications Register — NAXX-CS03-P3-RAW-ARCHIVE

- **Owner:** CS03 (Claude). **Status:** DRAFT, not invoked by anything, not
  merged or deployed.
- **Source baseline:** CS01 combined DRAFT #280 `deebd7b68d2966ede6dc80a8da92d1351e4cb7eb`.
- **Files (all new):**
  - `scripts/f15_raw_archive.py`
  - `tests/test_f15_raw_archive.py`
  - `tests/f15_raw_archive_mutants.py`
  - `.github/workflows/f15-raw-archive-20261101.yml`
  - this document
- **Dependencies:**
  - Python 3;
  - the existing F15 `f15_process_supervisor.py` receipt and run layout;
  - `f15_supervised_retention` (`RUN_ID`, the receipt schemas, `_receipt`);
  - `f15_supervised_storage_audit` (`existing_private_dir`, `_raw_stat`,
    `_observed_exit`);
  - `f15_operator_collector.Refused`.
- **Risks:**
  - It needs at least as much free space as the selected raw output.
  - It assumes a POSIX filesystem where `rename` is atomic within the
    destination root.
  - It covers only runs made by the F15 supervisor, not PM2, tmux or installed
    host logs.
  - The owner's real paths, binaries and launch method are not verified.
  - The manifest proves byte identity of the copy, not that a run was a crash.
- **Not done (needs separate owner approval):**
  - deleting or rotating originals after a verified archive;
  - automatic or scheduled runs;
  - any retention for this archive.
- **Rollback:** revert this additive draft. Nothing is scheduled. Copies made
  during testing can be removed by the operator; the archiver itself never
  deletes anything.

## Results by level

| Level | Result |
|---|---|
| Local (Python 3, umask 022) | 20/20 tests and 13/13 mutants pass; the storage-audit and supervisor suites pass |
| Hosted | `f15-raw-archive-20261101.yml`. **Not yet run** |
| Owner host / real World/Auth | **none** |

## Review revision (1 Nov 2026)

CS01 (#143, 6564100860) found two gaps in re-verifying an existing archive:

1. **Receipts were read with `read_bytes()`, which follows a symlink.** The
   manifest and both archived receipts are now read through `_read_private`.
   It opens with `O_NOFOLLOW` and refuses anything that isn't a private
   single-link regular file before reading a byte.
2. **The manifest's `exit_code` and `exit_time_utc` were not compared with the
   source exit receipt.** Both are now checked.

The four new negative tests fail on the previous head `64d820e` and pass now.
Three new mutants cover the fixes.

## Finding outside this change (reported to CS01)

At #280, `tests/test_f15_supervised_retention.py::test_unfinished_child_is_skipped_with_no_data_change`
passes under umask 077 but fails under the common default 022. Its fixture
creates run folders with bare `mkdir()`, giving 0755, which the collector's
`private_dir` correctly refuses. No workflow currently runs that suite. CS01
fixed the fixture separately in #282; it is not part of this change.
