# Mod-Naxxramas-Core — Part 27 Living Development Checklist

**Opened:** 26 October 2026. **Updated after CS01 live GitHub source/CI checks:** 26 October 2026.
**Scope:** Part 27 from the uploaded complete Part 26→27 handover. **Repository PUBLIC.** Historical Part 26 checkpoint retained; this is a current status, not a historical rewrite.

**Status words:** DONE—source, DONE—native, DONE—linked, REVIEW, PENDING—CI, BLOCKED—owner, NOT OPERATIONAL. An offline model/CI PASS is never gameplay evidence.

## 1. First five-fix gameplay acceptance — **0/5 signed off together**

| Fix | Verified source state | Required real acceptance |
|---|---|---|
| GFPP EXACT 120 seconds | DONE—source and DONE—linked in frozen #160 | Owner stopwatch, expiry and raid/bot interactions |
| A02 genuine Hunter pet autocast ON/OFF | #164 FULL pinned linked PASS; #165 fail-closed v1 protection, source/native PASS and full link in progress; #166 unwired model PASS | **BLOCKED** by post-validated native accepted human choice, durable pet birth and positive human/SelfBot exclusion, proper IP rank reconciliation, real 3.3.5a |
| A04 human group quest loot | #153 synthetic source research only | **BLOCKED**: (1) fellow human needs item but receives none; (2) sparkling corpse cannot be looted; genuine owner-private stock-group-loot casework |
| F12 Scarlet physical exits | DONE—source/native/linked in frozen #160 | Owner Cathedral 610↔604 and Armory 612↔606 physical walk out/back |
| F13 Atiesh exterior | DONE—source/native/linked in frozen #160 | Owner Vanilla exterior of Karazhan in-game |

F14 vanilla `/who` remains OPTIONAL and default OFF. Golemagg/B10 diagnostics are not owner stress acceptance.

## 2. Fresh PR/CI verification — 26 October 2026, Part 27

