# Golemagg Playerbot Action Audit — Controlled Pilot and Rollback Plan

**Stage:** S5/S6 *proposal only* · **Not an instruction to deploy now**  
**Tracking:** [Master checklist #28 / A01](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28) · [issue #27](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/27) · [draft PR #30](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/30)  
**Target:** `src/Systems/BotGolemaggActionAudit.cpp` and the exact-name policy header; TWO independent defaults in `conf/mod_naxxramas_core.conf.dist`: `NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0` **and** `NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName = ""`.

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
- [ ] Confirm the active conf contains **both** `NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0` and `NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName = ""`, with no duplicate/conflicting keys. The C++ caches both at first `OnPlayerUpdate` call: **changing the file does not hot-toggle either control; restart is required**.
- [ ] Verify Worldserver starts with its usual modules, normal grouped Playerbot commands, instance entry and startup scripts intact.
- [ ] Under disabled config, verify **zero `GolemaggActionAudit READ ONLY:` messages**, no movement change, no Worldserver startup failure and normal MC ability use.
- [ ] Record actual binary/source SHA and test date; prior partial build results alone are insufficient.

## Stage 2 — Approved **one-bot** controlled pilot (not the full raid)

**Proposed initial target: Grau, the Combat Rogue.** Do not simultaneously enable diagnostic on all 40 raid bots. Only proceed after Stage 0–1 verification and separate owner approval of config=1 and the Worldserver restart.

- [ ] Confirm Grau is the correct **Altbot with game-client master**, is DPS and not tank/healer, is alive, in combat in Molten Core map **409**, and Golemagg is alive in the bot's playerbot context. No random bots or real players should be sampled.
- [ ] Explicitly set **both** keys in the backed-up active configuration, **only with prior owner approval**:
```ini
NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 1
NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName = "Grau"
```
  The exact name is an independent gate: **empty means no bot**, and wildcard `*` or a comma-separated list is never accepted. The real `IsAltBot()`, DPS/melee, map, combat and Golemagg checks still apply. Restart to load both options; do not infer enabled behaviour from merely editing the file.
- [ ] Observe only during Golemagg's encounter. Verify the log's fields: bot name, sample count, Magma Splash stacks, remaining aura duration, **`boss_lookup_present`**, boss HP %, bot-boss distance, current AI target and a bounded `recent_actions` string. In the current reference source implementation `ff77deb`, **boss HP and distance are `-1` when lookup is missing**; these are explicit unknown sentinels, not real measurements.
- [ ] Correlate a visible retreat/return with successive time-stamped log entries and video/screenshot. Note whether `reach melee`, `set behind`, `rear flank`, `combat formation move`, another movement action, or a target change appears. **A recent text tail does not prove the last action caused the observed position change.**
- [ ] Check whether the suspected approach occurs **while stacks are >=20**, boss health is **above 10%**, target is Golemagg and distance alternates near the nominal 12-yard back-off distance. In particular, do **not** incorrectly suppress the last-10% burn override, off-tank Core Rager movement, lava escape, healer repositioning or owner-issued moves.
- [ ] Record whether the bot truly returns to Golemagg **before the Magma Splash aura expires**, or whether the loop is caused by subsequent valid retreat cycles after expiration.
- [ ] Verify no log output from real players, tanks, non-DPS/healers, Random Bots, other maps, an absent/dead Golemagg, out-of-combat state or logout. Verify logs stop after leaving the encounter.
- [ ] Record if the probe produced **no** sample despite a visible issue. The pinned `FindTargetValue` searches the **bot's threatened-by-me list** and requires its group; when the bot has never successfully looked up Golemagg in the current combat window, the current draft probe intentionally refuses to sample unrelated MC encounters. Missing logs may also indicate hook timing/classification or the 24-line cap; never treat this as proof the movement issue is fixed.
- [ ] Restore config to **0**, perform the approved restart, verify the observer becomes silent and original behaviour is unchanged.

### Sampling interpretation and limitations

- The **earlier hardening** retained the 24-sample quota while a bot remains eligible even if Golemagg temporarily disappears from its threat context. The **current PR #30 threat-lookup improvement** can log changed recent actions when the lookup subsequently disappears **but only after the same Player previously found Golemagg alive in the same eligible combat window**. It does **not** persist a boss pointer, log unrelated MC encounters before that sighting, or replenish the quota on a lookup miss. This source behaviour is already part of reference PR #30 `ff77deb` and has passed pinned source/C++/full-link CI, but it has not been verified live. The cap still resets on leaving the eligible encounter, death, map change, incompatible role or logout, as defined in code. This is a **read-only diagnostic adjustment**, not a movement fix. A later docs-only PR head must receive separate exact-head CI.
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

- **Preferred disable path:** restore backed-up active config to `GolemaggActionAudit.Enabled = 0` **and** `GolemaggActionAudit.AllowedBotName = ""`, restart Worldserver in an approved maintenance window, verify no new audit lines. Revert the isolated module source/release using ordinary reviewed Git operations or restore backed-up known-good binary if necessary.
- There is no corresponding character/world SQL migration and **no database writes from this diagnostic**; do not execute SQL rollback or change DBC in response to it.
- A successful pilot is evidence only that an observer produced bounded logs. **It does not authorize a Golemagg movement patch**, upstream Playerbots source edits, merge, general production enablement, or deletion of the old working module revision.

**NEXT ACTION:** The pinned source reference PR #30 `ff77deb` has already passed [full Worldserver CI #39133607869](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39133607869), [source #39133607885](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39133607885) and [NT1 #39133607863](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39133607863). Check any newer documentation-only source SHA independently; **then** compare actual installed revisions, rehearse binary/config backups and rollback, and seek separate explicit operator permission before enabling the Grau-only diagnostic. No live test or movement fix is claimed.
