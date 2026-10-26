---
name: New Naxxramas Core feature or fix
about: Register a new module idea or change, with an entry in the permanent master checklist
title: "[PROJECT] "
---

> **Always update [MASTER DEVELOPMENT CHECKLIST #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) BEFORE implementation.**
> If this feature already appears there, use its existing issue/PR and update the section rather than duplicating it.

## Link to master section
- Master checklist: https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28
- Existing related issues/PRs:
- Status: BACKLOG / ACTIVE / WAITING / PAUSED
- Proposed stage: S0

## Goal / why
<!-- User-observed problem, expected gameplay or administrative benefit -->

## Scope and safety
- Naxxramas Core changes proposed:
- AzerothCore / Playerbots / Individual Progression changes: **NONE unless separately approved**
- Current source/dependencies and relevant revisions:
- Does the work touch character/world SQL, config, server/client DBC or installed modules?:
- Owner approval/backup/restore requirements:
- Conflicts with older module projects:

## Stage checkpoints (evidence required for each)
- [ ] S0: Register and link this project in master #28
- [ ] S1: Pinned-source research, dependencies, architecture and explicit blockers
- [ ] S2: Implement in isolated reviewable branch; identify files/commit
- [ ] S3: Source, standalone and regression tests on exact commit
- [ ] S4: Pinned C++ build + Worldserver link on exact commit
- [ ] S5: Verify backup **restorability**, rollback, deployment plan and required owner approvals
- [ ] S6: Approved in-game acceptance and regressions on identified server revision
- [ ] S7: Approved merge, release/install/config enable and monitored outcome

## Next concrete action
<!-- Identify one immediately useful action. Update this after any milestone, failure or task switch. -->

**Opening this issue is NOT permission for live server/database/DBC edits, upstream patches, merges or installs.**
