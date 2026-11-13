# F15 pre-overwrite live-log snapshot — 2026-11-13

**Owner:** CosmicCuddle  
**State:** isolated DRAFT; source/tests only; not installed in any launcher/rotation path.  
**Parent:** F15 read-only host probe DRAFT #304 head `03aad73cbd1593927e00e19375df8085c5e85a96`.

## Owner requirement

Before a live server log under `/root/cosmic_core/logs/` is truncated,
rotated or overwritten, its previous contents must be preserved. F15-owned
archived server logs and crash artifacts are retained for 30 days.

## This slice

`f15_preoverwrite_log_snapshot.py` copies an existing regular log file into an
independent private archive copy. It never truncates, renames, unlinks, rotates
or overwrites the source.

A snapshot records:

- UTC observation time;
- original absolute source path;
- device/inode/size/mtime identity;
- SHA-256 of copied bytes;
- independent snapshot filename;
- explicit 30-day retention metadata.

The archive directory must be mode 0700; snapshots/manifests are mode 0600.

The directory helper scans only direct regular files in the selected log root.
It excludes `Crash Logs` and the archive destination itself to avoid recursive
archiving. Other subdirectories are ignored unless separately approved.

## Continuity and overwrite safety

The source is opened without following symlinks. Hardlinked sources are
refused. The copy is written to a collision-safe pending file.

After all bytes are copied and fsynced, F15 rechecks the source's
device/inode/size/mtime. If those facts changed during copying, publication is
refused and the pending artifact is retained for manual review. The source
remains untouched.

This is intentionally conservative: a torn snapshot must never be labelled a
complete pre-overwrite archive.

## Guarantee boundary

This helper alone cannot guarantee it runs before an unrelated external
process truncates a file. The final production deployment must invoke it from
the actual pre-rotation/pre-start path that owns the overwrite, or otherwise
prove that the live logger only appends and the journal collector has already
captured every byte.

Therefore the exact Worldserver PM2/Authserver launcher/logger/rotation
topology must be verified before installation.

## Retention

Owner decision: retain archived log snapshots for 30 days. Crash reports and
crash evidence are also retained for 30 days. Expiry may remove only F15-owned
artifacts; active original logs are never retention targets.

The deletion implementation is a separate child slice so snapshot creation and
retention authority can be reviewed independently.

## Custom Modifications Register — F15-PREOVERWRITE-LOG-SNAPSHOT-20261113

| Field | Record |
| --- | --- |
| Intended behavior | Preserve independent copies of live log bytes before an approved overwrite/rotation/start path replaces them. |
| Owning component | Mod-Naxxramas-Core F15 operational tooling. |
| Affected paths | `scripts/f15_preoverwrite_log_snapshot.py`, `tests/test_f15_preoverwrite_log_snapshot.py`, this note. |
| Parent | #304 head `03aad73cbd1593927e00e19375df8085c5e85a96`. |
| Dependencies | POSIX regular-file semantics; final launcher/rotation hook not yet installed. |
| Config/SQL/DBC/client | None. |
| Risks/limits | Cannot guarantee pre-overwrite timing until connected to the actual overwrite owner; source mutation during copy fails closed; files >1 GiB are refused in this draft. |
| Tests | Focused disposable test source authored; no hosted Actions/live host tests. |
| Live status | DRAFT/uninstalled. |
| Rollback | Abandon child branch/PR; no live log is changed. |
