# Mod-Naxxramas-Core — Part 31 Living Development Checklist

**Prepared 28 October 2026 UTC by CS01 for a future Part31 conversation. PUBLIC documentation-only draft, non-authorising.** This is not a new release, a change in feature toggles or evidence of owner gameplay acceptance.

**Before starting: read [the complete Part30→Part31 Engineering Handover](2026-10-28_PART30_TO_PART31.md) and this checklist IN FULL.** If you still work in Part30, leave Part30's living checklist as the active progress log; use this document only when the Part31 handoff is needed. The [complete Part30 historical checklist](2026-10-27_PART30_LIVING_DEVELOPMENT_CHECKLIST.md) contains the source-by-source evidence and prior revisions.

## 0. Mandatory safety — recheck every Part31 session

- [ ] Refresh GitHub `main` and ALL relevant DRAFT PR HEADs, branch ancestry, changed files, CI status, drafts/merges. Never assume this prepared document reflects later changes.
- [ ] **Protected `main` and combined DRAFT #160: no edits, merge, deployment or cherry-pick.** Preserve source candidate DRAFT #186 GFPP, #187 F13, #189 CI-only and Part30 docs #188. Any new source patch would require independently justified *isolated* branch and separate review.
- [ ] **No owner production or staging host, World/Auth service, private SQL/DBC/logs/player/quest/item records, binary installation, build change, configuration, restart, feature toggle, N-Core, core, Playerbots or IP edits without explicit separately scoped owner permission.** This user's routine “please continue” authorises PUBLIC code/research only, not private access or release.
- [ ] **Five mandatory gameplay features stay 0/5 owner accepted** unless a real, authorised private in-game test proves both positive and negative behavior and the owner signs off. Source/native tests and 1,896/1,896 link are **NOT** gameplay.
- [ ] Preserve `MapUpdate.Threads=8`; F12/F13 startup-snapshot flags and GFPP's distinct atomic reload behavior are not interchangeable.
- [ ] Any future owner-approved nonproduction trial requires **privately verified installed dependency/DB/DBC parity, tested restorable backups and rollback, precise feature scope, isolated negative controls and private evidence** before any change.
- [ ] PUBLIC GitHub: no owner-private module/build inventory, SQL IDs, logs, host/user/account/creature/quest/item identifiers, personal data or secrets. Claude remains on break: do not assign or assume tasks.

## 1. Current immutable snapshot — verify, do not assume

