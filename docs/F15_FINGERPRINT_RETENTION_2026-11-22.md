# F15 sampled executable identity and launcher receipt compatibility

Owner: CosmicCuddle. Source-only child of PR350061a22a4ac6a6b8a5c570b0c6c81a2789fcbe898.

## Prelaunch file sample

Resolve command[0] through the current PATH and sample the resolved regular file
through a descriptor. SHA256 is emitted only when size and device/inode/mode/
mtime/ctime remain stable across the read. Cap512MiB; nonregular, oversized,
unavailable or changing samples are UNKNOWN. No command arguments/environment or
exception text are captured. Report includes sampled executable path/hash, raw
bundle includes executable-fingerprint.json; operator-declared build/source fields
remain distinguished from verified identity. Sampling does not block a later
explicit child launch merely because identity is UNKNOWN.

This is a prelaunch regular-file sample, not kernel exec identity. A file/path can
change after sampling. For an interpreter command it fingerprints the interpreter,
not script or libraries. Large-file reads may add startup latency; no hard real-time
bound is promised. Do not infer the owner's binary/source/version from fixtures.

## Launcher receipt schema correction

Launcher receipts add boolean stop_escalated. Existing shared _receipt rejected
all extra fields, blocking launcher raw archive/audit/retention. Permit only this
one optional boolean for EXIT_FIELDS; keep legacy exact schemas, unknown-field
refusal, receipt identity checks and retention ownership unchanged. stop_escalated records a kill request, not proof of causal signal delivery: the
child can exit between poll and signal. The report now says SIGKILL requested;
observed wait status remains authoritative. This does not
grant new deletion authority. Completed raw source logs stay untouched.

Tests exercise the actual historical reader's rejection, the current reader,
actual supervised launcher archive/audit/expiry, preserved source bytes and invalid
extension refusal. Fingerprint tests cover exact digest, oversize no-read, changing
file, unavailable/FIFO and private report/bundle integration with UNKNOWN gaps.
Exact compiler/runtime/results belong to PR/review queue. No host services, real
Crash Logs, DB/config/SQL/DBC/client changes. Rollback reverts source child and
preserves raw files/receipts; historical code still cannot process extended launcher
receipts, so do not erase that evidence to make an older reader succeed.
