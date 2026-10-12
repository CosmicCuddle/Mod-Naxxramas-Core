# NT1 Read-Only Release Candidate: Build and In-Game Acceptance Gate

**Owner source checkpoint:** 12 October 2026. **Status:** draft PR #16; source review only. Nothing in this document authorizes a Git pull/merge, compile, production configuration change, server restart, character reset or database writes.

## Target and installed baseline

Read [Owner Installed Baseline](NT1-OWNER-INSTALLED-BASELINE-2026-10-12.md) before planning any build. Operator-provided source SHAs:

| Source | Operator-observed Git HEAD |
|---|---|
| Playerbots-compatible AzerothCore | `b7f06a16ac7120b5abc2e8d3f96a94265a363224` |
| Playerbots | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Individual Progression | `283abe12774801e5671da746ea8bf535cc0252e0` |
| Naxxramas Core (installed) | `969f0429b4f02d8ba64ee83ecf4c91323e474bdd` |

Git source is not binary provenance. The operator did **not** supply executable hash, build revision, active `worldserver` config values, DBC hashes, or restoration results. The above SHAs were independently located in public GitHub history and the **specific** talent/spec/item and IP quest interfaces were reviewed. **No C++ compile has yet occurred.**

## Final source-review findings

- `Player.h`: `GetTalentMap() const`, `GetSpellMap() const`, `HasTalent(spell, spec) const`, `PlayerTalent::{State, specMask, talentID}`, `GetActiveSpec`, `GetSpecsCount` and `GetGlyph` are present. `GetGlyph(slot)` is active-spec **only**.
- `PlayerbotAI.h`, `PlayerbotMgr.h`, `RandomPlayerbotMgr.h`: the existing master, AI lookup and random-bot classification signatures are present.
- IP `src/IndividualProgression.cpp` uses rewarded quest `66000 + stage` to determine progress, with configured `IndividualProgression.ProgressionLimit`; Vanilla up to 7, TBC from 8 and WotLK from 13. The **human issuer's** era is not automatically the bot's.
- `Player::resetTalents` invokes `OnPlayerTalentsReset` **before** its no-spent-talents early return. Later it may call `RemovePet`, clear Titan's Grip/Dual Wield and call `AutoUnequipOffhandIfNeed`. Offhand relocation can move or **mail the original item**. Therefore **even a returned false reset is not a harmless inspection**, and no test should ever call reset merely to observe data.
- Draft PR #16 `safetypreview` checks session, real human identity, command access, online bot identity, controlling player, non-Random Bot status and issuing human allowlist **before** reporting protected information. Both owned spec talent maps are scanned without `ActivateSpec`. The original occupied-offhand/active-pet blockers and mode-3/4 Apply refusal stay intact.
- Source review confirms required declarations in the operator-reported GitHub commits. It cannot verify hooks from unrelated installed modules, custom DBC content, build/link compatibility, runtime messages, pet state or DB restoration.

## Approved single bundled build: separate permission required

**Before doing anything:** obtain owner approval, arrange a maintenance window and document current executable/config locations. Prepare verified independent backups of the Naxxramas Core source, existing worldserver binary, effective configuration and build-specific patches. Keep a rollback path that restores the **previous binary and module/config combination**, not just a Git `reset`. Back up relevant character DB data as an additional precaution; never treat a dump as restored until an isolated recovery was demonstrated.

Do not run `git pull` on a random branch, merge draft PR #16 without review, update core/Playerbots/IP, or replace the operator's compatible fork. After the owner approves a precise source revision, compile the reviewed Naxxramas Core with the reported dependency revisions in **one bundled build**, retaining compiler logs and recording which binary was deployed. A passing C++ build does **not** establish safe reset.

When a compiled read-only revision is approved for the test environment, configure `NaxxramasCore.BotTalentImport.AccessMode = 4` for ordinary authorized humans and GMs, or `3` for GMs only; confirm the issuing **human character** appears in `AltBotAllowedPlayers` when intended. The upstream `conf.dist` default is mode **0**, not 4; setting 4 is a separate owner-approved configuration choice. Last operator-shared live setting was mode **2**, which permits experimental Apply and must **not** be used for the read-only acceptance session. Never assume mode 4 is available in the still-installed older binary.

