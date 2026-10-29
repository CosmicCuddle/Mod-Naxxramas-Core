# P13-R13 — Pinned money-change hook subscriber source inventory

**29 October 2026 UTC. Source-only / disposable CI. No owner-host or production authority.**

[Pre-registered at master issue #28 comment 6499969648](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28#issuecomment-6499969648), BEFORE authoring. New isolated DRAFT from unchanged project-protected-by-policy Mod main at `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; no changes to original sources, SQL/DBC, configurations or player data.

## Why a new test instead of trusting code search

GitHub repository code search returned zero even when querying **known present** `ModifyMoney` and `HonorOverflow` symbols. Those zero-index results DO NOT prove an absence of registered money callbacks. Instead, CI checks out the following immutable repositories and invokes Git's direct **tracked-tree grep**, NOT GitHub's index:

1. `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`, paths `src/` and `modules/` (including those actually tracked in this core snapshot, but NOT external Git submodules absent from its object tree).
2. Project Mod `CosmicCuddle/Mod-Naxxramas-Core@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, path `src/`; this intentionally scans immutable protected-by-project main rather than test files or the owner-installed module directory.
3. `mod-playerbots/mod-playerbots@d750b4b3a50effdf22bedc8032f0e8e5f7cb8091`, path `src/`; this historical source pin does **NOT** prove the version installed on the owner server.

Original `git grep -n -F` matches on BOTH `OnPlayerMoneyChanged` and `PLAYERHOOK_ON_MONEY_CHANGED` across C/C++ tracked source files are printed with repository, path and line, and classified as either pinned-core API/dispatch references or **nonframework candidate references**. The scanner prints total source file counts, matched lines, and candidates, so every scoped zero-candidate result is reviewable. "Candidate" is deliberately weaker than *registered* or *installed*.

## Known core source contract — independent from R12 hypothetical hook callbacks

Original source-blob guards require `Player::ModifyMoney` to invoke the money change callback and `PlayerScript.h` to expose an `int32&` parameter; `PlayerScript.cpp` must forward that parameter via the enabled hook API; `ScriptMgr.h` must declare the same reference. Source guards are pinned to original Grimfeather blobs documented in R12. Four **invented synthetic scanner fixtures** test that a fake nonframework money hook and a fake registration in another tree would be classified as candidates, and that normal pinned core API references are not mistaken for installed subscribers.

This R13 inventory does **NOT** repeat R12's six synthetic money-mutation outcomes. It investigates actual **tracked source references** in specified commits. Any code found remains distinct from an actual runtime enabled script, actual money credited, module load order, script lifecycle, ThreadSanitizer result or gameplay evidence.

## What the result can and cannot establish

- **YES if verified by hosted CI:** which exact tracked source files under the three pinned trees contain either hook name, and whether any nonframework source candidate occurrences exist under this strictly defined scope.
- **NO:** full inventory of actual owner-installed custom modules, patches, hooks loaded by dynamic modules, owner configuration, real runtime registration, replay/reentry, money behavior or server incidents. Script registrations and hook activation cannot be established from an indexed search or a grep occurrence alone.
- **Additional limitation:** The scanner filters C/C++ source filename extensions and two literal symbol spellings. It does not examine compiler-expanded or dynamically constructed registration, files outside the declared paths, external submodules, arbitrary installed plugin directories or private N-Core code.

## Blocked design / safety

P13 H-DEFAULT, H-SELFBOT, H-REMEDIATION remain unselected. R7 shared `unordered_map` potential race remains a release HOLD. R9 actual Player/session lifetime unproven, R10/R11 money return/finality and R12 hook mutability are source-level findings only. Any money remediation needs owner policy and actual credited-delta contract, not assumed hook absence.

No merge/deploy/install, no `MapUpdate.Threads=8` change (must remain **8**), no original Mod/N-Core main or frozen PR #160 changes, no owner Worldserver, server/client, database, SQL/DBC, original core/Playerbots/IP or private addon mutation. F14 stays OFF/unwired, N-Core NoWrite and relay OFF, K1 Step1 not before 1 November 2026, D18 armed in-combat pet A→B HARD NO-GO; **mandatory owner-accepted gameplay 0/5**. For any future separately approved high-impact action, require dated restorable backups, restoration verification and rollback.

## Original hosted inventory results (initial evidence checkpoint)

The original test-only first-head `a72fe92d023c42d38be9870770759f45ff8c3fec` hosted [push run 40895811170 / job 123524462766](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40895811170) **SUCCESS, complete original 946-line job log independently read**; [PR run 40895844935 / job 123524586859](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40895844935) **SUCCESS, complete original 945-line job log independently read**. Exact first-head Git source scopes and counts:

| Immutable source and path boundary | Tracked C/C++ source files | Matched lines | Known core framework lines | Additional non-framework candidate lines |
| --- | ---: | ---: | ---: | ---: |
| Grimfeather core `src/` + `modules/` | 1718 | 6 | 6 | **0** |
| Project-protected Mod main `src/` | 38 | 0 | 0 | **0** |
| Historic mod-playerbots `src/` | 1422 | 0 | 0 | **0** |
| **TOTAL** | **3178** | **6** | **6** | **0** |

The exact six core framework references are:
- `src/server/game/Entities/Player/Player.cpp:11702` — money event call;
- `src/server/game/Scripting/ScriptDefines/PlayerScript.cpp:130,132` — dispatcher and enabled hook;
- `src/server/game/Scripting/ScriptDefines/PlayerScript.h:62,305` — hook enum and virtual callback;
- `src/server/game/Scripting/ScriptMgr.h:318` — manager declaration.

Both complete original logs also independently show **4/4 synthetic candidate-detector checks**, four pinned original framework blob checks, immutable Git pins, and the three-additive-path scope guard succeeding. No negative test reproduces owner economy.

**Precise conclusion:** No *additional literal hook-name references* were found in C/C++ tracked source under these **particular original tree paths and versions**. This is **not** a full runtime subscription inventory: no claim is made about other Git submodules, private or dynamically loaded modules, owner-installed versions, Lua bridges, dynamically constructed names or host hook activation. In particular, "zero non-framework candidates" is NOT a proof that no script could alter currency on the owner's live host.

All evidence is source-only. Keep R7 release HOLD and all P13 owner policy decisions OPEN. This research does not authorize enabling HonorOverflow or changing the core.
