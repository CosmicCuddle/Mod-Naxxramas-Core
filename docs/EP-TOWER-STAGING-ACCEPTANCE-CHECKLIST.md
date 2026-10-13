# Eastern Plaguelands tower locks — staging acceptance checklist

**Status:** TEST PLAN ONLY. PR #21 remains a draft. No staging deployment, SQL migration, hard-crash simulation or live-server modification is authorised by this document.

**Scope:** `Mod-Naxxramas-Core` custom C++ and one reversible module-supplied world-SQL binding.

**Critical installation safeguard:** The optional forward binding lives under `docs/install/`, not `data/sql/db-world/`. The pinned AzerothCore updater scans module `data/sql/db-world` automatically; do **not** move the optional binding there. Merely compiling/loading the module must not change the world handler. Explicitly apply the binding **only on isolated staging after owner approval, preflight and verified backups**, and confirm it was not already applied before any manual SQL. Keep the rollback under `docs/rollback/`. No original AzerothCore C++ modifications. Do not deploy the superseded core-patch PR #20.

## 1. Gates before any staging work

- [ ] Obtain explicit owner approval for *staging* installation and tests.
- [ ] Record actual installed AzerothCore fork commit, Playerbots commit, Individual Progression commit and Naxxramas Core commit; compare their relevant EP APIs with the pinned CI stack. CI is not proof of installed-fork compatibility.

### Read-only installed-source revision check (no staging activation)

This step can be performed from an owner's **source checkout**, without stopping Worldserver, changing SQL or applying the PR. Use **MobaXterm SSH** and replace `/actual/path/to/azerothcore` with the known source folder; do not guess paths. Commands only **read Git metadata**. If the module paths differ, locate their actual checkout folders first. If Git returns `not a git repository`, stop and ask for the source location—do not initialise a new repository or switch branches.

```bash
git -C /actual/path/to/azerothcore rev-parse HEAD
git -C /actual/path/to/azerothcore/modules/mod-playerbots rev-parse HEAD
git -C /actual/path/to/azerothcore/modules/mod-individual-progression rev-parse HEAD
git -C /actual/path/to/azerothcore/modules/mod-naxxramas-core rev-parse HEAD
```

Capture all four output SHAs with their labels. Compare the owner-supplied result against the **pinned CI references**:

| Component | CI-pinned revision |
|---|---|
| Playerbots-compatible AzerothCore | `b7f06a16ac7120b5abc2e8d3f96a94265a363224` |
| Playerbots module | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Individual Progression module | `283abe12774801e5671da746ea8bf535cc0252e0` |
| Proposed Naxxramas Core EP branch | Read current draft PR #21 head; do not assume deployed main is the same |

If the owner's core or modules differ, stop automatic compatibility claims and review relevant C++ interfaces, build settings and SQL updater behaviour on those exact revisions **before** an isolated staging build. This Git check proves source checkout identity only; it does **not** establish which binary is currently running, nor is an installed-module/rebuild instruction.

- [ ] Confirm this is a conventional realm Worldserver **not a cross-realm node**. In the pinned core `WorldState::setWorldState` intentionally keeps cross-realm state in memory only, so persistent 90-minute locks cannot be promised on cross-realm nodes. **STOP** until this is independently addressed if the server is cross-realm.
- [ ] Confirm the exact PR head has both a successful real-source compile and a **completed successful full Worldserver link**, including the unique module script string; an in-progress build does not satisfy this gate.
- [ ] Make and restore-test **full staging** backups of `acore_world` and `acore_characters`; save a known-good Worldserver executable, original module, configs and pinned source revisions in a separate safe location.
- [ ] Ensure staging does not share credentials, DB endpoints, or character data with production. Do not use earned live characters for destructive/fault-injection tests.

### Read-only SQL preflight on STAGING only

Run the first query against `acore_world`:

```sql
SELECT TypeId, ScriptName
FROM outdoorpvp_template
WHERE TypeId = 6;
```

Expected: **one** row, script name exactly `outdoorpvp_ep`. A custom name or unexpected row count is a **STOP**.

Run this query against `acore_characters`:

```sql
SELECT entry, value
FROM worldstates
WHERE entry BETWEEN 93420020 AND 93420023
ORDER BY entry;
```

Expected before a *first installation*: **no rows**. Unexpected rows are a **STOP**, not permission to overwrite or delete them.

The pinned character table stores `value` as `INT UNSIGNED`; the packed expiry + faction occupies **one unsigned 32-bit value per tower**. Verify the owner's actual schema too.

| Tower | Original pinned EP enum | Reserved worldstate entry | Expected special effect |
|---|---:|---:|---|
| Eastwall | `EP_EWT = 0` | `93420020` | Support NPCs |
| Northpass | `EP_NPT = 1` | `93420021` | Shrine |
| Plaguewood | `EP_PWT = 2` | `93420022` | Flight master |
| Crown Guard | `EP_CGT = 3` | `93420023` | Graveyard link; restore stock neutral baseline |

## 2. Isolated staging activation (requires separate permission)

1. Stop **staging** Worldserver. Retain pre-migration backup snapshots.
2. Install only the PR #21 Naxxramas Core build with matching pinned-fork headers; do not copy/patch upstream `OutdoorPvPEP.cpp` or `.h`.
3. Apply `docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql` to **staging `acore_world` only**, after the read-only checks. The UPDATE intentionally matches `TypeId=6` and the unmodified stock handler.
4. Read back `TypeId=6`. Require exactly one row with `ScriptName='outdoorpvp_naxxramas_ep_lock'`; verify the module handler is registered in startup logs.
5. If the binding does not match, STOP; do not blindly re-run SQL or add duplicate scripts.

