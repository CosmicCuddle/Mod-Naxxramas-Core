"""A04 / #109 S2 award-path proof.

Synthetic review model of four stages for one human click:

1. corpse sparkle (per-viewer UNIT_DYNFLAG_LOOTABLE)
2. loot-window row and LootSlotType
3. QuestLootProtection CanPacketReceive
4. Player::StoreLootItem award

This is not a loot-entitlement rule. It does not mutate a shared LootItem,
suppress SMSG_LOOT_RESPONSE, or choose personal copies or a new owner.
Gameplay is not executed. Core lines are the Grimfeather pin recorded in
docs/research/A04-QL-109-CS02-S2-AWARD-PROOF.md.
"""

from __future__ import annotations

import re
import unittest
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "src" / "Systems" / "QuestLootProtection.cpp"
DOC_PATH = ROOT / "docs" / "research" / "A04-QL-109-CS02-S2-AWARD-PROOF.md"
POLICY_PATH = ROOT / "docs" / "research" / "A04-QL-109-OWNER-POLICY-ABC.md"
TABLE_PATH = ROOT / "docs" / "research" / "A04-QL-109-DECISION-TABLE.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "naxx-a04-ql109-cs02-s2-award.yml"
CONF_DIST = ROOT / "conf" / "mod_naxxramas_core.conf.dist"
CONCLUSION = (
    "No hook inside `StoreLootItem`. For human socket pickups the existing "
    "`CanPacketReceive` guard can reject a single slot, so closing "
    "H09/H10/released-turn is an owner policy choice, not a missing hook. "
    "Rolls, master loot and bot `HandleBotPackets` remain outside it."
)
POLICY_NOTE = (
    "If the owner wants the friend's human click stopped without creating "
    "extra items, A or C can use the existing single-slot click check. "
    "The click check cannot mint a copy. B would use the generation-time "
    "hook instead. This note does not choose or approve B, and it is not "
    "Michael's decision."
)

CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MODULE_BLOB = "48729dc9fdd674eea0f4bb7bd1a47762558daf6f"
AUTOSTORE = "CMSG_AUTOSTORE_LOOT_ITEM"
GUARDED_METHODS = ("GROUP_LOOT", "ROUND_ROBIN", "NEED_BEFORE_GREED")

# First permit/deny site in src/Systems/QuestLootProtection.cpp on main.
GUARD_SITE = {
    "permit_disabled": "QuestLootProtection.cpp:211",
    "permit_method": "QuestLootProtection.cpp:59",
    "permit_no_turn": "QuestLootProtection.cpp:74",
    "permit_is_holder": "QuestLootProtection.cpp:75",
    "permit_normal_slot": "QuestLootProtection.cpp:82",
    "permit_no_quest_view": "QuestLootProtection.cpp:86",
    "permit_already_looted": "QuestLootProtection.cpp:94",
    "permit_freeforall": "QuestLootProtection.cpp:102",
    "permit_follow_loot_rules": "QuestLootProtection.cpp:102",
    "permit_blocked": "QuestLootProtection.cpp:103",
    "permit_count": "QuestLootProtection.cpp:101",
    "permit_holder_absent": "QuestLootProtection.cpp:142",
    "permit_holder_no_view": "QuestLootProtection.cpp:173",
    "permit_holder_ineligible": "QuestLootProtection.cpp:177",
    "deny": "QuestLootProtection.cpp:194",
    "not_on_opcode": "WorldSession.cpp:461",
}


@dataclass(frozen=True)
class LootLine:
    bucket: str
    quest_required: bool
    count: int = 1
    freeforall: bool = False
    follow_loot_rules: bool = False
    conditional: bool = False
    underthreshold: bool = True
    blocked: bool = False
    currency: bool = False

    def __post_init__(self) -> None:
        if self.bucket not in ("quest", "items"):
            raise ValueError(self.bucket)
        if self.bucket == "quest" and not self.quest_required:
            raise ValueError("quest_items are QuestRequired lines")
        if self.bucket == "items" and self.quest_required:
            raise ValueError("QuestRequired lines are not loot.items")
        if self.currency and not self.freeforall:
            raise ValueError("pinned currency autostore is the freeforall loop")


@dataclass(frozen=True)
class Scene:
    """One human, one corpse line, one pickup attempt.

    holder is the live roundRobinPlayer. None means the turn was cleared.
    clicker is the human sending the pickup. owner_name is documentary.
    """

    case_id: str
    method: str
    holder: str | None
    clicker: str
    clicker_has_quest: bool
    holder_needs_quest: bool
    line: LootLine
    meets_condition: bool = True
    gold: int = 0
    also_own_ffa: bool = False
    guard_enabled: bool = True
    path: str = "manual"
    clicker_is_master: bool = False
    inventory_full: bool = False
    already_looted: bool = False
    same_map: bool = True
    holder_has_view: bool = True


@dataclass(frozen=True)
class Trace:
    case_id: str
    sparkle: bool
    slot: str | None
    guard: str
    guard_site: str
    award: str
    opcode: str | None
    shared_consumed: bool
    personal_copy: bool

    def stages(self) -> tuple:
        return (self.sparkle, self.slot, self.guard, self.award)


def permission(scene: Scene) -> str:
    """Player::SendLoot group permission. Player.cpp:8323-8340."""
    if scene.method == "MASTER_LOOT":
        return "MASTER" if scene.clicker_is_master else "RESTRICTED"
    if scene.method == "FREE_FOR_ALL":
        return "ALL"
    if scene.method == "ROUND_ROBIN":
        return "ROUND_ROBIN"
    if scene.method in ("GROUP_LOOT", "NEED_BEFORE_GREED"):
        return "GROUP"
    raise AssertionError(scene.method)


def quest_view(scene: Scene) -> bool:
    """FillQuestLoot keeps a row when AllowedForPlayer passes, and also for the master looter."""
    if scene.line.bucket != "quest":
        return False
    if scene.already_looted and not scene.line.freeforall:
        return False
    if scene.clicker_has_quest:
        return True
    return scene.method == "MASTER_LOOT" and scene.clicker_is_master


def has_item_for(scene: Scene) -> bool:
    """Loot::hasItemFor. LootMgr.cpp:907-948. Gold is not in this predicate."""
    if scene.also_own_ffa:
        return True
    if scene.already_looted and not scene.line.freeforall:
        return False
    if scene.line.bucket == "quest" and quest_view(scene):
        return True
    if scene.line.bucket == "items" and scene.line.freeforall:
        if scene.line.conditional and not scene.meets_condition:
            return False
        return True
    if (
        scene.line.bucket == "items"
        and scene.line.conditional
        and not scene.line.freeforall
        and scene.meets_condition
    ):
        return True
    return False


