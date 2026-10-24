# A04 — human-friend quest-loot observation gates (S1, review only)

**Owner report:** a real human friend has actually taken a quest-related item from a group corpse, not just seen a sparkle. Treat human-to-human pickup as a real open defect. **No source/config/DB/DBC/binary/live-server change in this branch. Do not merge.**

**Why this note exists:** Earlier `docs/QUEST-LOOT-PROTECTION.md` (main) has QL-01–QL-15 controlled acceptance rows. CS02's [#117](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/117) contains the much larger pinned award-path proof, decision table, and unchosen policy A/B/C. This note adds a **small, evidence-first identification plan for the *reported* human-human pickup**, deliberately distinguishing runtime/config visibility from packet/loot-policy outcomes. It is **not** an additional loot policy or an instruction to run tests now.

## Exact source anchors

| Question | Source evidence (pinned tree) | Constraint |
| --- | --- | --- |
| Is the existing guard even active? | `src/Systems/QuestLootProtection.cpp:26-30,205-226` uses `NaxxramasCore.QuestLootProtection.Enabled` (default false). `conf/mod_naxxramas_core.conf.dist` sets it to 0. | The owner's loaded config, binary and current runtime state are **UNKNOWN**. Seeing a configured value in a distributed example or hearing that the setting was switched on cannot prove the running binary took the guarded path. |
| When does its debug line appear? | `QuestLootProtection.cpp:185-194`: `if (Debug())` at line 185 gates the sole `LOG_INFO("module", ...)` at lines 186-191; `SendLootError(sourceGuid, LOOT_ERROR_LOCKED)` and `return false` at lines 193-194 run **regardless of Debug**. | **No permitted path logs in this file.** A real denial with `QuestLootProtection.Debug=0` also emits **no** module log line, but still sends client `LOOT_ERROR_LOCKED`. Even with `Debug=1`, logger filtering can hide the INFO line. Neither a missing log nor a client symptom alone proves execution; do not request global verbose packet logging. |
| Friend is actual round-robin holder | `QuestLootProtection.cpp:73-76` returns true for `roundRobinPlayer == player's GUID`; `Player::StoreLootItem` permits eligible quest-view rows without checking that turn. | Current narrow protection **cannot prevent** that eligible friend from consuming the shared item. Not yet an approved rule change. |
| Turn was released | `QuestLootProtection.cpp:73-76` returns true if `roundRobinPlayer` is empty; `LootHandler.cpp:459-461` can clear it on release. | A human pickup after release does **not** establish that the guard was disabled. |
| Item belongs to ordinary `loot.items` | `QuestLootProtection.cpp:79-82` permits any slot below `loot.items.size()`. | A quest-relevant item id can still be in **normal** loot when `QuestRequired = 0`. Need actual loot-template bucket; “it was for my quest” does not prove it was a `quest_items` slot. |
| It was already personal MULTI_DROP | `QuestLootProtection.cpp:100-108`; `LootMgr.cpp:400`; `Player.cpp:13915-13943`. | Do not classify a friend's independent personal copy as theft of the other person's one shared copy. `FREE_FOR_ALL` group loot method is **not** `ITEM_FLAG_MULTI_DROP`. |
| Is the loot source a creature corpse? | `QuestLootProtection.cpp:62-72` skips non-creature/vehicle loot GUIDs, non-corpse loot types and a recipient group mismatch before checking the round-robin holder. | Game objects/chests, skinning or pickpocket loot, and differently tagged corpses stay under native rules; the current module guard does not protect them. |
| Was another award path used? | `WorldSession.cpp:461-464` calls `CanPacketReceive` before native socket autostore; Playerbots `HandleBotPackets`, group rolls and master-loot award have other paths (see #117). | This S1 plan is **human socket pickup first**. No assumption that every bot or roll path passes through this hook. |

**Pins:** module main `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9` for `QuestLootProtection.cpp`; public Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`. #117 also pins Playerbots `e88cc4099e69f35126b28942a412ca702d20453b` when tracing bot packet handling; public pinned CI uses Playerbots `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091`. Neither represents or overwrites the owner's two uncommitted compatibility edits. This note is a synthesis of existing source evidence, **not a fresh live trace**.

## Read-only evidence identification, *before* any proposed S5 gameplay

No owner action is requested now. If separately authorised later, a reviewer should first confirm (without changing anything):

1. Exact **installed module/core/Individual Progression/Playerbots SHAs**, and record separately whether the owner's **two uncommitted local Playerbots changes** are still present. Never run a command that resets or overwrites them.
2. Exact **active** module configuration path and loaded `QuestLootProtection.Enabled` / `Debug` values, distinguishing running process from `.conf.dist`. A restart, config change or instrumentation needs its own separate approval.
3. The **quest id, item id, loot source (creature corpse vs game object vs other), creature or game-object entry where applicable, loot-template row and `QuestRequired`**, item count and `ITEM_FLAG_MULTI_DROP`; note whether source places the item in `loot.items` or `loot.quest_items`. Avoid importing private SQL into GitHub: only post necessary non-sensitive observations.
4. Human-only group membership, **loot method**, actual **round-robin holder** and whether the turn was released; which players still need the item, whether they were eligible for reward, and whether a *shared* item count fell after the friend's pickup.
5. Distinguish **(a) corpse sparkle, (b) visible loot row, (c) client click/autoloot request, (d) server guard permit/deny, and (e) actual inventory award**. A screenshot of (a) or (b) cannot substitute for evidence of (e).

Without items 1–4 there are several plausible paths to the same symptom. A source prediction is not an observed runtime diagnosis.

## Future staging acceptance additions — not authorised or run

These **extend** rather than replace main's QL-01–QL-15 and #117's decision table. Use *new disposable corpses per scenario*, in a separately owner-approved staging/test environment **after a proven, restorable characters/world database and binary/config backup**. No unapproved manipulation of characters or real loot.

| New row | Human-human setup | Today’s source expectation with existing guard ON | What one observation would distinguish |
| --- | --- | --- | --- |
| **HF-01** | Both humans need single-copy `quest_items` row; **friend is the round-robin holder** | Guard permits; friend can consume shared copy | A successful award here is the known **#117 H09 permit**, not proof that packet hook was bypassed |
| **HF-02** | Both need same row; **owner is active round-robin holder**, friend clicks before release | Guard denies if all narrow owner/creature/eligibility conditions hold | A successful friend award under *confirmed* eligible conditions demands binary/config/hook/slot investigation |
| **HF-03** | Same row; previous holder **released** turn, then friend clicks | Guard permits native path | Friend award is expected without an explicitly chosen replacement policy |
| **HF-04** | Friend needs item id for a quest but underlying row is **normal `loot.items`** (`QuestRequired=0`) | Guard permits; core loot method/visibility determines normal presentation | Confirms scope gap distinct from quest-only single-copy item; do not infer hidden client row was clicked |
| **HF-05** | Both qualify for item with **`ITEM_FLAG_MULTI_DROP`** | Each may take an independent personal copy | Inventory additions must be attributed to separate viewer copies, not presumed shared theft |
| **HF-06** | Keep same eligible quest-item scenario but alternate **GROUP_LOOT / ROUND_ROBIN / NEED_BEFORE_GREED / MASTER_LOOT / FREE_FOR_ALL** | Guard only considers the first three; native behaviour elsewhere | Differentiates skipped group-method branch from bad owner eligibility |
| **HF-07** | Human picks a quest-relevant item from a **game-object chest** or other **non-creature/non-LOOT_CORPSE** source; separately a corpse with a mismatched loot-recipient group | Guard returns `true` (native rules) before quest/turn checks at `QuestLootProtection.cpp:62-72` | Correctly identifies an intentionally unguarded source category; do not misdiagnose a permitted native pickup as failure of the creature-corpse guard |

### Safe review / abort boundary

- Every row is **NOT RUN**; no PASS or FAIL should be assigned from source alone. No player, item, server, config, database or bot changes are authorised by this document.
- Do not ask the owner to consume irreplaceable quest items for a demonstration. On any unexpected deletion, duplication, stuck loot, inventory change, crash, or bot side effect, abort the approved staging test and follow its *previously rehearsed* restore procedure.
- A debug message exists only for an actual **denial** and only if `Debug=1` **and** logger filtering permits INFO. With `Debug=0`, a real denied pickup still sends `LOOT_ERROR_LOCKED` but writes no module denial log. A permitted path logs nothing. In particular `Debug=1` plus **no denial message** cannot confirm that the code was skipped, nor that a friend was entitled to receive the item.
- Avoid identifying information in public comments: do not publish character GUIDs, account identifiers, private database extracts or credentials.
- **No A/B/C choice is implied.** A preserves one copy with limited gate, B gives eligible individuals separate copies (economy change), C names the one-copy owner and needs fallback rules. Choose only after owner reviews policy implications.
- Request an independent source-only review of this matrix. A later implementation proposal requires explicit owner permission, a narrowly scoped default-OFF design, native tests, backups and rollback. Existing PR #117 remains OPEN DRAFT.

**Status:** S1 documentation-only, no proposed hook write or automatic action. — CosmicScript01
