# Mod-Naxxramas-Core — Part 30 Living Development Checklist

**Opened 27 October 2026 (UTC), CS01.** This is a PUBLIC docs-only, DRAFT and **non-authorising** checklist. Read the [complete Part29 → Part30 handover](2026-10-27_PART29_TO_PART30.md) and the previous [Part29 living checklist](2026-10-27_PART29_LIVING_DEVELOPMENT_CHECKLIST.md) in full before engineering.

## 0. Safety invariants — reverify every new session

- [ ] Refresh actual GitHub heads, merge/draft state, protected and `main` refs; don't trust yesterday's refs without checking. At handover **`main=80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`** and **protected #160 `a7523ebb823169edc969d971d00aa293119f2f05`**, both unchanged/unmerged.
- [ ] **NO MERGE, deployment, owner host/World/Auth, private SQL/DBC/config/player/log access, installed binary, service restart, feature toggle or gameplay without separate owner approval.** Real staging requires privately verified exact builds, authorised scope, and **restorable backups/rollback**. No private IDs to PUBLIC GitHub.
- [ ] Preserve eight map threads; no upstream core, Playerbots, IP, N-Core or protected PR edits. Claude remains on break. Do not assume GitHub comment automatically assigns work.
- [ ] Keep **five mandatory gameplay items 0/5 owner accepted** until genuine witnessed real-game positives AND negatives; source/native CI is not owner runtime acceptance.

## 1. Critical first gate — F13 #187 own linked-binary outcome

