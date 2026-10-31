# F15 — consented external-file polling into disposable journal (DRAFT / test-only)

**Owner:** CosmicCuddle. **Integration:** CS01 Server-Side-Maintenance.  
**Base:** [F15 source-admission DRAFT #257](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/257) exact `31107fb9400a57e56238cdca8a0911cb08c077b7`. This branch is **stacked** on #257 and therefore indirectly on Claude's untouched [synthetic #256](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/256) and the #249–#252 research chain.

**Not installed. Not authorised for execution on CosmicCuddle's live host. Not a production collector.** No CLI/daemon, launcher/service, scheduler, PM2/tmux invocation, remote source, runtime Core, or owner-host integration.

## Narrow advancement over #257

#257 verifies *metadata* only for a supplied World PM2 stdout/stderr pair and explicitly named Auth **native log**. This draft adds a **caller-invoked read-only file-descriptor input seam** that deliberately **does read log bytes** from the three separately authorised paths. Its only downstream writer is the existing `IntegratedRunner`, which refuses a workspace other than its own `tempfile.TemporaryDirectory`. This is a disposable end-to-end test of external-file bytes → exactly one existing journal/checkpoint → separate UTC observation-day text archives; it is not a service or operational log capture.

- `tests/f15_consented_source_poll.py` inherits the #256 `IntegratedRunner` and changes **only** `_open_source`. The inherited `poll`, `_adopt`, `_checkpoint`, `seal_through`, and retention functions remain unchanged. No second independent capture offset or persistent spool is introduced.
- Given caller-supplied PM2 **JSON snapshot**, exact expected World executable/name, explicit Auth *native* source and separately approved absolute source roots, first use #257's three-file admission. At every poll, open the actual file again by descriptor-relative `O_NOFOLLOW/O_DIRECTORY` path walk and final `O_RDONLY/O_NONBLOCK`, verify unique regular file and original device/inode. No shell, `pm2 jlist` call, redirection, seek/write/truncate of the sources.
- If the file rotates/replaces at its original pathname, **stop and require operator review**; do not silently begin at the new inode and imply the unread old tail was captured. Restart against a recorded old journal identity likewise refuses the new inode. Same-inode truncation is visible through the existing runner's gap notes.
- On the first poll, the existing source bootstrap explicitly **skips pre-existing bytes**; only later observed additions are eligible for capture. Whole-file/PTY completeness is **not** claimed.

## Disposable test plan

The new `tests/test_f15_consented_source_poll.py` defines 16 cases over temporary *fake* PM2 and Auth files: three independently captured streams and separate archives, one inherited journal/checkpoint, bootstrap skip, crash after segment publication/before checkpoint and exact-once adoption, no external-file mutations, symlink swaps, inode rotation and restart rejection, same-inode truncation note, hardlink, stopped/wrong PM2 process, disallowed source directory, nonregular Auth source, World/Auth physical inode alias and failed-admission non-mutation. These are **test specifications** until a current-head job actually succeeds; the 15 metadata-only #257 tests should also run as regression.

Exact expected changed paths on this child branch: two new Python test-only files, this memo and one new pull-request CI workflow. **No changes to any ancestor C++/SQL, module/runtime source, configs, prior tests/fixtures, original workflows or Claude's branch.** The workflow requires a four-added-file diff and runs tests only on GitHub-hosted disposable files.

## Release blockers remain

No real PM2 process was queried and none of the owner's installed log paths/configuration/permissions are verified. The PM2 JSON snapshot is an **untrusted self-description**, not attestation; an Auth path that points to a regular file is not proof of Auth log completeness or authenticity.

This prototype requires an explicit caller and ephemeral workspace; it cannot run continuously, survive destruction of the workspace, or provide accessible next-day archives. It does not handle a rotated old inode's unread tail, same-inode same-size rewrites with preserved timestamps, quick truncate/regrow, Auth tmux PTY, unflushed source bytes, real quota/power loss, secure host permissions, unattended rotation/restarts, crash-vs-stop attribution or race-free production deletion. Observation time ≠ event timestamp; stdout/stderr cannot be merged into a proven original chronology. **P3 remains not operational**, and the owner's P1–P4 coordinated test gate remains unchanged.

**Preservation/rollback:** discard this unmerged isolated review branch/PR; no live state exists to restore. Before any separate owner-authorised pilot, collect minimal redacted actual host facts, evaluate log retention/disks, effective configs, installed commits and restorable backups, and agree a reviewable collector/lifecycle/rotation plan. Never place raw PM2 JSON, log contents, account data or secrets into an Issue.