def has_item_for_all(scene: Scene) -> bool:
    """Loot::hasItemForAll. LootMgr.cpp:892-903."""
    if scene.gold:
        return True
    if scene.already_looted:
        return False
    return (
        scene.line.bucket == "items"
        and not scene.line.freeforall
        and not scene.line.conditional
    )


def has_over_threshold(scene: Scene) -> bool:
    """Loot::hasOverThresholdItem scans loot.items only. LootMgr.cpp:952-960."""
    return (
        scene.line.bucket == "items"
        and not scene.line.freeforall
        and not scene.line.underthreshold
        and not scene.already_looted
    )


def sparkle(scene: Scene) -> bool:
    """Player::isAllowedToLoot. PlayerStorage.cpp:5746-5796."""
    if not has_item_for_all(scene) and not has_item_for(scene):
        return False
    if scene.method in ("MASTER_LOOT", "FREE_FOR_ALL"):
        return True
    if scene.holder is None or scene.holder == scene.clicker:
        return True
    if scene.method in ("GROUP_LOOT", "NEED_BEFORE_GREED") and has_over_threshold(scene):
        return True
    if scene.method == "ROUND_ROBIN":
        return has_item_for(scene)
    if scene.method in ("GROUP_LOOT", "NEED_BEFORE_GREED"):
        return has_item_for(scene)
    return False


def window_slot(scene: Scene) -> str | None:
    """LootView slot type for this line, or None when the row is omitted.

    Quest rows: LootMgr.cpp:1099-1162. No roundRobinPlayer test in that loop.
    Normal rows: 994-1088. Conditional rows: 1184-1223. FFA rows: 1165-1181.
    """
    if scene.already_looted and not scene.line.freeforall:
        return None
    perm = permission(scene)
    line = scene.line
    allow = "ALLOW_LOOT"

    if line.bucket == "quest" and quest_view(scene):
        if not scene.clicker_has_quest:
            return "MASTER" if perm == "MASTER" else "LOCKED"
        if line.follow_loot_rules:
            if perm == "MASTER":
                return "MASTER"
            if perm == "RESTRICTED":
                return "LOCKED" if line.blocked else allow
            if perm in ("GROUP", "ROUND_ROBIN"):
                return "ROLL_ONGOING" if line.blocked else allow
            return "OWNER" if perm == "OWNER" else allow
        if not line.freeforall:
            if perm == "MASTER":
                return "MASTER"
            return "OWNER" if perm == "OWNER" else allow
        return "OWNER" if perm == "OWNER" else allow

    if line.bucket == "items" and line.freeforall:
        if line.conditional and not scene.meets_condition:
            return None
        return allow

    if line.bucket == "items" and line.conditional and not line.freeforall:
        if not scene.meets_condition:
            return None
        if line.follow_loot_rules:
            if perm == "MASTER":
                return "MASTER"
            if perm == "RESTRICTED":
                return "LOCKED" if line.blocked else allow
            if perm in ("GROUP", "ROUND_ROBIN"):
                return "ROLL_ONGOING" if line.blocked else allow
            return allow
        return "MASTER" if perm == "MASTER" else allow

    if line.bucket == "items" and not line.conditional:
        if perm in ("GROUP", "MASTER", "RESTRICTED"):
            if line.blocked:
                if perm == "GROUP":
                    return "ROLL_ONGOING"
                if perm == "MASTER":
                    return "MASTER"
                return "LOCKED"
            if scene.holder is None or scene.holder == scene.clicker or not line.underthreshold:
                return allow
            return None
        if perm == "ROUND_ROBIN":
            if scene.holder and scene.holder != scene.clicker:
                return None
            return allow
        if perm == "ALL":
            return allow
        if perm == "OWNER":
            return "OWNER"
    return None


def guard(scene: Scene) -> str:
    """First return from PermitPickup. Later clauses do not run."""
    if scene.path not in ("manual", "autoloot"):
        return "not_on_opcode"
    if not scene.guard_enabled:
        return "permit_disabled"
    if scene.method not in GUARDED_METHODS:
        return "permit_method"
    if scene.holder is None:
        return "permit_no_turn"
    if scene.holder == scene.clicker:
        return "permit_is_holder"
    if scene.line.bucket != "quest":
        return "permit_normal_slot"
    if not scene.clicker_has_quest:
        return "permit_no_quest_view"
    if scene.already_looted:
        return "permit_already_looted"
    line = scene.line
    if line.freeforall:
        return "permit_freeforall"
    if line.follow_loot_rules:
        return "permit_follow_loot_rules"
    if line.blocked:
        return "permit_blocked"
    if line.count != 1:
        return "permit_count"
    if not scene.same_map:
        return "permit_holder_absent"
    if not scene.holder_has_view:
        return "permit_holder_no_view"
    if not scene.holder_needs_quest:
        return "permit_holder_ineligible"
    return "deny"


def store_loot_item(scene: Scene) -> str:
    """Player::StoreLootItem. Player.cpp:13861-13961.

    Quest views skip the master-loot threshold check (13881-13886) and the
    is_blocked check (13894-13898). There is no roundRobinPlayer comparison.
    """
    line = scene.line
    if scene.already_looted and not line.freeforall:
        return "already_looted"
    if line.bucket == "quest" and not quest_view(scene):
        return "no_slot"
    if line.bucket == "quest" and not scene.clicker_has_quest:
        return "rejected_allowed_for_player"
    if line.bucket == "items" and line.conditional and not scene.meets_condition:
        return "rejected_allowed_for_player"
    if (
        scene.method == "MASTER_LOOT"
        and not scene.clicker_is_master
        and scene.holder
        and not line.underthreshold
        and line.bucket != "quest"
        and not line.freeforall
        and not line.conditional
    ):
        return "rejected_master_threshold"
    if line.bucket != "quest" and line.blocked:
        return "rejected_blocked"
    if scene.inventory_full:
        return "rejected_inventory"
    if line.freeforall:
        return "stored_personal_copy"
    return "stored_shared_consumed"


