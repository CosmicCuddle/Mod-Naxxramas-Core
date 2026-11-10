# F15 World/Auth supervisor: public CLI refusal must not disclose private paths

**Owner:** CosmicCuddle. **Implementation:** CS01 Maintenance temporarily covering Naxx CS03/Claude while on break.
**State:** isolated default-OFF DRAFT; source/tests only; never a live host operation.
**Base:** immutable [Naxx combined DRAFT #292](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/292) `51d0611476358286505aed3ca806ea250f644f66`.
**Review:** [Naxx CS03 assignment #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143); independently reproduced by CS02/Grok in [#48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6744332211).

## Confirmed source defect

`scripts/f15_process_supervisor.py::main` caught `Refused`, `OSError` and `ValueError`, then interpolated the exception into public stderr as `F15 supervisor REFUSED: {exc}`. The exception often contains a private `output_root` or `archive_root` path (e.g. a symlink, wrong directory mode or missing parent). That exposes a sensitive path on a public console/CLI stream. This is a **source and disposable-reproduction finding**, not proof that the owner's host leaked a path.

## Narrow correction and preservation

Only the handled-exception CLI error is changed to a constant, non-sensitive message:

`F15 supervisor REFUSED: operation rejected; details withheld`

The handler preserves exit status 2, original `--execute` default-OFF requirement, service checks and subprocess safety. Existing private JSON run/launch-failure evidence, exception provenance inside `supervise`, valid success-path JSON with its intentional run path, and child capture behavior remain unchanged. The correction does **not** suppress detailed structured evidence that was intentionally written to a protected private directory.

The tests use disposable temporary directories and fake child commands only. They verify symlink root, nonprivate 0755 root, missing-parent `OSError`, injected `Refused`/`ValueError`/`FileNotFoundError`, no secret sentinel on stdout/stderr, return code 2, no `subprocess.Popen` call, existing default-OFF refusal and intended successful output. No real Worldserver/Authserver is launched. The dedicated workflow reproduces the original source leak via a throwaway symlink (parent **RED**) and confirms the fixed error via the identical CLI request (child **GREEN**). The parent and new code are invoked only in an isolated hosted test runner.

**Evidence status:** The original hosted GitHub Actions run must complete successfully at the exact PR head before reporting test success. A source diff or successful local test is not a real supervised World/Auth process, PM2 capture, archival/retention, or production operation.

## Custom Modifications Register entry — P3-F15-CLI-PRIVACY-20261110

| Field | Record |
| --- | --- |
| Intended behavior | Refuse unsafe F15 operation without revealing any private path in public stderr; keep private evidence, nonzero code 2 and OFF-by-default launch gating. |
| Owning module / source | `Mod-Naxxramas-Core` isolated `fix/cs01-f15-supervisor-cli-private-path-20261110` child of frozen #292 `51d0611476358286505aed3ca806ea250f644f66`. |
| Affected files | `scripts/f15_process_supervisor.py`, `tests/test_f15_process_supervisor.py`, `.github/workflows/f15-supervisor-cli-private-path-20261110.yml`, this documentation/register entry. |
| Version and dependencies | Existing Python POSIX `f15_operator_collector.private_dir`, private `atomic_write`, `subprocess.Popen` and opt-in supervisor CLI; no Core, IP, Playerbots, Services or loader changes. |
| Config / SQL / DBC / client | No changes. Existing `--execute` manual opt-in still required; no live service or data touched. |
| Risks and limits | The fixed CLI message deliberately omits file path diagnostics for public users; source-level protected private evidence remains. This patch does not certify any real child supervision, capture or retention nor imply a real-world secret was exposed. |
| Test status | Strict four-path CI, old-RED/new-GREEN disposable CLI, existing and new Python tests pending terminal hosted confirmation. No server/host/client tests. |
| Merge / live status | DRAFT, unmerged, uninstalled, not enabled, no actual game test. CosmicCuddle approval required for any production use. |
| Rollback | Abandon isolated DRAFT branch; original #292 and all previous custom source, SQL, config, DB and client state untouched. Future live rollout requires source inventory, restorable backups, safe staging and owner approval. |

**Safety:** No deletion, overwrite of established custom logic, live log access, PM2 probe, service startup, DB migration, release merge, client patch or production operation is authorised by this draft.
