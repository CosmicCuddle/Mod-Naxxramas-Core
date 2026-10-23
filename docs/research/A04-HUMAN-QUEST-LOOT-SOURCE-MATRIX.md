# A04 / #109 — Human-to-human quest loot: current-source characterization

**Status:** isolated S1/S3-model research only, **not a fix**. See [Issue #109](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/109). No production code, config, SQL, DBC, Playerbots, core, inventory, server actions or default-off behaviour was modified.

## Owner report: TWO distinct real-human experiences

1. Earlier: a corpse falsely sparkles, another group member tries to loot its protected quest item, and the attempt is **denied**.
2. Latest: a **real human friend repeatedly accidentally picks up the owner's quest loot** because the corpse/item appears available when it should not. **Not a bot-only problem.** This is an owner-reported human pickup, but *whether one unique protected copy was actually transferred* and the exact conditions are not independently established.

Keep both. Do **not** assert that human enforcement is universally effective based on scenario 1. Do **not** assume all intended MULTI_DROP or free-for-all copies are theft.

## Three independent paths at the pinned public source

Source set: module `main` `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; QuestLootProtection.cpp blob `48729dc9fdd674eea0f4bb7bd1a47762558daf6f`; Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`.

**1. Human corpse sparkle:** `Unit::PatchValuesUpdate` computes per-viewer `UNIT_DYNFLAG_LOOTABLE` from `Player::isAllowedToLoot`. In group/RR modes, `Loot::hasItemFor` can be true merely because the viewer has an unlooted personal quest-item *view*. This is broader than the module's protected turn policy.

**2. Human pre-handler guard:** `ServerScript::CanPacketReceive` only considers `CMSG_AUTOSTORE_LOOT_ITEM`. Its `PermitPickup` denies a subset of *one-copy* `quest_items` after all checks agree: group method, living corpse/loot-type, active other RR turn, item index/view/flags, owner present and eligible in same map/instance. An absent RR owner, a normal `loot.items` slot (including quest-related `QuestRequired=0`), item count >1, MULTI_DROP, and disabled config are explicit **permit/fallback** paths. A permit is **not itself proof** that a game client succeeded in storing an item.

**3. Native storage:** `WorldSession::HandleAutostoreLootItemOpcode` calls `Player::StoreLootItem`. The pinned `StoreLootItem` resolves `LootItemInSlot`, checks `AllowedForPlayer`, item-block/roll conditions and inventory, but does not universally check `roundRobinPlayer` before accepting a quest-view slot. Thus some guard fallbacks plausibly reach native item storage, **subject to all other real native checks**. Playerbots use a separate queued packet processing route and are NOT simulated by this human-case suite.

## 4. Loot-window item visibility is a SECOND UI surface

**New pinned-source verification:** `LootMgr.cpp::operator<<(ByteBuffer&, LootView const&)` (~970–1160) separately serializes the loot-window **item row** and its `LootSlotType`, not the corpse's `UNIT_DYNFLAG_LOOTABLE`. The normal `loot.items` group/RR loop checks `roundRobinPlayer` before advertising an under-threshold item. **In contrast, the personal `loot.quest_items` loop, for a viewer with `HasQuestForItem(itemid)` true and an item that is neither `follow_loot_rules` nor `freeforall`, sends `partySlotType`: `LOOT_SLOT_TYPE_ALLOW_LOOT` for group/restricted/round-robin permission, with no active `roundRobinPlayer` test in that quest loop.** Under Master Loot the slot type differs. `follow_loot_rules`, roll/blocked and own MULTI_DROP copies each take another path.

That creates a more precise *source-backed* explanation for **'my friend's loot window says it is available'**, beyond corpse glitter: a quest row may be sent as `ALLOW_LOOT` even when our `CanPacketReceive` later blocks that clicked slot. If round-robin has already been cleared, the narrow guard permits and native storage may proceed, subject to its own checks. This is a candidate mechanism—not proof that the owner's exact item was a one-copy quest slot.

**Design consequence:** a future corpse-sparkle-only `UnitScript::OnPatchValuesUpdate` correction is **insufficient** if the friend can still open a corpse for legitimate gold/other loot and find an unauthorized quest row marked available. The client loot-window row/slot-type presentation and server authoritative pickup denial both require explicit safe, peer-reviewed coverage. Do not globally remove quest views or rewrite `SMSG_LOOT_RESPONSE` without proving slot-index stability and preservation of valid loot for that viewer.

## 5. Socket-bound send hook cannot safely rewrite one item row (pinned source)

Read-only verified against Grimfeather AzerothCore `8daffdabe`:

- `src/server/game/Server/WorldSession.cpp::SendPacket` (~307–360) first calls `OnPacketSent(session, *packet)`; if a socket exists it then calls `CanPacketSend(session, *packet)` and either returns (false) or sends the **entire unchanged packet**. With no socket, bot sessions return before the send veto.
- `src/server/game/Scripting/ScriptDefines/ServerScript.h` provides `bool CanPacketSend(WorldSession*, WorldPacket const&)` and `void OnPacketSent(WorldSession*, WorldPacket const&)`. The former can **allow or deny a whole outgoing response**, and both receive a **const packet**; neither is an endorsed item-aware mutable serializer API. Casting away const or re-sending substitute packets is not a safe workaround.
- The `UnitScript::OnPatchValuesUpdate` hook affects unit *field flags* (corpse sparkle), not the later `LootView` quest-item list or its `ALLOW_LOOT` slot type. `PlayerScript::OnPlayerBeforeFillQuestLootItem(Player*, LootItem&)` involves loot generation, not a demonstrated safe per-viewer send-time row-filter API, and changing the shared item could affect valid other viewers.

**Negative design case:** if the viewer is correctly eligible for gold, an ordinary item, a roll or an independent FFA copy, **vetoing the entire `SMSG_LOOT_RESPONSE` to hide one wrongly advertised quest item would also hide that rightful reward**. The two added synthetic counterexample tests enforce this limitation in the research model; they do not exercise a real send hook.

**Working architecture decision:** prefer the conservative per-viewer sparkle mask for the corpse only after proving entitlement; do not claim it fixes the loot window. The item-aware window and final pickup must be addressed separately through verified native hooks or a separately **owner-authorized** minimal upstream extension if no safe module-only alternative exists. No upstream work approved.

## Current-source synthetic matrix, **not owner gameplay**

| Case | Native per-viewer sparkle model | Module packet denies? | Can proceed toward native storage? |
| --- | --- | --- | --- |
| H01: eligible non-turn human has quest view, active protected owner | Yes, possibly false-positive | Yes, narrow guard | No, for modeled intercepted opcode |
| H02: same, owner releases RR turn | Yes | No | Candidate if native eligible |
| H03: normal item slot that is quest-related (QuestRequired=0) | Yes | No | Candidate if native eligible |
| H04: guard off/not loaded | Yes | No | Candidate if native eligible |
| H05: MULTI_DROP / personal FFA copies | Yes legitimately | No intentionally | Yes **for each own valid copy**, not theft |
| H06: gold/other legitimate normal/roll loot | Should remain Yes | Guard may deny *specific quest slot*, not other rights | Core must preserve legitimate rights |
| H07: non-turn human with no quest view or other right | No | No | No quest slot |
| H08: missing/off-instance/or no-longer-needing owner | May still be visible | Fails open | Revalidate core entitlement, avoid permanent lock |

**Boundaries:** `tests/test_quest_loot_human_source_characterization.py` now models the **loot-window quest-row slot type separately from corpse sparkle and pickup**. The tests model these **possible** paths with simplifying assumptions (valid corpse, packet, slot, map, group and native item). A green model run does not prove server/client behaviour or satisfy S4/S5/S6. Test labels describe **existing source**, not desired final semantics.

## Revised implementation acceptance before code

- Human A/B both actor orders, real client manual clicks and auto-loot: wrong human sees neither misleading sparkle nor a loot-window row falsely labelled available for a *reserved* item, and cannot acquire an unauthorized single copy through allowed native paths.
- Preserve both `sparkle -> denial` and `sparkle -> apparent successful pickup` as separate reproduction cases, including already-open loot windows and release/refresh.
- Do not remove sparkle when the viewer has own valid loot, money, an independently allocated MULTI_DROP copy, legitimate roll/Master Loot, or skinning/profession access.
- Current `roundRobinPlayer` is a rotating corpse turn, **not an unambiguous player quest owner**. Do not silently redefine quest-drop ownership or give protected copies to someone else. Reconcile entitlement rules from each actual scenario before broad denial.
- For any future module-only human per-viewer `OnPatchValuesUpdate` filter: only clear the outgoing viewer flag after checking a safe shared helper; never touch the global `Creature` state. Prove update cache/refresh and exact 4-byte pointer bounds.
- A visual-only patch **cannot** close possible native human pickup fallbacks; both visibility and award-authorisation need independently supported acceptance.
- Headless Playerbots direct dispatch bypass needs its own separate test and potentially owner-approved upstream change.
- Require independent CS02/CS03 review, exact pinned C++/Worldserver link, zero unsafe artifacts, installed-compatible backups and **owner-approved** eventual H01–H08 gameplay before acceptance.

**Safety:** draft only; no merge/install, prod SQL/DBC, configured runtime toggle, inventory or live host mutation.
