# NT1 Dependency API Preflight — Read-Only Operator Guide

**Development status:** Draft PR #16. This guide and checker are for **source-revision discovery and compatibility risk only**; neither authorizes nor performs a build, merge, installation, character change, database action or talent Apply.

## Why this check was added

AzerothCore `Player.h`, `Player.cpp`, `Unit.h`, `Item.h`, `Chat.h` and the Playerbots/Individual Progression APIs may not match public `master` in a customized server. We need **the exact server checkout and local changes**, not an assumed upstream commit.

The script `scripts/audit_nt1_dependency_apis.py` performs local *source-only* checks:

- Reads Git HEAD, Git top-level, and **tracked/untracked working-tree status** for four explicitly provided paths. If two module paths resolve to the same parent Git top-level, it warns that the module lacks an independent Git revision.
- Searches the installed source for per-spec `HasTalent`, const talent/spell-map getters, active-spec glyph read access, core item and chat APIs, Playerbots headers and the conservative offhand/talent-reset risk branches.
- Locates the Individual Progression header if present, but **deliberately does not claim automatic verification** of rewarded quest stages, 66001–66018, limits, or changing external module rules.
- Notes differences between the installed `BotTalentImport.cpp` and the draft PR #16 command names without treating an older installed source as an error requiring deployment.
- Prints a report **only to stdout**; does not save output or files, use a database, modify config, execute a build, fetch/pull source, change specs, move equipment, or contact GitHub.

**Potential mismatch** means manual review, NOT permission to alter a core function or reset any bot.

## How to run later (only when ready to collect source evidence)

First identify the **real paths** using the existing [dependency-revision checkpoint](NT1-DEPENDENCY-REVISION-CHECKPOINT.md). The following is a **template**: replace every `/actual/...` placeholder with the real source directory from your server. Do not run it with placeholders.

```bash
python3 /reviewed/draft/source/scripts/audit_nt1_dependency_apis.py \
  --core /actual/core \
  --playerbots /actual/core/modules/mod-playerbots \
  --ip /actual/core/modules/mod-individual-progression \
  --module /actual/core/modules/mod-naxxramas-core
```

**Important:** Until the draft branch is installed or the checker file has been safely copied to an isolated workstation, the live module directory **will not necessarily contain this script**. There is no reason to install the draft on the live server merely to run a preflight. The module names above are illustrative and **must be verified** on your host. The script works when invoked from a separately checked-out reviewed source and pointed at read-only server source directories.

To obtain machine-readable output without writing it to disk, add `--json` at the end. Do not add shell redirection unless you independently approve where the report will be saved.

## How to interpret results

| Finding | Meaning |
|---|---|
| `FOUND` | The named **textual signature** was located in source; compiler compatibility is still unproven |
| `MISSING` | Expected file/API/repository information could not be found or accessed; inspect revisions before attempting a build. The program exits with code 1 |
| `REVIEW` | Manual evaluation required: potentially custom DBC, IP schema, Git worktree difference, shared module checkout or runtime provenance |

The program may return exit code **0** when source signatures were found. **That does not mean a build has succeeded, nor that the PR may be merged, installed or used to Apply talents.** It explicitly reports unresolved runtime and recovery limitations in every result.

## Built-in safety limits

- The script has no source-modifying or database-writing path.
- It uses Git read commands with `--no-optional-locks`, does not follow symlink directories while searching Playerbots/IP headers, and limits search/read size.
- It reports only a yes/no dirty-worktree indicator, not file contents. Even a clean checkout may contain runtime, compile or configuration differences.
- Public upstream method signatures do not establish the real branch, binary provenance or whether Playerbots/IP hooks mutate state.
- The live mode most recently shared was `AccessMode = 2`, which permits **experimental Apply** on installed prior code; **do not run Apply** to test this checker.
- The original **any occupied offhand or active pet** Alt Bot guard must remain strict. Offhand equipment can be moved or mailed during core talent reset. Full offline `characters` DB recovery needs to be tested on an isolated restoration before any destructive experiment.

## Acceptance gates still outstanding

1. Source-preflight regression CI and documentation review on draft PR #16.
2. Operator-supplied exact AzerothCore / Playerbots / Individual Progression / Naxxramas Core Git SHAs, dirty flags and any relevant custom patches.
3. Human comparison of the checker findings with **actual** source, DBC policy, C++ compiler output and a documented **single bundled approved build**.
4. Approved in-game **read-only** Mode-4 diagnostics, including chat readability and protected-state comparison across ten classes.
5. Separate isolated database backup/restore proof and explicit permission before considering any **destructive** repair/Apply work.

For overarching project status, see [development handover](NT1-CROSSCLASS-HANDOVER-2026-10-12.md), [talent map integrity](NT1-TALENT-MAP-INTEGRITY.md) and the [safety audit](NT1-CROSSCLASS-TALENT-SAFETY-AUDIT.md).

