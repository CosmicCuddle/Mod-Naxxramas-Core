# A04 — Part 24 native item-award entrypoint audit (read-only source evidence)

**Status:** isolated **DRAFT / RESEARCH ONLY**. No A04 gameplay fix, policy change, test server, SQL, DBC, enabled config, merge or real-player-data analysis. **Owner policy is ordinary WoW/AzerothCore group loot with ONLY a proven incorrect human-to-human quest-drop award fixed.** No personal-loot invention, additional copies, claimant reservation or unjustified recipient denial.

## Reproducible source pins and limitations

- Module **main** `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`, `src/Systems/QuestLootProtection.cpp` lines 24–231; feature master is default OFF. Claude's map-thread lookup correction #132 `6d86ab39093a791319804d102c5e4e88ef2673d6` is an **isolated safety proposal, not the bugfix**. Normal hidden-slot parity candidate #129 `a57136306225f078e636a63d82eac4b0c231cebf` remains unproven for the owner's symptom.
- Grimfeather AzerothCore **exact** `8daffdabe9202c228e45d833c9a1d399597a15cd`, files and line ranges below, fetched read-only via GitHub on 25 October 2026.
- Playerbots selected by owner and installed runtime, loaded world DB item flags/rows, actual example, configuration, client packet history and real loot behavior were **NOT** inspected. The pinned code and module are not a statement of the owner's actual running binary. Do not put character names, account/GUID values or raw loot logs in a public draft.

## Native entrypoints — NOT a single unified packet path

| Award route | Pinned source | Key eligibility time | Packet-only A04 guard coverage | Source-backed status |
|---|---|---|---|---|
| Human direct item click / autoloot of creature, GO, owned item, corpse or pickpocket | `Handlers/LootHandler.cpp:33–119` calls `Player::StoreLootItem`; `Entities/Player/Player.cpp:13864–13950` | `LootItemInSlot`, `item->AllowedForPlayer(this, source)`, block and rollWinner checks **before** `StoreNewItem` | Module `SERVERHOOK_CAN_PACKET_RECEIVE` sees `CMSG_AUTOSTORE_LOOT_ITEM` but `PermitPickup` narrows to creature corpse/quest bucket; GO, items, other native sources fail open | Missing eligibility on a quest-required item cannot be presumed bypassed: verify actual item type/flags and award |
| Master-looter gift to another player | `Handlers/LootHandler.cpp:478–573` | `HandleLootMasterGiveOpcode` checks master role, raid association, then `item.AllowedForPlayer(target, source)` **before** `target->StoreNewItem` | Distinct `CMSG_LOOT_MASTER_GIVE`, not the module autostore hook | Not an automatic loophole for ineligible quest-only items; if friend received one, inspect eligibility and any other script producer |
| Group Loot roll Need or Greed | `Groups/Group.cpp:1106–1121, 1124–1199, 1598–1670, 1705–1755` | `CanRollOnItem` calls `AllowedForPlayer` on **roll admission**; accepted winner is awarded using `StoreNewItem` in `CountTheRoll` without a fresh `AllowedForPlayer` call on these Need/Greed branches | A roll result is not the human autostore packet | Distinguish **earlier eligibility** from **changed status during pending roll**. Time-of-check/time-of-award difference is a research hypothesis, not proof of bad gameplay |
| Need Before Greed roll | `Groups/Group.cpp:1288–1430` | `CanRollOnItem` on admission for regular high-quality and `follow_loot_rules` quest rows | Not autostore packet | Eligibility at roll start shown; no evidence of invalid user example |
| Master/Group/Round Robin loot view | `Loot/LootMgr.cpp:976–1155` | `LootView::operator<<` applies per-viewer eligibility, roll lock, round-robin and quest-slot presentation | Visibility only — not inventory mutation | A loot sparkle/slot display cannot prove a bag award; ordinary hidden slot may differ from native autostore turn gating |
| Personal currency tokens generated while filling loot | `Loot/LootMgr.cpp:602–630` | `freeforall && AllowedForPlayer` before auto `StoreLootItem` | No human packet necessarily | Automatic award exists; distinguish from ordinary quest drop |
| Standalone loot from enchant/disenchant roll | `Groups/Group.cpp:1760–1803`, `Player::AutoStoreLoot` | Roll success creates separate disenchant loot, not the same source item slot | Not the ordinary human autostore-click path | Separate secondary item creation; not evidence a player took the original quest drop |

**Additional hook distinction:** `OnPlayerLootItem` appears on successful `Player::StoreLootItem`, while group roll awards use `OnPlayerGroupRollRewardItem`; master-loot assignment calls `StoreNewItem` directly. Therefore **a single packet filter or a single success observer cannot claim comprehensive coverage**. Confirm all actual registered hook implementations before proposing a global diagnostic.

## Quest-item status is a SOURCE PROPERTY, not the name of a quest

