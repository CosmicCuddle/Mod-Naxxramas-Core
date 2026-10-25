# F15 S3 — Offline restart-outcome sidecars (isolated design + executable tests)

**NOT A LIVE SERVER MONITOR. DO NOT MERGE, INSTALL OR ENABLE.**

This stacked draft builds on the S2 offline storage prototype [PR #136](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/136) at independently reviewed exact `a2b1185f29f32b8d71ed17f53058a62baea0e435` (Claude S2 PASS for storage only). It adds an S3 **host-independent** layer, not Worldserver or Authserver restart detection.

## Why sidecars?

The original finalized incident report remains **immutable**. When a trusted supervisor later supplies evidence of a real restart attempt and its observed result, the offline store may attach another immutable, no-clobber report with the same crash incident ID. `Crash-History.txt` is rebuilt with the latest verified attempt's status, but its Worldserver/Authserver/Total crash counts do **not** increase. Two separate attempts, including a failed attempt followed by recovery, both remain on disk.

## Source and trust boundary

- `tools/f15/offline_restart.py` adds `RestartObservation` and `RestartSidecarStore` (subclass of the S2 `IncidentStore`). It never starts, stops, watches, connects to or obtains evidence from a process.
- A `RestartObservation` must contain a canonical, **already verified original crash incident ID**, a bounded allowlisted attempt identity, explicit UTC observation time, exactly `succeeded` or `failed`, and `verified=True`. The layer itself **cannot authenticate these claims**. The actual supervisor/owner launcher has not been identified and no adapter exists.
- Derived sidecar identity uses a UUIDv5 from **incident ID + attempt ID**; **not** the time of later notification. A repeated identical observation is idempotent; a contradictory result for the same attempt is a no-clobber conflict that requires investigation.
- Every sidecar is a restrictive UTF-8 file under the preexisting private, directory-descriptor-pinned output, via the S2 `flock`, temp-file `fsync`, atomic `link` no-clobber and directory sync. It contains deterministic JSON metadata and a SHA256 finalization trailer; the original report remains untouched.
- History rebuilding validates both the base crash and its sidecars. Corrupt, symlinked, orphan or modified sidecars are **excluded and explicitly listed as unverified**, rather than counted as verified restarts. Latest displayed state is chosen from verified observed UTC time and deterministic sidecar ID. Original crash totals remain unchanged.
- A failed report/index publication can leave a durable report/sidecar despite an exception; the next locked rebuild can recover it. A detected corrupt sidecar cannot be overwritten, including when the corresponding index must be rebuilt.

## Integration limitation: no mixing old S2 and new S3 writers

**The S3 store must be the only incident+restart writer used by any future integration.** An older S2 `IncidentStore.rebuild()` will rewrite the derived index without the restart projection. Original reports and sidecars remain intact; running the S3 rebuild reconstructs it, but this means mixing implementations is not a supported deployment design. A future adapter needs a single named implementation and a tested migration plan, not parallel incompatible collectors.

## Deliberately unresolved

- **Actual host supervisor, GDB, restart loop and operating system evidence** remain UNKNOWN. No real crash, no real restarter, and no proof of a successful restart.
- No retries/delays/restart-launching service, no verified `/root/cosmic_core/logs/Crash Logs/` access, no output-directory creation, no root broker, shell scripts, SQL/DBC, Worldserver/Authserver binary or config modifications.
- Sidecar verification relies on the future trusted OS adapter. The implementation must distinguish a confirmed next process ready-to-serve from merely a wrapper restarting, with source/time evidence and pending outcome handling. There is currently **no production policy** for SIGKILL after a planned shutdown, stale temporary files or host-mounted filesystem races.
- Same-attempt conflicting sidecars are **never overwritten**. A legitimate correction may require a separately reviewed evidence correction/annotation mechanism; no implicit rewrite is allowed.
- A sidecar reporting `succeeded` reflects the caller's claimed verified event, not guaranteed long-term availability of the service. Health/readiness semantics must be agreed with the owner when the actual startup supervisor is known.
- Path and uid restrictions are S2 research only, not approval of a privileged service or creation of the live output path. All tests use private temporary directories.

## Synthetic test commands (GitHub Actions; no output artifacts)

```bash
python3 -m unittest discover -s tests -p 'test_f15_offline_store_s2.py' -v
python3 -m unittest discover -s tests -p 'test_f15_restart_sidecar_s3.py' -v
```

The new suite tests idempotence across collector restart, process-concurrent publishers, distinct same-second restart attempts, no-clobber conflicts, tampering and orphan recovery, cross-process original report binding and crash-count invariance. A successful test proves **offline S3 projections only**. Independent Claude security review and eventual Grok review remain pending; no live adapter or staging permission is implied.

Project delivery: [Issue #28 master checklist](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) / [Issue #48 team coordination](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48). Preserve the full first-build gameplay requirements and Grok-owned #135 research branch.
