# Mod-Naxxramas-Core — Part 27 Living Development Checklist

**Opened:** 26 October 2026. **Updated after CS01 live GitHub source/CI checks:** 26 October 2026.
**Scope:** Part 27 from the uploaded complete Part 26→27 handover. **Repository PUBLIC.** Historical Part 26 checkpoint retained; this is a current status, not a historical rewrite.

**Status words:** DONE—source, DONE—native, DONE—linked, REVIEW, PENDING—CI, BLOCKED—owner, NOT OPERATIONAL. An offline model/CI PASS is never gameplay evidence.

## 1. First five-fix gameplay acceptance — **0/5 signed off together**

| Fix | Verified source state | Required real acceptance |
|---|---|---|
| GFPP EXACT 120 seconds | DONE—source and DONE—linked in frozen #160 | Owner stopwatch, expiry and raid/bot interactions |
| A02 genuine Hunter pet autocast ON/OFF | #164 FULL pinned linked PASS; #165 exact-head fail-closed v1 protection source/native and FULL pinned Worldserver link PASS; #166 unwired model PASS | **BLOCKED** by post-validated native accepted human choice, durable pet birth and positive human/SelfBot exclusion, proper IP rank reconciliation, real 3.3.5a |
| A04 human–human quest loot | #110 and #153 isolated source/model research, #109 owner observations authoritative; actual loaded guard/config UNKNOWN | **BLOCKED**: (1) a real friend apparently successfully takes quest loot shown available though the owner considers it theirs; (2) a different sparkle/visible-loot case results in denied pickup. Determine entitlement, group turn and guard state without assuming either case is proved or disproved by synthetic CI |
| F12 Scarlet physical exits | DONE—source/native/linked in frozen #160 | Owner Cathedral 610↔604 and Armory 612↔606 physical walk out/back |
| F13 Atiesh exterior | DONE—source/native/linked in frozen #160 | Owner Vanilla exterior of Karazhan in-game |

F14 vanilla `/who` remains OPTIONAL and default OFF. Golemagg/B10 diagnostics are not owner stress acceptance.

## 2. Fresh PR/CI verification — 26 October 2026, Part 27

