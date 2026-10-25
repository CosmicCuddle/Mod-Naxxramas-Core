# F15 S3 — Offline restart-outcome sidecars (isolated design + executable tests)

**NOT A LIVE SERVER MONITOR. DO NOT MERGE, INSTALL OR ENABLE.**

This stacked draft builds on the S2 offline storage prototype [PR #136](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/136) at independently reviewed exact `a2b1185f29f32b8d71ed17f53058a62baea0e435` (Claude S2 PASS for storage only). It adds an S3 **host-independent** layer, not Worldserver or Authserver restart detection. The latest S3-only peer-review correction also updates the inherited offline S2 source **on this stacked branch only**; independently reviewed S2 PR #136 stays unchanged.

## Why sidecars?

The original finalized incident report remains **immutable**. When a trusted supervisor later supplies evidence of a real restart attempt and its observed result, the offline store may attach another immutable, no-clobber report with the same crash incident ID. `Crash-History.txt` is rebuilt with the latest chronologically unambiguous verified attempt's status, but its Worldserver/Authserver/Total crash counts do **not** increase. Where multiple attempts share the same most-recent UTC second, order is **ambiguous**, and no arbitrary result is selected. Two separate attempts, including a failed attempt followed by recovery, both remain on disk.

## Source and trust boundary

- `tools/f15/offline_restart.py` adds `RestartObservation` and `RestartSidecarStore` (subclass of the S2 `IncidentStore`). It never starts, stops, watches, connects to or obtains evidence from a process.
- A `RestartObservation` must contain a canonical, **already verified original crash incident ID**, a bounded allowlisted attempt identity, explicit UTC observation time, exactly `succeeded` or `failed`, and `verified=True`. The layer itself **cannot authenticate these claims**. The actual supervisor/owner launcher has not been identified and no adapter exists.
- Derived sidecar identity uses a UUIDv5 from **incident ID + attempt ID**; **not** the time of later notification. A repeated identical observation is idempotent; a contradictory result for the same attempt is a no-clobber conflict that requires investigation.
- Every sidecar is a restrictive UTF-8 file under the preexisting private, directory-descriptor-pinned output, via the S2 `flock`, temp-file `fsync`, atomic `link` no-clobber and directory sync. It contains deterministic JSON metadata and a SHA256 finalization trailer; the original report remains untouched.
- History rebuilding validates both the base crash and its sidecars. Corrupt, symlinked, orphan or modified sidecars are **excluded and explicitly listed as unverified**, rather than counted as verified restarts. Latest displayed state uses verified observed UTC time only when that establishes a unique latest attempt. If two or more distinct attempts share the latest UTC second, history displays **Ambiguous (sequence not verified)**, rather than choosing success or failure by UUID ordering. A sidecar observed earlier than the original crash's recorded termination time is refused or flagged unverified. Original crash totals remain unchanged.
- A failed report/index publication can leave a durable report/sidecar despite an exception; the next locked rebuild can recover it. A detected corrupt sidecar cannot be overwritten, including when the corresponding index must be rebuilt.

## Additional S3 source-order safety witnesses

The source-only audit found two gaps in the original 21-case model: separate attempts at the same UTC second could be sorted by their UUIDs and projected as a false latest `succeeded`, and a correctly hashed sidecar could claim a restart **before** its original crash ended. Both are now fail-closed in this research model. Five additional synthetic witnesses cover opposite outcomes at the same time, identical outcomes with unresolved order, later uniquely timed recovery, pre-crash publication refusal, and pre-crash forged-but-checksummed sidecars excluded from history. These assumptions require a later trusted adapter to establish accurate chronological evidence, including possible cross-source clock skew, before S4 acceptance.

## S3 peer-review corrections — legacy writer and future clock safety

**Review response on the isolated S3 branch (not on the independently approved S2 #136 branch):**
- An S2-only `IncidentStore.rebuild()` now **raises** when `restart-*.txt` sidecars exist, BEFORE rewriting `Crash-History.txt`. An S2-only `publish()` rejects these S3 directories BEFORE writing an incident. The S3 subclass retains its own sidecar-aware index rebuilding. This intentionally modifies the inherited `tools/f15/offline_store.py` **only on this stacked S3 branch**; S2 #136 remains unchanged. Tests demonstrate the legacy index cannot silently erase verified restart projections.
- A verified restart sidecar claiming a timestamp more than **five minutes ahead of the writer's UTC wall clock** is rejected before publish. During locked history rebuilding, an otherwise valid, correctly hashed future-dated sidecar is listed as **unverified**, not chosen as the latest outcome. This is a conservative offline sanity check, not a substitute for trusted supervisor event ordering, monotonic identity, reliable clocks or cross-observer skew handling. Sidecar evidence is preserved for independent investigation.
- Four new S3 negative tests cover both legacy-writer operations, future-date publication refusal and a correct-hash future-sidecar attempt to hide a later failed restart.

**The S3 store must be the only crash+restart writer used by any future integration.** An old S2 collector whose code lacks these new guards could still erase a projection; deploying mixed, unreviewed versions is forbidden. All future S4 adapters need a single implementation, pinned source identity, a migration policy and independent tests.

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

The new suite tests idempotence across collector restart, process-concurrent publishers, distinct same-second restart attempts and ambiguous ordering, pre-crash event rejection, no-clobber conflicts, tampering and orphan recovery, cross-process original report binding and crash-count invariance. A successful test proves **offline S3 projections only**. Independent Claude security review and eventual Grok review remain pending; no live adapter or staging permission is implied.

Project delivery: [Issue #28 master checklist](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) / [Issue #48 team coordination](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48). Preserve the full first-build gameplay requirements and Grok-owned #135 research branch.