| Candidate | Known verified head at 28 Oct 2026 | Public CI status / role |
| --- | --- | --- |
| `main` | `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` | Frozen |
| Combined [DRAFT #160](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/160) | `a7523ebb823169edc969d971d00aa293119f2f05` | Frozen gameplay base, unmerged |
| GFPP child [DRAFT #186](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/186) | `ea16700710698ca0515925838f3274c2da3760b8` | Full pinned native Worldserver PASS |
| F13 lifetime child [DRAFT #187](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/187) | `de6816a1e3f94f2e530fca093dd596c11903b8d3` | [Actions 40584203475](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40584203475): source/native and **five-symbol** full 1,896/1,896 linked Worldserver PASS |
| One-workflow CI fix [DRAFT #189](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/189) | `fbecdf223eb0a5e4970573eda482aeed161a0f5c` | [Actions 40599644891](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40599644891) BOTH jobs PASS; 498 Python cases, **six existing EP skips**, F13 GO 6/6, **three-symbol** full 1,896/1,896 link |
| Part30 documentation-only [DRAFT #188](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/188) | `21835fdc2ed1d8948ecee16671f721b7e531082b` | Four Markdown-only paths, source audit and owner worksheets |
| Part31 preparation | `docs/cs01-part30-to-part31-handover-20261028` | **Documentation-only child stacked on #188** containing Part30→31 handover and this checklist; refresh final head/PR number, never assume it was merged |

Published CI core `8daffdabe9202c228e45d833c9a1d399597a15cd`, Playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091`, IP `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61`. **Not necessarily owner's installed versions.**

## 2. Completed PUBLIC milestones — no needless repeated work

- [x] Exact-head F13 #187 real-core GO lifetime source checks and five-registered-symbol full Worldserver link PASS.
- [x] Original legacy CI source job fixture failure conclusively diagnosed: missing pinned four-file `acore` checkout, distinct old #187 native binary still PASS.
- [x] Isolated #189 one-workflow-only fixture correction exact-head source job and full Worldserver job **both SUCCESS**. No six F13 tests skipped. Distinct six EP prior source skips remain honest coverage limitations.
- [x] F12 pinned global `ALEScript` registration/dispatch, prepacket consumption and non-debug GM route divergence documented as conditional source-level parity, NOT confirmed owner defect.
- [x] Part30 read-only **298 distinct scoped public C++/header files** scanned: zero **direct** ALE callback symbols in those selected scopes; actual installed callback absence NOT proved. Full audit [Part30 registered ALE R0 note](../research/PART30-F12-ALE-REGISTRY-READONLY-R0-GATE.md). Stop over-expanding the audit without an actionable hypothesis or explicit owner-approved R0.
- [x] [Master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) updated at material Part30 milestones, with unmerged protected refs and 0/5 owner accepted.

## 3. First next useful evidence — F12 and exact real environment

- [ ] **F12 OFF / NO-GO** while installed core and module callback registrations are unknown. A registered global `ALEScript::CanAreaTrigger` could observe or affect exit 604/606 when native runs; F12 eligible prepacket consumption bypasses it, even if the trigger-specific script ID is blank.
- [ ] Only after **separate written PRIVATE R0 read-only authorisation**, inspect the **effective installed** source/build/module registry and whether any callbacks relevant to those two exits are actually registered. Following the [public R0 decision protocol](../research/PART30-F12-ALE-REGISTRY-READONLY-R0-GATE.md) must not leak private details into this PUBLIC repo. If inconclusive/relevant, leave OFF and request a separately reviewed design.
- [ ] Independently agree desired normal-player, non-debug GM and debug-GM exit route expectations; native skips script callbacks for non-debug GMs but does not skip all native teleport logic.
- [ ] Do not try to “fix” with recursive `sScriptMgr->OnAreaTrigger` from the packet hook; safe side-effect/duplicate dispatch behavior is unproven.

## 4. Owner-approved NONPRODUCTION gameplay — NOT RUN

- [ ] **Gate 0 permission and recovery:** separate owner written approval for exact nonproduction scope and each enabled switch; independently verify **actual installed core/PB/IP/module/build**, effective world/DBC/GO data, **restorable tested backups and rollback**; keep all unrelated flags OFF, preserve eight map threads. Do not start on production.
- [ ] **GFPP 120 seconds:** one genuine successful eligible MC aura, no early refresh, one due attempt after >=120s, no second attempt, safe dead/absent/caster/party conditions; test OFF/ON via approved atomic config reload, requiring a new command for a new window; check Juju separation; rollback OFF. Owner result **NOT RUN**.
- [ ] **F12 physical Scarlet doors:** eligible human Cathedral 604 and Armory 606 reach correct own exterior location and facing/no bounce; reject unsafe live rows; preserve Graveyard/Library, Dungeon Finder, native quest/script and GM agreed outcomes; only after R0 parity gate and approved restart; rollback OFF. Owner result **NOT RUN**.
- [ ] **F13 actual Atiesh game object:** qualifying Vanilla-stage real GO click, verified final exterior Karazhan landing/facing, owner/other-owner/ownerless use-count and lifetime, wrong progression/GM/foreign-GO/failed request negatives, same-map owned GO tradeoff where legitimate; accepted `TeleportTo(true)` alone is **not** arrival proof; rollback OFF. Owner result **NOT RUN**.
- [ ] Record all staged observations and incident identifiers PRIVATELY. PUBLIC only non-identifying yes/no, high-level outcome and verified authorisation status. Owner approval, not CS01, determines acceptance.

## 5. Other mandatory gates (independent of F12/F13 CI)

- [ ] **A02 Hunter pet manual autocast — NoWrite.** Needs actual human accepted preference click distinction, excluding SelfBot automation, IP legal rank changes, pet birth identity and durable writer/revision evidence. Protected default OFF, no SQL/schema/writer authorisation.
- [ ] **A04 quest loot — H1/H2 separately unverified.** H1 actual friend item award vs window; H2 sparkle/hidden/denied quest row and count-vs-bag mismatch. Owner-private facts required, not in PUBLIC GitHub. No optional guard called fix before genuine case is proven.
- [ ] **F15 BOTH World/Auth crash and WARN/ERROR — BLOCKED_AT_R0, NOT OPERATIONAL.** Requires separately approved private read-only launcher/parent/stdio/log/kernel provenance. No speculative automation, false crash injection or service modification.
- [ ] **F14 optional Vanilla /who** remains OFF and outside the five required gameplay acceptance items.

## 6. Working practice, review and future handover

- [ ] Choose one **source-backed** engineering issue at a time, with exact-commit evidence and isolated DRAFT scope. If installed/private facts are essential, explicitly mark **BLOCKED**; don't pad progress with redundant scans, unknown “fixes”, automatic staging or unnecessary full CI.
- [ ] Prefer confirming a meaningful existing run over rerunning unchanged expensive full-link CI. Treat EP six upstream-layout skips as not executed at #189; older EP workflows use DIFFERENT pinned dependencies and cannot close that claim.
- [ ] Keep only this Part31 checklist current during Part31, retain Part30/earlier docs as history. Update [master issue #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) only for substantive verified milestones. No Claude work assignments.
- [ ] After genuine Part31 progress, prepare a complete Part31→Part32 handover with exact SHAs, source evidence, stage acceptance outcomes (or NOT RUN), owner approvals and explicit blockers **before** a new chat is needed.

**Opening state (28 October 2026, before Part31 work): FIVE mandatory owner-accepted gameplay outcomes = 0/5; GFPP/F12/F13 pilot tests NOT RUN; F12 public-source risk documented but installed R0 unknown and master OFF; F13 #187 and CI #189 pinned native links PASS; A02 NoWrite; A04 H1/H2 unverified; F15 BLOCKED_AT_R0. No server, SQL/DBC, owner config or protected code change.**
