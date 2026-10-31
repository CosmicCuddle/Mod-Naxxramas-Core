# F15 — manually reattach a rotated old file using the existing journal (disposable proof only)

**Owner:** CosmicCuddle. **From:** CS01 Maintenance. **Status:** DRAFT, noninstalled, no owner-host access or deployment.

## Frozen dependencies

This narrow test-only child is stacked on [F15 #259](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/259), exact parent `8259071de5b7c1604f18a441999b5bfa3577ba8e`. No edit to parent #259, #258, #257 or Claude's #256, which contain the only existing disposable journal/checkpoint/sealing implementation. No extra journal or second cursor.

## New limited behavior

`tests/f15_manual_old_inode_recovery.py` reopens a **caller-specified exact old pathname**, bounded by a separately specified approved root, after closing the original **test reader**. It does **not** scan for rotating files, follow the newly created filename, take live PM2 JSON, invoke a shell, or touch service processes. Reopen is allowed only when:

- All three stream names are explicitly present and the disposable workspace has the original signed journal marker and previous checkpoint.
- Each stream has at least one actual published and checkpointed **byte segment**, not merely a bootstrap note. The earlier bootstrap explicitly skipped history; it cannot attest the skipped bytes.
- The source is reached through the existing directory-relative no-symlink open, remains a regular file with one hard link, and matches the journal's **device/inode/offset**.
- The final contiguous journal segment at that checkpoint matches the bytes at the same offset in that source file; a truncation, changed anchor, unexpected old inode or shared physical stream fails closed.
- The source descriptor remains read-only. New post-recovery bytes go through **the exact existing** `IntegratedRunner.poll`, journal/checkpoint and UTC-day seal.

This is **manual historical recovery of an old named inode**, not a general solution to automatic log rotation.

## Negative and positive verification

`tests/test_f15_manual_old_inode_recovery.py` specifies **14 fake-file tests**: renamed old inode plus appended tail, three independent stream recoveries, rejection of new inode, deleted old file, symlink/hardlink, modified last journalled bytes, truncate below checkpoint, bootstrap-only journal, wrong source root, missing/extra stream keys, bad candidate pair, preserved original source bytes and timestamps, and a late old-writer append after an idle poll (no automatic next-file handoff).

The test restarts only the **Python reader object inside the same disposable workspace**, not a production collector across process crashes or system reboot. Journal and archives are under a disposable `TemporaryDirectory`, not available on the owner's host or as durable daily archives.

## Explicit remaining failure cases

- If the old inode was **unlinked and all old file descriptors lost**, no manual filename can recover its unread bytes. Source code cannot conjure them; report a gap.
- Same-device/inode identification and matching **last segment** cannot authenticate the entire source history. Inode reuse and earlier same-size rewrites may evade this limited check; this proof does not certify total fidelity.
- No proof of when old writer stops, no automatic transition to next inode, no exact stdout/stderr chronology, no Auth tmux PTY parity, no persistent service, no real crash/stop evidence, no host permission/quota/power-loss or atomic race-safe 30-day retention.
- No install, scheduler, owner PM2 read, auth tmux operation, Worldserver changes, SQLite/MySQL/SQL, config, backups, characters or gameplay tests. The code **will read supplied file bytes if explicitly called**, therefore must never be pointed at owner's sources without separate permission.

## Rollback / readiness

The new draft may be closed and branch discarded without affecting installed code or host data. The owner still requires P1 + P2 + **operational** P3 + actual human H1/H2 P4 ready for **one** approved future test. This proof does not satisfy P3's operational gate or owner approval.