- [x] GitHub repository visibility **public**; `main` commit `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; verified current #160/#164/#165/#166/#167 are OPEN DRAFT, UNMERGED.
- [x] Frozen #160 `a7523ebb823169edc969d971d00aa293119f2f05` unchanged; previously verified FULL pinned Worldserver symbol link. **Do not amend.**
- [x] #164 `b480dff6da325763c48cdf56b2211e1f2b65d7e6` [Actions 40310850784](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40310850784): `source-and-native` and `pinned-worldserver-link` COMPLETED SUCCESS. Not gameplay.
- [ ] #165 `0bec377725addedf0257e93765b7fd72b3a55ac9` [corrected run 40315821299](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40315821299): `source-and-native` COMPLETED SUCCESS; `pinned-worldserver-link` IN PROGRESS at latest 26 Oct read. **Do not call overall run/full link green yet.** Actual production v1 write quarantine mandatory, default OFF.
- [x] #166 `9f0af14539c454d41860911d87199bda6b06eed3` [Actions 40319206646](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40319206646): 76/76 C++17 + 76/76 C++20 source-only assertions PASS, with hypothetical trusted birth/receipt inputs; unwired.
- [x] F15 #167 `ecccd5b17023a4fc8be04c2ff178f11229fda29c` [Actions 40324444951](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40324444951): `disposable-children-only` SUCCESS, self-reported 24 tests, no owner World/Auth, reports or deployment.
- [x] CS01 independently read F15 #167 actual producer and test source at current head. [Actionable peer review comment](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/167#issuecomment-6416724244) flags startup cleanup, active-child deadline abandonment, hot-writer starvation and group-scan best-effort failure. Source-review findings; new regressions remain requested, not run by CS01.
- [x] CS01 Part27 pinned source audit and [source-only accepted handler receipt integration contract](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/docs/cs01-p27-a02-native-postacceptance-contract/docs/research/A02-PART27-POSTHANDLER-RECEIPT-INTEGRATION-CONTRACT.md) on isolated draft review branch based on #166; **no core hook implemented**.
- [x] Cheap isolated five-path workflow fix `ci/cs01-p26-p0-f12-f13-f14-trigger-paths` @ `c197ef0ef4ab78ff8a624b3d7f842e824ea27a9a` preserved without unnecessary heavy PR CI.

## 3. A02 — CS01 primary

- [x] Native `CMSG_PET_SPELL_AUTOCAST` handler per actual controlled target, same-entry multiunit possibility, existing spell/owner and autocast validation reviewed at public pinned core.
- [x] `CMSG_PET_SET_ACTION` actionbar moves/repeats may call `ToggleAutocast`; pre-handler packet and poststate matching alone **cannot attest a human choice**.
- [x] Pinned `PetScript.h` contains no accepted-autocast callback; `CanPacketReceive` is before handler. `PROCESS_INPLACE` AUTOCAST can execute on map/world and `PROCESS_THREADUNSAFE` SET_ACTION routes differently; do not assume world-thread affinity.
- [x] Design now distinguishes initial post-validated `AUTOCAST` candidate, stricter **diagnostic-only** SET_ACTION until real-client evidence, and value-only synchronized receipts; refuses ambiguous bar/state or same-entry other pet.
- [ ] **OWNER C1:** explicitly approve smallest proposed upstream-core hook before ANY core source edit, even disposable patch.
- [ ] **OWNER C2:** approve durable pet-birth scheme before storage/schema/IP modification. PetNumber is recycled; model birth token is not real.
- [ ] **OWNER C3:** review positive human/SelfBot exclusion; `SelfBotLevel=0` and unsafe unlocked Playerbots map are NOT valid assurance. Preserve 8 map threads.
- [ ] Native/client real-source proof for right-click OFF/ON and off-bar `SET_ACTION`, rejected command/no-op, current pet/swap, latest OFF superseding old ON.
- [ ] Persistent same-birth relog/re-summon, pet replacement/recycle, server revision ordering, IP permitted rank down/up and repeated reconciliation. No 200ms guessed timer.
- [ ] Keep #165 guard before all automatic writes; old v1, addon whisper and synthetic model may never set `VerifiedHumanManualOrigin`.

## 4. F15 — Claude primary

- [x] #167 genuinely implemented **disposable-owned-child** pidfd/waitid exit classification and bounded stderr drain, exact-hosted source fixture CI success.
- [x] CS01 independently reviewed full source and posted four concrete follow-up corrections on PR #167.
- [ ] Claude response + next exact-head review/CI on startup-failure cleanup, active-child no-reap timeout, continuous writer fairness, optional group scan errors.
- [ ] Owner-approved R0 **read-only** actual host launch/log origin discovery for both Worldserver AND Authserver; owner S4 approval separately necessary before actual binary launch or fault injection.
- [ ] Real warning/error + crash provenance for BOTH daemons, report writer/durability (R2/R4 as scoped), least privilege, protected storage and rollback R5.
- [ ] **NOT OPERATIONAL**. Current prototype writes no actual owner crash or error reports and is not installed.

## 5. A04 owner-private evidence

- [ ] Preserve both distinct symptoms: fellow human did not receive a needed item, sparkling corpse cannot be looted.
- [ ] Collect effective installed module revision/feature flag ONLY with owner-approved private evidence. Never publish exact NPC/item/quest/loot mappings.
- [ ] Protect stock party loot, loot rights, eligible in-range group members and ordinary rotation/UI.
- [x] #153 synthetic research does not solve owner incident.

## 6. Coordination

- **CS01** — A02 source-grounded integration design, integration gates, source/CI verification, #167 code review.
- **CS02 (Grok)** — Module reviews/comments ONLY until owner changes coding availability; challenge A02 accepted/autocast, SET_ACTION and C1 proposal, review N-Core as separate research. Do not spend paid overage.
- **CS03 (Claude)** — PRIMARY F15 genuine crash+warning/error reporting, PR #167 feedback. BACKUP1 A04 private symptom matrix. BACKUP2 A02 #166/#165 native callback critique. BACKUP3 prior F15 safe source/CI hygiene. Do not idle while awaiting review.
- [Team #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48) · [Claude #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143) · [Master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28). GitHub comments **do not** autonomously start other AI agents.

## 7. Mandatory safety (all unchecked for future operations)

- [ ] Public repo: NO private host SQL, NPC/item/quest/loot/IP mappings, passwords, keys or host secrets.
- [ ] No merge, deployment, live testing, root/service, server binaries, SQL, DBC, upstream core, Individual Progression, N-Core or customized Playerbots edits without separate owner approval.
- [ ] Preserve `MapUpdate.Threads=8`; never access unlocked `_playerbotsAIMap` from arbitrary workers.
- [ ] Preserve exact GFPP 120 seconds, F12 physical exits, F13 OUTSIDE destination, F14 default OFF, stock loot and frozen #160.
- [ ] Both A02 feature flags remain OFF. Even flag ON does not authorize v1. No fake accepted receipt.
- [ ] Before staging: backups, rollback, pinned Worldserver build, full human/client acceptance plan. In-game milestone remains **0/5**.
