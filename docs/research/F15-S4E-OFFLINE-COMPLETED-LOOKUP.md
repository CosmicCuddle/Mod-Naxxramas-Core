# F15 S4e — OFFLINE completed restart lookup from immutable S3 sidecars

**IMMUTABLE-REPORT LOOKUP + NARROW TEMP-ALIAS CLEANUP / SOURCE MODEL / DRAFT ONLY. DO NOT MERGE OR INSTALL.**

## What this is

Original S4e #147 has four paths. **Part 24 follow-up [draft #149](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/149)** adds a targeted cleanup to this model, eight tests and this documentation update without changing S2/S3/S4 parent branches. This CS01-owned research draft is stacked on #142 S4d exact `d5b7782218bbfec4cd22bb59fa21c657c07c2155`, then #141 S4c, #140 S4b, #139 S4, #137 S3 and #136 S2. The original #147 added four paths: `tools/f15/offline_completed_lookup.py`, negative tests, source-only exact-head workflow and this review document. No parent contributor branch or main is modified.

The S4d offline state machine has an optional `finished_lookup` callback. A purely in-memory completed cache would permit replay after eviction or collector restart. This S4e model demonstrates a **read-only immutable result lookup with narrowly scoped unlink of abandoned matching private S2/S3 temporary aliases**, using the existing immutable `restart-*.txt` sidecar and its original S2 incident. For a valid completed attempt it returns `succeeded` or `failed`; for a never-used attempt on a **known verified immutable incident**, it returns `None`; unsafe files, unknown incidents or corrupted/ambiguous evidence cause `ValueError` and S4d fails closed.

## Exact evidence and safety boundaries

- Validates canonical incident UUID and sanitized bounded attempt name. Computes **the same UUID5 sidecar ID** as S3 without using an event timestamp. An arbitrary matching-looking filename is not enough.
- Uses S3's private, existing FD-anchored directory and shared writer lock, never a caller path re-resolution, root directory creation or log/network access.
- Rejects a missing/corrupted original incident rather than interpreting missing sidecar as permission to issue a restart. An existing original must also be private regular owned storage with exactly one link, except that one abandoned private same-inode `.f15-s2-<32 lowercase hex>` alias may be removed under the shared lock and pinned directory FD; otherwise fail closed.
- Existing sidecar is opened `O_NOFOLLOW|O_NONBLOCK`, must have one link (after any narrowly verified orphan-alias cleanup), private mode and current writer owner; then must pass the existing S3 canonical SHA and identity checks. Timestamp must not predate the original death or be implausibly in the future. Tampered, public, symlink, hardlinked, orphan or wrongly ordered sidecars **never** confirm success.
- Supports separately recorded Worldserver/Authserver and distinct attempts. Simulates completed success and failure across newly constructed collector and S3 store objects. A fresh S4d collector with this lookup rejects an already completed attempt.
- Does **not** publish a sidecar or invent `verified=True`, does not call any operating-system process API, and does not change the contents or counts of `Crash-History.txt`. The only permitted filesystem mutation is unlinking one independently verified stale private temp alias to a validated finalized record.
- Uses deliberately fabricated process IDs, crash records and PRIVATE temporary directories created by the hosted test suite only. It never touches the owner's actual `/root/cosmic_core/logs/Crash Logs/`.

## Critical limitations preventing operational acceptance

1. **This is an advisory immutable-outcome lookup (with narrow orphan cleanup), not a crash-safe atomic begin/finish protocol.** A lookup returning `None` and a concurrent writer completing the same attempt could race. The eventual producer must use one durable, authenticated and serialized begin/finish journal and reconcile lost state after a crash before declaring `succeeded`.
2. Existing S3 sidecar SHA is **not source authentication**. An attacker running as the writer could forge matching hashes. The real adapter must independently authenticate true kernel child termination, supervisor replacement and service readiness and preserve per-invocation identity.
3. The original #147 strict `nlink=1` check rejected interrupted S2/S3 `link(temp, final)` crashes with leftover temporary hardlinks. Follow-up #149 recovers **only** a matching, privately owned regular `.f15-s2-<32 lowercase hex>` alias of the validated final inode, under the same shared flock/FD, then requires `nlink=1`. Generic external links, symlinks, unrelated/private junk, public permissions and tampered final records still fail closed. New exact-head CI and independent peer review remain outstanding. Uncooperative same-UID actors and real power-loss fault injection are NOT proven safe.
4. The lookup insists on an already verified S2 original; a missing original isn't a fresh attempt. This is safe but can prevent processing after a directory/broker outage. The adapter needs durable fail/retry/diagnostic handling, never a success fallback.
5. No actual Linux Worldserver/Authserver launcher or GDB mode has been inspected. GDB may hide SIGSEGV behind a wrapper's exit 0. Current `verified` signals in S2–S4d remain fixture assertions, not real OS evidence.
6. No actual error logs, stack traces, report quota/backoff policy, least-privilege output broker or approved staged S4 fault injection. Even successful exact-head hosted tests and peer review are source-level only.

## Gate before any merge/release

Require source CI exact head and independent CS03 peer review, stack reconciliation without older S2-only writers, operator consent for **read-only** true launcher/GDB evidence, a reviewed supervisor/log adapter, crash-safe durable attempt state, real readiness probes, secure permission-separated broker for the intended operator directory, staged fault injection, explicit owner backups/approvals S5–S7, and rollback. No config, Worldserver/Authserver, root/SQL/DBC, Playerbots-local files, or main branch changes authorized.

The first combined owner-playable game test remains all FIVE **FUNCTIONAL** changes: #120 P0/B10 GFPP **exactly 120 seconds**, human Hunter addon-assisted A02 persistent ON/OFF, human-human native-parity A04 quest loot, F12 physical Scarlet exits/entries, F13 exterior Karazhan Atiesh. Golemagg #133/#144, F14 #145, NT1, Hallow's End F10, consumables and historical backlog tracked in master #28. Claude's continuous backup queue #143 remains mandatory while Grok #135 stays on owner-reported break.

[Team #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48) · [Master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) · [Claude queue #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143)