- [x] GitHub repository visibility **public**; `main` commit `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; verified current #160/#164/#165/#166/#167 are OPEN DRAFT, UNMERGED.
- [x] Frozen #160 `a7523ebb823169edc969d971d00aa293119f2f05` unchanged; previously verified FULL pinned Worldserver symbol link. **Do not amend.**
- [x] #164 `b480dff6da325763c48cdf56b2211e1f2b65d7e6` [Actions 40310850784](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40310850784): `source-and-native` and `pinned-worldserver-link` COMPLETED SUCCESS. Not gameplay.
- [x] #165 `0bec377725addedf0257e93765b7fd72b3a55ac9` [corrected run 40315821299](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40315821299) COMPLETED **SUCCESS** 26 Oct 14:05:56 UTC: `source-and-native` and `pinned-worldserver-link` both SUCCESS. CS01 read the original pinned link job `121581755581` full steps/logs: C++ production translation unit compiled; full Worldserver linked; actual final log says `PASS linked: AddHunterPetAutocastScripts + both update hooks + addon chat hook`. Binary stays on disposable runner, not uploaded/installed; **NOT in-game**. Actual production v1 write quarantine mandatory; both flags default OFF, and accidentally turning them on does not enable unverified v1 restoration.
- [x] #166 `9f0af14539c454d41860911d87199bda6b06eed3` [Actions 40319206646](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40319206646): 76/76 C++17 + 76/76 C++20 source-only assertions PASS, with hypothetical trusted birth/receipt inputs; unwired.
- [x] F15 #167 current exact `91faf6af2a6d781240b652c419c623b7fd1df543` [Actions 40331736971](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40331736971), job `121602624906`: original log independently verified **35/35 Python disposable-child tests PASS** in 8.670 s, exact-head COMPLETED SUCCESS. Prior heads `ecccd5b` 24/24 and `de02ece` 32/32 passed separately, not attributed to this new SHA. Source-only R1/R3; no World/Auth launch, reports or deployment.
- [x] CS01 [original lifecycle review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/167#issuecomment-6416724244): first four source flaws addressed at prior `de02ece` with 32/32 verified; [later P2 exception review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/167#issuecomment-6417258688) now addressed at `91faf6a` with 3 more tests covering read EIO, selector ENOMEM and waitid EINTR. Independent exact-source and [original-log follow-up PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/167#issuecomment-6417403744) for the disposable-only prototype. Daemon reaper is still not a durable host service.
- [x] CS01 Part27 pinned source audit and [source-only accepted handler receipt integration contract](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/docs/cs01-p27-a02-native-postacceptance-contract/docs/research/A02-PART27-POSTHANDLER-RECEIPT-INTEGRATION-CONTRACT.md) on isolated draft review branch based on #166; **no core hook implemented**.
- [x] Cheap isolated five-path workflow fix `ci/cs01-p26-p0-f12-f13-f14-trigger-paths` @ `c197ef0ef4ab78ff8a624b3d7f842e824ea27a9a` preserved without unnecessary heavy PR CI.

## 3. A02 — CS01 primary

- [x] Native `CMSG_PET_SPELL_AUTOCAST` handler per actual controlled target, same-entry multiunit possibility, existing spell/owner and autocast validation reviewed at public pinned core.
- [x] `CMSG_PET_SET_ACTION` actionbar moves/repeats may call `ToggleAutocast`; pre-handler packet and poststate matching alone **cannot attest a human choice**.
- [x] Pinned `PetScript.h` contains no accepted-autocast callback; `CanPacketReceive` is before handler. `PROCESS_INPLACE` AUTOCAST can execute on map/world and `PROCESS_THREADUNSAFE` SET_ACTION routes differently; do not assume world-thread affinity.
- [x] Design now distinguishes initial post-validated `AUTOCAST` candidate, stricter **diagnostic-only** SET_ACTION until real-client evidence, and value-only synchronized receipts; refuses ambiguous bar/state or same-entry other pet.
- [x] **NEW source audit:** exact public Individual Progression `dd96f2b` `IndividualProgressionSpells.cpp:56–112,1270–1373` re-derives allowed rank from server-side player spell markers, queues a deduplicated 200-ms post-pet-load event with up to ten deferred loading retries; **not** a guaranteed 200ms settlement oracle. A02 must re-evaluate current book/allowed rank, not copy tables or learn spells. Details in updated [PR #168 integration contract](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/168).
- [x] **NEW exact public Playerbots audit:** `d750b4b` `PlayerbotAI.cpp:4523–4536` `IsRealPlayer/IsSelfBot` query `GET_PLAYERBOT_AI`; `PlayerbotMgr.cpp:1828–1875` `_playerbotsAIMap` insert/erase/read without visible synchronization. Unsafe to invoke as a positive classifier on arbitrary `PROCESS_INPLACE` map workers. Actual owner's customized code UNKNOWN; C3 owner approval remains mandatory.
- [ ] **OWNER C1:** explicitly approve smallest proposed upstream-core hook before ANY core source edit, even disposable patch.
- [ ] **OWNER C2:** approve durable pet-birth scheme before storage/schema/IP modification. PetNumber is recycled; model birth token is not real.
- [ ] **OWNER C3:** review positive human/SelfBot exclusion; `SelfBotLevel=0` and unsafe unlocked Playerbots map are NOT valid assurance. Preserve 8 map threads.
- [ ] Native/client real-source proof for right-click OFF/ON and off-bar `SET_ACTION`, rejected command/no-op, current pet/swap, latest OFF superseding old ON.
- [ ] Persistent same-birth relog/re-summon, pet replacement/recycle, server revision ordering, IP permitted rank down/up and repeated reconciliation. No 200ms guessed timer.
- [ ] Keep #165 guard before all automatic writes; old v1, addon whisper and synthetic model may never set `VerifiedHumanManualOrigin`.

## 4. F15 — Claude primary

- [x] #167 at `91faf6a` genuinely implements **disposable-owned-child** pidfd/waitid exit classification, bounded stderr drain and a reaper handoff, with exact-hosted 35/35 Python fixture CI PASS.
- [x] CS01 reviewed actual source and original CI logs, confirmed four initial corrections plus unexpected observation-exception handoff regression; [independent precise PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/167#issuecomment-6417403744) scoped only to disposable source prototype.
- [x] **NEW verified native logging blocker:** pinned AzerothCore `AppenderConsole.cpp:172–210` routes WARN/INFO to **stdout**, ERROR/FATAL to stderr; F15 #167 uses `stdout=DEVNULL`, `stderr=PIPE`, so native stdout warnings are discarded. The stock World/Auth `Appender.Console` configs use **flags=0**, and `Appender.cpp:55–100` adds `WARN ` / `ERROR ` prefixes only when explicit loglevel-prefix flag 2 is selected; #167 `_PREFIXES` cannot treat bare native text as authoritative severity. Exact source links and needed positive/negative fixtures in [PR #167 comment](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/167#issuecomment-6418047787).
- [ ] **Next F15 engineering:** source-only proposed R3 **dual-stream** provenance-and-severity strategy or chosen owner-authorized file/journal route, explicitly preserving complete stdout/stderr drain; define trustworthy severity semantics, bounded redaction/report schema and both World/Auth service identities. Current #167 35/35 CI remains valid for owned stderr bytes/kernel R1, **NOT** operational WARN + ERROR reporting. R0 actual launch/logger destinations and Q3 real-daemon tests need separate owner approval. Process-lifetime daemon reaper is not production reliability.
- [ ] Owner-approved R0 **read-only** actual host launch/log origin discovery for both Worldserver AND Authserver; owner S4 approval separately necessary before actual binary launch or fault injection.
- [ ] Real warning/error + crash provenance for BOTH daemons, report writer/durability (R2/R4 as scoped), least privilege, protected storage and rollback R5.
- [ ] **NOT OPERATIONAL**. Current prototype writes no actual owner crash or error reports and is not installed.

## 5. A04 — authoritative owner report, no premature policy change

- [x] Corrected this checklist against [owner incident #109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109) rather than inventing a missing-item/failed-award scenario. **Observation H1 (apparently accepted):** a real human friend repeatedly sees a quest item/corpse as available and apparently successfully collects what owner regards as their quest loot. **Observation H2 (denied):** another group member sees an apparently lootable/sparkling corpse, opens or attempts pickup, yet cannot collect the protected quest item. These are **different outcomes** and neither may be erased.
- [x] Read exact module `main@80e9de1` `src/Systems/QuestLootProtection.cpp` blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f`: `Enabled` defaults FALSE, `CanPacketReceive` intercepts only `CMSG_AUTOSTORE_LOOT_ITEM`. `PermitPickup` is deliberately **fail-open** except for one-copy creature quest rows with a verified active eligible group round-robin owner; normal slots, `freeforall`, `follow_loot_rules`, rolls, owner release, absent/moved owners and other group modes follow core. This is source behaviour only; actual installed config, quest/item/loot row and human eligibility UNKNOWN.
- [x] Related [PR #110](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/110) investigates packet fail-open and per-viewer sparkle mismatch; [PR #153](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/153) is synthetic roll timing research. Neither is a verified fix or in-game acceptance. A successful friend's pickup may be an eligible stock single-copy award, **or** an actual inappropriate grant. The present evidence does not decide.
- [ ] **Human–human acceptance H01–H05:** non-entitled viewer's sparkle and loot slot, correct pickup rejection; eligible viewer's correct reward; a claimed wrong-human successful pickup versus merely visible denied slot; normal loot/gold/FFA/MULTI_DROP/professions; group round-robin release, loot-method change, each human order, roll and corpse refresh. Test playerbots separately.
- [ ] Confirm owner's installed module SHA and effective config, quest/item/drop/group eligibility and actual packet pathway **privately and only with owner approval**. No private NPC/item/quest/loot IDs or source relationships in PUBLIC GitHub.
- [ ] **Do not** broadly suppress sparkles, reserve ordinary loot, invent per-human item copies, change item flags/loot economy or enable custom guard while the owner case is unknown; preserve stock group loot and the eight map threads.

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
