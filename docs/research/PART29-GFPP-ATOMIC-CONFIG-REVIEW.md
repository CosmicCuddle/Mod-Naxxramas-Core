# Part29 — GFPP one-shot config read safety (isolated C++ child of protected #160)

**DRAFT / REVIEW-ONLY / NO MERGE OR INSTALL.** The owner has not approved staging, any config change, running an installed server or gameplay. This isolated child starts at exact unchanged, protected combined #160 `a7523ebb823169edc969d971d00aa293119f2f05`. The only production-code change is inside `src/Systems/BotRaidConsumables.cpp`. All main, core, Playerbots, IP, SQL, DBC, host configs and game clients remain untouched. Neither F12 nor F13 implementation changes.

## Confirmed source-level safety gap

The original #160 GFPP one-shot reads `sConfigMgr->GetOption<bool>(NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled, false)` twice: while scheduling a successful aura on `.bot consumables mc`, and in `ProcessOneShotFireProtections` run from `NaxxramasCoreBotRaidConsumablesTracker::OnPlayerUpdate` via `PLAYERHOOK_ON_UPDATE`. The latter is a map-worker read. AzerothCore's mutable ConfigMgr option storage can be written by config reload on the world thread without an equivalent read lock inside `GetOption`; this is the same previously researched hazard handled in CrossMapAuraSafety, F12/F13 config snapshots and A04 #175. It is an **inferred C++ memory-safety/data-race exposure in the default-OFF optional feature when active/reloading**, not a witnessed realm crash.

The same file **already** has a `NaxxramasCoreBotRaidConsumablesWorld` subscribed to `WORLDHOOK_ON_AFTER_CONFIG_LOAD`, taking `CrossMapAuraSafetyEnabled` as an `std::atomic<bool>` snapshot. The narrow GFPP correction follows that existing local precedent:

1. Add `std::atomic<bool> GreaterFireProtectionOneShotEnabled{ false }` and an atomic relaxed-load helper, keeping the feature OFF until the world config hook runs.
2. Read the GFPP `sConfigMgr` option **once**, in `OnAfterConfigLoad` on the world thread, and atomically store it alongside the existing CrossMapAuraSafety option. Continue updating on both initial load and `.reload config` so a reload **can still disable** pending one-shots (no surprise restart-only conversion). A reload that enables the feature allows future eligible command sequences, as before.
3. Replace only the two GFPP runtime mutable-config reads with atomic loads. **Preserve** the timer's exact 120,000ms deadline, one-time consume-before-eligibility, command/instance/group checks, cross-caster aura exclusion, failed-attempt no-retry semantics and one pending record per original GUID.
4. Keep exact P0/F12/F13/F14 other feature blobs and configs pinned by the existing source assembly test; update the one GFPP source fingerprint only on this child. Never edit #160 to erase the reviewed baseline.

**Memory order:** relaxed is sufficient for this independent Boolean because it publishes no associated non-atomic object graph or payload. A time-concurrent `.reload config` and a due timer might observe OFF or ON depending on atomic ordering—consistent with a single live toggle; it does not guarantee a globally ordered game action. Importantly, it removes the unsafe direct access to ConfigMgr's mutable option map from the timer path.

## Evidence and acceptance boundary

The inherited GFPP standalone native C++ timer test still verifies exact 120 seconds, no early retry, an overshoot tick and independent fresh command. Updated original source assertions and five new source contract tests require one default-OFF key, one world-thread `GetOption`, two runtime atomic loads, reload disable *after* timer consume and no change to CrossMapAuraSafety or eligibility paths. Existing combined native full pinned AzerothCore+Playerbots+IP Worldserver workflow compiles/links the **current child HEAD** without launching a game. Its exact result must be independently checked before claims of success.

**Still unresolved:** no owner installed-source compatibility, runtime tests of `.reload config` races with a real map worker, exact effect start/remaining aura, 120s stopwatch, item/DBC verification, bot scope on actual Playerbots, or owner-backed rollback. GFPP remains default OFF and **NOT owner accepted**. Do not activate the switch without a separate owner-approved restored staging plan. F12/F13 also remain untested. Overall five gameplay requirements remain **0/5**; A02/A04 blockers, F15 BLOCKED_AT_R0 and frozen #160 remain unchanged.