def award(scene: Scene, guard_result: str) -> str:
    if scene.path == "roll":
        if scene.line.follow_loot_rules:
            return "bypass_roll_store_new_item"
        return "no_roll"
    if scene.path == "master_give":
        if scene.line.bucket == "quest" and not scene.clicker_has_quest:
            return "rejected_allowed_for_player"
        return "bypass_master_give_store_new_item"
    if scene.path == "currency_fill":
        if scene.line.freeforall and scene.line.currency:
            return "direct_store_loot_item"
        return "not_currency_fill"
    if guard_result == "deny":
        return "not_reached"
    return store_loot_item(scene)


def trace(scene: Scene) -> Trace:
    guard_result = guard(scene)
    award_result = award(scene, guard_result)
    opcode = AUTOSTORE if scene.path in ("manual", "autoloot") else None
    shared = award_result in (
        "stored_shared_consumed",
        "bypass_roll_store_new_item",
        "bypass_master_give_store_new_item",
    )
    personal = award_result in ("stored_personal_copy", "direct_store_loot_item")
    return Trace(
        case_id=scene.case_id,
        sparkle=sparkle(scene),
        slot=window_slot(scene),
        guard=guard_result,
        guard_site=GUARD_SITE[guard_result],
        award=award_result,
        opcode=opcode,
        shared_consumed=shared,
        personal_copy=personal,
    )


def one_copy_quest() -> LootLine:
    return LootLine("quest", True)


def quest_required_zero() -> LootLine:
    return LootLine("items", False)


@dataclass(frozen=True)
class Hook:
    name: str
    signature: str
    where: str
    boolean_deny: bool
    receives_resolved_item: bool
    called_from_store_loot_item_before_commit: bool
    also_gates_visibility: bool
    mutates_shared_lootitem: bool
    blanket_smsg: bool
    socket_autostore_only: bool

    @property
    def inside_store_before_commit(self) -> bool:
        """A deny of one resolved item inside StoreLootItem, leaving other loot visible."""
        return (
            self.boolean_deny
            and self.receives_resolved_item
            and self.called_from_store_loot_item_before_commit
            and not self.also_gates_visibility
            and not self.mutates_shared_lootitem
            and not self.blanket_smsg
        )

    @property
    def human_socket_single_slot(self) -> bool:
        """Refuse one human autostore slot without hiding the loot window."""
        return (
            self.boolean_deny
            and self.socket_autostore_only
            and not self.also_gates_visibility
            and not self.blanket_smsg
            and not self.mutates_shared_lootitem
            and not self.called_from_store_loot_item_before_commit
        )


HOOKS = (
    Hook(
        "ServerScript::CanPacketReceive",
        "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)",
        "ServerScript.h:75; WorldSession.cpp:461; module QuestLootProtection.cpp:205",
        True,
        False,
        False,
        False,
        False,
        False,
        True,
    ),
    Hook(
        "ServerScript::CanPacketSend",
        "bool CanPacketSend(WorldSession* session, WorldPacket const& packet)",
        "ServerScript.h:65; WorldSession.cpp:351",
        True,
        False,
        False,
        True,
        False,
        True,
        False,
    ),
    Hook(
        "GlobalScript::OnAllowedForPlayerLootCheck",
        "bool OnAllowedForPlayerLootCheck(Player const* player, ObjectGuid source)",
        "GlobalScript.h:98; LootItem::AllowedForPlayer LootMgr.cpp:465; StoreLootItem Player.cpp:13888",
        True,
        False,
        True,
        True,
        False,
        False,
        False,
    ),
    Hook(
        "GlobalScript::OnAllowedToLootContainerCheck",
        "bool OnAllowedToLootContainerCheck(Player const* player, ObjectGuid source)",
        "GlobalScript.h:101; Player::SendLoot Player.cpp:8373",
        True,
        False,
        False,
        True,
        False,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerBeforeSendLoot",
        "void OnPlayerBeforeSendLoot(Player* player, ObjectGuid lootGuid, Loot* loot)",
        "PlayerScript.h:311; Player.cpp:8383",
        False,
        False,
        False,
        False,
        True,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerBeforeFillQuestLootItem",
        "void OnPlayerBeforeFillQuestLootItem(Player* player, LootItem& item)",
        "PlayerScript.h:461; Loot::FillQuestLoot LootMgr.cpp:669",
        False,
        True,
        False,
        False,
        True,
        False,
        False,
    ),
    Hook(
        "MiscScript::OnAfterLootTemplateProcess",
        "void OnAfterLootTemplateProcess(Loot* loot, LootTemplate const* tab, LootStore const& store, Player* lootOwner, bool personal, bool noEmptyError, uint16 lootMode)",
        "MiscScript.h:84; Loot::FillLoot LootMgr.cpp:563",
        False,
        False,
        False,
        False,
        True,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerAfterCreatureLoot",
        "void OnPlayerAfterCreatureLoot(Player* player)",
        "PlayerScript.h:817; LootHandler.cpp:104",
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerCanSendErrorAlreadyLooted",
        "bool OnPlayerCanSendErrorAlreadyLooted(Player* player)",
        "PlayerScript.h:809; Player.cpp:13872",
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerLootItem",
        "void OnPlayerLootItem(Player* player, Item* item, uint32 count, ObjectGuid lootguid)",
        "PlayerScript.h:458; Player.cpp:13954",
        False,
        True,
        False,
        False,
        False,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerStoreNewItem",
        "void OnPlayerStoreNewItem(Player* player, Item* item, uint32 count)",
        "PlayerScript.h:464; PlayerStorage.cpp:2685",
        False,
        True,
        False,
        False,
        False,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerBeforeStoreOrEquipNewItem",
        "void OnPlayerBeforeStoreOrEquipNewItem(Player* player, uint32 vendorslot, uint32& item, uint8 count, uint8 bag, uint8 slot, ItemTemplate const* pProto, Creature* pVendor, VendorItem const* crItem, bool bStore)",
        "PlayerScript.h:494; Player.cpp:10863",
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ),
    Hook(
        "PlayerScript::OnPlayerGroupRollRewardItem",
        "void OnPlayerGroupRollRewardItem(Player* player, Item* item, uint32 count, RollVote voteType, Roll* roll)",
        "PlayerScript.h:476; Group.cpp:1664",
        False,
        True,
        False,
        False,
        False,
        False,
        False,
    ),
    Hook(
        "LootScript::OnLootMoney",
        "void OnLootMoney(Player* player, uint32 gold)",
        "LootScript.h:44",
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ),
)


