# NT1 Integrated Development Build — Review and Operator Checkpoint

**Status:** PLANNING ONLY. No development PR has been merged, no files have been checked out on the user's Linux server, no SQL has been executed, no Worldserver has been recompiled, and no real Alt Bot repair has been attempted as part of this checkpoint.

## 1. Branch topology and required review order

All numbered PR references are within CosmicCuddle/Mod-Naxxramas-Core.

| PR | Feature | Base | Review dependency |
| --- | --- | --- | --- |
| #6 | Integration audit and recovery-policy documents | main | Documentation-only; does not install #7–#12 |
| #7 | Shared read-only Apply preflight | main | Common ancestor for the following feature branches |
| #8 | NT1L1 rank-priority read-only level projection | #7 feature branch | **Sibling of #9**: not automatically part of the Alt Bot branch |
| #9 | Read-only Alt Bot repair diagnostic | #7 feature branch | #7 first |
| #10 | Offline DB backup integrity checks and offhand warnings | #9 feature branch | #9 first |
| #11 | Known-risk Alt Bot offhand/active-pet pre-reset denial | #10 feature branch | #10 first |
| #12 | Read-only cross-spec talent/spell and equipment-identity observation | #11 feature branch | #11 first |

PR #12 contains the ancestor code from #7, #9, #10 and #11, **but does NOT contain the sibling PR #8**. Building PR #12 alone will not install the NT1L1 lower-level project command. A future **reviewed integration branch** is required to combine #8 with the Alt Bot stack; their changes overlap src/Systems/BotTalentImport.cpp and must be reviewed for conflicts and tests, not blindly force-merged.

## 2. What is safe to test next

A controlled development build can initially test **read-only** functions: existing NT1 preview, the PR #7 shared preflight, PR #9 Alt Bot repairpreview (including PR #10–#12 warnings, spec counts, item GUID fingerprints), and optionally the independent PR #8 project command when separately integrated.

These are **not** approval to run .naxxbot talents apply on an Alt Bot with an illegal original build. The current Apply fails closed because the old ranks cannot be restored under Vanilla restrictions. No .naxxbot talents repairapply exists anywhere in PR #12.

## 3. Before changing the production source tree

- Obtain operator approval and record exact current git branch, HEAD and uncommitted modifications in the Naxxramas Core module, core, Playerbots and Individual Progression. Do not reset, force-pull or discard local changes. Avoid modifying the upstream repositories.
- Back up the **working** Mod-Naxxramas-Core source directory (including configs and local patches), plus a securely stored full acore_characters database backup, before checking out a development branch. Verify the backup checksum and independently rehearse a restore on an isolated test database.
- Keep Worldserver stopped for a coherent production-DB checkpoint; ensure no other process writes to the character DB while taking the backup. Do not present a structurally valid .sql.gz file as a restore-tested backup.
- Confirm the current server's actual character DB schema, its Talent.dbc content (especially custom Priest/Mage ranks), and relevant config keys before compiling.
- Review all changes between the current main and the proposed test branch, including the original experimental Apply path. This stack has only passed **Python source/synthetic tests**, not compilation.
- Verify that NaxxramasCore.BotTalentImport.AccessMode retains fail-closed default 0, and AltBotAllowedPlayers retains default empty. If enabled for authorized read-only tests, note that AccessMode modes 1 and 2 ALSO expose the existing experimental Apply: do not assume they create a preview-only state.
- Confirm that the account-controlled Alt Bots are isolated test characters; never risk valued inventory or the only copy of a character.
- Preserve the user's explicit invariant: **Alt Bot equipment, bags, item ownership, professions and other inactive talents must not be altered**. The current PR #11 Alt-only preflight conservatively blocks when offhand or active pet is present. This is a known-risk mitigation, not a proof that any C++ reset hook is safe.

## 4. Compilation / smoke-test acceptance

After the administrator explicitly approves a controlled source checkout/build (no instructions here run automatically):

1. Compile against the user's **actual installed** AzerothCore, mod-playerbots, mod-individual-progression and Mod-Naxxramas-Core versions. Capture the first real compiler error, especially header/API differences. Never claim source-contract Python tests validate compiler compatibility.
2. Start a test Worldserver against a recoverable characters DB. Verify command registration and the .naxxbot talents preview positive Vanilla Mage case and blocked non-Vanilla cases. Do not Apply.
3. Verify .naxxbot talents repairpreview for a backed-up, noncritical Priest Alt Bot. Confirm old illegal Talent.dbc IDs 1768 / 1202 are reported, a valid target 51/51 is distinguishable from un-restorable original ranks, both specs' talent/spell records and equipment slot counts render correctly and all warnings are visible.
4. Negative tests: incorrect issuer era, name allowlist missing (GM included), unauthorized other bot, Random Playerbot target, invalid class/DBC rank, target in combat, active pet/equipped offhand. Expect **no changes** to talents, items, spells, other spec or bags.
5. Observe relog and restart and validate the read-only observations only. An unchanged checksum is not a substitute for comparing real offline baseline state.
6. Only after compiling and testing the combined read-only path should administrators consider a **separate experimental, disabled-by-default Alt Bot repair Apply PR**. That later project needs fully rehearsed recovery, client/issuer confirmation, no item motion or mail fallback and failed-rebuild recovery proof.

## 5. Remaining independent work

- **Alt Bot repair (highest priority):** offline full restore rehearsal, rigorous spec/glyph/pet/item invariants, Playerbots maintenance conflict controls, default-off per-Alt-Bot confirmation, and controlled destructive recovery tests.
- **NT1L1 lower-level talent Apply:** PR #8 currently provides only read-only projection. A stored priority plan, secure server confirmation ticket, target budget, atomic recovery strategy and tests are not ready.
- **MultiBot client confirmation:** the addon UI currently sends commands but cannot treat chat dispatch as proof of successful server Apply without server acknowledgement/token.
- **Random Playerbot gear automation:** separate later feature. Never gear Alt Bots by NT1.

**Operator action needed today:** none. Do not recompile or change live core/Playerbots merely because these draft source checks have passed.