## 3. Behaviour acceptance — record actual observations

Use disposable Alliance and Horde test characters in the **isolated staging realm**, with both factions available to capture each point. Record a timestamp and an observed result for each case.

| Test | Expected result |
|---|---|
| Initial boot, no locks | Four towers neutral; original slider and zone UI functional |
| Alliance reaches 60% / 99% | No new 90-minute lock yet; ordinary stock transition effects may already occur before 100% |
| Alliance reaches actual server-side +100% | **Only that tower** begins one 90-minute wall-clock lock |
| Horde approaches locked Alliance tower | No opposing slider movement, owner change or recapture for full lock duration |
| Mirror all above with Horde to -100% | Same behaviour and independent timer |
| Capture Eastwall and Northpass at different times | Each expiry differs by the actual capture timestamp; other towers remain contestable |
| Stagger all four towers | Four independent expiry timestamps and four separate DB entries |
| Capture point empties for long period | Timer continues; expiry does not need nearby players |
| Lock reaches expiry | Tower meter **0 (neutral midpoint)**; neutral flags, counts and buffs; normal PvP resumes |
| Eastwall expiry | Support NPCs removed |
| Northpass expiry | Shrine removed |
| Plaguewood expiry | Flight master removed |
| Crown Guard expiry | Original neutral graveyard link restored, **not** deleted |
| Restart after 10 minutes of a lock | Same absolute expiry; approximately 80 minutes remain, not another 90 |
| Restart after 89 minutes | Approximately 1 minute remains |
| Keep Worldserver offline past expiry then start | Tower is neutral immediately on next startup, without an extra capture/loss announcement |
| Restart while EP tower grid is unloaded; first character enters later | Both tower capture point and flag show the retained faction artkit; after expiry and later grid reload they show neutral artkit |
| Restart while Northpass shrine grid is unloaded; visit after restart | Shrine spawns with the original faction (Alliance=84, Horde=83), and neutral expiry removes it; other GO factions remain unchanged |
| Concurrent active zone, Playerbots and IP | No duplicate handler, quest credit, buff or off-zone regressions |
| Terokkar Forest towers | Entirely unchanged |

**Time tolerance:** observe the server's normal OutdoorPvP update polling interval; a visible reset may appear on its next scheduled tick. Do not interpret an expected tick delay as a new 90-minute timer.

Check persisted values with the read-only `acore_characters` query again. Decoding reference for an individual row (read-only):

```sql
SELECT entry, value,
       CASE WHEN value = 0 THEN 'neutral'
            WHEN (value & 1) = 1 THEN 'horde'
            ELSE 'alliance' END AS locked_faction,
       CASE WHEN value = 0 THEN NULL
            ELSE FROM_UNIXTIME(1577836800 + (value >> 1)) END AS expiry_server_timezone
FROM worldstates
WHERE entry BETWEEN 93420020 AND 93420023
ORDER BY entry;
```

`expiry_server_timezone` displays in the database session's timezone; compare absolute Unix timestamps when proving timing. The persisted expiry may be updated asynchronously, so verify it has reached the database before drawing restart conclusions.

## 4. Restart and crash limitations

- Clean restarts: validate saved **absolute expiry**, not simply that a tower remains owned.
- The pinned core writes `WorldState::setWorldState` asynchronously. A newly captured tower is **not proven durable against an immediate hard crash**; do not claim crash-proof persistence based only on normal restart tests.
- A deliberate hard-crash test, if requested, requires explicit additional approval, an **isolated disposable staging** server, no real users, and proven full DB restore. Do not kill a live Worldserver to test this.
- Cross-realm nodes deliberately do not persist worldstates through this API. Deployment on cross-realm is **blocked** pending a separately reviewed persistence design.

## 5. Rollback drill (staging only, with owner approval)

1. Stop staging Worldserver and preserve the test-state/DB snapshot.
2. Run `docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql` against **staging `acore_world`**. It updates only the matching custom `TypeId=6` binding.
3. Verify the exact stock script name `outdoorpvp_ep` is selected.
4. Start the known-good staging binary/module and verify stock tower captures.
5. **Do not** delete the four worldstate keys automatically; they are inert while the stock script is selected. Preserve them for forensic comparison unless backed-up, ownership-confirmed cleanup is separately authorised.
6. If any post-rollback check fails, use the verified complete database and binary backups. Never guess at repair SQL.

## 6. Required evidence before proposing merge or release

- [ ] GitHub full Worldserver link **finished SUCCESS**, at exact current PR HEAD.
- [ ] Installed-fork compile and ScriptMgr binding verified.
- [ ] Backup and **off-server restore** actually tested.
- [ ] No worldstate-key collision and no pre-existing custom EP binding.
- [ ] All 4 towers and both factions tested, with recorded capture and expiry times.
- [ ] Clean-restart and downtime expiry verified.
- [ ] NPC/shrine/flight master/graveyard, buffs, UI and Terokkar unchanged as intended.
- [ ] Cross-realm and crash-durability limits disclosed/mitigated appropriately.
- [ ] Staging rollback completed successfully.
- [ ] Explicit separate owner approval before merge, release, production installation or any production database mutation.

**Other workstreams:** draft talent PR #18 remains independent and the Zero Gear Mutation Rule stays in force. Do not use an EP deployment to change bot equipment, talent Apply or player progression data.