def hook_named(name: str) -> Hook:
    for hook in HOOKS:
        if hook.name == name:
            return hook
    raise KeyError(name)


FRIEND = "friend"
OWNER = "owner"


def decision_scene(
    case_id: str,
    method: str = "ROUND_ROBIN",
    items_multidrop: bool = False,
) -> Scene:
    """The five CS01 cases, modeled against today's PermitPickup guard.

    (i) friend holds the turn and needs the one-copy quest line.
    (ii) owner holds the turn and no longer needs it; the friend still does.
    (iii) the turn is cleared.
    (iv) the only line is an unconditional under-threshold loot.items row
    with QuestRequired = 0. The friend is not the holder.
    (v) both humans qualify for ITEM_FLAG_MULTI_DROP. The friend is not
    the holder. items_multidrop selects the loot.items bucket.
    """
    if case_id == "i":
        return Scene(case_id, method, FRIEND, FRIEND, True, True, one_copy_quest())
    if case_id == "ii":
        return Scene(case_id, method, OWNER, FRIEND, True, False, one_copy_quest())
    if case_id == "iii":
        return Scene(case_id, method, None, FRIEND, True, True, one_copy_quest())
    if case_id == "iv":
        return Scene(case_id, method, OWNER, FRIEND, True, True, quest_required_zero())
    if case_id == "v":
        line = (
            LootLine("items", False, freeforall=True)
            if items_multidrop
            else LootLine("quest", True, freeforall=True)
        )
        return Scene(case_id, method, OWNER, FRIEND, True, True, line)
    raise AssertionError(case_id)


def current_guard_token(scene: Scene) -> tuple[str, str]:
    """Effect of today's guard plus the first permit/deny site.

    socket deny is a false CanPacketReceive. A hide is a missing row and
    no sparkle. personal-copy is a freeforall store with the row still shown.
    permit-and-show stores the one shared copy while the row stays visible.
    """
    row = trace(scene)
    if row.guard == "deny":
        effect = "socket-deny"
    elif row.personal_copy and row.sparkle and row.slot == "ALLOW_LOOT":
        effect = "personal-copy"
    elif row.slot is None and not row.sparkle and row.guard != "deny":
        effect = "hide-not-socket-deny"
    elif (
        row.sparkle
        and row.slot == "ALLOW_LOOT"
        and row.shared_consumed
        and row.guard != "deny"
    ):
        effect = "permit-and-show"
    else:
        raise AssertionError((scene.case_id, row))
    return effect, row.guard_site


CURRENT_GUARD_TOKENS = {
    "i": ("permit-and-show", "QuestLootProtection.cpp:75"),
    "ii": ("permit-and-show", "QuestLootProtection.cpp:177"),
    "iii": ("permit-and-show", "QuestLootProtection.cpp:74"),
    "iv": ("hide-not-socket-deny", "QuestLootProtection.cpp:82"),
    "v-quest": ("personal-copy", "QuestLootProtection.cpp:102"),
    "v-items": ("personal-copy", "QuestLootProtection.cpp:82"),
}


def scene_h09_friend(**kwargs: object) -> Scene:
    base = dict(
        case_id="H09",
        method="GROUP_LOOT",
        holder=FRIEND,
        clicker=FRIEND,
        clicker_has_quest=True,
        holder_needs_quest=True,
        line=one_copy_quest(),
    )
    base.update(kwargs)
    return Scene(**base)  # type: ignore[arg-type]


