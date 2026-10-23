# Quest loot owner cross-pickup — evidence and fail-open coverage

**Issue #109** · **23 October 2026** · **IN-GAME FAIL** · **root cause unknown**
**Status: NOT a gameplay fix.** This document and its Python checks are a
read-only diagnostic map. No code, loot algorithm, configuration or live realm
has been modified. The owner's report is authoritative *evidence of failure*,
not a proven predicate or item-template diagnosis.

## Report

Owner reports `NaxxramasCore.QuestLootProtection.Enabled` is ON, yet other
group members can take quest drops attributed to the owner, and the owner can
take theirs. No named quest/item, NPC, loot setting, character composition,
worldserver binary SHA, or runtime trace has been supplied. Never invent one.

The distribution file says `Enabled=0` and `Debug=0` by default. This is
NOT proof that the owner's active settings were off.
**ACTIVE WORLDserver CONFIG: UNKNOWN**. Note that `Debug=1` on existing code
only logs denials; it cannot show which of its many early allow exits fired.

## Exact source scope (pinned public source, not live realm)

Production module source at `main@80e9de1` and the heads of P4 draft #89
(`c2e13d6`) and P0 draft #105 (`b5311a7`) is the **same Git blob**
`48729dc9fdd674eea0f4bb7bd1a47762558daf6f`. This function is a
`ServerScript::CanPacketReceive` gate for ordinary
`CMSG_AUTOSTORE_LOOT_ITEM` packets. It explicitly returns `true` and
hands control to native core for all exclusions listed below.

At pinned AzerothCore `Grimfeather/azerothcore-wotlk@8daffdabe`:
`Loot::AddItem` selects `loot.quest_items` from loot-template
`QuestRequired` (`needs_quest`); other quest-relevant items can be
`loot.items`. `Loot::FillLoot` initially sets `roundRobinPlayer` for
nonpersonal grouped loot. `LootHandler::DoLootRelease` clears it when that
owner releases; `Player::StoreLootItem` can subsequently award eligible
quest slots without another active round-robin ownership check.
These are source-grounded **possible escape routes**, not necessarily
the explanation for the owner's specific in-game incident.

### Currently known ALLOW paths (each returns to native behaviour)

| Cause classification | Source-based condition | Consequence for this feature |
| --- | --- | --- |
| NORMAL LOOT SLOT | `requestedSlot < normalCount` | Item in `loot.items` never reaches quest-slot owner check |
| QuestRequired=0 | `!item.needs_quest` or normal loot representation | Quest collection relevance alone does not confer protected status |
| COUNT GREATER THAN ONE | `item.count != 1` | Stacked/shared physical drops not guarded |
| MULTI_DROP | `item.freeforall`, `ITEM_FLAG_MULTI_DROP` | Intentionally independent per-player copy remains native; do not count that as theft |
| FOLLOW RULES / ROLL | `follow_loot_rules`, blocked or roll-winner | Native group rules remain authoritative |
| NO ROUND-ROBIN OWNER | `!loot.roundRobinPlayer` | No active turn to defend with current predicate |
| RELEASED | owner release clears the native marker | Subsequent collection is deliberately passed through |
| OWNER INELIGIBLE / ABSENT | missing/offline/different instance, unlooted owner slot missing, quest no longer needed | Fail-open to prevent permanently stranded loot |
| UNSUPPORTED LOOT MODE | e.g. FREE_FOR_ALL or MASTER_LOOT | No change to those modes |
| DIRECT STORE / SCRIPTED AWARD | not a `CMSG_AUTOSTORE_LOOT_ITEM` packet | A packet-only hook cannot intercept all possible item awards |

Current guard does not know that an arbitrary normal `loot.items` entry is
"my quest drop" and cannot safely assign ownership merely from somebody
having a quest. **DO NOT blanket-ban** all quest-relevant items without an
explicit, source-backed ownership/entitlement rule; doing so can break
MULTI_DROP, FREE_FOR_ALL, valid releases, rolls and looting after a player
leaves an instance.

## New diagnostic requirements before a functional code change

1. Confirm whether the item was one shared physical loot copy or individually
   granted loot for each eligible member (the latter may legitimately be
   looted by both). Verify group loot mode, quest/name/item/NPC and relevant
   loot template's `QuestRequired`, count and `ITEM_FLAG_MULTI_DROP`.
2. Determine whether owner was in the same instance, still eligible, had an
   unlooted personal quest slot and whether `roundRobinPlayer` was set
   when the pickup happened. Opening and closing the window can release turn.
3. Confirm **actual loaded module binary and active Worldserver config**
   (not the distributed default). Treat a confirmed missing hook or disabled
   runtime key differently from a genuine predicate loophole.
4. Trace the actual human/Altbot action through packet queue or any direct
   item award. Pinned public Playerbots source supports a queued autostore
   path, not a proof that every real owner-installed Playerbots path uses it.
5. **DEBUG ALLOW-REASON DIAGNOSTICS** would log only opted-in, redacted,
   bounded `allow_reason` labels for relevant autostore packets. No such
   capability exists in the current production implementation; do not say
   that `Debug=1` already reports them. Any proposed diagnostic must stay
   OFF by default, be peer-reviewed, compile on the exact pin, and require
   separate approval before live activation.

## Separate future owner-approved negative acceptance cases — all NOT RUN

| ID | Case | Required property |
| --- | --- | --- |
| QLO-01 | One shared single-copy `QuestRequired=1` drop; wrong turn attempts first | Other player cannot consume eligible owner's copy |
| QLO-02 | Owner's own pickup | Native collection succeeds exactly once |
| QLO-03 | Normal `QuestRequired=0` collection item | Distinguish legitimate shared rule from an actual owner entitlement defect |
| QLO-04 | Same quest item marked MULTI_DROP/FFA | Independent per-player copies remain available |
| QLO-05 | Count greater than one | Define physical-stack and entitlement semantics before denying |
| QLO-06 | Original owner releases turn or leaves group/instance | No stranded loot, correct native fallback |
| QLO-07 | Owner is offline/ineligible/has completed quest | Item not permanently locked |
| QLO-08 | GROUP_LOOT vs ROUND_ROBIN vs NEED_BEFORE_GREED; MASTER_LOOT and FREE_FOR_ALL controls | Respect chosen group method and rolls |
| QLO-09 | Human vs Altbot vs headless/direct award paths | Packet bypasses and item changes documented without assumptions |
| QLO-10 | Feature OFF, then ON (separate authorised staging trial) | OFF changes nothing; ON enforces agreed narrowly scoped policy |

**Gate:** Any observed wrong-member consumption under the *agreed intended
scope* is a blocker for A04 S6/release. Do not mark PASS from these models,
prior green source CI, or binary registration alone. No host, SQL/DBC,
config, inventory, Playerbots/IP, protected branch, merge, gameplay action,
restart or deployment is performed by this documentation.
