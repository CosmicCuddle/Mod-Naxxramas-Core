# NT1 Server Integration Audit and MultiBot 4.0.4 Handover

**Audit date:** 2026-10-11. **Status:** design/review only. No destructive source changes, database changes, config activation, or merge are authorised by this document.

**Audited server baseline:** `CosmicCuddle/Mod-Naxxramas-Core` `main` at `1e00c5537a1e22d1be7572437c884ca05f4c3337`.
**Client reference:** `CosmicCuddle/N-MultiBot-Chatless` draft [PR #5](https://github.com/CosmicCuddle/N-MultiBot-Chatless/pull/5), `fix/nt1-confirm-class-package-audit` at `6a935f129d3bc9e0478f2956ff5af71b980544d6`. It is not merged or in-game approved.

## 1. Server-side implementation audit

| Area | Current implementation | Acceptance boundary |
| --- | --- | --- |
| Input | `.naxxbot talents preview <online-botname> <NT1-code>` and `.naxxbot talents apply <online-botname> <NT1-code>` | Server parser understands NT1 Talent.dbc IDs in base36; chat transport may cap complete command at 255 characters |
| Validation | Code structure, class mask, era row/column rules, available talent points, DBC ranks, dependencies, tier prerequisites, deterministic *full-build* purchase ordering | Full-build ordering is not a historical per-level spend order |
| Permissions | `AccessMode` 0/1/2; non-GM account/AI-master check; Random Bot group/master check in Apply; human issuer IP era restriction | Check permissions on Apply again; preview currently does not check every Apply prerequisite |
| Alt Bots | `AltBotAllowedPlayers` human-character allowlist checked in Apply only; empty default denies all; successful Alt Bot build saved as `guid,spec,code` intent row | GM mode does not override allowlist; permission is talent-only and must never grant equipment mutations |
| Random Bots | Grouped Random Bot Apply has one real successful 51-point Mage test on Zevon, user-confirmed 14/0/37 | It saves normal talents but deliberately no permanent NT1 intent; rerandomisation may overwrite later |
| Full budget | Apply rejects any target with unused points before reset; preview shows an `NT1 APPLY BLOCKED` warning | Latest restriction not confirmed compile-and-in-game tested |
| IP compatibility | Reads rewarded hidden quests 66001–66018 from issuing human, clamps `ProgressionLimit` and requires exact code era: Vanilla 0–7, TBC 8–12, WotLK 13+ | `IndividualProgression.h` intentionally not included, avoiding its `GENERAL` enum clash with `PlayerbotAI.h`; only the modern hidden-quest schema is claimed |
| Persistence SQL | Additive `mod_naxxramas_bot_talent_import` table, PK (`guid`,`spec`), varchar(2048) code; DB existence checked before Apply | Table is required even for Random Bot Apply though Random Bot intent is not written; reconcile in later guarded revision |
| Recovery | Capture previous active spec, validate through NT1, reset, learn exact ranks, verify, best-effort restore on failure | Not atomic; active-spec unexpectedly changing after reset exits without rollback, and DB failure handling is incomplete |
| Gear | No equipment generation or replacement in NT1 | **Alt Bot inventory/equipment must never be touched by NT1**; Random Bot gearing is future opt-in and disabled by default |

### High-priority safety gaps

1. **Preview/Apply mismatch.** `ValidateRequest` checks the target, syntax, class, general permission and IP era, but `ApplyValidated` additionally checks grouped Random Bot control, Alt Bot allowlist, alive/out-of-combat state, full allocation, level-era guard, SQL table and restorable old talents. A technically valid preview is not a promise to Apply.
2. **No server-bound confirmation/plan token.** The addon binds a name/GUID locally but sends a name-based command. There is no single-use server-issued ticket bound to issuer GUID, bot GUID, spec, bot level, IP stage, current plan/NT1 hash, group/master ownership and expiry. Re-resolve and revalidate every mutable condition immediately before changing talents.
3. **Recovery is best-effort.** Neither reset plus talent learning nor character/intent-table saves occur in one reversible transaction. An unexpected active-spec switch exits before the restore path. A stored intent row is not evidence of an automatic on-login restore mechanism.
4. **No passive safety against maintenance.** `mod-playerbots` `RandomPlayerbotMgr::ProcessBot` can call `Randomize(bot)`, `PlayerbotFactory::InitTalentsTree` is used during maintenance, and `AltMaintenanceTalentTree` may modify Alt Bots. A normal party or `SaveToDB` does not prove permanent talent retention.
5. **Expansion/level intersection.** The exact human IP-era rule and current target level-based Apply guard are separate: a TBC-progressed human using a TBC code for a level-30 bot may be rejected because the current importer reserves Vanilla for target levels <=60. Do not relax either policy without an explicit tier-and-level design review.
6. **Client command transport.** MultiBot checks `#('.naxxbot talents ...') <= 255`; its current 40 bundled Vanilla presets fit, but a future full-length custom NT1 or extra metadata may not. Do not truncate codes to make them fit.

### Current, exact human-facing chat responses (examples)

- Preview, valid: `NT1 valid for Zevon (level 60 mage, era vanilla).` / `Points: 51 planned / 51 available; 0 deliberately unspent.` / `Read-only validation: no talents have been reset or applied.`
- Preview, incomplete: `NT1 APPLY BLOCKED: 49 of 51 points spent (2 unspent). Spend all points before applying this build.` (this path still requires live testing).
- Wrong class: `NT1 rejected: Talent code class does not match the bot's class.`
- Wrong IP era: `NT1 rejected: NT1 era blocked by Individual Progression: your character is in vanilla but this talent code is for tbc. Choose a build for your current expansion. No talents changed.` (illustrative source-format message, not field evidence).
- Alt Bot deny: `NT1 apply aborted: Alt Bot NT1 apply denied: your character is not in NaxxramasCore.BotTalentImport.AltBotAllowedPlayers. No talents changed.` (illustrative source-format message).
- Prior real Apply success: `NT1 build applied to Zevon: 51 spent / 0 unspent.` followed by a warning that Random Bot builds are session-scoped and may be rerandomised.
- **Important:** Submit/dispatch acknowledgement in MultiBot is not an Apply-success acknowledgement. Do not show success based on `SendChatMessage` alone.

## 2. Proposed gated implementation sequence

### Gate A — compile, tests and read-only full preflight (first reviewable code PR)

- Confirm successful server compile on the exact target AzerothCore/Playerbots/IP revision; the previous `GENERAL` duplicate-enumerator problem was fixed in source by removing `IndividualProgression.h`, but no post-fix compiler result has been supplied.
- Refactor shared validation into immutable read-only `PreparePlan/CheckApplyEligibility` called from Preview and again immediately before Apply, including target GUID/class/account control/group/master, IP stage, bot level and active spec, full projected allocation, current-talent restorable snapshot and database readiness. Emit separate `PLAN_VALID` versus `APPLY_READY` statuses with reason codes. Preview must never reset, learn, save or grant items.
- Handle no-op imports and distinguish client dispatch, preview-ready, apply-succeeded, rollback-succeeded and rollback-failed. Use a structured, versioned server chat result only after confirming safe 3.3.5a message lengths and addon parsing.
- Prefer a short-lived one-time server-side confirmation token (bound to actor+target GUID, NT1 plan hash, active spec, level, era, ownership and pre-change talent snapshot). **A token never substitutes for a fresh final authority check.** Token-less legacy Apply may remain GM-only during migration, disabled where it could undermine new safety.
- Add deterministic non-destructive C++ tests for code parser, full allocation, malformed/rank/prerequisite/row violations, cross-class, era gates and preview error codes. No 3.3.5a runtime claims until realm-tested.

### Gate B — lower-level template projection (pure, read-only first)

- **Do not interpret NT1 entry order as talent purchase order.** NT1 stores final talent IDs and ranks, and the importer currently sorts them to find *one* legal full-build purchase order, not necessarily the intended levelling plan.
- Propose an explicit `NT1 levelling priority` companion format/version (or server-approved named template with an ordered list of individual rank steps), preserving the existing NT1 wire format for compatibility. Each step refers to the exact Talent.dbc ID and next rank, and a template carries source era/class/full ranks and a plan identity/hash. Validate metadata against the completed source NT1 plan; duplicate/ambiguous/contradictory steps are rejected. **Do not silently invent priorities for older NT1-only codes.**
- Server calculates `bot->CalculateTalentsPoints()`; replay only that many explicitly prioritised *legal* rank steps, enforcing loaded Talent.dbc ranks, dependencies, `Row*5` tier unlocks, exact issuing-human IP era, actual target level, and Playerbots' stricter expansion row policy. Validate the complete projected plan before returning it; final result must consume the target's full available points or be rejected. Example normal Vanilla level-30 Mage projection: 21/21 from a reviewed 51/51 source template.
- Preview reports bot level/available/allocated points, per-tree distribution, complete projected rank list, any skipped future ranks, plan/version/checksum, and `APPLY_READY` or a specific refusal. Apply must replay exactly the previewed validated steps only after confirmation and fresh revalidation; if any prerequisite cannot be fulfilled do not change the bot.
- Note the intersection problem: while the human is TBC/WotLK, an exact-era TBC/WotLK code may not currently apply to a sub-61/sub-71 bot due to independent target-era restrictions. Resolve with explicit user approval and separate tests; do not bypass silently.

### Gate C — persistence and recovery acceptance

- Record per-spec bot talent/spell/glyph/dual-spec baselines and backup/restore verification in a disposable realm or against disposable bots. Abort if the pre-change spec cannot be validated as recoverable.
- Test failures at each LearnTalent stage, active-spec switches, character-DB save errors, intent-table availability and maintenance races. Never claim SQL-only rollback reconstructs unsaved runtime talents. Prefer fail-before-reset and a stored, verified recovery snapshot; bound runtime callbacks and safe cancellation need exact upstream API review.
- Test Alt Bot restart and relog, dual spec swaps, correct learned spells/auras, group joins/exits, Random Bot rerandomisation while grouped, and Playerbots trainer/maintenance scripts. Do not introduce permanent Random Bot ownership/NT1 profile locks without separate impact review.

### Gate D — Random Playerbot role and equipment proposal (strict opt-in, separate PR)

- **No Alt Bot inventory, bag or equipment changes** through NT1. This remains an invariant regardless of allowlist or GM status.
- Role must be explicit (`tank`, `healer`, `melee_dps`, `caster_dps`, and explicit `bear`/`cat` for Feral Druid), checked against class, selected talents and real Playerbots ability. The current upstream Feral tree maps to both tank/DPS; spec-name alone is insufficient.
- Begin with a *read-only* gear assessment comparing new role to existing equipped slots. Determine human IP tier, the content actually unlocked, bot equip eligibility/level and conservative per-slot quality/power ceilings. Do **not** equate item level with loot-source entitlement; require an audited eligible item-source pool.
- Current upstream `PlayerbotFactory::InitEquipment` and `AutoGear` create items and may call `DestroyItem` (especially second-chance/reset), so do not invoke blindly. No production generation until a server-side generated-item provenance/ownership model and verified non-transfer restrictions exist (trade/mail/AH/bank/guild bank/vendor/disenchant/loot/exploit paths). BOP alone is insufficient.
- Avoid player bag consumption. Keep a reversible snapshot or server-side recovery record of the Random Bot's previous equipment; do not destroy earned gear. Refresh exactly once per confirmed role transition, never as an unrestricted repeatable reward source. Enforce no item/gold economy extraction and audit repeated respec, death, logout, crash/restart and ownership changes.
- Proposed config (NOT IMPLEMENTED): `NaxxramasCore.BotTalentImport.RandomBotGear.Enabled = 0`. This alone is not a safety control; provenance and source eligibility must be verified before activation. When unsupported/unsafe, report `GEAR_UNCHANGED` with reason and do not mutate inventory.

## 3. MultiBot 4.0.4 integration contract

- Draft client [PR #5](https://github.com/CosmicCuddle/N-MultiBot-Chatless/pull/5) at `6a935f1` is **open, draft, unmerged**. Its Lua tests and packaging/lint/format Actions at head all completed successfully: `38129826784`, `38129826858`, `38129826787`. This is *automated addon validation only*, not a WoW client or server run.
- Current addon validates syntax/class locally; target is locally bound by name and GUID where available; direct send uses `SendChatMessage('.naxxbot talents preview/apply ...', 'SAY')` and enforces a 255-character message limit. The server currently resolves the target again by name and does **not** accept the local GUID as authoritative.
- Saved Builds, website preset browsing, importing/exporting, role/raid/solo filters, and clicking/selecting builds must remain **read-only with no server mutation**. Exclude Warrior, Warlock and Death Knight from website presets until individually approved; preserve original Playerbots `Bot specs` menu for those and unavailable classes.
- **Future confirmation window:** show bot name/class (and GUID where available), issuer's era, full source build name, projected target level/trees/points, chosen role and the server's current `APPLY_READY` status/expiry. Force refreshed confirmation when target, source code, class, level, plan, spec or server response changes. Never infer status from addon-side parse or from a successful chat send.
- Addon should only send the user's requested NT1/role and any *server-issued* short-lived plan token; server independently authorises ownership, group/master, Alt Bot allowlist, IP, level/DBC legality, active-spec match, talent-budget, gear allow/deny and final post-apply outcome. Do not build a client-side bypass, do not truncate chat commands, and do not add a generic privileged command executor.

## 4. Configuration, SQL, rollback and test evidence

- **Actual current settings:** `NaxxramasCore.BotTalentImport.AccessMode = 0` (disabled), `NaxxramasCore.BotTalentImport.AltBotAllowedPlayers = ""` (denies Alt Bot Apply even for GMs). Optional admin example: `"Takali, Drakka, Sequoia"` in **active**, not `.conf.dist`; it grants only additional Alt Bot talent eligibility and does not override access mode or non-GM control. Existing separate `NaxxramasCore.BotTalentCompletion.Enabled = 0` remains independent.
- **Database today:** `data/sql/db-characters/2026_10_10_00_bot_talent_import.sql` creates only an additive `guid,spec,code,updated_at` table. Confirm table schema in the real `acore_characters` DB before testing; no new migration required by this audit. Dropping this table removes stored NT1 intent, **not** applied character talents.
- **Backup:** require a tested, restore-capable `acore_characters` backup and a pre-change baseline of the disposable test character/spec before experimental Apply. To stop new NT1 applies use `AccessMode = 0` and restart Worldserver; this does **not** undo already-applied changes. Never delete arbitrary items or alter player inventories as rollback.
- **Verification ledger:** (a) past in-game Zevon Random Mage 51/51 and 14/0/37 confirmation: PASS on earlier revision; (b) 11 Oct 2026 `GENERAL` enum compile error: real observed failure; header conflict corrected at commit `bd3957c98da4783c6b2adb8f4fbff87900d883a1`, **post-fix build unconfirmed**; (c) current server `main` automated CI at head: none found; (d) new full-spend/IP/Alt allowlist rules: source present, full runtime verification **PENDING**; (e) lower-level scaling, role-specific gear generation, structured preview: **NOT IMPLEMENTED**; (f) addon PR #5 workflow green at head, actual 3.3.5a client test **PENDING**.

## 5. Precise next handover tasks

**Server:** (1) obtain real post-header-fix compile result and current deployed SHA; (2) create a separate *draft code PR* for shared non-destructive `APPLY_READY` preflight and tests; (3) design explicit rank-priority source format and server projected-plan preview; (4) independently validate rollback and Playerbots maintenance; (5) only afterward, review a distinct `RandomBotGear.Enabled=0` design/provenance PR. Do not merge/enable until approved.

**MultiBot:** (1) retain draft PR #5, confirm head checks and in-game screenshots/SavedVariables tests; (2) implement the proposed confirmation window client-side *without* transmitting Apply from Save/Browse/Import/Export; (3) do not claim existing server Preview is Apply-ready; (4) plan to consume server `APPLY_READY`, projection and token protocol after server PR review; (5) display **actual server result** and unchanged-gear reason, never equate message-dispatch with success; (6) preserve exclusion and original Bot specs fallback.

**Explicit status:** This audit is documentation-only. No live destructive talents/gear were enabled, no SQL executed, and no existing PR merged.