class AwardPathTests(unittest.TestCase):
    def test_h09_friend_turn_four_stages_commit_single_copy(self) -> None:
        row = trace(scene_h09_friend())
        self.assertEqual(row.stages(), (True, "ALLOW_LOOT", "permit_is_holder", "stored_shared_consumed"))
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:75")
        self.assertTrue(row.shared_consumed)
        self.assertFalse(row.personal_copy)
        self.assertEqual(row.opcode, AUTOSTORE)

    def test_h09_owner_click_while_friend_holds_turn_stops_before_store(self) -> None:
        row = trace(
            Scene(
                "H09-owner",
                "GROUP_LOOT",
                FRIEND,
                OWNER,
                True,
                True,
                one_copy_quest(),
            )
        )
        self.assertEqual(row.stages(), (True, "ALLOW_LOOT", "deny", "not_reached"))
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:194")
        self.assertFalse(row.shared_consumed)

    def test_h10_holder_no_longer_needs_item_and_friend_stores_it(self) -> None:
        row = trace(
            Scene(
                "H10",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                False,
                one_copy_quest(),
            )
        )
        self.assertEqual(
            row.stages(),
            (True, "ALLOW_LOOT", "permit_holder_ineligible", "stored_shared_consumed"),
        )
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:177")
        self.assertTrue(row.shared_consumed)

    def test_h10_friend_without_quest_has_no_row_and_no_award(self) -> None:
        row = trace(
            Scene(
                "H10-friend-ineligible",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                False,
                False,
                one_copy_quest(),
            )
        )
        self.assertEqual(row.stages(), (False, None, "permit_no_quest_view", "no_slot"))
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:86")
        self.assertFalse(row.shared_consumed)

    def test_released_turn_lets_friend_store_the_single_copy(self) -> None:
        row = trace(
            Scene(
                "released",
                "ROUND_ROBIN",
                None,
                FRIEND,
                True,
                True,
                one_copy_quest(),
            )
        )
        self.assertEqual(row.stages(), (True, "ALLOW_LOOT", "permit_no_turn", "stored_shared_consumed"))
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:74")
        self.assertTrue(row.shared_consumed)

    def test_quest_required_zero_row_hidden_but_packet_still_awards(self) -> None:
        row = trace(
            Scene(
                "quest-required-0",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                quest_required_zero(),
            )
        )
        self.assertFalse(row.sparkle)
        self.assertIsNone(row.slot)
        self.assertEqual(row.guard, "permit_normal_slot")
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:82")
        self.assertEqual(row.award, "stored_shared_consumed")
        self.assertTrue(row.shared_consumed)

    def test_conditional_quest_relevant_items_row_is_allow_loot_and_consumed(self) -> None:
        row = trace(
            Scene(
                "conditional",
                "NEED_BEFORE_GREED",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, conditional=True),
                meets_condition=True,
            )
        )
        self.assertEqual(
            row.stages(),
            (True, "ALLOW_LOOT", "permit_normal_slot", "stored_shared_consumed"),
        )
        self.assertTrue(row.shared_consumed)

    def test_conditional_miss_does_not_award(self) -> None:
        row = trace(
            Scene(
                "conditional-miss",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, conditional=True),
                meets_condition=False,
            )
        )
        self.assertIsNone(row.slot)
        self.assertEqual(row.guard, "permit_normal_slot")
        self.assertEqual(row.award, "rejected_allowed_for_player")
        self.assertFalse(row.shared_consumed)

    def test_friend_has_quest_and_active_holder_is_denied_before_store(self) -> None:
        row = trace(
            Scene(
                "friend-has-quest",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
            )
        )
        self.assertEqual(row.stages(), (True, "ALLOW_LOOT", "deny", "not_reached"))
        self.assertEqual(store_loot_item(Scene(
            "friend-has-quest",
            "GROUP_LOOT",
            OWNER,
            FRIEND,
            True,
            True,
            one_copy_quest(),
        )), "stored_shared_consumed")

    def test_manual_and_autoloot_share_opcode_and_award(self) -> None:
        common = dict(
            case_id="manual-autoloot",
            method="GROUP_LOOT",
            holder=None,
            clicker=FRIEND,
            clicker_has_quest=True,
            holder_needs_quest=True,
            line=one_copy_quest(),
        )
        manual = trace(Scene(**common, path="manual"))  # type: ignore[arg-type]
        auto = trace(Scene(**common, path="autoloot"))  # type: ignore[arg-type]
        self.assertEqual(manual.opcode, AUTOSTORE)
        self.assertEqual(auto.opcode, AUTOSTORE)
        self.assertEqual(manual.stages(), auto.stages())
        self.assertEqual(manual.award, "stored_shared_consumed")
        denied = trace(
            Scene(
                "manual-autoloot-deny",
                "ROUND_ROBIN",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                path="autoloot",
            )
        )
        self.assertEqual(denied.opcode, AUTOSTORE)
        self.assertEqual(denied.award, "not_reached")

    def test_multidrop_quest_line_keeps_the_other_humans_copy(self) -> None:
        row = trace(
            Scene(
                "multidrop-quest",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                LootLine("quest", True, freeforall=True),
            )
        )
        self.assertEqual(row.guard, "permit_freeforall")
        self.assertEqual(row.slot, "ALLOW_LOOT")
        self.assertEqual(row.award, "stored_personal_copy")
        self.assertTrue(row.personal_copy)
        self.assertFalse(row.shared_consumed)

    def test_multidrop_items_bucket_is_a_different_permit_site(self) -> None:
        row = trace(
            Scene(
                "multidrop-items",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, freeforall=True),
            )
        )
        self.assertEqual(row.guard, "permit_normal_slot")
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:82")
        self.assertEqual(row.award, "stored_personal_copy")
        self.assertFalse(row.shared_consumed)

    def test_ffa_method_one_copy_is_not_a_personal_multidrop(self) -> None:
        row = trace(
            Scene(
                "ffa-method",
                "FREE_FOR_ALL",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
            )
        )
        self.assertTrue(row.sparkle)
        self.assertEqual(row.slot, "ALLOW_LOOT")
        self.assertEqual(row.guard, "permit_method")
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:59")
        self.assertEqual(row.award, "stored_shared_consumed")
        self.assertTrue(row.shared_consumed)
        self.assertFalse(row.personal_copy)

    def test_master_loot_non_master_quest_row_allow_loot_and_store(self) -> None:
        row = trace(
            Scene(
                "master-quest",
                "MASTER_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                clicker_is_master=False,
            )
        )
        self.assertEqual(permission(Scene(
            "master-quest",
            "MASTER_LOOT",
            OWNER,
            FRIEND,
            True,
            True,
            one_copy_quest(),
        )), "RESTRICTED")
        self.assertEqual(row.slot, "ALLOW_LOOT")
        self.assertEqual(row.guard, "permit_method")
        self.assertEqual(row.award, "stored_shared_consumed")

    def test_need_before_greed_quest_row_matches_group_loot(self) -> None:
        group = trace(
            Scene("nbg-g", "GROUP_LOOT", OWNER, FRIEND, True, True, one_copy_quest())
        )
        nbg = trace(
            Scene("nbg-n", "NEED_BEFORE_GREED", OWNER, FRIEND, True, True, one_copy_quest())
        )
        self.assertEqual(group.stages(), nbg.stages())
        self.assertEqual(nbg.guard, "deny")

    def test_round_robin_over_threshold_does_not_sparkle_for_nonholder(self) -> None:
        row = trace(
            Scene(
                "rr-threshold",
                "ROUND_ROBIN",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, underthreshold=False),
            )
        )
        self.assertFalse(row.sparkle)
        self.assertIsNone(row.slot)
        self.assertEqual(row.award, "stored_shared_consumed")

    def test_group_over_threshold_sparkles_and_shows_allow_when_not_blocked(self) -> None:
        row = trace(
            Scene(
                "group-threshold",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, underthreshold=False),
            )
        )
        self.assertTrue(row.sparkle)
        self.assertEqual(row.slot, "ALLOW_LOOT")
        self.assertEqual(row.award, "stored_shared_consumed")

    def test_blocked_normal_item_is_not_stored_but_blocked_quest_item_is(self) -> None:
        normal = trace(
            Scene(
                "blocked-normal",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, underthreshold=False, blocked=True),
            )
        )
        quest = trace(
            Scene(
                "blocked-quest",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                LootLine("quest", True, follow_loot_rules=True, blocked=True),
            )
        )
        self.assertEqual(normal.slot, "ROLL_ONGOING")
        self.assertEqual(normal.guard, "permit_normal_slot")
        self.assertEqual(normal.award, "rejected_blocked")
        self.assertEqual(quest.slot, "ROLL_ONGOING")
        self.assertEqual(quest.guard, "permit_follow_loot_rules")
        self.assertEqual(quest.award, "stored_shared_consumed")
        self.assertTrue(quest.shared_consumed)

    def test_gold_is_not_an_item_award_and_survives_a_quest_deny(self) -> None:
        row = trace(
            Scene(
                "gold",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                gold=50,
                also_own_ffa=True,
            )
        )
        self.assertEqual(row.guard, "deny")
        self.assertEqual(row.award, "not_reached")
        self.assertTrue(has_item_for_all(Scene(
            "gold",
            "GROUP_LOOT",
            OWNER,
            FRIEND,
            True,
            True,
            one_copy_quest(),
            gold=50,
        )))
        self.assertEqual(window_slot(Scene(
            "ffa-row",
            "GROUP_LOOT",
            OWNER,
            FRIEND,
            False,
            True,
            LootLine("items", False, freeforall=True),
        )), "ALLOW_LOOT")

    def test_second_human_finds_the_consumed_copy_already_looted(self) -> None:
        row = trace(
            Scene(
                "second",
                "GROUP_LOOT",
                None,
                OWNER,
                True,
                True,
                one_copy_quest(),
                already_looted=True,
            )
        )
        self.assertFalse(row.sparkle)
        self.assertIsNone(row.slot)
        self.assertEqual(row.award, "already_looted")
        self.assertFalse(row.shared_consumed)

    def test_inventory_full_does_not_consume_the_copy(self) -> None:
        row = trace(
            Scene(
                "bags",
                "GROUP_LOOT",
                FRIEND,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                inventory_full=True,
            )
        )
        self.assertEqual(row.guard, "permit_is_holder")
        self.assertEqual(row.award, "rejected_inventory")
        self.assertFalse(row.shared_consumed)

    def test_currency_fill_calls_store_loot_item_without_the_guard(self) -> None:
        row = trace(
            Scene(
                "currency",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                False,
                True,
                LootLine("items", False, freeforall=True, currency=True),
                path="currency_fill",
            )
        )
        self.assertEqual(row.guard, "not_on_opcode")
        self.assertIsNone(row.opcode)
        self.assertEqual(row.award, "direct_store_loot_item")
        self.assertTrue(row.personal_copy)
        self.assertFalse(row.shared_consumed)

    def test_roll_and_master_give_bypass_store_loot_item(self) -> None:
        roll = trace(
            Scene(
                "roll",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                LootLine("quest", True, follow_loot_rules=True),
                path="roll",
            )
        )
        plain = trace(
            Scene(
                "roll-plain",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                path="roll",
            )
        )
        master = trace(
            Scene(
                "master-give",
                "MASTER_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                path="master_give",
            )
        )
        self.assertEqual(roll.guard, "not_on_opcode")
        self.assertEqual(roll.award, "bypass_roll_store_new_item")
        self.assertTrue(roll.shared_consumed)
        self.assertEqual(plain.award, "no_roll")
        self.assertEqual(master.award, "bypass_master_give_store_new_item")
        self.assertTrue(master.shared_consumed)

    def test_guard_off_reaches_store_for_the_same_quest_slot(self) -> None:
        row = trace(
            Scene(
                "guard-off",
                "GROUP_LOOT",
                OWNER,
                FRIEND,
                True,
                True,
                one_copy_quest(),
                guard_enabled=False,
            )
        )
        self.assertEqual(row.guard, "permit_disabled")
        self.assertEqual(row.award, "stored_shared_consumed")

    def test_no_listed_hook_is_an_exact_pre_storage_reject(self) -> None:
        self.assertGreaterEqual(len(HOOKS), 14)
        inside = [hook.name for hook in HOOKS if hook.inside_store_before_commit]
        self.assertEqual(inside, [])
        socket = [hook.name for hook in HOOKS if hook.human_socket_single_slot]
        self.assertEqual(socket, ["ServerScript::CanPacketReceive"])
        receive = hook_named("ServerScript::CanPacketReceive")
        self.assertTrue(receive.boolean_deny)
        self.assertTrue(receive.socket_autostore_only)
        self.assertFalse(receive.called_from_store_loot_item_before_commit)
        self.assertFalse(receive.inside_store_before_commit)
        self.assertTrue(receive.human_socket_single_slot)
        allowed = hook_named("GlobalScript::OnAllowedForPlayerLootCheck")
        self.assertTrue(allowed.called_from_store_loot_item_before_commit)
        self.assertTrue(allowed.also_gates_visibility)
        self.assertFalse(allowed.receives_resolved_item)
        self.assertFalse(allowed.inside_store_before_commit)
        self.assertFalse(allowed.human_socket_single_slot)
        send = hook_named("ServerScript::CanPacketSend")
        self.assertTrue(send.blanket_smsg)
        self.assertFalse(send.inside_store_before_commit)
        self.assertFalse(send.human_socket_single_slot)
        fill = hook_named("PlayerScript::OnPlayerBeforeFillQuestLootItem")
        self.assertTrue(fill.mutates_shared_lootitem)
        self.assertFalse(fill.boolean_deny)
        after = hook_named("PlayerScript::OnPlayerAfterCreatureLoot")
        self.assertFalse(after.boolean_deny)
        self.assertFalse(after.receives_resolved_item)
        post = hook_named("PlayerScript::OnPlayerLootItem")
        self.assertFalse(post.called_from_store_loot_item_before_commit)
        vendor = hook_named("PlayerScript::OnPlayerBeforeStoreOrEquipNewItem")
        self.assertFalse(vendor.called_from_store_loot_item_before_commit)

    def test_blanket_smsg_veto_and_shared_mutation_are_not_selected(self) -> None:
        send = hook_named("ServerScript::CanPacketSend")
        fill = hook_named("PlayerScript::OnPlayerBeforeFillQuestLootItem")
        self.assertTrue(send.blanket_smsg)
        self.assertTrue(fill.mutates_shared_lootitem)
        self.assertFalse(send.human_socket_single_slot)
        self.assertFalse(fill.human_socket_single_slot)
        self.assertFalse(fill.inside_store_before_commit)
        # A deny of the whole response removes gold and an independent FFA row
        # together with the quest row. The model records that as hiding valid loot.
        hidden = ("gold", "ffa-row", "quest-row")
        self.assertEqual(len(hidden), 3)
        self.assertTrue(send.also_gates_visibility)

    def test_allowed_hook_deny_hides_valid_item_rows(self) -> None:
        allowed = hook_named("GlobalScript::OnAllowedForPlayerLootCheck")
        self.assertTrue(allowed.also_gates_visibility)
        # AllowedForPlayer false drops quest, FFA and conditional rows. Gold stays
        # in hasItemForAll and is not an item row. That is still hiding valid loot.
        self.assertTrue(has_item_for_all(Scene(
            "gold-remains",
            "GROUP_LOOT",
            OWNER,
            FRIEND,
            True,
            True,
            one_copy_quest(),
            gold=1,
        )))
        self.assertFalse(allowed.inside_store_before_commit)

    def test_container_hook_hides_the_whole_window(self) -> None:
        hook = hook_named("GlobalScript::OnAllowedToLootContainerCheck")
        self.assertTrue(hook.boolean_deny)
        self.assertTrue(hook.also_gates_visibility)
        self.assertFalse(hook.called_from_store_loot_item_before_commit)
        self.assertFalse(hook.inside_store_before_commit)
        self.assertFalse(hook.human_socket_single_slot)

    def test_module_source_permit_sites_and_no_store_hook(self) -> None:
        text = GUARD_PATH.read_text(encoding="utf-8")
        self.assertIn("SERVERHOOK_CAN_PACKET_RECEIVE", text)
        self.assertNotIn("SERVERHOOK_CAN_PACKET_SEND", text)
        self.assertNotIn("StoreLootItem(", text)
        self.assertIn("Reject BEFORE Player::StoreLootItem", text)
        self.assertNotIn("OnPlayerBeforeFillQuestLootItem", text)
        self.assertEqual(text.count("return false;"), 1)
        self.assertIn("loot.roundRobinPlayer == player->GetGUID()", text)
        self.assertIn("!loot.roundRobinPlayer", text)
        self.assertIn("requestedSlot < normalCount", text)
        self.assertIn("!owner->HasQuestForItem(item.itemid)", text)
        self.assertIsNone(re.search(r"roundRobinPlayer\s*=(?!=)", text))
        self.assertIsNone(re.search(r"\b(?:item|loot|view)\.[A-Za-z0-9_]+\s*=(?!=)", text))
        self.assertNotIn("SMSG_LOOT_RESPONSE", text)

    def test_research_doc_pins_core_and_states_hook_insufficient(self) -> None:
        doc = DOC_PATH.read_text(encoding="utf-8")
        self.assertIn(CORE_SHA, doc)
        self.assertIn(MODULE_BLOB, doc)
        self.assertIn(CONCLUSION, doc)
        self.assertNotIn("only while `m_Socket` is set (`WorldSession.cpp:461", doc)
        self.assertIn("WorldSession.cpp:414", doc)
        self.assertIn("WorldSession.cpp:461", doc)
        self.assertIn("PlayerbotMgr.cpp:319", doc)
        self.assertIn("e88cc4099e69f35126b28942a412ca702d20453b", doc)
        self.assertIn("HandleBotPackets", doc)
        self.assertIn("Player::StoreLootItem", doc)
        self.assertIn("Player.cpp:13861", doc)
        self.assertIn("H09", doc)
        self.assertIn("H10", doc)
        self.assertIn("CMSG_AUTOSTORE_LOOT_ITEM", doc)
        self.assertIn("SMSG_LOOT_RESPONSE", doc)
        self.assertIn("not a production", doc)
        self.assertIn("Do not merge", doc)
        for hook in HOOKS:
            self.assertIn(hook.signature, doc, hook.name)
        self.assertIn("LootHandler.cpp:459", doc)
        self.assertIn("LootMgr.cpp:1154", doc)
        self.assertIn("Player.cpp:13941", doc)
        self.assertIn("Opcodes.h:294", doc)
        self.assertIn("not merely visual", doc)
        self.assertIn("Enabled() default is false", doc)
        self.assertIn("actually loaded config/binary is UNKNOWN", doc)
        self.assertIn("A04-QL-109-DECISION-TABLE.md", doc)
        self.assertIn("No owner policy is chosen", doc)

    def test_owner_policy_note_is_not_a_choice(self) -> None:
        text = POLICY_PATH.read_text(encoding="utf-8")
        self.assertIn("## A — Keep one copy", text)
        self.assertIn("## B — A real personal copy", text)
        self.assertIn("## C — Name one owner", text)
        self.assertIn("not chosen", text.lower())
        self.assertIn(POLICY_NOTE, text)
        self.assertIn("docs/research/A04-QL-109-DECISION-TABLE.md", text)
        self.assertIn("It does not choose A, B, or C.", text)
        for phrase in (
            "Does the friend still take it?",
            "Vanilla and the economy.",
            "Ordinary quest drops.",
            "Free-for-all and multi-drop",
            "Gold and dice.",
            "Proven in the source.",
            "Unresolved:",
        ):
            self.assertGreaterEqual(text.count(phrase), 3, phrase)
        self.assertIn("does not rewrite the shared item", text)
        self.assertIn("The click/packet check (`CanPacketReceive`) cannot mint a copy.", text)
        self.assertIn("potentially module-feasible at loot generation", text)
        self.assertIn("OnAfterLootTemplateProcess", text)
        self.assertIn("`LootMgr.cpp:563`", text)
        self.assertIn("LootStore const& store", text)
        self.assertIn("not reliably `LOOT_CORPSE`", text)
        self.assertIn("separately authorised selection and scope", text)
        self.assertIn("does not choose or approve B", text)
        self.assertIn("not Michael's decision", text)
        self.assertIn("must not affect those, or an existing `MULTI_DROP`", text)
        self.assertNotIn("without changing the shared drop", text)
        self.assertNotIn("would edit the shared drop", text)
        self.assertNotIn("src/", text)
        words = len(text.split())
        self.assertLess(words, 1200)
        self.assertGreater(words, 500)

    def test_decision_cases_match_current_guard_and_not_a_hide_or_deny(self) -> None:
        scenes = {
            "i": decision_scene("i"),
            "ii": decision_scene("ii"),
            "iii": decision_scene("iii"),
            "iv": decision_scene("iv"),
            "v-quest": decision_scene("v"),
            "v-items": decision_scene("v", items_multidrop=True),
        }
        for key, scene in scenes.items():
            self.assertEqual(current_guard_token(scene), CURRENT_GUARD_TOKENS[key], key)
            auto = trace(replace(scene, path="autoloot"))
            manual = trace(scene)
            self.assertEqual(auto.stages(), manual.stages())
            self.assertEqual(auto.opcode, AUTOSTORE)
            self.assertEqual(manual.opcode, AUTOSTORE)
        for method in ("ROUND_ROBIN", "GROUP_LOOT", "NEED_BEFORE_GREED"):
            for key, case_id, items in (
                ("i", "i", False),
                ("ii", "ii", False),
                ("iii", "iii", False),
                ("iv", "iv", False),
                ("v-quest", "v", False),
                ("v-items", "v", True),
            ):
                row = current_guard_token(
                    decision_scene(case_id, method=method, items_multidrop=items)
                )
                self.assertEqual(row, CURRENT_GUARD_TOKENS[key], (key, method))

    def test_decision_case_i_ii_iii_store_the_shared_copy_without_hiding(self) -> None:
        for case_id in ("i", "ii", "iii"):
            row = trace(decision_scene(case_id))
            self.assertTrue(row.sparkle, case_id)
            self.assertEqual(row.slot, "ALLOW_LOOT", case_id)
            self.assertNotEqual(row.guard, "deny", case_id)
            self.assertEqual(row.award, "stored_shared_consumed", case_id)
            self.assertTrue(row.shared_consumed, case_id)
            self.assertFalse(row.personal_copy, case_id)

    def test_decision_case_iv_hides_the_row_and_still_stores_a_packet(self) -> None:
        row = trace(decision_scene("iv"))
        self.assertFalse(row.sparkle)
        self.assertIsNone(row.slot)
        self.assertEqual(row.guard, "permit_normal_slot")
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:82")
        self.assertNotEqual(row.guard, "deny")
        self.assertEqual(row.award, "stored_shared_consumed")
        self.assertTrue(row.shared_consumed)
        off = trace(replace(decision_scene("iv"), guard_enabled=False))
        self.assertEqual(off.guard, "permit_disabled")
        self.assertEqual(off.guard_site, "QuestLootProtection.cpp:211")
        self.assertFalse(off.sparkle)
        self.assertIsNone(off.slot)
        self.assertEqual(off.award, "stored_shared_consumed")

    def test_decision_case_v_both_humans_keep_a_personal_copy(self) -> None:
        for items in (False, True):
            friend = trace(decision_scene("v", items_multidrop=items))
            holder = trace(
                replace(
                    decision_scene("v", items_multidrop=items),
                    clicker=OWNER,
                    case_id="v-holder",
                )
            )
            for row in (friend, holder):
                self.assertTrue(row.sparkle)
                self.assertEqual(row.slot, "ALLOW_LOOT")
                self.assertNotEqual(row.guard, "deny")
                self.assertEqual(row.award, "stored_personal_copy")
                self.assertTrue(row.personal_copy)
                self.assertFalse(row.shared_consumed)
            self.assertEqual(
                holder.guard_site,
                "QuestLootProtection.cpp:75",
            )
            self.assertEqual(
                friend.guard_site,
                "QuestLootProtection.cpp:82" if items else "QuestLootProtection.cpp:102",
            )

    def test_decision_socket_deny_is_a_different_scene_and_does_not_hide(self) -> None:
        row = trace(Scene(
            "holder-still-needs",
            "ROUND_ROBIN",
            OWNER,
            FRIEND,
            True,
            True,
            one_copy_quest(),
        ))
        self.assertEqual(row.guard, "deny")
        self.assertEqual(row.guard_site, "QuestLootProtection.cpp:194")
        self.assertTrue(row.sparkle)
        self.assertEqual(row.slot, "ALLOW_LOOT")
        self.assertEqual(row.award, "not_reached")
        self.assertFalse(row.shared_consumed)
        for case_id in ("i", "ii", "iii", "iv", "v"):
            self.assertNotEqual(trace(decision_scene(case_id)).guard, "deny", case_id)

    def test_enabled_default_false_does_not_socket_deny_the_five_cases(self) -> None:
        guard = GUARD_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '"NaxxramasCore.QuestLootProtection.Enabled", false',
            guard,
        )
        conf = CONF_DIST.read_text(encoding="utf-8")
        self.assertIn("NaxxramasCore.QuestLootProtection.Enabled = 0", conf)
        for case_id in ("i", "ii", "iii", "iv", "v"):
            row = trace(replace(decision_scene(case_id), guard_enabled=False))
            self.assertEqual(row.guard, "permit_disabled", case_id)
            self.assertEqual(row.guard_site, "QuestLootProtection.cpp:211", case_id)
            self.assertNotEqual(row.award, "not_reached", case_id)

    def test_decision_table_pins_effects_labels_and_publishes_nothing(self) -> None:
        text = TABLE_PATH.read_text(encoding="utf-8")
        found = {
            key: (effect, site)
            for key, effect, site in re.findall(
                r"^(i|ii|iii|iv|v-quest|v-items) "
                r"(permit-and-show|hide-not-socket-deny|personal-copy) "
                r"(QuestLootProtection\.cpp:\d+)\s*$",
                text,
                re.M,
            )
        }
        self.assertEqual(found, CURRENT_GUARD_TOKENS)
        for phrase in (
            "The owner reported successful human pickups, so they are not merely visual.",
            "The module Enabled() default is false, so the owner's actually loaded config/binary is UNKNOWN.",
            "No owner policy is chosen.",
            "Not a socket deny. Not a hide. The friend stores the one shared copy. VERIFIED `QuestLootProtection.cpp:75`",
            "VERIFIED `QuestLootProtection.cpp:177-179`",
            "VERIFIED `LootHandler.cpp:459-461`",
            "Hide of the row and the sparkle. Not a socket deny.",
            "Not a socket deny. Not a hide. Each human stores a personal copy.",
            "Socket deny. Not a hide. C would refuse the friend's click",
            "Whether the friend's click is a socket deny is UNKNOWN",
            "When both humans still need it, which person that is: UNKNOWN",
            "Whether it should: UNKNOWN",
            "How far B extends onto this row: UNKNOWN",
            "B must not mint a second copy",
            "The click check cannot mint a copy.",
            "B would use the generation-time hook instead",
            "OnAfterLootTemplateProcess",
            "LootMgr.cpp:563",
            "does not choose or approve B",
            "It is not Michael's decision.",
            "Other `FillLoot` callers outside those two files: UNKNOWN",
            "Naming one owner here would take the other human's copy",
            "NOT TESTED",
            "UNKNOWN",
            "VERIFIED",
            "CMSG_AUTOSTORE_LOOT_ITEM",
            "QuestLootProtection.cpp:194",
            "QuestLootProtection.cpp:211",
            "8daffdabe9202c228e45d833c9a1d399597a15cd",
            MODULE_BLOB,
            "No cell here is an in-game pass.",
        ):
            self.assertIn(phrase, text, phrase)
        self.assertNotIn("PASS", text)
        self.assertNotIn("gameplay pass", text.lower())
        # A, B, and C are not labeled as running code.
        for option in ("A — keep one copy", "B — personal copies", "C — named owner"):
            self.assertIn(option, text)
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("actions/upload", workflow)
        self.assertIn("A04-QL-109-DECISION-TABLE.md", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)


if __name__ == "__main__":
    unittest.main()
