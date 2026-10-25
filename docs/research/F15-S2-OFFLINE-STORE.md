# F15 S2 — Offline crash-report publisher (draft, **not a server monitor**)

**Priority:** HIGH, owner requires F15 to be completed. **Scope:** isolated S2 host-independent prototype on CS01's own branch. It is not ready for installation, not an end-to-end service, and does not resolve the actual owner launcher dependency.

## What exists

- `tools/f15/offline_store.py`: Python 3 POSIX-only immutable crash report persistence core. Accepts **caller-supplied verified actual-child death records**; cannot discover or verify deaths itself.
- `tests/test_f15_offline_store_s2.py`: 23 synthetic tests in a private temporary directory, including real multi-process file locking and same-event duplicates. No actual Worldserver/Authserver runs.
- `.github/workflows/f15-offline-store-s2.yml`: exact-head pinned Actions test, no artifacts, host adapters, service edits, root path, DB, AzerothCore, core/PB/IP or module C++ changes.

The storage design follows the reviewed F15 S1 architecture from [draft #106](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/106), exact `50dc668cb3054c23af0889e6512f61f4be919a4c` (CS02 and CS03 S1 source PASS).

**Preserved owner production destination (NOT created):** `/root/cosmic_core/logs/Crash Logs/`. This code deliberately receives only an existing, absolute, private output directory; tests use temporary directories and never this live path.

## Verified synthetic contract, not yet approved production behavior

1. Identity: hostname/boot/service/invocation/real-child-PID/verified UTC **start** time; the *observed exit time* is not a dedup key. Stable UUIDv5 yields deterministic same-event filename.
2. Classification: callers must declare verified unexpected actual-child death. Planned clean exits, planned exit code 2 and uncertain GDB wrapper statuses do not count. Verified later fatal signals after planned restart intent still count.
3. Immutable text: output is a never-overwritten UTF-8 `*-crash-...txt` containing schema, UTC times, observed exit evidence and the mandatory exact cause label `Crash cause: Unknown — further investigation required`. Strict input allowlists; no arbitrary full private journal dump.
4. Durability: POSIX `link(temp, final)` prevents replacement; flushed/fsynced temp and directory; a cross-process `flock` serializes publishing and history rebuild.
5. Recovery: `Crash-History.txt` is a **derived** atomic `os.replace` index of finalized, SHA256-validated, filename- and identity-validated individual reports; a bad/incomplete file is excluded. Final report remains if index write is interrupted.
6. Keeps worldserver/authserver counts separate and histories sorted by UTC, handling repeated wall-clock hours around UK daylight-saving changes.

## Deliberately NOT implemented — stop gates

- **No actual supervisor adapter** (AzerothCore `starter`, GDB, systemd, tmux, custom wrapper, PM2) or current server monitoring. Actual launcher, GDB flag, permissions and restart policy remain UNKNOWN. Never derive process signal from wrapper status; pinned GDB-enabled starter can mask exits to zero.
- **No approved privileged /root broker**. Private leaf directory verification is a preliminary check only; parent-chain symlink/permissions and TOCTOU race handling need security review before elevated deployment.
- **No restart/status sidecar**, attachments, redaction of arbitrary logs, error-burst watcher, time-zone-local presentation or actual process reaping. The initial report always says restart is unverified; those features require further S2 stages.
- **No real-server stop/crash/restart**, simulated service installation, database reads/writes, root access, shell execution, CI upload, merge or feature activation. This code MUST NOT be pointed at the owner's live path until separate S5–S7 authorization and review.
- Linux-only `fcntl` and hard-link atomicity require local supported filesystem semantics; NFS/remote filesystem portability not proven. Untrusted directory path handling is not production hardened.

## Exact offline test

```bash
python3 -m unittest discover -s tests -p 'test_f15_offline_store_s2.py' -v
```

A successful test establishes **S2/S3 simulated storage primitives ONLY**, not a functioning external crash reporter. Outstanding work: confirm actual installed supervisor read-only; implement adapter that produces *verified actual child* death events, no false positives and full restart preservation; new security and failure injection tests; separate independent reviews; owner-approved backups, staged test and production release.

Grok is on an owner-reported break: do not assert new Grok review. Claude may independently review the new draft while maintaining its other branches. Keep F15 ACTIVE/HIGH in master #28 and coordination #48.
