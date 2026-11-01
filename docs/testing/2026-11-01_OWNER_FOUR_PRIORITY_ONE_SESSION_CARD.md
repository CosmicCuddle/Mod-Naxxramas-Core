# CosmicCuddle's one-session P1–P4 test card — NOT READY TO RUN

**Date:** 1 November 2026. **Status:** DRAFT Information-only. **Owner:** CosmicCuddle. This is a short companion to [the full acceptance/source-evidence register](2026-10-31_FOUR_PRIORITY_UNIFIED_TEST_ACCEPTANCE.md); that longer record and approved decisions always control. **This document is not permission to merge, install, enable, restart, query/alter a live database, manipulate live loot or delete logs.**

## 0. The five readiness gates (Maintenance prepares; CosmicCuddle decides)

| Gate | What is needed? | Current evidence at this checkpoint |
|---|---|---|
| S0 source | P1 Warlock, P2 Hunter, P3 F15 collector, P4 H0/H1/H2 plus P4-H in ONE reviewable build | **DRAFT source candidate exists:** [combined #273 `e5431f03`](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/273); NOT merged or installed |
| S1 checks | Exact-head tests AND actual pinned full Worldserver compile/link, including failed/denied cases | **OPEN:** #273's [P4-H run 41322064241](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/41322064241) and 18 other visible exact-head workflows were **queued**, not passed, when checked |
| S2 integration | Verify actual installed Core/Playerbots/IP/module dependencies, configuration, loot hooks and current World/Auth collector process paths | **OPEN:** public pinned sources and source-parity are not proof of owner-host compatibility; integration compatibility review is owned by CS01 Maintenance and Naxx CS03, with Information providing separate source review. Grok CS02-IP is assigned to Individual Progression only |
| S3 restore-ready | Maintenance privately records current host revisions and customizations, sufficient backups and tested non-destructive rollback; preserve `MapUpdate.Threads=8` | **OPEN:** owner may perform routine backups, but no current exact staged restore proof is assumed |
| S4 approval / S5 result | CosmicCuddle separately approves the exact staged scope; then owner-observed PASS/FAIL with recorded results | **NOT REQUESTED and NOT RUN** |

**Current instruction to CosmicCuddle:** **Do nothing yet.** When the above S0–S3 gates are satisfied, Maintenance presents the exact build, scope, switches, rollback and a single approval request. No piece is independently activated beforehand.

## 1. The future test, in four short sections

Maintenance pre-fills the affected characters, expected inventory values, exact enabled keys, and evidence collection *privately*; do not publish personal account, server logs, character inventory or database dumps in public GitHub Issues.

### P1 — Warlock ritual + Meeting Stone

**Setup:** one Warlock, two valid nearby ritual helpers and one eligible distant target, in an approved test group.

- Warlock completes first green-circle ritual; confirm **second portal** is really created and helpers can use it.
- Distant target actually receives the final summon request, **accepts it and arrives** at the correct location. Seeing a visual portal alone is NOT a pass.
- Invalid target and ordinary Vanilla Meeting Stone controls must keep original level/group restrictions. No global stone bypass, double summon or crash.

**Record:** portal? / final request? / arrival? / ordinary stone still correct? Any wrong target or crash = **STOP**.

### P2 — Controlled Hunter Altbot ammo

**Setup:** eligible controlled Hunter Altbot with a valid, unbroken bow/crossbow and room in bags. Maintenance records inventory and actual selected ammo before the trial.

- Confirm approved **Jagged Arrow (11285)** increases in the **Altbot bag only**, without auto-equipping or changing ordinary human/RandomBot characters.
- Actually fire a normal ranged attack; compare before/after ammunition and the effective `InfiniteAmmo.Enabled` setting before declaring firing success or failure. Separate the supply check from consumption.
- Gun control uses **Accurate Slugs (11284)**, never arrows for the gun; selected rare **Doomshot (12654)** must NOT be minted. Invalid weapon, full bags and repeated preparation must fail safely.

**Record:** correct bag delta? / correct actual ranged shot? / wrong or rare ammo supplied? Any uncontrolled item creation = **STOP**.

### P3 — World/Auth readable console and crash evidence

**Setup:** Maintenance proves the approved **actual installed** World and Auth launchers and their read-only console/log sources first; do not substitute a disposable demo for real operational proof.

- Verify independent World/Auth stdout/stderr streams are captured, dated, readable next day and preserve original source logs without hijacking a running PM2/tmux session.
- Verify an ordinary **graceful stop** remains classified as **normal**, never a crash. Preserve available child-exit evidence and unfinished tail logs; only attribute a crash when real exit/signal evidence exists. **Do NOT intentionally crash the live realm.**
- Demonstrate the **30-day** rule with disposable files and an approved dry run before any real expiration. Originals, backups, unowned archives and young/open files must never be deleted; altered or missing old archives must not be silently called legitimate expiry.

**Record:** World captured? / Auth captured? / normal stop correctly labeled? / safe retention shown? Missing source or destructive retention = **STOP**.

### P4 — Two real humans, ordinary quest loot and Master Loot

**Setup:** two actual human-controlled characters A and B, legal quest/bag/bank states, valid common corpse, and a separate Master Loot two-quest setup. Do not use bot-only success as a substitute. Record actual item and quest objective before/after.

- **H0/H1:** A's legitimate needed quest item remains visible **and can actually be picked up** after B opens the corpse; opening order A→B and B→A must preserve rights. B cannot collect a hidden/denied row. Preserve stock group loot, FFA, gold, rolls and skinning.
- **H2:** a corpse must not falsely sparkle for B when nothing is genuinely actionable, and must still sparkle for an entitled viewer. Passive update must not secretly mark either player's loot as collected.
- **P4-H D3:** two quest items Q0/Q1, leader M sees both, A sees only Q1. Giving Q1 sends **M's own removed slot N+1** and **A's own removed slot N+0**; A gets Q1 exactly once, Q0 remains.
- **P4-H D1:** only when Master Looter role **changes after corpse loot was filled**, the new leader's restricted quest list must not give A a different item from the one clicked.
- **P4-H D2:** after A legitimately collected Q1, a stale Master Looter window **must not award a second copy**, even when leader's personal row is still visible. GameObject quest loot and other packet hooks need separate source/test coverage before this overall gate is cleared.

**Record:** correct human recipient? / exactly one copy? / viewer-specific removed slot? / ordinary loot untouched? Wrong person, duplicate, hidden award or lost rightful loot = **STOP**.

## 2. One-line results (fill only AFTER S4 approval)

| Priority | Outcome | Short evidence pointer or stop reason |
|---|---|---|
| P1 Warlock | NOT RUN | — |
| P2 Hunter | NOT RUN | — |
| P3 World/Auth archives | NOT RUN | — |
| P4 two humans + Master Loot | NOT RUN | — |

**Owner reply format when testing is actually authorized:** `P1 PASS; P2 PASS; P3 FAIL – Auth missing; P4 NOT RUN`. Maintenance fills technical evidence and reports; CosmicCuddle should not need to type long explanations.

## 3. Release boundaries

- S0/S1 source success is **not** S4/S5 permission or outcome.
- Do not merge any DRAFT into protected `main`, enable flags, replace the owner's installed module/Core/DB, run production SQL, alter gold/inventory, change World/Auth process managers or delete logs without specific owner approval.
- If any P1–P4 safety stop condition occurs, cease that staged trial and use the **approved exact restore/rollback**. Changing only an opt-in flag is not a substitute for restoring a modified DB or damaged inventory.
- This card deliberately avoids requiring additional A/B/C group-loot policy decisions: **the established owner rule is stock WoW/AzerothCore loot behavior without the bug**.
- Keep unrelated IP/paid-era policy risks (including [current IP #23 reload fail-open review](https://github.com/CosmicCuddle/Naxxramas-Server-Coordination/issues/11#issuecomment-6560071624)) in their own owner-gated workstream; do not silently enable either system for the P1–P4 session.