## Test evidence

`tests/test_nt1_dependency_api_audit.py` uses synthetic local fixtures and mock Git output to verify:
- Correctly-shaped interfaces and missing core signatures fail conservatively.
- Bot headers, source tree scanning, IP manual-review status, and old installed module warnings.
- Clean, untracked-dirty, invalid and inaccessible Git metadata.
- Strictly read-only Git arguments, stdout JSON, and no source-write/deployment commands.
- Every result carries a runtime/safety disclaimer.

**These tests do not run on the administrator's Linux server and do not compile C++.** PR #16 must remain draft until the user expressly approves merging and compilation.

## Verified first integration CI

Commit `17df097254d927f35bfe5a9ad661fd4762d94411` passed **all four GitHub Actions source/synthetic workflows** on 12 October 2026: [combined 185/185 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38260675563) (includes **18 new mock dependency tests**), [Alt Bot recovery 90/90 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38260675571), [read-only diagnostics 12/12 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38260675593), and [Mage 25/25 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38260675585). **Counts overlap.** No exact-local-AzerothCore compile, local-source-version evidence, in-game inspection, or backup/restore rehearsal was performed. Draft PR #16 remains unmerged; nothing changed on the user's installed server.


## Follow-up hardening — Playerbots fork and false-positive prevention

The official [mod-playerbots installation guide](https://github.com/mod-playerbots/mod-playerbots/wiki/Installation-Guide) states that the Playerbots module requires its compatible [AzerothCore `Playerbot` fork](https://github.com/mod-playerbots/azerothcore-wotlk/tree/Playerbot), not a stock unmodified AzerothCore checkout. The script now obtains **only a classified Git origin family**, never the raw origin URL, so credentials accidentally embedded in a Git remote cannot be printed. Possible classes are `PLAYERBOTS_FORK`, `STANDARD_AZEROTHCORE`, `CUSTOM_OR_OTHER` and `UNKNOWN`. A customised/private fork is flagged for **manual review**, not automatically rejected or declared compatible. Origin matching does not establish the checked-out branch, patches, installed binary or C++ build.

The checker also masks C++ comments and quoted strings before searching for signatures, preventing commented-out methods from appearing to pass. Reset risk markers are searched **inside the `Player::resetTalents` function body only**, not elsewhere in the huge `Player.cpp`, with a separate, explicitly inconclusive check for the offhand-mail fallback. A changed/missing safety side-effect emits `MISSING` for manual review; an observed side effect emits `REVIEW` and keeps Alt Bot Apply blocked. Neither permits talent Apply.

These are **static text checks**, not an AST parser or real compiled-runtime evidence. Source trees with macros, unusual declarations or customised refactors may need direct inspection despite warnings. Additional tests cover fake APIs in comments/strings, unrelated C++ methods, nested function braces, origin credentials, normal AzerothCore and custom origins.


### Verified checker-hardening CI (12 October 2026)

Commit `65ce613bbd59fbe333ce18593192829642606b26` passed four GitHub Actions workflows on 12 October 2026: [combined NT1 **191/191 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38264426320) (24 dependency preflight tests total, six new this pass), [Alt Bot recovery **90/90 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38264426376), [read-only diagnostics **12/12 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38264426199), [Mage projection **25/25 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38264426323). Counts overlap; **no C++ compilation, local checkout compatibility test, 3.3.5a runtime test, database action, or deployed binary verification**. PR #16 is still draft/unmerged.


## Easier first step — discover likely module directories

Before using the full checker, run the **discovery-only** option from a separately reviewed copy of the script. Replace `/actual/core` with your real AzerothCore source directory.

```bash
python3 /reviewed/draft/source/scripts/audit_nt1_dependency_apis.py \
  --core /actual/core --discover
```

This command **does not select a module**. It lists likely Playerbots, Individual Progression, and Naxxramas Core directories directly under `modules/`. It skips symlinked directories and does not recurse into other sources, run Git, install a branch, alter any files or contact the network. Only direct folder names are used. **Check the candidates yourself** before putting their actual paths in the full audit command. If the modules directory is missing or a symlink, the discovery exits unsuccessfully and asks for manual path review.

Use `--discover --json` for stdout JSON. The full checker still needs all four explicit paths, deliberately refusing to silently pick among similar folders.

The public API signatures have also been source-reviewed against the actual [Playerbots-compatible core `Playerbot` branch](NT1-PUBLIC-PLAYERBOTS-FORK-API-BASELINE.md), pinned to reviewed public Git commit `2a2211cd8f3d157da432ec0175ddd4b8a191931f`. This is **not** the administrator's installed fork or a verified C++ build.
