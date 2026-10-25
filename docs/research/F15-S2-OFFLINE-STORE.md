# F15 S2 — Offline crash-report publisher (draft, **not a server monitor**)

**Priority:** HIGH, owner requires F15 to be completed. **Scope:** isolated S2 host-independent prototype on CS01's own branch. It is not ready for installation, not an end-to-end service, and does not resolve the actual owner launcher dependency.

## What exists

- `tools/f15/offline_store.py`: Python 3 POSIX-only immutable crash report persistence core. Accepts **caller-supplied verified actual-child death records**; cannot discover or verify deaths itself.
- `tests/test_f15_offline_store_s2.py`: 38 synthetic tests in a private temporary directory, including real multi-process file locking and same-event duplicates. No actual Worldserver/Authserver runs.
- `.github/workflows/f15-offline-store-s2.yml`: exact-head pinned Actions test, no artifacts, host adapters, service edits, root path, DB, AzerothCore, core/PB/IP or module C++ changes.

The storage design follows the reviewed F15 S1 architecture from [draft #106](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/106), exact `50dc668cb3054c23af0889e6512f61f4be919a4c` (CS02 and CS03 S1 source PASS).

**Preserved owner production destination (NOT created):** `/root/cosmic_core/logs/Crash Logs/`. This code deliberately receives only an existing, absolute, private output directory; tests use temporary directories and never this live path.

## Verified synthetic contract, not yet approved production behavior

1. Identity: hostname/boot/service/invocation/real-child-PID/verified UTC **start** time; the *observed exit time* is not a dedup key. Stable UUIDv5 yields deterministic same-event filename.
2. Classification: callers must declare verified unexpected actual-child death. Planned clean exits, confirmed Worldserver planned exit code 2 and uncertain GDB wrapper statuses do not count. Authserver exit code 2 is not assumed planned. An independently established unexpected signal (including SIGXFSZ) is preserved; confirmed planned SIGTERM/SIGHUP/SIGINT is suppressed. Verified later fatal signals after planned restart intent still count.
3. Immutable text: output is a never-overwritten UTF-8 `*-crash-...txt` containing schema, UTC times, observed exit evidence and the mandatory exact cause label `Crash cause: Unknown — further investigation required`. Strict input allowlists; no arbitrary full private journal dump.
4. Durability: POSIX `link(temp, final)` prevents replacement; flushed/fsynced temp and directory; a cross-process `flock` serializes publishing and history rebuild.
5. Recovery: `Crash-History.txt` is a **derived** atomic `os.replace` index of finalized, SHA256-validated, filename- and identity-validated individual reports; a bad/incomplete file is excluded from verified counts **but is explicitly listed in an unverified/modified-files warning**. Final report remains if index write is interrupted; operators must not edit immutable reports.
6. Keeps worldserver/authserver counts separate and histories sorted by UTC, handling repeated wall-clock hours around UK daylight-saving changes.

## Additional S2 filesystem safeguards

- Open the absolute directory one component at a time using `O_DIRECTORY|O_NOFOLLOW`, keeping a pinned descriptor for the private output leaf.
- Use directory-relative report, index and lock operations. Later symlink swaps and renames of the original path cannot redirect an already-opened store's writes.
- Reject symlinked ancestor components, report-file symlinks, unsafe lock metadata, corrupt report hashes and conflicting filenames.
- New synthetic cases exercise ancestor symlinks, renamed/replaced original directories, hostile history-index symlinks, simulated index failure after final report publication, report modification warnings, realistic unlisted fatal signals, Authserver exit-code 2, modified-parent security and mocked foreign directory ownership.
- **Security limitation:** the prototype is not a privileged adapter or proof against every attacker who can control mounts, ancestor ownership, path traversal during initial open, or trusted evidence records.

## Claude's independent S2 review and the response

Claude independently reviewed the 29-case head and returned **CONDITIONAL, three should-fix items**: previously unlisted fatal signals, silent disappearance of tampered report entries from counts, and missing owner validation for the final directory. The latest revision addresses those items and also narrows the Worldserver-only meaning of exit code 2.

`Crash-History.txt` now distinguishes **verified incidents** from **unverified or modified files**. Invalid files remain on disk and are listed by name with a warning, but are NOT included in trusted totals. If the sole authoritative file was edited, the true historical contents are unrecoverable from its modified bytes alone: do not misrepresent verified totals as all real deaths. Keep human notes separate. Restart outcomes, error-burst reporting, actual supervisor events, privileged broker and safe cleanup of stale temp files remain open.

## Deliberately NOT implemented — stop gates

- **No actual supervisor adapter** (AzerothCore `starter`, GDB, systemd, tmux, custom wrapper, PM2) or current server monitoring. Actual launcher, GDB flag, permissions and restart policy remain UNKNOWN. Never derive process signal from wrapper status; pinned GDB-enabled starter can mask exits to zero.
- **No approved privileged /root broker**. Pinned directory-FD traversal rejects symlinked ancestors and anchors report operations. It checks the private leaf is owned by the writer and rejects untrusted or group/world-writable ancestors (except root-owned sticky parent, e.g. /tmp). Race-free privileged installation, mount changes and broker hardening still require independent review before elevated deployment.
- **No restart/status sidecar**, attachments, redaction of arbitrary logs, error-burst watcher, time-zone-local presentation or actual process reaping. The initial report always says restart is unverified; those features require further S2 stages.
- **No real-server stop/crash/restart**, simulated service installation, database reads/writes, root access, shell execution, CI upload, merge or feature activation. This code MUST NOT be pointed at the owner's live path until separate S5–S7 authorization and review.
- Linux-only `fcntl`, pinned directory-FD operations and hard-link atomicity require supported local filesystem semantics; NFS/remote filesystem portability not proven. Untrusted path, privileged operation and mount behavior are not production hardened.

## Exact offline test

```bash
python3 -m unittest discover -s tests -p 'test_f15_offline_store_s2.py' -v
```

A successful test establishes **S2/S3 simulated storage primitives ONLY**, not a functioning external crash reporter. Outstanding work: confirm actual installed supervisor read-only; implement adapter that produces *verified actual child* death events, no false positives and full restart preservation; new security and failure injection tests; separate independent reviews; owner-approved backups, staged test and production release.

Grok is on an owner-reported break: do not assert new Grok review. Claude may independently review the new draft while maintaining its other branches. Keep F15 ACTIVE/HIGH in master #28 and coordination #48.
