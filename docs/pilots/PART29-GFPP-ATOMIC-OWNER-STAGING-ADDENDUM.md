# Part29 — GFPP atomic-config overlay: owner staging addendum (NOT RUN)

**PREPARATION ONLY. This is NOT permission to install, merge, restart or change config on production or staging.** Keep filled observations and any real server identifiers PRIVATE; this repository is PUBLIC. Follow the existing [Part28 three-feature owner staging checklist](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/docs/cs01-p27-to-p28-handover-20261027/docs/pilots/PART28-THREE-FEATURE-OWNER-STAGING-ACCEPTANCE.md) first. That checklist belongs to protected source #160; this addendum covers ONLY the unmerged **optional GFPP safety overlay** [DRAFT #186](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/186).

## Current evidence — do not conflate build and gameplay

- Source lineage: protected combined #160 **`a7523ebb823169edc969d971d00aa293119f2f05`**, unchanged and unmerged. Its source-only child GFPP config-safety candidate #186 **`ea16700710698ca0515925838f3274c2da3760b8`**, still draft and unmerged.
- Public pinned compilation, not owner's installation: Grimfeather/AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`, Playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091`, Individual Progression `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61`, module #186 `ea167007...`.
- [Actions 40562187307](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40562187307) **SUCCESS exact #186 HEAD**, completed 27 October 2026: 5/5 combined feature source pin tests, 18/18 GFPP native timer/source checks, 27 F12, 23 F13, 12 and 21 F14 source/model checks, C++17/20 policy binaries, and full pinned Worldserver **1,896/1,896 compile/link** with `nm -C` verifying `AddBotRaidConsumablesScripts`, `AddBotGolemaggReachGuardScripts`, `AddScarletMonasteryExitScripts`, `AddAtieshKarazhanPortalScripts`, `AddWhoListingScripts`. This verifies **linked symbols**, not activated functionality.
- [Independent linked Worldserver Actions 40562187299](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40562187299) **SUCCESS** on the same candidate and pinned revisions, producing a runner executable. No game server was started in either job.
- GFPP feature configuration **default OFF**. Snapshot read is `std::atomic<bool>` in GFPP timer and scheduling; `WORLDHOOK_ON_AFTER_CONFIG_LOAD` publishes the current value at initial load and reload. At the exact time of a concurrent reload and timer tick, relative observation order is not guaranteed; do not over-specify which wins if they overlap.

## Gate A — owner permission, compatibility, backup (NOT RUN)

- [ ] Owner separately approves the exact nonproduction stage, maintenance boundaries, controlled test characters, approved GFPP-only config changes, recovery owner and an explicit stop/restart policy.
- [ ] Privately confirm installed core, custom Playerbots, IP, module and addon build SHAs and GFPP item/spell/aura DBC and current world data; the public pinned CI versions are **not** proof of the owner's installed combination.
- [ ] Make and verify a **restorable staging backup** for executable, relevant module configuration and affected world/character state; record the successful restore procedure privately. Keep World/Auth services and production data out of this trial.
- [ ] Ensure unrelated module flags remain **OFF**, F12/F13 are controlled separately, no unapproved C++/SQL/DBC/Playerbots/IP patches, and existing map-worker count is unchanged.

## Gate B — one-shot and reload negative controls (NOT RUN)

| Step (only on approved restored staging) | Expected outcome | Owner result |
| --- | --- | --- |
| 1. Observe GFPP OFF baseline, prepare ordinary MC consumables and inspect bot aura | No newly scheduled special GFPP one-shot | NOT RUN |
| 2. Enable GFPP via **approved** initial load or config reload, then successful new `.bot consumables mc` for one eligible controlled bot | Exactly one pending record for eligible original bot; stopwatch starts with confirmed successful aura | NOT RUN |
| 3. At 119 seconds, then first eligible world update at/after 120 seconds | No premature attempt; exactly **one** refresh attempt at the due tick, not a guarantee of millisecond-exact observed timing | NOT RUN |
| 4. Continue past another 120 seconds without re-preparing | No second attempt or repeated aura overwrite | NOT RUN |
| 5. On a **new separate** successfully scheduled attempt, set the flag OFF via an approved config reload **well before** the 120-second deadline | Pending timer consumes once at original deadline **without** applying the new aura; no delayed retry even after ON is restored | NOT RUN |
| 6. Set flag ON via approved reload **without reissuing** the preparation command after a disabled baseline | No retroactive one-shot scheduled; new successful `.bot consumables mc` is required | NOT RUN |
| 7. Confirm bot absent/dead, out of original party/instance, wrong map instance, or another caster's aura in controlled separate trials | No target redirection, no unapproved aura removal, no retry or cross-caster overwrite; no Juju Flurry timing change | NOT RUN |
| 8. Restore flag OFF and replay ordinary baseline | Baseline behavior preserved; approved restore snapshot and configuration are verified | NOT RUN |

**Stop immediately** on unexpected teleport, aura destruction, bot scope breach, server warning/error/crash, persistence anomaly or unexpected config cross-feature effect. Do not attempt live SQL repair, fake auras, player data edits or ad hoc binary changes to force a green result. Privately capture only an approved, minimal incident description, test step and staged build identity.

## Gate C — separate F12/F13 acceptance (NOT RUN)

Use Part28's original owner checklist for F12 (Cathedral 610→604 and Armory 612→606, Graveyard/Library and Dungeon Finder negatives, real physical location/facing) and F13 (real Atiesh GO, correct Vanilla exterior gate position, stock negative cases, safe failed teleport). Their controls are **startup snapshot** flags: do **not** infer they change via `.reload config` from the GFPP test. **F12 additional conditional GO/NO-GO:** prior to enabling its 604/606 interception, privately verify whether the installed build registers a global `ALEScript::CanAreaTrigger` callback relevant to those exits. Native `ScriptMgr::OnAreaTrigger` calls that global layer before a bound `AreaTriggerScript`, while F12's `BoundScript` check only tests the bound trigger ID; a consumed packet skips the global callback. Read the [Part29 F12 ALEScript parity research](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/docs/cs01-part28-to-part29-handover-20261027/docs/research/PART29-F12-GLOBAL-AREATRIGGER-HOOK-PARITY.md). Installed relevance is UNKNOWN: do not assume a regression or attempt a speculative hook call. With unknown or relevant callbacks, leave F12 OFF until a separately reviewed and approved compatibility plan exists. An F13 source audit found no missing native spellcaster cooldown gate; it did NOT verify the owner's GO template, SQL, IP stage or world geometry.

## Final acceptance

GFPP #186 native link: **PASS**. GFPP actual in-game acceptance: **NOT RUN**. F12 actual in-game acceptance: **NOT RUN**. F13 actual in-game acceptance: **NOT RUN**. Combined mandatory gameplay acceptance: **0/5** (A02 native manual hunter pet and A04 H1/H2 separately blocked). F15 R0 still blocked and non-operational. No owner staging is authorised by these notes, no merge/deployment occurred, and Claude remains on break.