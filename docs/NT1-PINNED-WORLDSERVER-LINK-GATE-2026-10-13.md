# NT1 — Pinned Worldserver Compile + Link Acceptance Gate

**Project:** Mod-Naxxramas-Core, draft [PR #18](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/18)  
**Status:** automated **full-link CI check requested**. Read the run logs for the exact PR revision before claiming success.

## Objective

Move beyond the existing successful `-fsyntax-only` import check and compile/link an entire Worldserver on a temporary GitHub Actions runner. This detects missing definitions and ABI/library incompatibilities that cannot be ruled out by a source-slice mock harness or a single translation-unit compile.

The `[NT1 pinned Worldserver compile and link](../.github/workflows/nt1-pinned-worldserver-link.yml)` workflow checks out:

| Component | Commit |
|---|---|
| Playerbots-compatible `mod-playerbots/azerothcore-wotlk` | `b7f06a16ac7120b5abc2e8d3f96a94265a363224` |
| `mod-playerbots/mod-playerbots` | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| `ZhengPeiRu21/mod-individual-progression` | `283abe12774801e5671da746ea8bf535cc0252e0` |
| This Naxxramas Core module | **exact PR head SHA**, verified before build |

CMake uses `-DMODULES=static -DSCRIPTS=static -DAPPS_BUILD=world-only -DTOOLS_BUILD=none`. This is a more complete, **fully linked** Worldserver target rather than the `-DSCRIPTS=none` isolated syntax compilation.

The runner:

1. Checks revision identities and installs Linux dependencies.
2. Configures CMake in `acore-build`.
3. Runs `cmake --build acore-build --target worldserver --parallel 2`.
4. Requires a non-empty executable named `worldserver` to exist and be executable.
5. **Never starts Worldserver**, runs SQL, changes any character or item, deploys a build, or modifies the owner's machine. The runner discards its build artefacts automatically.

The companion `tests/test_nt1_pinned_worldserver_link.py` prevents accidental weakening of pinned revisions, full-link flags, and original access/equipment protections.

## What PASS would prove — and what it does not

**A PASS**, tied to the exact revision, supports source compatibility and C++/link completion of that isolated build with the three pinned public dependencies.

It **cannot** prove that the owner's actual binary, custom patches, custom DBC files and other installed modules are identical. It cannot prove talent Apply is transactional, no equipment moves or mail occurs, the original `item_instance.guid` survives, inactive specs/pets remain safe, or the addon parses all server messages. Those require explicit separate verification.

**A FAIL** is a pre-release blocker. Diagnose the first actual build/link error and correct it on the draft branch. Do not disable the offhand guard, weaken permissions, alter SQL or change game behaviour to mask an unrelated compiler error.

**Source safety stays unchanged:** occupied offhand Alt Bots are blocked from Apply, active-pet Alt Bots are blocked, no automatic role gearing or no-op Apply has been approved, and modes 3/4 remain read-only.

## After the build check

If the full link passes: source review, backups, owner-approved local compile/restart and read-only in-game `.naxxbot talents preview`/`repairpreview` remain necessary before this work can be considered deployed. No destructive tests without a verified isolated `acore_characters` restore and explicit separate permission.

The **final copy-and-paste Naxxramas Core → N-MultiBot-Chatless handover** is still mandatory once actual behaviour, interface and release state are settled. No addon changes are required solely to run this CI workflow.
