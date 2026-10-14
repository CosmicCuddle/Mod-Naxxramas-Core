# NT1 Pinned-Fork Translation-Unit Compile Gate

**Status:** GitHub Actions gate prepared on draft PR #18. This test is separate from the previously passing 15-case isolated C++ fixture. **Results must be checked before declaring compatibility.**

## Why this exists

`scripts/check_nt1_active_match_cpp_contract.py` compiles the real NT1 exact-match function against *mock* AzerothCore interfaces. It is useful but cannot uncover missing declarations, incompatible headers, link failures, or additional module hooks in the owner's actual source stack.

To move beyond that, [`.github/workflows/nt1-pinned-translation-unit-compile.yml`](../.github/workflows/nt1-pinned-translation-unit-compile.yml) checks out the exact previously recorded source revisions:

| Component | Repository | Pinned SHA |
|---|---|---|
| AzerothCore (Playerbots-compatible fork) | `mod-playerbots/azerothcore-wotlk` | `b7f06a16ac7120b5abc2e8d3f96a94265a363224` |
| Playerbots module | `mod-playerbots/mod-playerbots` | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Individual Progression module | `ZhengPeiRu21/mod-individual-progression` | `283abe12774801e5671da746ea8bf535cc0252e0` |
| Naxxramas Core | This PR HEAD | Draft PR #18 |

This is a **source reproduction target**, not proof that the owner's live server still runs these SHAs or has no local patches.

## Exactly what the workflow does

1. Checks out the four public repositories, without persisting checkout credentials.
2. Verifies exact dependency commit SHAs and installs standard compilation dependencies on the disposable GitHub runner.
3. Configures a CMake build with modules enabled, CMake compile-command export, and script/core PCH disabled. **No Worldserver executable is built or started.**
4. Runs `scripts/check_nt1_pinned_compile_commands.py`. It selects the **one real** CMake compiler invocation for `src/Systems/BotTalentImport.cpp`, replaces object and dependency-file emission flags with `-fsyntax-only`, and compiles the entire **unmodified NT1 C++ translation unit against real checked-out source headers**. A missing/ambiguous compile command, CMake error or C++ diagnostic **fails the workflow**.
5. Does not connect to a database, edit real characters, call Apply, move/mail equipment, touch the owner's Linux host, or merge anything.

The compiler argument selection and strict source pinning are guarded by `tests/test_nt1_pinned_compile_runner.py`.

## Strict claims

A **PASS** verifies CMake configuration and syntax/types for the NT1 translation unit **for that precise source set and CMake configuration**. It still does **not** verify:
- Linking Worldserver or dynamic modules successfully.
- Runtime Playerbots/Individual Progression interaction, hooks, custom DBC edits, installed local patches, or player-access semantics.
- In-game availability of the new Preview/Repair Preview output.
- Any active or stabled pet preservation, no-mail/no-move guarantee, item-instance GUID preservation or full rollback.
- Whether a future `git pull` of `main` would install the draft work. **It will not while PR #18 is unmerged.**

A **FAIL** should be treated as a specific pre-release blocker. Diagnose the logs; do not bypass guards or lower compiler checks just to get green CI.

## Next after this compile gate

1. Review and resolve any compiler diagnostics in the **draft** branch.
2. Optionally build/link a complete server **on an isolated build runner** before owner-approved installation.
3. Back up the module source, configuration and known-good Worldserver binary, and keep the `acore_characters` restore procedure separate.
4. Only after approved deployment, perform **read-only** `.naxxbot talents preview` and `repairpreview` in-game on an appropriate disposable Alt Bot. No destructive Apply testing.
5. Provide the mandatory final owner-to-N-MultiBot-Chatless handover only after actual server behaviour is verified; record any new exact-match chat lines without advertising them as Apply authorization.

**The Alt Bot occupied-offhand and active-pet blocks remain unchanged.**

## Observed pinned-source check: PASS (13 October 2026)

[GitHub Actions run #38392268627](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38392268627) completed successfully. The logs confirmed checkout of the three exact pinned dependencies, CMake configuration, and a **successful `-fsyntax-only` compilation of the full `src/Systems/BotTalentImport.cpp` translation unit against real source headers and CMake-generated flags**. This check did not link Worldserver. The draft work remains unmerged; the offhand and active-pet protections are unchanged. Subsequent checks of this gate must inspect the **most recent PR HEAD workflow**, not rely on this older successful revision.
