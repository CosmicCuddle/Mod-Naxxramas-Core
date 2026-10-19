# Human Hunter autocast — module-owned, disposable IP compilation

**19 October 2026 · CI experiment ONLY, not a release or server change.**

The owner allowed a compilation investigation on the condition that **everything permanent remains self-contained within Mod-Naxxramas-Core**. The *test instructions*, un-applied IP proposal, C++ compile-command selector and workflow all live solely in this Naxx module repository. The workflow uses a disposable GitHub runner that clones exact pinned upstream core/IP/Playerbots sources, temporarily applies the plain-text proposal to the runner's **uncommitted IP working copy**, compiles **one actual modified IP C++ translation unit** with pinned CMake flags, and restores that copy in an `if: always()` cleanup. It performs **no upstream commit, push, PR, installation, Worldserver execution or database operation**.

**Very important distinction:** the proposed code itself is presently an IP-source modification. Compiling it inside a module-owned workflow does **not** make the eventual gameplay solution a **module-only runtime implementation**. Any permanent IP patch, auto-applied build-time patch or modified installed IP would **violate the user's module-contained requirement** unless the user independently and explicitly changes that requirement. This experiment therefore cannot authorize such deployment.

## Exact input identities

| Component | Pinned revision |
| --- | --- |
| Grimfeather AzerothCore | `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` |
| Grimfeather Individual Progression | `4ff4b5fcc1480348f058c632573143e62d4e3a41` |
| Compatible Playerbots (compile dependency only) | `037c01418b5d01506917a3db9b44fd56ac5f965c` |
| Naxxramas Core | Exact invoking PR HEAD; workflow rejects any mismatch |

## What the test measures

- Verifies the four exact checked-out SHAs before touching anything.
- `git apply --check` then `git apply` the proposal against only the **ephemeral CI checkout** of `src/IndividualProgressionSpells.cpp`.
- Fails if any *other* tracked IP file was changed or if the diff has whitespace errors.
- Configures the known-compatible pinned Worldserver CMake environment without launching a server or connecting to any database.
- Locates the **one exact C++ compile command** for `src/IndividualProgressionSpells.cpp` in CMake's `compile_commands.json`. Fails if there are zero or multiple matching units; no placeholder/synthetic replacement.
- Executes that real compile command against the patched disposable IP file. This tests whether the **proposed C++ translation unit** compiles with the pinned compiler/configuration. It is deliberately **not** a full executable link or a real player test.
- Restores the IP tracked source using `git restore`, checks the pinned IP HEAD SHA and clean status; it does not commit/push/fork/upload IP code or binaries. GitHub destroys the temporary runner when finished.

### Pending design decision: functional delivery remains Naxx-only

A functional first release must be implemented in the Naxx module using supported native hooks **without changing IP**, and must preserve manually selected human Hunter pet autocast ON and OFF, legal rank and spellchain, both PetSpell and actionbar state, same-pet identity, and reliable post-IP sequencing. The public pinned hooks reviewed to date do not establish a safe atomic before-unlearn/after-relearn interception across IP's existing reconciliation.

If no trustworthy module-only hook exists, **stop at research** and present the blocker to the owner. Do not ship a hidden IP source patch, a CMake copy/rewrite trick, periodic autocast toggling, new preference DB workaround, or a change to Playerbots AI. The original real-player symptom is still not independently reproduced. Separate **restorable characters DB + binary/config backups** and explicit staging approval would be needed for any future player test.

**Expected result text when CI passes:** “Proposed IP C++ translation unit compiled in disposable CI.” It is NOT “Hunter autocast fixed,” “module-only implementation,” “Worldserver linked,” or “safe to deploy.”

See [draft PR #37](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/37), and [master checklist #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28). All changes remain draft.