- `Loot/LootMgr.cpp:395–466` constructs a `LootItem` with `needs_quest` from the **effective generated loot row**, and `ITEM_FLAG_MULTI_DROP` sets `freeforall` per template. Do not confuse group `FREE_FOR_ALL` loot method with `MULTI_DROP`.
- `LootItem::AllowedForPlayer` checks conditions, faction, recipes, disables, quest starter restrictions and `needs_quest && !HasQuestForItem`. Crucially, `ITEM_FLAGS_CU_IGNORE_QUEST_STATUS` can bypass quest-status rules. Other hooks also participate. `QuestRequired=0` can be a normal one-copy shared item EVEN IF a quest objective.
- `Loot::FillQuestLoot` at `Loot/LootMgr.cpp:658–691` creates per-player quest slots after eligibility, with deliberate exception for the master looter's listing (not an unrestricted award). `Loot::LootItemInSlot` at 821–878 maps each player's own quest slot list; ordinary normal slots and shared drops are a different path.
- A **friend without a quest** taking an ordinary `QuestRequired=0` item on their legitimate turn is not automatically a bug. A **friend eligible for the same quest** taking one normal shared drop is also not automatically a bug. A `MULTI_DROP` personal copy is not stealing the other person's drop.

## Exact negatives / falsifiers before implementing a correction

| Case | Native expectation to verify | Evidence that would matter |
|---|---|---|
| Q1: Two human players, `QuestRequired=1`, no ignore-status flag, friend ineligible | Direct `StoreLootItem` should deny if `AllowedForPlayer=false` | Proof of actual bag receipt plus effective template flags, other script/hook, source kind and award path; impossible to infer from sparkle |
| Q2: Ordinary `QuestRequired=0`, legitimate friend current shared-loot holder | Native group loot normally permits it | Record method and turn; do **not** change loot economy |
| Q3: Friend and owner both qualify for single shared copy | Current legitimate holder's stock rights remain | Confirm turn/roll/master rather than treating every shared pickup as defective |
| Q4: Multi-drop personal copies | Viewer-specific copies can each be looted | Check `item_template.Flags` and whether *the same* shared copy disappeared |
| Q5: Normal under-threshold row hidden to nonholder, client sends forged/stale autostore anyway | Candidate visibility-vs-award seam from #129; requires synthetic packet/native parity proof | Two-human turn, slot, normal vs quest bucket, before/after bag and loot count |
| Q6: Roll admitted as eligible, then player abandons quest or eligibility changes while 60s roll pending | `CanRollOnItem` already checked at roll creation; final Need/Greed award code lacks a second predicate | Controlled negative source/model + owner-approved staged reproduction; decide against normal stock semantics before any change |
| Q7: Master Loot direct assignment | Recipient `AllowedForPlayer` is checked at give-time | Other bypass path, modified flags or mismatched loaded core required for a surprising award |
| Q8: GO/chest, container, pickpocket, skinning, corpse and direct Playerbot action | Different GUID/source/award call paths | Identify actual source and trigger; module corpse-only hook cannot certify coverage |
| Q9: Released round-robin owner, disconnect, group change, different map or two active instances | Native turn release and same-map safety must not be broken | Exact sequence of events, no process-global owner cache |
| Q10: Same current valid item and stable quest eligibility | Do not block a valid loot-turn human | A proposed patch must pass this explicit stock-parity negative |
| Q11: OFF flag and unrelated sources | Must exactly match pinned native behavior | Test OFF first, then only an evidence-driven scoped ON |
| Q12: Failed click/display with no awarded item | Not a successful incorrect loot grant | Distinguish packet rejected, window shown, bag receipt, loot count changed |

## Next steps and firm stop gates

1. **Owner's one anonymized sample** (when available, no personal data): quest ID, item ID, creature/GO entry, whether the friend actually received it, each human's native quest eligibility, group loot method and round-robin/roll/master context. Prefer loaded item flags and effective `QuestRequired` row if already known; do **not** request another full world dump or SQL executed on live without approval.
2. Continue **source-only** trace of all alternate award sources and module hook registrations, including Playerbots and customized scripts; match to one of Q1–Q12. No claim of exhaustive path coverage from this file.
3. If and ONLY IF a reproducible *invalid* award is proven, propose a smallest **module-owned / default-OFF / reversible** code change and adversarial native C++ tests. Preserve `AllowedForPlayer` stock semantics, valid normal group sharing, rolls/master rules, inventory and counts, map-thread safety and no other player denial. Review exact-head CI and pinned full Worldserver link.
4. **Gameplay S5/S6 requires explicit separate owner consent**, restorable backups, tests on an isolated clone and rollback; never conflate source evidence with a working A04. First playable still requires GFPP exactly **120 seconds**, functional A02 human Hunter ON/OFF, this actual A04, F12 physical Scarlet portals and F13 Atiesh outside Karazhan **in the same verified build**.

**Related historical proofs:** [#122](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/122) research, [#129](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/129) narrow hidden-slot prototype, [#132](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/132) map-scoped safety only, [master #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28), [team #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48), [Claude queue #143](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/143). Keep these drafts separate; Grok remains owner-reported on break.
