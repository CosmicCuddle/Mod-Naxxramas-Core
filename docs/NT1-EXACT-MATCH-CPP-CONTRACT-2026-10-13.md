# NT1 Exact Match — Isolated C++ Verification and Release Gate

**Status:** automated source-slice C++ test passed; **full AzerothCore Worldserver build and live acceptance NOT done**.  
**Branch:** [research/nt1-offhand-preservation-review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/tree/research/nt1-offhand-preservation-review) (draft [PR #18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/18)).  
**Safety:** existing offhand/pet protections, error rollback resets, AccessMode and AltBotAllowedPlayers retained; **no automatic Apply no-op or gear changes**.

## What was actually compiled

The script [`scripts/check_nt1_active_match_cpp_contract.py`](../scripts/check_nt1_active_match_cpp_contract.py) extracts the **exact** `ActiveTalentMatchStatus`, `ActiveTalentMatch`, `InspectActiveTalentMatch` and `PrintActiveTalentMatch` C++ definitions from `src/Systems/BotTalentImport.cpp` and compiles them **unchanged** in a deterministic, temporary C++17 executable.

The surrounding `Player`, `PlayerTalent`, `TalentEntry`, talent stores, spell store and `ChatHandler` are **minimal synthetic stand-ins** using the visible member names/types/signatures reviewed in the pinned `mod-playerbots/azerothcore-wotlk` fork at `b7f06a16ac7120b5abc2e8d3f96a94265a363224`. The test does **not** include real AzerothCore headers, link Worldserver libraries, install modules, contact the database, invoke Playerbots AI, or access/modify real characters/items.

It does compile and **execute the actual draft function** against 15 isolated inputs:

1. Exact rank match.
2. Valid different rank despite known point count.
3. Multiple active ranks of one talent.
4. Unrecognised DBC talent.
5. Mismatched class.
6. Inconsistent spent/free points.
7. Missing server spell entry.
8. Duplicate DBC rank-spell mapping.
9. Temporary/unrecognised active record state.
10. Talent present only in the inactive specialisation.
11. Removed (non-active) spell record.
12. Null talent-map record.
13. Out-of-range active specialisation.
14. Proposed rank sum disagrees with the declared spent points.
15. Proposed high-rank spell missing from current DBC mapping.

Each case expects `EXACT`, `DIFFERENT` or fail-closed `CANNOT VERIFY` as appropriate.

## Verified CI result at 13 October 2026

The GitHub Actions [combined read-only integration check](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38390259005) on branch commit `3765d1668efac0b39c5cb90e83c4776cb9010610` completed successfully:

- **243/243 Python source/synthetic regression tests**.
- **15/15 isolated C++ runtime scenarios** on the unmodified C++ comparator source slice.
- The other existing NT1 Alt Bot read-only diagnostics, recovery and NT1L1 projection workflows were green on the same commit.
- The compiler harness runs as an added step in `.github/workflows/nt1-integration-readonly-tests.yml`. It uses a temporary build directory, standard `g++ -std=c++17 -Wall -Wextra -Werror -pedantic`, and deletes its temporary artefacts afterwards.

**These checks do not demonstrate that `BotTalentImport.cpp` compiles as part of the owner's real Worldserver**, or that the module is actually installed/restarted. Dependencies and other enabled hook implementations may still differ from our reviewed source. Do not substitute a synthetic API passing for a full fork C++ build.

## Remaining prerequisites — before owner-approved install

1. Confirm and back up the actual server source/configuration and currently working Worldserver binary. Verify exact `azerothcore-wotlk`, `mod-playerbots` and Individual Progression revisions, local patches and effective config.
2. Perform a complete **pinned actual-fork Worldserver rebuild**, or at minimum compile the module as part of that source tree (not solely the isolated fixture). Investigate all C++ diagnostics and link errors.
3. With an owner-approved test plan, use a disposable Alt Bot for read-only **`.naxxbot talents preview`** and **`repairpreview`**; confirm `EXACT`, `DIFFERENT` and a safely reproducible `CANNOT VERIFY` from isolated data. Preview must not change gear or talents.
4. Confirm human issuer `AltBotAllowedPlayers` authorisation for the new Alt-only match report, the existing IP-era checks, AccessMode 3/4 Apply refusal, and the unchanged offhand/pet preflight. A status of `EXACT` is **NOT** permission to Apply or to bypass those guards.
5. Do not conduct destructive Apply, talent resets or gear tests without a separately **restored and verified isolated** `acore_characters` backup. See the [disposable evidence procedure](NT1-DISPOSABLE-ALTBOT-EVIDENCE-PROCEDURE.md). Arndor and Rakari should not be used for these tests.

## MultiBot handover condition

When the Naxxramas Core workstream is actually finished, supply the owner a **copy-paste-ready final transfer note** for [N-MultiBot-Chatless PR #5](https://github.com/CosmicCuddle/N-MultiBot-Chatless/pull/5). Include precise server merge/deployment status, all new read-only output strings, whether Addon needs to display the lines, preserved `preview` / `repairpreview` / `safetypreview` / `apply` interfaces, no claimed `APPLY_READY` handshake, owner/GM allowlist, unchanged equipment guard, and real acceptance results.

**Never label this work "complete" solely because the isolated C++ harness passed.**

## Additional validation after the original mock harness

The separate [pinned-header translation-unit GitHub Action](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38392268627) has now **passed**: it used the actual CMake-generated build command to syntax-check the *complete* `BotTalentImport.cpp` against the pinned AzerothCore/Playerbots/Individual Progression repository stack. This addresses the original mock-harness header compatibility gap, but **not linking, runtime operation, custom installed patches, or safety of any equipment mutations**. Both stages of evidence should remain clearly distinguished.
