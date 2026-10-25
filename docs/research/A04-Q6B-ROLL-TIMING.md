# A04 Q6b — roll-time vs award-time eligibility (CS03 research witnesses)

**Status:** research only, authorised by CS01 (#143 `6399878253`) as one Claude-owned synthetic test branch. **Not a loot policy, not a fix, and not proof of the owner's report.** No module code, Playerbots, core, SQL, DBC or config change. Every result below is source behaviour at Grimfeather core `8daffdabe9202c228e45d833c9a1d399597a15cd`, not a game result.

It follows CS03's scrutiny of #150 ([6399573014](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/150#issuecomment-6399573014)).

## What is modelled

`tests/research/a04_roll_model.py` copies, in Python, only the decisions these native functions make. Each line in the model cites its source line.

| Function | File and lines | Role |
|---|---|---|
| `CanRollOnItem` | `Group.cpp` L1106–L1121 | roll admission (max count, `AllowedForPlayer`) |
| `Group::GroupLoot` | `Group.cpp` L1123–L1286 | which slots roll; auto-pass for ineligible members |
| `Group::SendLootStartRoll` | `Group.cpp` L928–L950 | roll window only to members still `NOT_EMITED_YET` |
| `Group::CountRollVote` | `Group.cpp` L1497–L1546 | vote counting |
| `Group::CountTheRoll` | `Group.cpp` L1604–L1826 | Need, then Greed award; mail; roll winner reservation |
| `SendRollWonItemViaMail` | `Group.cpp` L67 | mail award when bags are full |
| `Player::StoreLootItem` | `Player.cpp` L13861–L13962 | direct pickup gates |
| `Player::HasQuestForItem` | `PlayerQuest.cpp` L2338–L2385 | quest still needs the item (reads the objective **counter**) |
| `AdjustQuestReqItemCount`, `ItemAddedQuestCheck`, `ItemRemovedQuestCheck` | `PlayerQuest.cpp` L1838–L1855, L1909–L1946, L1948–L1985 | objective counter on accept, receipt and removal |
| `LootItem::AllowedForPlayer` | `LootMgr.cpp` L417–L470 | eligibility |
| `Loot::LootItemInSlot`, `LootView` | `LootMgr.cpp` L821–L880, L1033–L1037, L1130–L1149 | quest slots and visibility |

- **Drift gate.** `scripts/check_a04_roll_fingerprint.py` hashes all 20 functions at the pin. A one-character change fails it, which forces this model to be re-reviewed.
- **Simplifications:** one loot source; one slot per roll; injected roll numbers instead of `urand`; no conditions, faction, recipe or disable rules (none of which change during a roll); no packets or achievements.

## Objective counters, not inventory (revision after CS01 review `6400615303`)

`AllowedForPlayer` calls `HasQuestForItem`, which reads the quest log's `QuestStatusData.ItemCount` (the objective **counter**), not inventory. The counter moves only through these three functions, and the model now copies each one separately:
- **On accept**, `AdjustQuestReqItemCount` sets it to `min(held, required)`.
- **On receipt**, `ItemAddedQuestCheck` raises it only while the quest is `INCOMPLETE`, capped at the required count. The quest becomes complete when every objective is met.
- **On removal**, `ItemRemovedQuestCheck` re-reads a met counter from inventory, reduces it, and marks the quest `INCOMPLETE` again.

**Login is the case where the two differ.** `_LoadQuestStatus` loads the counter as stored, with no re-adjust to current inventory. So after a login, the counter, not the bags, decides eligibility.

Five tests cover the cases the first version could not express:
- a multi-objective quest stays `INCOMPLETE` while one item's objective is already met (that item is no longer eligible);
- destroying the item reopens eligibility;
- items held before accepting count at accept;
- after login, a loaded counter differs from the bags and still decides eligibility;
- the same-pull surplus gap also happens while a multi-objective quest is still incomplete.

**Still simplified:**
- every quest is a deliver quest;
- no source-item, timed or reward-choice objectives;
- turn-in is modelled as leaving the quest log;
- `CountRollVote` provenance (map, packet and session state) beyond the vote itself.

## The owner's two #109 observations, matched to native paths

`tests/research/a04_turn_model.py` adds a transcription of group loot turns, turn release and the module's existing guard (`QuestLootProtection.cpp` on main, blob `48729dc`, pinned by a test):
- `Unit::Kill` → `Group::UpdateLooterGuid`: the loot turn **rotates every kill** among members in range (every method except Free-for-All).
- `Loot::FillLoot` L569: `roundRobinPlayer` is set to that kill's loot owner.
- `DoLootRelease` L459–L461: the turn ends when that owner closes the loot window.
- `Player::isAllowedToLoot` decides the corpse sparkle.

The setting is a **one-copy** quest drop (`QuestRequired=1`, no `MULTI_DROP`, no flag 0x4) under group loot, with the guard ON as reported:

| Owner observation | Native path that produces it | Bug? |
|---|---|---|
| **1. The friend sees the corpse sparkle, tries, and is denied** | On the **owner's** turn the friend has their own quest slot (sparkle via `hasItemFor`), and the module refuses the pickup (`LOOT_ERROR_LOCKED`) | No: the guard working as designed |
| **2a. The friend successfully takes "the owner's" quest item** | On the **friend's own turn** (every other kill), the friend is the turn owner and takes the single shared copy | No: stock one-copy group loot |
| **2b. The same, after the owner looked** | The owner opened the corpse and **closed** it without taking the item, which ends the turn; the module fails open and the friend takes it | No: stock release, and the guard fails open by design |
| 2c. The friend lacks the quest or has already met the objective | No quest slot at all, so neither sparkle nor pickup from the quest item | Would be a bug if it happened; the model shows it **cannot** on these paths |

So **both reports are reproduced by stock rules plus the guard, provided the friend also had the quest and still needed the item.** An invalid award needs one of the other mechanisms in this document:
- Q6b, Q6 or mail (the drop must roll: flag 0x4);
- Q13 or Q15 (a modified client);
- a `QuestRequired=0` row, which is an ordinary item to the core.

**One owner sample decides between these** (no new test run needed):
- Was the friend on the quest, and still short of the item, at the time?
- Whose loot turn was it? The client prints the looter.
- Did the owner open and close that corpse first?
- The item's `Flags` (`MULTI_DROP`) and `flagsCustom` (0x4).
- The loot row's `QuestRequired`.

If the owner wants each eligible human to get their **own** copy, that is a loot **policy** change (personal or `MULTI_DROP`-style quest loot), not a bug fix, and it needs an explicit owner decision.

## Results (31 tests: 8 GAP, 23 REF)

GAP means a stock path that gives an item to a player the native rule would refuse at award time, or strands a copy. REF means legitimate stock behaviour that any later change must keep.

| Test | Kind | Finding |
|---|---|---|
| quest bucket rolls only with flag 0x4 | REF | Quest rows roll only with `ITEM_FLAGS_CU_FOLLOW_LOOT_RULES` (L1220–L1224). Otherwise they use per-player quest slots. |
| admission checks eligibility and max count | REF | Ineligible members are auto-passed and get no roll window. |
| direct pickup re-checks eligibility | REF | Without flag 0x4, the second copy is refused to the player who completed the quest and goes to the other eligible human. |
| single roll / two rolls split | REF | Ordinary group rolls stay legitimate. |
| **Q6b surplus copy** | GAP | Two same-pull rolls are admitted while both humans are eligible. A wins both: the second award (L1662) happens after A's quest is complete, so `AllowedForPlayer(A)` is now false, yet A gets a second copy. B, eligible throughout, gets none. |
| **Q6b Greed branch** | GAP | Same gap on Greed (L1746). |
| **Q6b max count strands the copy** | GAP | With `maxcount = 1`, the second award fails with `CANT_CARRY_MORE`, which is not `INVENTORY_FULL`, so it is not mailed. The slot is reserved to A (L1682–L1683): hidden from B (LootMgr L1033–L1037) and refused to B (L13902). A is refused too. Nobody can loot it. |
| **Q6 abandon while pending** | GAP | A abandons within the 60-second window and still wins. |
| ignore-quest-status item | REF | With flag 0x2 a second copy is the item's intended rule, not a lapse. |
| mail: default off / LFG only / everywhere | REF / REF / GAP | Only when `LFG.MailItemOnFullInventory` is not 0 (the default is 0): the full-bag win is mailed with no eligibility check. |
| **Q13 vote overrides auto-pass** | GAP | **Forged or replayed packet only.** A Need vote from an auto-passed member is counted. Because the earlier pass is never subtracted, pass + need already equals the number rolling, so the roll ends at once and that member wins **before others vote**. |
| **Q15 quest-slot pickup during roll** | GAP | **Forged packet only.** The honest window shows `ROLL_ONGOING`, but `StoreLootItem` skips `is_blocked` for quest slots (L13895). The pickup succeeds, and `CountTheRoll` does not check `is_looted`, so the roll winner also gets a copy: one drop, two items. Playerbots `d750b4b` skips non-`ALLOW_LOOT` slots (`LootAction.cpp` L423) and checks `NOT_EMITED_YET` before voting (`LootRollAction.cpp` L26–L27). |
| normal pickup blocked during roll / disenchant / all pass | REF | Stock blocking, the disenchant result and unblocking stay as they are. |

**Mutation check (local).** Each of these mutants turns specific GAP tests red, and the original passes all tests:
- the award re-checks `AllowedForPlayer` (8 tests);
- votes require `NOT_EMITED_YET` (Q13);
- quest slots honour `is_blocked` (Q15);
- max-count failures are also mailed (the stranded case).

## What this means for A04, and what it doesn't

- **Scope.** Q6b, Q6 and the mail cases need the drop to **roll**. For a quest objective, that means the item has custom flag 0x4 or is a non-quest-bucket row. Most quest drops do not roll; they use per-player quest slots, and pickup re-checks eligibility (REF).
- **The owner sample decides.** Any of these is a candidate only once the owner's one anonymized sample shows the item's `flagsCustom` and `maxcount`, the quest's required count, how many copies dropped in one pull, the loot method, each human's eligibility, and whether the copy reached bags, mail, or stayed visible to the winner only.
- **Stock behaviour to preserve** in any later change: ordinary shared one-copy items, `MULTI_DROP` personal copies, a legitimate roll or turn winner, and the flag-0x2 intended rule.

## Not verified

- the owner's binary, config, item rows or flags;
- any client, packet or game behaviour;
- other modules' `OnAllowedForPlayerLootCheck` or `OnPlayerBeforeFillQuestLootItem` hooks;
- master loot and Need Before Greed (`CanRollForItemInLFG`) beyond what #150 documents.