- [x] DRAFT [#187](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/187) child of unmodified #186, exact handover HEAD **`de6816a1e3f94f2e530fca093dd596c11903b8d3`**. Only `AtieshKarazhanPortal.cpp` gameplay C++ changes; six total tests/docs/workflow paths.
- [x] Source/native [Actions 40584203475](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40584203475), job **`122471236948` SUCCESS**: 5 source pins, 25 F13, 6 new real-upstream owned-GO lifetime checks, GFPP 18, F12 27, F14 and policy passes.
- [ ] **URGENT RECHECK** [#187 full pinned Worldserver link, job **`122471429518`**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40584203475): was **IN PROGRESS** at handover, NOT green just because older #186 links were. Independently read completed job's original log, verify exact #187 HEAD, pinned Grimfeather/Playerbots/IP, **1,896/1,896 native link** and all five script registrations. Investigate actual failure without touching #160/#186. Also recheck remaining #187 exact SHA workflows (including `40584203450`).
- [ ] If the job passes, record source/linked candidate ready for **later** owner staging, NOT accepted or safe to merge. If it fails, isolate the exact cause; don't claim success.

## 2. Bounded interrupted source review — F12 and F13 native behaviour

- [x] Native `MiscHandler.cpp:691–808` confirmed area-trigger order (flight, trigger DBC, radius, GM/debug area script, quest/rest/PvP, native teleport). F12 `SERVERHOOK_CAN_PACKET_RECEIVE` consumes selected 604/606 early; built-in validation is not identical to all script layers.
- [ ] F12 **GLOBAL ALEScript** parity risk: native `AreaTriggerScript.cpp:24–40` invokes `ALEScript::CanAreaTrigger` before per-trigger AreaTriggerScript, but protected F12 checks only a bound script. **Installed plugin relevance UNKNOWN**, so **F12 OFF / NO-GO** until privately approved read-only checks and reviewed compatibility; no manual recursive hook. Research [F12 global hook parity](../research/PART29-F12-GLOBAL-AREATRIGGER-HOOK-PARITY.md).
- [ ] Review native GM/debug trigger handling and native `PlayerCannotEnter`/LFG forwarding versus prepacket F12 on pinned source for any further **concrete**, independently verified difference; document unknowns without inventing an exploit or changing protected code.
- [x] F13 native `GameObjectTemplate::GetCooldown` does **not** apply cooldown to spellcaster GO type; no cooldown patch needed.
- [x] F13 source-supported clicker-owned portal lifetime risk identified. #187 snapshots `go->GetOwnerGUID() == player->GetGUID()` before `TeleportTo`; after true result, avoids `go->AddUse` for clicker-owned GO that may have been removed on cross-map travel. Other/ownerless GO successful use count preserved. **No owner UAF reported; same-map owned GO use counter may differ.**
- [ ] Explicitly distinguish `Player::TeleportTo` returning `true` for **accepted or deferred** teleport from **actual confirmed exterior arrival**. Pinned `Player.cpp:1509–1517,1574–1581,1618–1645` permits delayed return and tears down old map before final return in far path. Check whether any additional narrow logic fix is provably required, or carry physical arrival as staging-only; **do not** alter #187 speculative code.
- [ ] Owner-real GO template, IP Vanilla stage, row 4436/28147, linked database and actual coordinates **UNKNOWN** and PRIVATE. Do not infer from public synthetic pin.

## 3. Three prepared owner-staging candidates (0/3 performed)

- [x] **GFPP 120-second** DRAFT [#186](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/186), exact `ea16700710698ca0515925838f3274c2da3760b8`: default-OFF world-thread atomic config snapshot on startup and `.reload config`, map-worker read no longer touches mutable ConfigMgr. All 13 exact-head workflows SUCCESS, including pinned 1,896/1,896 Worldserver full link [40562187307](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40562187307); **in-game 120s/reload/no-repeat NOT RUN**.
- [ ] **F12 Cathedral/Armory**: 610→604 and 612→606 outdoors with correct location/facing, no Graveyard/Library/Dungeon Finder regression, startup-config restart-only, no global ALE hook side effects. **NO-GO if callback relevance unknown**.
- [ ] **F13 exterior Atiesh**: original owned vs other-owned vs ownerless/static (only if actual installed GO supports); Vanilla IP-only, live object remains safe before/after teleport, invalid destination no count, no inside fallback, correct map/facing, same-map owned GO counter tradeoff. **#187 full-link must pass first**.
- [x] Two separate **UNFILLED PRIVATE owner worksheets** prepared: [Part28 original GFPP/F12/F13 pilot](../pilots/PART28-THREE-FEATURE-OWNER-STAGING-ACCEPTANCE.md) and [Part29 GFPP atomic/F12 ALE/F13 GO addendum](../pilots/PART29-GFPP-ATOMIC-OWNER-STAGING-ADDENDUM.md). Neither is permission to run. Before actual tests: explicit separate owner consent, installed source+DBC+DB compatibility, restorable nonproduction backups, rollback owner, disabled unrelated flags and private results.

## 4. Other mandatory blockers (still 0/5 total)

- [ ] **A02** real native Hunter pet manual autocast accepted click / SelfBot exclusion / IP allowed rank / birth identity / durable preference: **NoWrite**, default OFF, no SQL approval or writer. DRAFTs [#165](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/165), [#173](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/173), [#178](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/178). No verified owner acceptance.
- [ ] **A04 H1** purported real friend *item award* vs mere window/click, eligibility/group loot method/bucket/copy/turn; **H2** actual corpse sparkle but locked/hidden/denied quest row and counter-vs-bag mismatch. Distinct owner-private evidence needed; no real case proven. DRAFT [#179](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/179) / [#180](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/180); other guards OFF and not proven fixes. No private IDs/logs in public documents.
- [ ] **F15** separate operational milestone: both World/Auth crash and WARN/ERROR monitoring **NOT OPERATIONAL / BLOCKED_AT_R0**. [Launcher topology gate #185](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/185) needs **separate owner-approved private read-only** launch/parent, stdout/stderr/log prefixes, privilege and kernel/manager provenance. No speculative adapter/deployment.
- [ ] **F14** optional Vanilla /who remains OFF, not a sixth mandatory gameplay item.

## 5. Part30 working practice and evidence log

- [ ] Start by confirming both handover docs were read in full, refreshing GitHub refs, exact-head CI, original job logs and source lineage.
- [ ] Choose **one source-backed issue at a time**. Prefer completing #187 full linked check and carefully bounding F12/F13 native difference. If no actual change justified, document evidence and proceed to owner permission-dependent staging preparedness rather than repeatedly creating unrelated source-only PRs.
- [ ] Keep a single Part30 checklist on a docs-only draft; leave Part29 checklist historical. Update [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) only at verified substantive milestones. No auto-assigning Claude, no unnecessary PR churn.
- [ ] Record positive evidence and source of uncertainty, whether test is pure Python, C++ unit/native, full linked Worldserver, deployed staging or **owner in-game accepted**. Never substitute one for another.
- [ ] At end of Part30 prepare a complete Part30→Part31 handover with exact GitHub refs, status and **unresolved blockers**.

**Snapshot:** main and protected #160 frozen/unmerged. #186 complete pinned full link green. #187 own full link awaiting verification. Gameplay 0/5 owner-accepted, A02 NoWrite, A04 H1/H2 private facts missing, F15 BLOCKED_AT_R0. Claude still on break. No server or SQL changes made by this handover.
