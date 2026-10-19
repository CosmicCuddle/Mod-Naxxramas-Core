# Naxxramas Core — read-only source preflight (prepared, not deployed)

**Prepared for owner review on 19 October 2026.** This is a GitHub-only safety aid for a *future separately authorised staging/deployment process*. It does not install anything, compare effective live settings or touch a database. An **optional** read-only Linux /proc check can identify and hash an existing Worldserver process executable by a separately confirmed PID. It cannot prove the build's origin, the service manager launch configuration or gameplay.

## Why this exists

Pinned GitHub Actions builds prove that the draft module compiles on **particular Git SHAs**. They do **not** establish which AzerothCore, Playerbots, Individual Progression or Naxx Core sources are installed on the owner's realm. A module may have successful CI but be incompatible with locally modified or older dependencies. Before any owner-approved S5/S6 rollout, gather read-only source evidence and **stop on source drift**.

The preflight checks each checkout's independent **real Git root**, exact HEAD SHA and tracked worktree state. It does not mistake a missing module checkout for the parent AzerothCore repository. It does not print dirty filenames (or file contents), effective account names, full configuration or database data. Git runs with optional index-refresh locks disabled.

## Checked dependencies

| Checkout under AzerothCore | Historical pinned test SHA |
| --- | --- |
| AzerothCore | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` |
| `modules/mod-playerbots` | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| `modules/mod-individual-progression` | `4ff4b5fcc1480348f058c632573143e62d4e3a41` |
| `modules/mod-naxxramas-core` | Recorded without presuming a single target version; pass `--expected-naxx` with the **separately chosen** exact candidate SHA |

These are pinned **CI development baselines**, not claims about the user's installation. A mismatch means *review compatibility*; it does not mean the current server is necessarily broken or that it should be forcibly reset to the pinned revision.

## Owner-approved future MobaXterm / Linux use

**Do not run as part of this prepared research or initiate any deployment now.** When the operator chooses to inspect the actual installation and has confirmed the correct source directory, the following command is read-only. The paths are examples to be replaced with the true installed source tree:

```bash
python3 /path/to/azerothcore/modules/mod-naxxramas-core/scripts/check_naxx_source_preflight_readonly.py \
  --core /path/to/azerothcore
```

For a **specific separately reviewed** candidate revision, add `--expected-naxx <full-40-character-Git-SHA>` (replace the placeholder; do not type angle brackets literally in a shell). The default omits Naxx Core's expectation and clearly marks it **not certified**. To hash a known on-disk binary without executing it, optionally add `--worldserver /path/to/worldserver`.

**Optional running-process check (separate future owner authorization required):** use the read-only `pgrep -x worldserver` command in MobaXterm to list candidates and privately confirm the intended server PID. Do not select an unrelated process or run the preflight as root merely to bypass permissions. Then add `--worldserver-pid 12345`, replacing `12345` with the confirmed existing PID. The helper reads **only** `/proc/12345/comm`, the kernel's `/proc/12345/exe` symlink and that executable's bytes. It does **not** read command-line arguments, environment, memory, sockets, accounts, DB configuration, or secrets; does **not** signal/restart a process. It requires the process name to be exactly `worldserver` and **fails closed** for inaccessible, exited, renamed or deleted executables.

If both optional flags are given, the preflight compares the **running-process executable bytes** with those of the specified on-disk binary and STOPs if they differ. This is stronger process-to-file identity evidence, but **matching binaries still do not prove matching linked source SHAs, actual loaded module configuration, successful SQL migration or correct gameplay**. For a server started inside a different process namespace/container, a PID may not be visible and the result must remain **NOT VERIFIED**. Keep any result containing local paths private.

The script requires **read access** to the four Git working trees; do not run `sudo`, `git pull`, `git checkout`, database commands or server restarts to satisfy it. If any checkout is missing, nested inside the wrong repository, dirty, unreadable or at a different SHA, **STOP** and review the actual installed source. An expected revision change belongs in a separately reviewed plan, not an automatic repair script.

Return codes: 0 = checks pass (source and **any requested optional process/file identity checks only**), 2 = missing/invalid nested/unknown Git root, 3 = pinned mismatch, 4 = modified tracked files, 5 = unreadable/mismatching optional binary or unverified PID. Higher-numbered failures take precedence when multiple conditions coexist. Untracked files are **not** inspected by this tool.

## Separate S5/S6 safety gates still required

1. Confirm the actual **running** Worldserver executable bytes and separately the service startup path. The optional `/proc/PID/exe` hash identifies the inspected Linux process executable **at that inspection moment**; its source provenance, process manager definition and effective config still require separate review.
2. Record active Naxx, IP and Playerbots configuration **privately**. Do not post account names, passwords, database DSNs, character data, full config or logs containing secrets into GitHub.
3. Before any later approved install/enablement, back up the actual binary, active configuration, module source, **complete characters DB** and any touched world SQL rows; for DBC/client work, include exact client/server DBC/MPQ revisions. **Prove a restore on disposable staging**; file existence alone is insufficient.
4. Pilot **one** default-off feature at a time, only after separately explicit owner permission. Golemagg read-only Grau action probe, Hunter Ammo inventory grants, Quest Loot packet guard and Eastern Plaguelands SQL activation require different acceptance matrices and rollback rules; one successful pinned build authorises none of them.
5. Track exact candidate/source/binary SHA, config, failure results and rollback in the [single master register #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28). Never equate source presence, full link, deployed process, enabled feature or live gameplay acceptance.

**Research-only:** This checklist and script cannot perform backups, install packages, stop a service, enable flags, select ammo, modify bots, or mutate databases. The fake `/proc` tests run entirely in disposable local directories and never inspect a live Worldserver. It is safe to leave unmerged if no staged deployment is planned.
