# Golemagg Playerbot Action Audit — Controlled Pilot and Rollback Plan

**Stage:** S5/S6 *proposal only* · **Not an instruction to deploy now**  
**Tracking:** [Master checklist #28 / A01](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) · [issue #27](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/27) · [draft PR #30](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/30)  
**Target:** `src/Systems/BotGolemaggActionAudit.cpp`; `NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0` in `conf/mod_naxxramas_core.conf.dist`.

> **This is a read-only, OFF-by-default *diagnostic*, not a movement fix.** Even an exact-head C++ build PASS proves neither that PlayerScript updates are invoked for real Altbots nor which action causes a movement loop. Never modify Playerbots, AzerothCore, Individual Progression, raid boss stats or character data to make the diagnostic work. The player has no separate test realm; the existing live realm may be used for a **narrow, separately approved** pilot only after verified backups/rollback.

## Stage 0 — Mandatory proof before contemplating deployment

- [ ] Record the owner's **actual installed** Git SHAs for Naxxramas Core, AzerothCore, Playerbots and IP; note any local source edits. GitHub's pinned commits are reference builds, not evidence of the operator's machine.
- [ ] Verify that the selected draft PR revision has passed **source-safety tests, exact pinned C++ translation-unit compile, full Worldserver link and binary registration**. Cite the *same exact head* for all checks. Never infer full link PASS from an earlier head.
- [ ] Check the local fork's `PlayerbotAI::HandleRemoteCommand("action")`, `"target"`, `IsAltBot()`, PlayerScript `PLAYERHOOK_ON_UPDATE`, and `PlayerbotsMgr::GetPlayerbotAI` for compatibility, including controlled bots that are offline/relogging.
- [ ] Explicit owner approval of the **particular commit**, merge strategy (if any), build/install, config change, restart and game-test scope; no approval by implication from a successful workflow or an issue checkbox.
- [ ] Save rollback copies of the **known-working Worldserver executable**, module source/commit and active `mod_naxxramas_core.conf`. Verify these files can be restored. If any character/world data or DBC is part of the wider update, also back up complete characters DB, affected world rows and all active DBC/MPQ and prove recoverability. **The diagnostic itself has no SQL migration or DBC change.**
- [ ] Confirm logs have enough free storage; decide a short sampling interval and who may access chat logs. The sampled character name is logged, not passwords or account identifiers.
- [ ] Rehearse a normal config-disable/restart procedure without mass bot resets, forced `git reset --hard`, deleting build directories or changing source files upstream.

**Hard stop:** if any prerequisite or approval is missing, leave the active module unchanged with audit disabled; do not proceed.

## Stage 1 — Offline and disabled-mode acceptance

- [ ] Compile the approved revision against the owner's installed-compatible fork; review the first compiler/linker failure if any.
- [ ] Confirm the active conf contains **`NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0`** and no duplicate/conflicting key. The C++ caches this at first `OnPlayerUpdate` call: **changing the file does not hot-toggle the observer; restart is required**.
- [ ] Verify Worldserver starts with its usual modules, normal grouped Playerbot commands, instance entry and startup scripts intact.
- [ ] Under disabled config, verify **zero `GolemaggActionAudit READ ONLY:` messages**, no movement change, no Worldserver startup failure and normal MC ability use.
- [ ] Record actual binary/source SHA and test date; prior partial build results alone are insufficient.

## Stage 2 — Approved **one-bot** controlled pilot (not the full raid)

**Proposed initial target: Grau, the Combat Rogue.** Do not simultaneously enable diagnostic on all 40 raid bots. Only proceed after Stage 0–1 verification and separate owner approval of config=1 and the Worldserver restart.

- [ ] Confirm Grau is the correct **Altbot with game-client master**, is DPS and not tank/healer, is alive, in combat in Molten Core map **409**, and Golemagg is alive in the bot's playerbot context. No random bots or real players should be sampled.
- [ ] Explicitly enable `NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 1` in the backed-up active config; perform the approved restart. **This produces logs, never direct AI commands**.
- [ ] Observe only during Golemagg's encounter. Verify the log's fields: bot name, sample count, Magma Splash stacks, remaining aura duration, boss HP %, bot-boss distance, current AI target and a bounded `recent_actions` string.
- [ ] Correlate a visible retreat/return with successive time-stamped log entries and video/screenshot. Note whether `reach melee`, `set behind`, `rear flank`, `combat formation move`, another movement action, or a target change appears. **A recent text tail does not prove the last action caused the observed position change.**
- [ ] Check whether the suspected approach occurs **while stacks are >=20**, boss health is **above 10%**, target is Golemagg and distance alternates near the nominal 12-yard back-off distance. In particular, do **not** incorrectly suppress the last-10% burn override, off-tank Core Rager movement, lava escape, healer repositioning or owner-issued moves.
- [ ] Record whether the bot truly returns to Golemagg **before the Magma Splash aura expires**, or whether the loop is caused by subsequent valid retreat cycles after expiration.
- [ ] Verify no log output from real players, tanks, non-DPS/healers, Random Bots, other maps, an absent/dead Golemagg, out-of-combat state or logout. Verify logs stop after leaving the encounter.
- [ ] Record if the probe produced **no** sample despite a visible issue. This may mean update-hook timing/Altbot classification/action context mismatch and must not be treated as proof the issue is fixed.
- [ ] Restore config to **0**, perform the approved restart, verify the observer becomes silent and original behaviour is unchanged.

### Sampling interpretation and limitations

- The **prepared hardening change** retains the 24-sample quota while a bot remains in eligible MC combat even if Golemagg temporarily disappears from its target context; it **does not** reset and refill that quota on transient boss lookup loss. The cap still resets on leaving the eligible encounter, death, map change, incompatible role or logout, as defined in code. This fix is **not yet on PR #30** and needs new exact-head CI after safe promotion.
- The observer permits at most **24 changed recent-action tails per bot per continuous eligible combat window**, with **at least 2.5 seconds between**. In a busy fight that may exhaust its cap in approximately one minute; **an absent log near 50% boss health may simply mean sampling ended**.
- If the owner-observed movement occurs later than the sampled window, **do not lengthen or broaden production logging ad hoc**. Record the timing gap and return to separate code review for a more targeted bounded sampler.
- Playerbots `GetLastAction()` only exposes a recent text tail (about 512 characters upstream); `OnPlayerUpdate` sampling is not a trusted atomic action callback. Matching strings alone cannot prove cause or establish safe veto logic.
- The audit does not measure raid DPS, healing throughput or Golemagg's Core Rager control. Those remain independent issues.

## Stage 3 — Evidence-led decisions (do not immediately implement a veto)

| Field observation | Next engineering action |
| --- | --- |
| `reach melee` / boss-targeted formation movement repeatedly appears during high-stack retreat | Verify the exact action's `GetTarget` / `isUseful` code and public module interception surface; test suppression in an offline model before separate default-OFF runtime PR |
| Action changes occur but not targeting Golemagg | Investigate target choice/core-rager, formation or group tactics; do not block all movement actions |
| Re-entry occurs only after Magma Splash expires | Existing intentional retreat behaviour may be working; review DPS loss and reapplication rather than mislabelling as command fight |
| Loop persists with no splash stacks or boss below 10% | Rule out 20-stack backoff as primary cause; investigate generic movement/AI target/follow actions |
| No reliable action observations | Re-evaluate logging hook and diagnostic viability; do not assume an upstream patch is required |
| Issue appears resolved but tank deaths continue | Investigate healing, debuff load and Core Rager positioning separately; this is not acceptance of Golemagg |

## Rollback, scope and signoff

- **Preferred disable path:** restore backed-up active config value `GolemaggActionAudit.Enabled = 0`, restart Worldserver in an approved maintenance window, verify no new audit lines. Revert the isolated module source/release using ordinary reviewed Git operations or restore backed-up known-good binary if necessary.
- There is no corresponding character/world SQL migration and **no database writes from this diagnostic**; do not execute SQL rollback or change DBC in response to it.
- A successful pilot is evidence only that an observer produced bounded logs. **It does not authorize a Golemagg movement patch**, upstream Playerbots source edits, merge, general production enablement, or deletion of the old working module revision.

**NEXT ACTION:** Wait for the exact pinned full Worldserver link of PR #30 to pass, then compare the operator's actual source and prepare a small, separate approval request for any configuration enablement/in-game pilot.
