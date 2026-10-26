# What changed and why
<!-- Keep one focused workstream per PR. This PR template does not authorise any release. -->

**Master tracker:** [Issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28)
**Feature issue/section:**
**Stage before / after:** S__ → S__
**Exact source SHA / dependency pins:**
**Status:** Draft / research / source implemented / test pending

## Mandatory master checklist synchronization
- [ ] **Before coding**, registered the new idea/change and its next step in #28 (or updated the existing project section)
- [ ] Updated the dedicated issue/PR and linked it to #28; did not silently abandon earlier work
- [ ] Recorded what changed, current blocker and **NEXT ACTION** after this checkpoint
- [ ] Only checked stages with actual test/CI/build/gameplay evidence linked below
- [ ] Reviewed possible regressions against the other open projects on #28
- [ ] No merge/release/deployment/enablement assumed from this PR

## Evidence and outstanding gates
- S1 research/design evidence:
- S2 source files and implementation:
- S3 tests/CI:
- S4 exact pinned Worldserver compile/link:
- S5 backup/recovery and config, SQL or DBC impact:
- S6 in-game testing and what is **not** verified:
- S7 release approvals/rollback (not requested by draft alone):

## Safety review
- [ ] AzerothCore, Playerbots and Individual Progression unchanged (or separate approval explicitly linked)
- [ ] No unexpected character/world SQL or DBC changes
- [ ] Existing feature defaults and normal gameplay preserved
- [ ] Any experimental feature disabled by default unless explicitly approved
- [ ] Destructive changes require verified backups and restoration plan
- [ ] PR stays **DRAFT/unmerged** until separate owner review and approval

## Next concrete action
