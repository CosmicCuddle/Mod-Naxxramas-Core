# NT1 Read-Only Integration Branch — controlled compilation candidate

**Review status:** Unmerged, **not yet C++ compiled, not deployed and not tested in-game**. Integration branch combines the independent draft NT1L1 read-only projection (#8) with the stacked Alt Bot diagnostic/recovery/protected-state drafts (#7, #9, #10, #11 and #12). The integration adds a **new GM-only read-only AccessMode 3** to avoid exposing experimental Apply during initial field checks.

## Branch and source boundaries

- Base: branch feature/nt1-altbot-protected-state-readonly (PR #12; inherits #11 -> #10 -> #9 -> #7). Source code remains confined to src/Systems/BotTalentImport.cpp and module config, never to AzerothCore/Playerbots/Individual Progression upstream repositories.
- Integrated from sibling feature/nt1-level-priority-preview (PR #8): **ProjectPriorityCode** and **HandleProject** C++ operations, read-only PR #8 fixture/checker/tests, NT1L1 design docs and offline workflow. New commands coexist with repairpreview and existing preview/apply in a single command table.
- AccessMode 0 remains default disabled; modes 1 and 2 retain **experimental destructive Apply**; **mode 3** enables GM-only read-only operations and refuses Apply during the shared CheckApplyReadiness before calling resetTalents. It is NOT an authorisation for normal non-GM characters. Repairpreview still requires AltBotAllowedPlayers, including for GMs, and explicitly rejects Random Playerbots.
- The mode-3 refusal runs near the **end** of readiness checks. A Priest with an illegal original build still receives its specific old-build restoration error rather than an unrelated generic read-only-mode error. For an otherwise valid plan, the message explains that no Apply is permitted in mode 3.
- The existing special Alt Bot repair **Apply does not exist**. Mode 3 is for investigating the cause, not for fixing talents.

## Read-only command matrix in mode 3

| Command | Expected | Restrictions |
| --- | --- | --- |
| .naxxbot talents preview <BotName> <NT1-code> | Parse and explain points and preflight; no mutation | GM issuer, class/era/IP, actual online bot |
| .naxxbot talents project <BotName> <NT1L1-code> | Produce lower-level rank projection; no mutation | GM issuer, full explicit valid rank purchase order, server DBC and IP |
| .naxxbot talents repairpreview <BotName> <NT1-code> | Explain out-of-era original ranks, two specs, active glyphs, equipment identity and recovery warnings; no mutation | GM issuer **and** human character in AltBotAllowedPlayers, non-Random Alt Bot, actual source class/era |
| .naxxbot talents apply <BotName> <NT1-code> | BLOCKED with no reset | Mode 3 forbids Apply; other old-build/offhand/pet restrictions still apply |
| .naxxbot talents repairapply ... | DOES NOT EXIST | No token, gear manipulation or destructive repair capability is added |

The production config must **not be switched to mode 3** until this branch is explicitly reviewed, compiled and approved for a controlled test. Existing distributed default mode 0 remains safest.

## Review evidence

- Source contract asserts all four handlers are registered once, PR #8 priority source remains explicit ordered-rank validation and read-only, and shared Apply preflight retains old-build recovery refusal, Alt name allowlist, gear and pet fail-closed checks.
- Integration-specific source-contract tests assert new mode 3 cannot reach the Apply reset, while modes 1/2 keep existing behaviour.
- The combined CI workflow invokes every test matching tests/test_nt1*.py, bringing together the prior 25 Mage NT1L1 tests, read-only Alt Bot state and recovery synthetic tests, and integration safety checks.
- **Actual GitHub Actions evidence (11 October 2026):** [combined integrated suite 38161836971](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38161836971) **89/89 PASS**; [Mage NT1L1 fixture 38161837049](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38161837049) **25/25 PASS**; [Alt Bot recovery/backup 38161837064](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38161837064) **52/52 PASS**; [Alt Bot read-only diagnostic 38161836955](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38161836955) **12/12 PASS**. All succeeded on the reviewed integrated source, before documentation-only notes. The combined suite includes 12 integration-specific source contract tests; the separate suites overlap with the combined suite and **must not be summed as unique tests**.
- **Python tests cannot verify C++ compilation, WotLK 3.3.5a chat command execution, loaded custom DBCs, actual spec/glyph/pet state, race-safe rollback, or database restore correctness.** Real build and server tests remain to be done.

## Important live blockers

1. **Original Priest builds:** current Alt Bots possess legacy out-of-era talents 1768 (Holy Concentration) or 1202 (Borrowed Time); old-build rollback check still refuses even otherwise-valid 51/51 Priest replacement NT1. This integration **does not reset or fix them**.
2. **Actual recovery:** verify consistent stopped-Worldserver characters DB backup **and isolated test restoration**; preserve exact talent/spec, glyph, spell/aura, pet, item GUID, bag, mail and offspec state. Structural CSV/gzip tests/fingerprints are insufficient.
3. **Offhand and pet side effects:** AzerothCore reset can move or mail offhand equipment and dismiss pets; the branch blocks ordinary Alt Bot Apply with either risk, but unreviewed hooks may have other effects.
4. **Mode 3 preflight may still check optional SQL import table existence** before reporting mode denial; if missing, repairpreview reports that other blocker. No schema migration is introduced in this integration branch.
5. **PR #8 is a sibling**, not automatically included by simply checking out PR #12. This integration branch explicitly collects both, but must still undergo real C++ review and compilation before user testing.

## Controlled compile and testing roadmap

1. Preserve exact local modules and C++ versions, backup user's working tree and validate restore-ready characters DB; obtain administrator approval to use a separate test build. No force-reset.
2. Compile this reviewed integration branch against exact AzerothCore and Playerbots revisions; fix any real API/compiler mismatches inside Mod-Naxxramas-Core only.
3. With a backed-up disposable Priest Alt Bot and GM issuer in AltBotAllowedPlayers, set AccessMode=3 in the **approved development/test config**, then run only read-only preview, project and repairpreview.
4. Verify mode-3 Apply refusal and allowed/denied callers; inspect active/inactive spec counts, full equipment item-GUID identities and repeated read-only output. Inspect real chat lines for truncation.
5. Restore normal AccessMode=0 in production after testing. Do not attempt destructive repair until its entirely separate future implementation has an explicit approval and successful complete recovery rehearsal.

**No changes in this branch automatically equip, unequip, mail or delete Alt Bot items. No bot talent reset is invoked by the three new/read-only handlers.**
