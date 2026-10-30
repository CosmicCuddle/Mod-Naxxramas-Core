# Module Edits — Part 40 → Part 41 Recovery Handover

**Prepared:** 30 October 2026 (UTC). **Purpose:** reconstruct continuity after an interrupted chat that did not produce its usual handover.  
**Repository:** [CosmicCuddle/Mod-Naxxramas-Core](https://github.com/CosmicCuddle/Mod-Naxxramas-Core).  
**Status:** documentation-only, non-authorising. This snapshot is not a compilation, merge, live installation, server backup or gameplay acceptance.

## 1. Start here in Part 41

1. Consult the [master development register #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), the [module team queue #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48), and current PR state **including new comments/CI after this snapshot**. The last pre-Part-40 complete engineering handover is [draft #236](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/236), and its Part 38 living checklist; later chat progress is summarised below, not assumed included in #236.
2. Keep owner priorities in this order: **P1 Warlock second-stage portal**, **Hunter arrows/ammunition**, **F15 functional crash/error observation plus daily World/Auth console archiving**, **A04 both human-human quest-loot bugs**. Owner also requested safe, genuinely test-ready secondary candidates, but none takes priority over these four.
3. Do **not** ask for further serial owner terminal copy/paste commands; owner explicitly requested reducing manual workload. Favor GitHub-only source review and runner-owned synthetic testing while the host inventory/approval gate remains.
4. Distinguish **source/model pass**, **full native C++ Worldserver link**, **owner's actual installed binaries/configs**, **in-game result**, and **released feature**. The existing main-module native build is not proof of the draft combinations or owner-installed system.
5. Do not edit protected-by-project main, frozen draft #160, owner machine, databases, SQL/DBC/client, IP/Core/Playerbots, start or stop daemons, change `MapUpdate.Threads=8`, merge or enable an experimental feature without appropriate separate approval and safeguards.

## 2. Exact GitHub source/checkpoint inventory

- Module `main` last observed **80e9de1c39a6dc995188a80c31a5e785d0f2a6f9**. Confirm live head before relying on it. Documentation baseline **1.0.6.8.4**; development line **1.0.6.8.5** ([roadmap](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/main/ROADMAP.md)).
- [#247 first controlled build profile](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/247): DRAFT **62ffe47c602d3f045d08408e6c72e2193841adff**. Earlier full Worldserver linked in isolated CI using historical Oct 12 Core/Playerbots/IP dependencies; NOT the currently proven installed host, and does NOT include the newer Warlock repair.
- [#248 Warlock second-stage pilot](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/248): DRAFT **aac4b3c75de3d83896982cf4fa52efffb9d0bc85**, default OFF. Historical [native compatibility build 41089053235](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41089053235) described in master issue #28 as successful. The owner's second-stage S6 gameplay remains FAIL/unaccepted; no native result authorises installation.
- [#253 cross-IP integration workflow](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/253): DRAFT **766e99b50d3902429234c4aa494fdd19ca99dfe4**, base **be17ead517b6db268a19063aa033b8af706031fa**. Exactly ONE new CI workflow file, no module runtime edit. Pins Grimfeather Core **8daffdabe9202c228e45d833c9a1d399597a15cd**, Playerbots **e88cc4099e69f35126b28942a412ca702d20453b** with two temporary runner-only historic compatibility line substitutions, current unmerged Cosmic IP grouping **e0cd785f6b2090c8f099c824811077d0ab2a9de5**, and unmodified combined module Warlock/Hunter/Quest Loot/EP runtime source. [Original workflow run 41138075456](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41138075456) was **IN PROGRESS** at this handover inspection, NOT verified green. Check exact-head jobs and original results; do not confuse other runs/old IP revision with this combined test.
- [IP grouping draft #3](https://github.com/CosmicCuddle/mod-individual-progression/pull/3): DRAFT **e0cd785f6b2090c8f099c824811077d0ab2a9de5** at snapshot. Source-only exact-head checks reported successful; historical older IP native runs completed successfully, but latest exact-head native link was still pending in the cross-project record. Preserve existing approvals and compare the latest CI first.
- Current module F15 archive test chain: [#249](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/249) pure policy → [#250](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/250) temporary-file I/O → [#251](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/251) intentionally failing legacy-gap negative controls → [#252](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/252) crash-recoverable checkpoint-journal fake streams. #252 DRAFT **90e269d4f43bb653ec7979ec7a0a55e713ef8809**, [original CI 41133408324](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41133408324) reported **SUCCESS, 101/101** (38 policy + 29 fake-file positive + 10 OLD-gap demonstrations + 24 journal failpoints). **Ten passing negative demonstrations intentionally reproduce previously known vulnerabilities**, not fixes. All #249–#252 work is OFFLINE and nondeployable.

All SHAs are point-in-time references. Branches/CI may have moved since the recovery.

## 3. P1 Warlock portal — still a mandatory in-game failure

Owner previously observed the **first green Ritual of Summoning portal and helper participation working**, followed by an incorrect Vanilla-only Meeting Stone restriction when clicking the second portal. Database read-only evidence: **GO194097** is `GAMEOBJECT_TYPE_MEETINGSTONE` / type 23, while first ritual GO194108 is type 18. Relevant core's generic type-23 handler casts **23598** instead of the expected **61994** continuation; [issue #84](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/84) has exact source discussion.

Draft #248 introduces narrow, default-OFF type-23 GO194097 created by spell61993 continuation to 61994, with same-raid/target/min-level validations. Native compilation and isolated checks do NOT prove final in-game target teleport, helper class, reagent/channel behavior, true spawned GO identity or no duplicate casts. Preserve genuine Vanilla dungeon Meeting Stone restriction. Obtain independent review, verify actual owner source, run explicitly authorised small test; record each stage and negatives. Keep S6 FAIL until owner confirms the full sequence.

## 4. Hunter ammunition — separate from pet autocast

[Issue #31](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/31) and main module source include the Hunter bot ammunition provisioning design; experimental distribution/config is default OFF in combined pilot. Confirm Altbot inventory, selected compatible ammo, actual arrow/bullet counts and firing consumption under approved live test. CI source/build checks are not gameplay acceptance. Avoid unrelated Hunter pet autocast changes: that remains separately IP/N-Core-coordinated with NoWrite/relay OFF and strict old-pet/active-click safety. Do not conflate the two features.

## 5. F15 — owner-requested crash reports + console archives

Authoritative [master requirement #28 comment](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6532886167), [coordination implementation/readiness #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4).

**Owner-approved intended outcomes, NOT installed:**
- Identify/report credible crashes and errors without treating intentional stops as crashes; preserve a legible incident history and provenance.
- Capture ongoing Worldserver AND Authserver console/log output in separate readable timestamped plain-text daily archives; previous day's available lines must survive normal rolling/clearing/restarts, subject to actual sink completeness limits.
- Unattended safe cleanup: only **verified collector-owned, closed archives older than 30 × 24 hours**, not arbitrary files or Crash-History. Don't delete active or original logs.
- Ensure archive naming/collision safety, checkpoint persistence, restart recovery, disk quota reserve, minimal interference with running services, private access, bounded processing and rollback.

**R0 source facts recorded in prior active session:** Worldserver is PM2-managed with separate large stdout/stderr logs; Authserver uses a tmux→bash path, separate native Auth.log FD3 is observed but console parity is NOT proven. Existing large PM2 log history must not be bulk-recopied. Previous owner facts were read-only; current host topology/revisions still need verified private approval to operate.

**Actual state:** no deployed PM2/tmux adapters, no complete Auth PTY parity, no automatic UTC midnight seal, no operational unattended prune, no proven reliable fatal-signal-to-crash semantics or tested live restart. #249–#252 are disposable CI research fixtures only. One integrated Maintenance-owned implementation should follow source review with a no-host synthetic pilot before separately approved staging. No more repetitive owner shell commands.

## 6. A04 human-human Quest Loot Protection

[Issue #109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109) records **both** owner-reported symptoms: inappropriate successful loot pickup by a wrong human group member and corpses sparkling for a human who then cannot loot. The narrow existing packet policy and diagnostic research do not independently solve both. Preserve stock eligible quest drops, normal Need/Greed/FFA/MULTI_DROP, coin, group entitlements, bot behavior. Live human-human incident data, active config/versions and owner gameplay results are not yet verified. Do not call combined #253 a fix: it only compiles existing narrow A04 source.

## 7. Owner progression and F14 rules — no accidental broadenings

Cross-project [#9 F14 rndbot scope](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/9) and [#10 grouping rules](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/10).

**Concealment** is **ONLY positively identified Random Bots (rndbots)** of Blood Elf/Draenei races 10/11 as seen by Vanilla-era observers. Real humans, Altbots, Selfbots and unknown identities **must not be hidden by this rule**. Neither race alone nor name/level/account heuristics securely proves rndbot identity. /who and real-world visibility/combat must be consistent. No F14 full implementation or accepted owner gameplay yet.

**Grouping:** if existing `IndividualProgression.EnforceGroupRules=1`, allow same-expansion bands, not exact tier: Vanilla **0–7**, TBC **8–12**, WotLK **13–18**. Different stages within an era may group. Owner's separate Blood Elf/Draenei anti-Vanilla grouping statement currently covers human and bot races 10/11; **human race 10/11 remains visible**, regardless of grouping restrictions. Keep original boolean OFF behavior. Do not rewrite human tier or automatically dissolve existing parties.

Real rndbot race 10/11 must not be assigned Vanilla stage 0–7, through spawn/login/manual/group sync, but **must not be illegally advanced to stage 8 through a Vanilla server cap**. Under Vanilla eligibility, suppress incompatible rndbot participation, not delete it. IP draft #3 includes a pure stage-floor predicate but has **not wired all runtime rndbot admission paths**. Direct bot group-add/rejoin, old persisted parties, stage advancement while grouped, special groups and default-OFF behavior remain review/owner-decision gates. Preserve already working ordinary bot invites.

## 8. Hold flags and cross-project boundaries

- **HonorOverflow** P13/R7 map-worker global state race and payout/identity uncertainties: release HOLD, safe first-profile OFF. Never alter the owner's eight map-update workers to mask the issue; no economy compensation/policy selected.
- F14 is OFF/unmerged; no speculative hide-all code. Frozen integration #160 stays untouched.
- N-Core Hunter pet autocast NoWrite and relay OFF; D18 already-armed in-combat pet A→B **HARD NO-GO**. K1 separate gating/authorization; do not turn a coordination comment into an active developer assignment.
- Individual Progression, Core and Playerbots source ownership is separate. Coordinate implementation-heavy work with **Server-Side-Maintenance**, and rule changes with **Server-Side-Information** through existing Issues; do not duplicate active tasks or change other developers' responsibilities.
- Other optional tests: Molten Core GFPP one-shot, Eastern Plaguelands tower lock and conditional announcement, Golemagg read-only observer, baseline class/racial/events only after same-binary/DB/DBC/owner review. They do NOT supersede four priorities.
- Dated restorable backups and rollback planning before changing owner binaries, DB, DBC, effective configs, data or live realm. No approvals are inferred from source/documentation work; gameplay acceptance still not achieved for priority pilots.

## 9. Concrete continuation sequence

1. **CI review, no host:** inspect [#253 exact head](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/253) and [run 41138075456](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41138075456) to completion. Report source job vs native link separately, any failure at its actual step, and whether it includes newest IP grouping. Never call queued/in-progress PASS.
2. **Maintenance single integrated F15 work item:** use [coordination #4](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/4), [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), and #249–#252 tests to plan one no-host reviewable operational candidate. Resolve PM2 World stdout+stderr and tmux/Auth parity without touching owner host; include durable daily archives, retention safety, crash/stop discrimination and limits. Avoid another unrelated prototype that cannot progress toward owner test.
3. **Owner first pilot readiness:** reconcile true owner-installed Core/Playerbots/IP/module revisions and effective configs against pinned CI; assess SQL/DBC and backup/restore. Do not infer from historical CI or screenshots that all versions match.
4. **P1/Hunter/A04 test matrix:** preserve safe OFF defaults until separate approval for a limited test, then test Warlock second portal, Hunter Altbot inventory and both human-loot bugs with positive and negative cases. Do not claim corrected while failing/untested.
5. Record major findings on the **existing** Issues/PRs, direct implementation actions to Maintenance where appropriate, and refresh this handover only with verified evidence. CosmicCuddle decides mergers, gameplay policy and live rollout.

**This file is a recovery record, not a deployment plan or proof of live fixes.**
