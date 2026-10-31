# F15 — manually reattach a rotated old file using the existing journal (disposable proof only)

**Owner:** CosmicCuddle. **From:** CS01 Maintenance. **Status:** DRAFT, noninstalled, no owner-host access or deployment.

## Frozen dependencies

This narrow test-only child is stacked on [F15 #259](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/259), exact parent `8259071de5b7c1604f18a441999b5bfa3577ba8e`. No edit to parent #259, #258, #257 or Claude's #256, which contain the only existing disposable journal/checkpoint/sealing implementation. No extra journal or second cursor.

## New limited behavior

`tests/f15_manual_old_inode_recovery.py` reopens a **caller-specified exact old pathname**, bounded by a separately specified approved root, after closing the original **test reader**. It does **not** scan for rotating files, follow the newly created filename, take live PM2 JSON, invoke a shell, or touch service processes. Reopen is allowed only when:

- Each of the three original stream names is explicitly accounted for as **either** an old-file candidate **or** a bootstrap-only quarantined stream; no stream is omitted or assigned both roles. The disposable workspace retains its original signed journal marker and journal/checkpoints.
- Every **recovered** stream has at least one actual published and checkpointed **byte segment**, not merely a bootstrap note. A quarantined stream must have exactly one original bootstrap-skip note and NO additional published records; the earlier bootstrap explicitly skipped history, so its bytes cannot be attested and its old source is never reopened.
- The source is reached through the existing directory-relative no-symlink open, remains a regular file with one hard link, and matches the journal's **device/inode/offset**.
- The final contiguous journal segment at that checkpoint matches the bytes at the same offset in that source file; a truncation, changed anchor, unexpected old inode or shared physical stream fails closed.
- The source descriptor remains read-only. New post-recovery bytes go through **the exact existing** `IntegratedRunner.poll`, journal/checkpoint and UTC-day seal.

This is **manual historical recovery of an old named inode**, not a general solution to automatic log rotation.

## Mixed quiet/anchored streams (reviewer finding, 31 October 2026)

Information [reviewed #261](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/261#issuecomment-6546934955) and noticed its original all-three-anchored prerequisite blocked legitimate stdout old-tail recovery when stderr or Auth had **only a bootstrap note**. The original fail-closed concern is valid: bootstrap-only history cannot authenticate even a last byte segment.

The revised manual test seam requires each of the three streams be **explicitly accounted for**. A stream is EITHER supplied as an anchored exact old filename/root OR separately named in `quarantined_quiet_streams`. Quarantine is permitted **only** when its complete original journal contains exactly one genuine bootstrap-skip record and the checkpoint matches it. The constructor checks the entire original published chain and refuses to quietly quarantine an already-captured stream or a segment published just before a simulated crash. The quarantined source is **never opened or polled**; `poll(quarantined)` fails closed. Quarantine is **not evidence that the stream remained silent after reader restart**, and any inherited idle UTC manifest entry is not proof of source completeness.

A single anchored World-out can therefore recover its own explicitly named old tail even when World-err/Auth-native are quarantined, with no extra cursor or next-file adoption. Real World/Err/Auth logging still requires separate complete-source operational design. This is a disposable reader-object proof only, not a validated host identity or collector process restart.

## Negative and positive verification

`tests/test_f15_manual_old_inode_recovery.py` specifies **20 fake-file tests**: renamed old inode plus appended tail, three independent stream recoveries, rejection of new inode, deleted old file, symlink/hardlink, modified last journalled bytes, truncate below checkpoint, bootstrap-only journal, wrong source root, missing/extra stream keys, bad candidate pair, preserved original source bytes and timestamps, and a late old-writer append after an idle poll (no automatic next-file handoff). Six additional mixed quiet/anchored tests cover explicitly quarantining one or two bootstrap-only streams, permitting anchored old-tail recovery without asserting quiet-stream completeness, rejecting silent omission or quarantine of an already captured stream, rejecting a segment published just before a simulated crash, and rejecting duplicate/unknown/overlapping quarantine lists.

The test restarts only the **Python reader object inside the same disposable workspace**, not a production collector across process crashes or system reboot. Journal and archives are under a disposable `TemporaryDirectory`, not available on the owner's host or as durable daily archives.

## Explicit remaining failure cases

- If the old inode was **unlinked and all old file descriptors lost**, no manual filename can recover its unread bytes. Source code cannot conjure them; report a gap.
- Same-device/inode identification and matching **last segment** cannot authenticate the entire source history. Inode reuse and earlier same-size rewrites may evade this limited check; this proof does not certify total fidelity.
- No proof of when old writer stops, no automatic transition to next inode, no exact stdout/stderr chronology, no Auth tmux PTY parity, no persistent service, no real crash/stop evidence, no host permission/quota/power-loss or atomic race-safe 30-day retention.
- No install, scheduler, owner PM2 read, auth tmux operation, Worldserver changes, SQLite/MySQL/SQL, config, backups, characters or gameplay tests. The code **will read supplied file bytes if explicitly called**, therefore must never be pointed at owner's sources without separate permission.

## Rollback / readiness

The new draft may be closed and branch discarded without affecting installed code or host data. The owner still requires P1 + P2 + **operational** P3 + actual human H1/H2 P4 ready for **one** approved future test. This proof does not satisfy P3's operational gate or owner approval.
