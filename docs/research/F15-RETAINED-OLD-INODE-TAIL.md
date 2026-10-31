# F15 — retained old-inode tail after fake PM2 rotation

**Owner:** CosmicCuddle. **Maintenance integration:** CS01.
**Status:** DRAFT, test-only, no installed service, no real PM2/World/Auth logs accessed.

**Stack:** [source-admission #257](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/257) → [external-file bridge #258](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/258) exact parent `c908304ff7248faf852f2e61f16dbe4bc08ce3f2` → this separate DRAFT. The earlier Claude #256 and every ancestor feature implementation remain untouched.

## Narrow improvement

Previously #258 reopened each approved external filepath on every poll and correctly **stopped** when a new inode replaced its name. The old file's unread tail was lost to this particular reader after a rename.

New isolated `tests/f15_retained_old_inode_poll.py` inherits the exact existing `ConsentedSourcePoll` and captures a **read-only original descriptor** for each of three explicitly approved synthetic external files at admission time. Each later poll duplicates that *original* descriptor; it never follows or adopts the new named inode. Thus, after a fake PM2 log rename, a caller can still read bytes appended to the original inode, even if its old pathname is subsequently removed. The inherited journal/checkpoint/UTC seal/retention logic is unchanged. Source descriptors are closed on `close()` and on failed construction; no source writes, redirection, second cursor or new journal authority.

`source_name_status` may report same original inode, replaced path, or missing/unsafe pathname. These are **observations only**; they do NOT prove that the previous writer has finished appending. A retained open descriptor allows reading what exists *while the test process is alive*; it cannot preserve that descriptor across a process restart or certify complete history. Source identity remains caller-supplied and untrusted until separately authorised host verification.

## Acceptance matrix

Synthetic fake-file tests (not owner logs): three distinct pinned descriptors; normal append; rename-and-append-old captured exactly once; new-path file excluded; unlinked old inode + separately open fake writer captured; symlink new name not followed; restart against new inode refused; simulated publish-before-checkpoint crash recovered on the same open process; unchanged single journal; unaffected stdout/stderr/Auth independence; added hardlink rejected; close prevents reuse; input bytes untouched; old writer continuing after an apparently empty read does not indicate end-of-stream.

The child branch changes **three new files** (retained reader, its tests, this memo) plus a new CI workflow and **one inherited CI-only one-step scope change** in `.github/workflows/naxx-f15-consented-source-poll-20261031.yml`. That pre-existing #258 frozen four-path assertion is constrained to its own branch. All inherited #257 and #258 Python tests and original #256 synthetic suites remain active; the child CI byte-compares this exact inherited one-step conditional.

No `src/`, `conf/`, `data/`, `tools/`, executable Worldserver, Authserver, Playerbots, Individual Progression, addon, SQL, DBC, host, source log, existing script/test code or production config is altered.

## Explicit remaining NO-GO

**No automated switch to new log inode.** A correct production rotation protocol must demonstrate old-writer quiescence and a non-duplicating next-file handoff, survive collector crashes where only old filename or fd is lost, recover old rotated tail where possible, support a persistent and secure archive location instead of `TemporaryDirectory`, and keep disk/quota/permissions/owner data safe. A momentary zero bytes from the old inode does **not** prove the writer is finished.

Still absent: operational PM2 lifecycle, Auth full PTY, cross-stdout/stderr timeline, crash-vs-stop authority, real power loss/fsync and low-disk tests, correct 30×24h owned-file retention without pathname race, and owner-config/source/backups validation. An Auth native file cannot be called a complete Auth console transcript. **F15 P3 is not test-ready on the owner host**, and P1/P2/P4 unified owner hold remains. No merge or deployment approval is inferred.

**Rollback:** discard the unmerged review branch/PR. It has not changed external host data.
