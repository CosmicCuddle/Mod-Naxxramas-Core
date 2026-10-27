# Mod-Naxxramas-Core — Part 28 Living Development Checklist

**Created 27 Oct 2026 UTC by CS01; new chat must maintain this actively.**
**Authority:** all PRs draft/unmerged; any owner direction on design is NOT code/SQL/host/activation permission. Public repository — do not publish private owner SQL, NPC/item/quest/loot or Individual Progression relationships.

## Start-up integrity checks

- [ ] Read [COMPLETE Part27→28 handover](2026-10-27_PART27_TO_PART28.md) and this checklist IN FULL.
- [ ] Read [current #168 owner-selected A02 decision memo](../research/A02-PART27-OWNER-MODULE-ONLY-CANDIDATE-AND-DURABLE-DB-DECISION.md) and former native hook comparison (technical context only).
- [ ] Refresh exact GitHub heads, CI, comments and statuses of #160/#164/#165/#166/#168/#169/#172/#173/#167/#170/#171; read [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), [team #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48), [A04 #109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109), [F15 #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143).
- [x] Preparation checkpoint: main **80e9de1**; protected frozen #160 **a7523eb**, still OPEN DRAFT UNMERGED at 27 Oct read. No merge/deploy by CS01.
- [ ] Record any activity after these checkpoint heads before proceeding.

## Combined five mandatory gameplay fixes — **0/5 owner-signed together**

- [ ] GFPP exactly **120 seconds**: owner timing/gameplay acceptance.
- [ ] A02 real Hunter pet autocast accepted human ON/OFF: **BLOCKED**; #165 native full link only proves fail-closed quarantine. Do not allow unverified automatic restore.
- [ ] A04 owner human loot incident **H1**: friend apparently successfully took what owner regards as their quest item, actual eligibility unknown.
- [ ] A04 separate owner human loot incident **H2**: loot sparkle/visible, but pickup denied, actual eligibility unknown. These two cases form ONE mandatory A04 fix with TWO required symptom checks.
- [ ] F12 physical Scarlet Cathedral **610↔604**, Armory **612↔606** exits and returns.
- [ ] F13 Atiesh Vanilla-stage Karazhan **exterior** arrival.
- [ ] OPTIONAL F14 /who filtering stays default OFF; not a sixth mandatory fix.

## A02 — owner direction and source-only engineering

- [x] **C1 owner choice via CS02:** no upstream-core hook as default; module-only pre-handler mirrored native candidate and later map observation, DIRECTION ONLY. #168 latest parent **fa87be31f9426d267ebd8f10b104dd61d4c47db9**; no implementation approval.
- [x] **C2 owner choice via CS02:** new restart-persistent preference table, owner/player+PetNumber hints, DIRECTION ONLY. No approved SQL/DDL/deploy/backup operation. Recycled PetNumber and asynchronous pet save mean no guaranteed canonical durable birth.
- [x] Exact pinned core C1 source: ordered, short-circuiting enabled ServerScript packet hooks then native handler. Stable **registered ServerScript*** comparison for last enabled observer — **NOT WorldScript::this**. Need installed hooks/source/ordering proof; last synchronous hook != native acceptance.
- [x] Exact pinned core C2: LoadPetNumber(MAX canonical row) before pre-network OnBeforeWorldInitialized; OnStartup too late. Database DirectExecute() **void**, empty Query may mean error — positive scalar readback required. Still no proof of another writer's absence, atomic birth or successful in-flight save.
- [x] #164 **b480dff**, source/native/full Worldserver link PASS for resolved self-whisper; no trusted human command.
- [x] #165 **0bec377**, [full pinned Worldserver link SUCCESS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40315821299), actual v1 writer fence. Both feature flags OFF, unknown choice never saved/applied.
- [x] #166 **9f0af14** unwired birth/summon synthetic C++ 76/76 C++17 and C++20 PASS.
- [x] #169 **5530f53**, [224/224 strict C++17+C++20 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40344747079), unwired 32-chain per-incarnation retries, fresh-summon reset.
- [x] #172 **f433aaa**, [113/113 strict C++17+C++20 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40394758887), UNWIRED cross-incarnation lifetime retry bound per certified birth + chain + accepted revision. 32 ever-used keys, no safe eviction/retirement, restart loses counter. Unknown => NoWrite.
- [x] #173 **a122c6e**, [12/12 pinned public core source checks PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40489921822); lexical/negative source sentinels, not compiled module or owner-installed hook proof.
- [ ] **C1 causal proof risk:** prepacket CandidateMatched + next-map state does not identify native writer if later veto/AI/IP/script changed state. Do not set TrustedManualReceipt or break #165 quarantine; positive installed source/hook-order proof still missing.
- [ ] **C2 durable lifetime:** verify unique birth vs PetNumber recycle and all delete/broad-slot/character-delete paths; async stock pet save and cross-pool/worker order; possible prelogin orphan sweep is conditional, not a birth certificate; plan backups/rollback privately. No SQL.
- [ ] **C3 human/SelfBot:** design synchronized positive mode proof at receipt and apply; never unlocked Playerbots map read on arbitrary map worker; preserve 8 map threads.
- [ ] IP **Policy A**: only current allowed **existing** spell rank, do not learn/disallowed rank; account for its delayed 200ms event and repeated rank churn.
- [ ] Per-player + certified birth + normalized spell chain **latest revision** with newer OFF superseding old ON; do not confuse a new summon with a new birth.
- [ ] Separate owner implementation approval, any lower-assurance restore risk decision, C2 SQL/backup/rollback approval, C4 backed-up installation and real 3.3.5a client acceptance.
- [ ] Decide from material source evidence (not more generic tests) the next **safe** C1 fake-dispatcher counterexample or C2 source proof gap.

## F15 — Claude primary, BOTH Worldserver AND Authserver

- [x] #167 **91faf6a** owned-disposable-child pidfd/waitid stderr producer, 35/35 hosted PASS; process-lifetime reaper, not real service.
- [x] #170 **480e08d**, [51/51 disposable-child tests PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40341487578), separate bounded stdout+stderr, severity UNKNOWN unless positively declared prefix; hints not authoritative. Real console stdin EOF and shutdown join remain unproven.
- [x] #171 **62c3df2**, [43 schema + 51 producer tests SUCCESS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40346318815). Strict in-memory text-free JSON, deep malformed input refusal. Unkeyed digest verifies consistency, not origin.
- [ ] F15 R0: owner-approved read-only facts for **both** daemons' launcher, service restarter, stdin/out/err, logger flags, paths, crash artefacts and service permissions. Claude proposed a redacted checklist on [#143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143); no actual owner host collection approved.
- [ ] F15 R4: source-only durable PRIVATE report writer threat model, least privilege, trust/authenticity boundary, retention/rollback, no raw log text or private host data on PUBLIC repo.
- [ ] No real World/Auth binary launched, no systemd/file/journal adapter, daemon install, crash injection, config, report storage or real incident response. **F15 NOT OPERATIONAL** until separate owner R0/Q3/S4 gates.

## A04 owner-private casework

- [ ] H1: apparently successful human friend's quest-loot pickup. Determine whether eligible stock group allocation vs genuine wrongful pickup — no assumptions.
- [ ] H2: another human sees sparkle and denied pickup. Separate evidence, no misleading shorthand.
- [ ] Preserve ordinary group loot methods, FFA/rolls/normal loot, eligibility, group turn and all protected private source relationships.
- [ ] Owner-private reproducible evidence only when permitted; no public NPC/item/quest/loot SQL or IDs.

## Team and release discipline

- [ ] CS01: source-grounded A02 integration/correctness and master tracker; maintain this checklist, exact-head checks, reviewer comments.
- [ ] CS02 Grok: COMMENTS-ONLY module reviews unless owner changes coding availability; avoid paid overage. Request concise review of material A02 source/race proofs, not redundant fixture work.
- [ ] CS03 Claude: F15 PRIMARY source-only R0 and private writer design; BACKUP A04 two human observations / A02 peer review. GitHub comments alone do not start agents.
- [ ] Verify all PRs remain DRAFT/UNMERGED and #160/main protected after changes. NO live server/root, real binary, upstream core, SQL, DBC, Playerbots/IP/N-Core, map thread, protected file, feature-flag or deployment changes without explicit separate owner approval.
- [ ] Never count synthetic source tests, pinned Worldserver link or a staged PR as **in-game acceptance**. Still **0/5 owner-signed together**.
