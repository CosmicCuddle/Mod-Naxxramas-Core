# F15 staging evidence collection plan — source-only

**Owner:** CosmicCuddle  
**Status:** planning artifact only; no host commands have been run by CS01.  
**Parent work:** DRAFT #310 evidence preflight.

This note defines the **minimum read-only evidence package** required before F15 can move from source-only design toward an owner-reviewed staging proposal.

It does not authorize production access, installation, scheduling, process control, log rotation, deletion, or deployment.

## Evidence handling rule

Collect evidence locally/private-side first. Do **not** paste secrets, tokens, passwords, database credentials, full environment dumps, or sensitive process command lines into GitHub.

For every fact, preserve:
- the value;
- where it came from;
- the date/time it was observed;
- whether it is VERIFIED, PROPOSED, or UNKNOWN.

The #310 preflight requires provenance-bearing envelopes and will not accept a bare string such as `"verified"`.

## Required fact set

### Worldserver / PM2

Required:
- exact PM2 process name;
- PM2 manager log path;
- worldserver stdout path;
- worldserver stderr path.

Suggested future read-only evidence sources:
- `pm2 jlist` or `pm2 describe <name>` for the selected process;
- the PM2 ecosystem/config file actually used by the owner host;
- filesystem metadata for the referenced log paths.

Do not run PM2 start/stop/restart/reload/delete commands.

### Authserver / tmux

Required:
- exact tmux session name;
- authserver process name;
- authserver log path.

Suggested future read-only evidence sources:
- `tmux list-sessions`;
- a name-only process lookup such as `pgrep -x <process-name>`;
- the launcher/script actually used to create the tmux session;
- filesystem metadata for the auth log.

Avoid capturing full process command lines if they may contain private arguments.

### Overwrite / rotation ownership

Required:
- the exact component that can overwrite, truncate or rotate each active log;
- the exact safe point where `snapshot-before-overwrite` would have to run.

Potential evidence sources:
- PM2 log configuration;
- launcher scripts;
- logrotate configuration, if used;
- AzerothCore logger configuration;
- any existing maintenance/rotation script.

A proposed hook is **not verified** until the overwrite owner is identified from real host evidence.

### Permissions

Required:
- runtime user expected to invoke F15 operational modes;
- owner/group expectations for `/root/cosmic_core/logs/` and the F15-owned archive/crash areas.

Potential read-only evidence sources:
- `stat` on the relevant directories/files;
- the actual service/launcher ownership model.

Do not change chmod/chown/ACLs during evidence collection.

### Capacity

Required:
- current free bytes on the filesystem containing `/root/cosmic_core/logs/`;
- a conservative projected 30-day F15-owned storage requirement.

Potential read-only evidence sources:
- `df -B1 /root/cosmic_core/logs`;
- read-only size measurements of existing logs/crash artifacts;
- observed growth samples, if already available.

Projection must include:
- archived copies made before overwrite;
- crash reports;
- raw crash evidence bundles owned by F15;
- margin for bursty crash/log periods.

Do not delete files merely to make the preflight pass.

### Build/source fingerprints

Required:
- a trustworthy build-version source;
- a trustworthy source-revision source.

Potential evidence:
- the exact binary/version output used by the running build;
- the exact checked-out Git revision from the build tree;
- build metadata already emitted by the server.

A repository HEAD alone is not proof that the running binary was built from it.

### Scheduling plan

Required:
- proposed cadence/trigger for `observe-once`;
- proposed cadence/trigger for `retain-once`.

These may remain `PROPOSED` at source-review stage. They are not installed schedules and do not authorize cron/systemd/PM2 changes.

## Suggested evidence manifest workflow

1. Copy `examples/f15_staging_manifest.example.json` to a private working location.
2. Fill only facts that have actual evidence.
3. Set unverified facts to `UNKNOWN`.
4. Record a concise provenance string for every VERIFIED/PROPOSED value.
5. Run the offline #310 preflight against that private manifest.
6. If the result is `UNKNOWN` or `BLOCKED`, resolve facts read-only.
7. A result of `READY_FOR_OWNER_REVIEW` still does **not** authorize staging.
8. CS01 then prepares backup, rollback and staging instructions for CosmicCuddle's explicit approval.

## Rollback

This document and example manifest are source-only planning artifacts. Rollback is to abandon/revert the draft branch. No host state exists from this work.
