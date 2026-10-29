# First controlled Mod-Naxxramas-Core test build — candidate gate

**29 October 2026 UTC — BUILD PREPARATION, NOT RELEASE APPROVAL**

## Goal and what actually exists

The owner wants to start in-game testing **soon**, not another cycle of independent HonorOverflow research. This DRAFT is a small nonproduction test gate for what already exists on protected-by-project \`Mod-Naxxramas-Core main@80e9de1c39a6dc995188a80c31a5e785d0f2a6f9\`. It adds no C++, feature changes, DB migration, DBC edits or installed configuration.

**Hunter ammo is implemented on main**, in \`HunterAmmoProvision.cpp\` and the \`.bot consumables\` raid/dungeon preparation. Bows/crossbows get eligible arrows; guns get eligible bullets. Supply is **ONLY to scoped Altbot Hunters**, in bags, and only when separately enabled. It does **not** auto-select ammo, give ammo to humans, or replace crafting. Its source tests and a historical full Worldserver link have succeeded, but **no owner in-game Hunter supply pass yet**.

**Blood Elf/Draenei hiding from Vanilla-stage /who:** prototype lives in separate unmerged **F14 DRAFT #145**, with additional research #234 and integrated frozen DRAFT #160. Not on protected main, F14 OFF/UNWIRED. Even /who-only filtering would NOT hide race from name queries, public unit fields or visible models. **General world invisibility is NOT implemented.** It is excluded from this first build.

Other existing main source includes consumables, progression meeting stones, Battlemaster queue restrictions, talent import diagnostics, race/class custom mechanics, quest-loot protection, events and HonorOverflow. Merely having source is NOT proof of current installed behavior. Many require DBC/SQL, individual enablement and separate gameplay passes.

## Build provenance — recorded, not assumed current

The prior **operator-reported** installation snapshot on **12 Oct 2026** (from \`docs/NT1-OWNER-INSTALLED-BASELINE-2026-10-12.md\`) was:

| Component | Reported / CI snapshot |
|---|---|
| Owner-compatible AzerothCore fork | \`mod-playerbots/azerothcore-wotlk@b7f06a16ac7120b5abc2e8d3f96a94265a363224\` |
| Playerbots | \`mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c\` |
| Individual Progression | \`ZhengPeiRu21/mod-individual-progression@283abe12774801e5671da746ea8bf535cc0252e0\` |
| Installed Mod (historical) | \`CosmicCuddle/Mod-Naxxramas-Core@969f0429b4f02d8ba64ee83ecf4c91323e474bdd\` |
| This isolated candidate | protected-main feature source \`80e9de1c...\` plus ONLY 3 additive docs/script/CI paths |

**CAUTION:** These external SHAs are historical owner-reported values, **not verified current installed sources**. They differ from newer research core@8daffd and latest public Playerbots/IP pins. Hosted CI builds the above historical owner-compatible combination as a **compatibility rehearsal**; no guarantee it matches today's running server.

## Offline build gate

[.github/workflows/naxx-first-controlled-build.yml](../../.github/workflows/naxx-first-controlled-build.yml) on the isolated DRAFT uses one disposable Ubuntu 24.04 GitHub runner, verifies all source pins and the exact candidate HEAD, enforces 3 additive-only paths vs protected main, and runs focused real existing tests:

- Hunter ammo, quest loot, MC GFPP consumables, Golemagg read-only audit, meeting-stone isolation and EP tower source tests;
- standalone native C++17 Hunter ammo selection and C++20 Golemagg allowlist;
- a full real CMake + **Worldserver compile and link** with the core, Playerbots, Individual Progression and this module;
- verifies final executable and module archive include **real defined Hunter ammo and bot consumable symbols**, plus QuestLoot and Golemagg; records SHA-256 and build provenance;
- generates a review-only \`mod_naxxramas_core.conf\` profile in a temporary runner directory with high-risk defaults OFF, and prints the linked binary's SHA-256 fingerprint in the hosted CI log for inspection. **No artifacts (including config files) are uploaded**, in accordance with existing QuestLoot release-safety tests. Neither build nor config is installed, used or deployed on owner host.

**A successful GitHub build is NOT in-game acceptance. A failed CI step should be fixed at its exact failing source/compilation point rather than interpreted as broken gameplay.**

## First-test switch set — review-only, DO NOT copy over active config

The upstream \`.conf.dist\` defaults \`HonorOverflow.Enabled=1\`, \`HonorReset.Enabled=1\`, \`ForcedPvP.Enabled=1\` and \`MeetingStones.ClassicMode.Enabled=1\`. For a **safe initial compilation/smoke-test phase**, the generated temporary profile overrides these to **0**, plus the following already-off experiments stay OFF:

\`\`\`ini
NaxxramasCore.HonorOverflow.Enabled = 0
NaxxramasCore.HonorReset.Enabled = 0
NaxxramasCore.ForcedPvP.Enabled = 0
NaxxramasCore.ForcedPvP.Silithus = 0
NaxxramasCore.ForcedPvP.EasternPlaguelands = 0
NaxxramasCore.MeetingStones.ClassicMode.Enabled = 0
NaxxramasCore.BotTalentImport.AccessMode = 0
NaxxramasCore.BotTalentCompletion.Enabled = 0
NaxxramasCore.BotConsumables.HunterAmmo.Enabled = 0
NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor = 0
NaxxramasCore.QuestLootProtection.Enabled = 0
NaxxramasCore.ElementalInvasion.Enabled = 0
NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled = 0
NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0
NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0
\`\`\`

The actual generator enforces additional OFF/empty settings, exact single active key per option, no F14 setting, and does **not modify** \`conf/mod_naxxramas_core.conf.dist\`, owner config or database. This build baseline is not a blanket promise that any native C++ effects outside toggles are inert.

**MapUpdate.Threads=8 MUST remain 8.** This is an AzerothCore world configuration setting and cannot be verified from the repository's module .conf.dist; owner must separately check the *active* server configuration read-only.

## Minimum owner preparation BEFORE installation or game testing

Do not run installation, SQL, DBC changes, reboot or a new binary until the owner separately approves a documented specific test.

1. **Read-only host revision inventory:** through MobaXterm in \`/root/azerothcore-wotlk\`, capture \`git rev-parse HEAD\` and \`git status --short\` for AzerothCore and the three module directories. This establishes whether the historical CI pins match; do not run \`git pull\`, \`git reset --hard\` or any build yet.
2. **Record actual running configuration** (not merely .conf.dist), the effective individual-progression enable/stage, \`MapUpdate.Threads=8\`, selected Playerbot revision, installed matching custom DBC set and currently applied world/characters SQL changes. The exact active file path must be confirmed, not guessed.
3. **Make dated, restorable backups:** current binary/build directory, source commit IDs, actual config, \`acore_characters\` and any affected \`acore_world\` tables, client+server custom DBC files. **Perform a non-destructive restore verification into a separate location before testing.** Keep rollback steps and recovery contacts ready.
4. **Owner separately approves test scope, timing and rollback** on a disposable bot; then use an appropriate isolated test environment if available. The repository previously records that no separate realm was available, so any live-realm test should be narrowly scoped, backed up and non-destructive until explicitly authorised.
5. **Confirm the compiled module loads and server starts cleanly** under OFF-profile first, with full startup logs. This alone is not proof the features work.
6. **First narrow gameplay passes:** read-only config/startup, then only with explicit owner approval, **one controlled Hunter Altbot** with bow or gun, known original inventory and empty bag slots, invoke existing \`.bot consumables\` command once after temporarily enabling **HunterAmmo only**, check correct projectile/quantity/no-op for human or Random Bot, actual before/after count, no auto-equip, and record command output. Re-disable; verify inventory rollback (minted ammo stays unless a tested restoration is performed).
7. Future independent passes after approval: quest loot with two humans, progression meeting stones Vanilla/TBC/WotLK, bot-consumable cooldowns, BG queues, spell/DBC checks, NT1 preview; never enable experimental NT1 Apply, F14, K1, R7 HonorOverflow or D18 in this first phase.

### Hard NO-GO boundaries

- P13 R7 concurrent shared-state **release HOLD** and economic owner H-DEFAULT/H-SELFBOT/H-REMEDIATION **UNSELECTED**. Do NOT use default-enabled HonorOverflow in an unreviewed test.
- F14 race concealment OFF/unwired; frozen DRAFT #160; no full invisibility claim. K1 individual Hunter pet settings on N-Core remain NoWrite/relay OFF, Step1 not before 1 Nov 2026 and with a separate approval; D18 in-combat pet A→B HARD NO-GO.
- Do not merge isolated DRAFTs, change protected Mod/N-Core main, alter original core/Playerbots/IP, run owner's server, apply SQL/DBC/client patches, modify bot inventories or start test without the owner approving each high-impact step. Mandatory owner-accepted gameplay **0/5** at preparation time.

**Exit status until confirmed:** build-candidate DRAFT prepared; real hosted build evidence and exact owner installed revision/current active configuration must be checked; **NOT a downloadable release or deployment GO**.