## In-game acceptance: one organised read-only session

Only after successful owner-approved compilation, installation/config review and restart:

1. **Authorization tests first.** Unlisted human issuer, account not controlling bot, non-real-human bot issuer, and Random Playerbot must all be denied without revealing a protected report. Explicitly authorised controlling human should receive output. Verify GM does not bypass the Alt Bot issuer allowlist.
2. **Confirm Apply denial in modes 3/4** by reviewing mode checks and expected error handling. **Do not issue an Apply command against a real character** as part of acceptance; use non-destructive source/static checks instead. No `repairapply` route should exist.
3. **Single bot read-only baseline.** Capture (copy or screenshot) `.naxxbot talents safetypreview <online-altbotname>` output. Record two-specialization talent/spell record counts, checksum strings, equipment checksum and active glyph summary. Re-run after the identical bot has been left unchanged; checksums should remain stable *only if the underlying state is stable*. The checksum is not a backup.
4. **All ten classes** (online controlled Alt Bots, as available): inspect only. Note spec 1/2, correct class label, occupied offhand, equipment hazards, pets, current issuer IP era vs bot's declared state, and bounded talent-map anomaly samples. A warning does **not** authorize repair or removal of custom DBC talents.
5. **Era cases.** With IP enabled, check that Vanilla-stage issuers receive Vanilla-era read-only rank flags, with no silent inference from bot level. For IP-disabled test realms, confirm the human issuer era scan is skipped. Observe only; never change a player's IP stage for testing on production.
6. **Repair proposal without repair.** With a validated NT1 code for a controlled test Alt Bot, run `.naxxbot talents repairpreview <online-altbotname> <NT1-code>`. Verify both specs are inspected without switching them, any occupied offhand/active pet remains a blocker, and actual item GUIDs are neither unequipped nor mailed. No reset, talent learn or DB writes are permitted.
7. **3.3.5a chat usability.** Confirm warnings and counts remain readable and limited (unmatched spell IDs capped at 3, active abnormal-era talents limited in chat). Save observations in the PR acceptance record.
8. **Compare protected state after the session.** Original equipment item GUIDs, active spec, pet and current known glyphs must remain unchanged, subject to unrelated gameplay changes. Neither client screenshots nor in-memory checksums capture bank, bags, mail, inactive-spec glyph records, stabled pets or full character state.

| Class | Primary read-only hazards to observe |
|---|---|
| Warrior | Dual two-hand weapons, Titan's Grip, stance spells |
| Paladin | Shield/offhand vs two-hand weapon, active auras |
| Hunter | Permanent/exotic pet and pet talent state |
| Rogue | Dual-wield equipment and talent-granted spells |
| Priest | Equipped offhand focus and source-era rank differences (including Rakari-style legacy cases) |
| Death Knight | Dual-wield gear, ghoul-related pet state |
| Shaman | Talent-dependent Dual Wield, shields/offhand equipment |
| Mage | Summon effect and talent rank policy |
| Warlock | Demon/pet presence, offhand and talent-granted spells |
| Druid | Form-specific abilities, offhand and restoration talent rank policy |

**Acceptance result:** record each scenario as *Passed*, *Blocked safely*, *Needs investigation* or *Not tested*. A skipped class remains untested, not passed. A broken or missing message is a defect, not proof of safe behavior. If compiler or gameplay tests fail, correct source on the draft, rerun checks, and seek new deployment approval as required.

## Destructive work remains separately gated

No Alt Bot talent `apply`/reset, restoration test against real characters, spec switching, pet removal, equipment handling, character DB edits or auto-repair is included in read-only acceptance. **Destructive work additionally requires a consistent worldserver-stopped characters database backup that has been successfully restored into an isolated database, plus explicit owner approval.** The original gear and pet guards remain fail-closed.

Reference: [NT1 Talent Safety Audit](NT1-CROSSCLASS-TALENT-SAFETY-AUDIT.md) and [NT1 Owner Installed Baseline](NT1-OWNER-INSTALLED-BASELINE-2026-10-12.md).
