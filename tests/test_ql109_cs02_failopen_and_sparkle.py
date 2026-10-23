"""A04 / #109 CS02 synthetic source model. Not a fix and not a gameplay run.

Locks three separations that draft PR #111 also keeps, without renumbering
CS01's H01-H08:

1. Per-viewer corpse sparkle (UNIT_DYNFLAG_LOOTABLE on an outgoing copy).
2. Loot-window quest-row slot type (ALLOW_LOOT without a round-robin check).
3. The module's narrow CMSG_AUTOSTORE_LOOT_ITEM conjunction, which fail-opens
   into native storage when any required check misses.

V01-V08 are negative cases for a future per-viewer bit clear. V01's money
refusal is a design prohibition: pinned isAllowedToLoot does not sparkle a
non-holder under GROUP/NBG/RR for gold alone. H01-H05 use the same
current-source meanings as PR #111 at c1d5b398. H09 and H10 are CS03's
cells: the friend's own turn, and a holder who does not need the item.
A personal-copy freeforall policy is UNSELECTED and is not implemented.
A green run does not mean the owner's corpse, item, method, or copy
transfer was reproduced.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/QuestLootProtection.cpp"
DOC = ROOT / "docs/research/A04-QL-109-CS02-ROOT-CAUSE-TRIAGE.md"
WORKFLOW = ROOT / ".github/workflows/naxx-a04-ql109-cs02-model.yml"

LOOTABLE = 0x0001
DEAD = 0x0020
SKINNABLE = 0x04000000
GROUP_METHODS = ("GROUP_LOOT", "NEED_BEFORE_GREED", "ROUND_ROBIN")

# Order matches the deny conjunction in QuestLootProtection.cpp. All must hold.
DENY_KEYS = (
    "opcode_autostore",
    "enabled",
    "session",
    "player",
    "packet_has_slot_byte",
    "in_world_with_map",
    "in_group",
    "method_group_rr_nbg",
    "loot_guid_creature",
    "creature_dead_near_same_group",
    "loot_type_corpse",
    "round_robin_set",
    "clicker_is_not_holder",
    "slot_is_quest_view",
    "personal_quest_vector",
    "personal_index_in_range",
    "view_unlooted_and_index_valid",
    "one_copy_quest_line",
    "template_without_multi_drop",
    "owner_found_in_group",
    "owner_same_map_still_needs_item",
)


@dataclass(frozen=True)
class GuardCase:
    opcode_autostore: bool = True
    enabled: bool = True
    session: bool = True
    player: bool = True
    packet_has_slot_byte: bool = True
    in_world_with_map: bool = True
    in_group: bool = True
    method_group_rr_nbg: bool = True
    loot_guid_creature: bool = True
    creature_dead_near_same_group: bool = True
    loot_type_corpse: bool = True
    round_robin_set: bool = True
    clicker_is_not_holder: bool = True
    slot_is_quest_view: bool = True
    personal_quest_vector: bool = True
    personal_index_in_range: bool = True
    view_unlooted_and_index_valid: bool = True
    one_copy_quest_line: bool = True
    template_without_multi_drop: bool = True
    owner_found_in_group: bool = True
    owner_same_map_still_needs_item: bool = True

    def denies(self) -> bool:
        return all(getattr(self, key) for key in DENY_KEYS)


@dataclass(frozen=True)
class ViewCase:
    """Current-source characterization inputs. Same H01-H05 shape as PR #111."""

    group_method: str = "GROUP_LOOT"
    rr_active: bool = True
    viewer_is_turn_holder: bool = False
    quest_view: bool = True
    other_valid_loot: bool = False
    quest_slot: bool = True
    has_quest_for_item: bool = True
    follow_loot_rules: bool = False
    blocked: bool = False
    count: int = 1
    multi_drop: bool = False
    owner_available_and_eligible: bool = True
    player_can_receive_item: bool = True
    guard_enabled: bool = True
    server_flag_lootable: bool = True
    # Not an input to the non-holder GROUP/NBG/RR arm. See core_sparkle.
    gold: bool = False
    # SendLoot: only this viewer gets MASTER_PERMISSION under MASTER_LOOT.
    viewer_is_master_looter: bool = False
    ordinary_item: bool = False
    over_threshold: bool = False
    loot_type_skinning: bool = False
    skinnable_for_viewer: bool = False
    viewer_in_money_group: bool = False
    live_same_group: bool = True
    live_has_quest: bool = True
    stale_snapshot_says_clear: bool = False


def core_sparkle(case: ViewCase) -> bool:
    """isAllowedToLoot for a recipient-group member, transcribed from the pin.

    PlayerStorage.cpp:5772-5774 returns true for every grouped member under
    FREE_FOR_ALL and MASTER_LOOT. It does not ask who the master looter is.
    The non-holder arms at 5775-5793 do not read gold and do not call
    hasItemForAll. Round robin returns hasItemFor. Group loot and
    need-before-greed also return true for an over-threshold line.
    Gold can pass the earlier emptiness gate (5758 via hasItemForAll at
    LootMgr.cpp:894-897) without granting this sparkle.
    """

    if not case.server_flag_lootable or case.loot_type_skinning:
        return case.loot_type_skinning and case.skinnable_for_viewer and case.server_flag_lootable
    if case.group_method in ("FREE_FOR_ALL", "MASTER_LOOT"):
        return True
    if case.group_method not in GROUP_METHODS:
        return False
    if not case.live_same_group:
        return False
    if not case.rr_active or case.viewer_is_turn_holder:
        return True
    if case.group_method in ("GROUP_LOOT", "NEED_BEFORE_GREED") and case.over_threshold:
        return True
    return case.quest_view or case.other_valid_loot or case.multi_drop


def module_blocks(case: ViewCase) -> bool:
    """Narrow human autostore deny. Any miss permits native handling."""

    guard = GuardCase(
        enabled=case.guard_enabled,
        method_group_rr_nbg=case.group_method in GROUP_METHODS,
        round_robin_set=case.rr_active,
        clicker_is_not_holder=not case.viewer_is_turn_holder,
        slot_is_quest_view=case.quest_slot,
        one_copy_quest_line=(
            case.count == 1
            and not case.multi_drop
            and not case.follow_loot_rules
            and not case.blocked
        ),
        template_without_multi_drop=not case.multi_drop,
        owner_found_in_group=case.owner_available_and_eligible and case.live_same_group,
        owner_same_map_still_needs_item=(
            case.owner_available_and_eligible and case.live_has_quest
        ),
        view_unlooted_and_index_valid=case.quest_view and case.quest_slot,
        personal_quest_vector=case.quest_view,
    )
    return guard.denies()


def viewer_permission(case: ViewCase) -> str:
    """Creature-corpse SendLoot for a member of the recipient group.

    Player.cpp:8329-8330. MASTER_LOOT maps GetMasterLooterGuid() == GetGUID()
    to MASTER_PERMISSION and every other member to RESTRICTED_PERMISSION.
    The chest split at 8124-8125 is the same pair. This is not the loot method
    enum by itself.
    """

    if case.group_method == "MASTER_LOOT":
        return "MASTER_PERMISSION" if case.viewer_is_master_looter else "RESTRICTED_PERMISSION"
    if case.group_method == "FREE_FOR_ALL":
        return "ALL_PERMISSION"
    if case.group_method == "ROUND_ROBIN":
        return "ROUND_ROBIN_PERMISSION"
    if case.group_method in ("GROUP_LOOT", "NEED_BEFORE_GREED"):
        return "GROUP_PERMISSION"
    return "NONE_PERMISSION"


def quest_row_slot_type(case: ViewCase) -> str:
    """Personal quest_items row. No roundRobinPlayer test in that loop.

    LootMgr.cpp:1094-1157. partySlotType is MASTER only for MASTER_PERMISSION
    (1097). A restricted viewer's ordinary !follow_loot_rules, !freeforall
    row is ALLOW_LOOT (1154-1155). follow_loot_rules under RESTRICTED is
    LOCKED when blocked, otherwise slotType / ALLOW_LOOT (1139-1140).
    """

    if not case.quest_view or not case.quest_slot:
        return "NO_QUEST_ROW"
    permission = viewer_permission(case)
    if not case.has_quest_for_item:
        return "MASTER" if permission == "MASTER_PERMISSION" else "LOCKED"
    if case.follow_loot_rules:
        if permission == "MASTER_PERMISSION":
            return "MASTER"
        if permission == "RESTRICTED_PERMISSION":
            return "LOCKED" if case.blocked else "ALLOW_LOOT"
        if permission in ("GROUP_PERMISSION", "ROUND_ROBIN_PERMISSION"):
            return "ROLL_ONGOING" if case.blocked else "ALLOW_LOOT"
        return "ALLOW_LOOT"
    if case.multi_drop:
        return "ALLOW_LOOT"
    if permission == "MASTER_PERMISSION":
        return "MASTER"
    return "ALLOW_LOOT"


def native_turn_versus_owner_expectation(case: ViewCase) -> str:
    """Native round-robin turn versus the owner's expected named ownership.

    Unit::Kill advances the group looter (Unit.cpp:13654) and FillLoot stores
    that player as roundRobinPlayer (LootMgr.cpp:569). The module permits
    when the clicker is that holder (H09, QuestLootProtection.cpp:74-76) and
    when the holder no longer HasQuestForItem (H10, lines 177-179). Neither
    cell is "this named player owns every quest drop".
    """

    if case.viewer_is_turn_holder and case.group_method in GROUP_METHODS:
        return "H09_NATIVE_HOLDER_TAKE"
    if (
        case.group_method in GROUP_METHODS
        and not case.viewer_is_turn_holder
        and case.owner_available_and_eligible
        and not case.live_has_quest
        and case.quest_view
        and case.has_quest_for_item
    ):
        return "H10_HOLDER_DOES_NOT_NEED"
    if (
        case.group_method in GROUP_METHODS
        and not case.viewer_is_turn_holder
        and case.live_has_quest
        and case.owner_available_and_eligible
    ):
        return "NON_HOLDER_WHILE_HOLDER_STILL_NEEDS"
    return "OTHER"


# Owner trade-off. Not selected and not implemented. OnPlayerBeforeFillQuestLootItem
# receives the shared quest_items[i] reference (LootMgr.cpp:667-669), so it
# cannot safely hide one line for a single viewer.
PERSONAL_COPY_POLICY = "UNSELECTED"


def personal_copy_policy() -> str:
    return PERSONAL_COPY_POLICY


def normal_row_visible(case: ViewCase) -> bool:
    """Under-threshold normal items consult the active round-robin holder."""

    if case.multi_drop:
        return True
    if not case.ordinary_item:
        return False
    if case.group_method in ("FREE_FOR_ALL",):
        return True
    if case.group_method == "ROUND_ROBIN":
        return (not case.rr_active) or case.viewer_is_turn_holder
    if case.rr_active and not case.viewer_is_turn_holder and not case.over_threshold:
        return False
    return True


def native_store_candidate(case: ViewCase) -> bool:
    """Guard permit plus a simplified StoreLootItem eligibility. Not an award."""

    return (not module_blocks(case)) and case.player_can_receive_item and (
        case.quest_view or case.ordinary_item or case.multi_drop
    )


def may_clear_lootable(case: ViewCase) -> bool:
    """Future per-viewer clear. Stale snapshots are ignored. Negatives refuse.

    The gold refusal is a design prohibition: do not drop LOOTABLE when a
    money share is still legitimate. It is not a transcript of isAllowedToLoot.
    This helper is not shipped code.
    """

    if case.gold and case.viewer_in_money_group:
        return False
    if case.ordinary_item:
        return False
    if case.group_method in ("FREE_FOR_ALL", "MASTER_LOOT"):
        return False
    if case.multi_drop:
        return False
    if case.over_threshold or case.follow_loot_rules or case.blocked:
        return False
    if not case.rr_active:
        return False
    if case.loot_type_skinning or case.skinnable_for_viewer:
        return False
    if not case.live_same_group or not case.live_has_quest:
        return False
    if case.stale_snapshot_says_clear:
        return False
    return (
        case.group_method in GROUP_METHODS
        and case.rr_active
        and not case.viewer_is_turn_holder
        and case.quest_view
        and case.quest_slot
        and not case.other_valid_loot
    )


def apply_offset(positions: dict, offset: int) -> dict:
    """BuildValuesCachePosPointers::ApplyOffset. Negative marks stay absent."""

    shifted = {}
    for name, pos in positions.items():
        shifted[name] = pos + offset if pos >= 0 else pos
    return shifted


def store_u32(value: int, big_endian: bool) -> bytes:
    """ByteBuffer append/put of uint32. EndianConvert runs only on big endian."""

    raw = value.to_bytes(4, "little")
    if big_endian:
        raw = raw[::-1]
    return raw


def load_u32(raw: bytes, big_endian: bool) -> int:
    if big_endian:
        raw = raw[::-1]
    return int.from_bytes(raw, "little")


class OutgoingBuffer:
    def __init__(self, initial: bytes = b"") -> None:
        self.storage = bytearray(initial)

    def size(self) -> int:
        return len(self.storage)

    def wpos(self) -> int:
        return len(self.storage)

    def append(self, data: bytes) -> None:
        self.storage.extend(data)

    def read_u32(self, pos: int, big_endian: bool) -> int:
        if pos < 0 or pos + 4 > len(self.storage):
            raise IndexError(f"read bounds pos={pos} size={len(self.storage)}")
        return load_u32(bytes(self.storage[pos:pos + 4]), big_endian)

    def put_u32(self, pos: int, value: int, big_endian: bool) -> None:
        # Pinned ByteBuffer::put ASSERTs. The helper must not reach this on a short buffer.
        if pos + 4 > len(self.storage):
            raise AssertionError(f"put bounds pos={pos} size={len(self.storage)}")
        self.storage[pos:pos + 4] = store_u32(value, big_endian)


def safe_clear_lootable(buf: OutgoingBuffer, pos: int, big_endian: bool, allow: bool) -> bool:
    """Clear LOOTABLE on this buffer only. Never sets the bit. Never grows the buffer."""

    if pos < 0 or pos + 4 > buf.size() or not allow:
        return False
    flags = buf.read_u32(pos, big_endian)
    if flags & LOOTABLE == 0:
        return False
    buf.put_u32(pos, flags & ~LOOTABLE, big_endian)
    return True


def build_update(cache_pos: int, big_endian: bool, flags: int) -> tuple[OutgoingBuffer, OutgoingBuffer, int]:
    """Fresh BuildValuesUpdate layout, then the cache-hit append into a later packet.

    Returns (cached template, outgoing packet, dynamic-flags position in the outgoing packet).
    """

    field = OutgoingBuffer()
    dynamic_pos_in_field = field.wpos()
    field.append(store_u32(flags, big_endian))
    mask_header = b"\x01\xff"
    cached = OutgoingBuffer()
    cached.append(mask_header)
    field_buffer_pos = cached.wpos()
    cached.append(bytes(field.storage))
    pointers = apply_offset({"UnitDynamicFlagsPos": dynamic_pos_in_field, "Absent": -1}, field_buffer_pos)

    outgoing = OutgoingBuffer(b"\x00" * cache_pos)
    packet_cache_pos = outgoing.wpos()
    outgoing.append(bytes(cached.storage))
    adjusted = apply_offset(pointers, packet_cache_pos if packet_cache_pos else 0)
    return cached, outgoing, adjusted["UnitDynamicFlagsPos"]


def playerbots_dispatch(guard_denies: bool) -> str:
    """HandleBotPackets calls opHandle->Call and does not consult the guard."""

    del guard_denies
    return "handler"


def worldsession_dispatch(guard_denies: bool) -> str:
    """WorldSession::Update calls CanPacketReceive before opHandle->Call."""

    if guard_denies:
        return "stopped"
    return "handler"


def allowed_after_global_hook(script_returns_true: bool) -> bool:
    """OnAllowedForPlayerLootCheck true makes ScriptMgr return false (not allowed)."""

    return not script_returns_true


class FailOpenAndSparkleModel(unittest.TestCase):
    def test_every_guard_miss_fail_opens(self):
        self.assertTrue(GuardCase().denies())
        self.assertEqual(len(DENY_KEYS), 21)
        for key in DENY_KEYS:
            missed = replace(GuardCase(), **{key: False})
            self.assertFalse(missed.denies(), key)

    def test_named_fail_open_paths_hand_off_to_native_storage(self):
        paths = {
            "quest_required_zero_normal_slot": ViewCase(quest_slot=False, ordinary_item=True, quest_view=True),
            "round_robin_released": ViewCase(rr_active=False),
            "free_for_all_method": ViewCase(group_method="FREE_FOR_ALL"),
            "master_loot_method": ViewCase(group_method="MASTER_LOOT"),
            "multi_drop_copy": ViewCase(multi_drop=True),
            "owner_left_group": ViewCase(live_same_group=False, owner_available_and_eligible=False),
            "owner_no_longer_needs_item": ViewCase(live_has_quest=False, owner_available_and_eligible=False),
            "count_above_one": ViewCase(count=2),
            "guard_disabled": ViewCase(guard_enabled=False),
            "client_slot_is_normal_index": ViewCase(quest_slot=False, ordinary_item=True),
        }
        for name, case in paths.items():
            with self.subTest(path=name):
                self.assertFalse(module_blocks(case))
                self.assertTrue(native_store_candidate(case))

    def test_h01_sparkle_and_allow_loot_row_while_packet_denies(self):
        case = ViewCase()
        self.assertTrue(core_sparkle(case))
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(normal_row_visible(case))
        self.assertTrue(module_blocks(case))
        self.assertFalse(native_store_candidate(case))

    def test_h02_release_fail_opens_storage_candidate(self):
        case = ViewCase(rr_active=False)
        self.assertTrue(core_sparkle(case))
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(module_blocks(case))
        self.assertTrue(native_store_candidate(case))

    def test_h03_quest_required_zero_bypasses_guard(self):
        case = ViewCase(quest_slot=False, ordinary_item=True, other_valid_loot=True)
        self.assertTrue(core_sparkle(case))
        self.assertEqual(quest_row_slot_type(case), "NO_QUEST_ROW")
        self.assertFalse(module_blocks(case))
        self.assertTrue(native_store_candidate(case))

    def test_h04_disabled_guard_does_not_stop_native_candidate(self):
        case = ViewCase(guard_enabled=False)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks(case))
        self.assertTrue(native_store_candidate(case))

    def test_h05_multi_drop_is_not_modeled_as_theft(self):
        case = ViewCase(multi_drop=True)
        self.assertTrue(core_sparkle(case))
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(module_blocks(case))
        self.assertTrue(native_store_candidate(case))

    def test_quest_row_ignores_active_round_robin_holder(self):
        held = ViewCase(rr_active=True, viewer_is_turn_holder=False)
        released = ViewCase(rr_active=False)
        self.assertEqual(quest_row_slot_type(held), "ALLOW_LOOT")
        self.assertEqual(quest_row_slot_type(released), "ALLOW_LOOT")
        self.assertFalse(normal_row_visible(ViewCase(ordinary_item=True, quest_view=False)))
        self.assertTrue(normal_row_visible(ViewCase(
            ordinary_item=True, quest_view=False, rr_active=False)))

    def test_sparkle_clear_does_not_change_row_or_packet_verdict(self):
        case = ViewCase()
        self.assertTrue(may_clear_lootable(case))
        self.assertTrue(module_blocks(case))
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")

    def test_v01_money_refuses_clear(self):
        """Design prohibition. Native non-holder sparkle does not follow gold."""

        quest = ViewCase()
        quest_gold = ViewCase(gold=True, viewer_in_money_group=True)
        self.assertTrue(core_sparkle(quest))
        self.assertTrue(core_sparkle(quest_gold))
        self.assertTrue(may_clear_lootable(quest))
        self.assertFalse(may_clear_lootable(quest_gold))
        bare = ViewCase(
            quest_view=False,
            quest_slot=False,
            other_valid_loot=False,
            over_threshold=False,
            multi_drop=False,
        )
        for method in GROUP_METHODS:
            with self.subTest(method=method):
                without_gold = replace(bare, group_method=method, gold=False)
                with_gold = replace(bare, group_method=method, gold=True, viewer_in_money_group=True)
                self.assertFalse(core_sparkle(without_gold))
                self.assertFalse(core_sparkle(with_gold))
                self.assertEqual(core_sparkle(without_gold), core_sparkle(with_gold))

    def test_v02_ordinary_item_refuses_clear(self):
        case = ViewCase(ordinary_item=True, other_valid_loot=True)
        self.assertFalse(may_clear_lootable(case))

    def test_v03_ffa_refuses_clear(self):
        self.assertFalse(may_clear_lootable(ViewCase(group_method="FREE_FOR_ALL")))

    def test_v04_multi_drop_refuses_clear(self):
        self.assertFalse(may_clear_lootable(ViewCase(multi_drop=True)))

    def test_v05_roll_refuses_clear(self):
        self.assertFalse(may_clear_lootable(ViewCase(over_threshold=True, follow_loot_rules=True, blocked=True)))

    def test_v06_master_refuses_clear(self):
        restricted = ViewCase(group_method="MASTER_LOOT", viewer_is_master_looter=False)
        master = ViewCase(group_method="MASTER_LOOT", viewer_is_master_looter=True)
        self.assertFalse(may_clear_lootable(restricted))
        self.assertFalse(may_clear_lootable(master))
        self.assertFalse(module_blocks(restricted))
        self.assertFalse(module_blocks(master))
        self.assertTrue(core_sparkle(restricted))
        self.assertTrue(core_sparkle(master))

    def test_positive_master_looter_ordinary_quest_row_is_master(self):
        case = ViewCase(
            group_method="MASTER_LOOT",
            viewer_is_master_looter=True,
            follow_loot_rules=False,
            multi_drop=False,
        )
        self.assertEqual(viewer_permission(case), "MASTER_PERMISSION")
        self.assertEqual(quest_row_slot_type(case), "MASTER")
        no_quest = replace(case, has_quest_for_item=False)
        self.assertEqual(quest_row_slot_type(no_quest), "MASTER")

    def test_negative_restricted_viewer_ordinary_quest_row_is_allow_loot(self):
        case = ViewCase(
            group_method="MASTER_LOOT",
            viewer_is_master_looter=False,
            follow_loot_rules=False,
            multi_drop=False,
            has_quest_for_item=True,
        )
        self.assertEqual(viewer_permission(case), "RESTRICTED_PERMISSION")
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")
        self.assertNotEqual(quest_row_slot_type(case), "MASTER")
        blocked = replace(case, follow_loot_rules=True, blocked=True)
        self.assertEqual(quest_row_slot_type(blocked), "LOCKED")
        unblocked_rules = replace(case, follow_loot_rules=True, blocked=False)
        self.assertEqual(quest_row_slot_type(unblocked_rules), "ALLOW_LOOT")
        no_quest = replace(case, has_quest_for_item=False)
        self.assertEqual(quest_row_slot_type(no_quest), "LOCKED")

    def test_h09_friend_turn_is_native_design_not_named_ownership(self):
        case = ViewCase(viewer_is_turn_holder=True)
        self.assertEqual(native_turn_versus_owner_expectation(case), "H09_NATIVE_HOLDER_TAKE")
        self.assertTrue(core_sparkle(case))
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(module_blocks(case))
        self.assertTrue(native_store_candidate(case))
        self.assertFalse(may_clear_lootable(case))
        self.assertNotEqual(native_turn_versus_owner_expectation(case), "NAMED_OWNER")

    def test_h10_holder_without_need_lets_eligible_friend_pick_up(self):
        case = ViewCase(
            viewer_is_turn_holder=False,
            live_has_quest=False,
            owner_available_and_eligible=True,
            has_quest_for_item=True,
            quest_view=True,
        )
        self.assertEqual(native_turn_versus_owner_expectation(case), "H10_HOLDER_DOES_NOT_NEED")
        self.assertTrue(core_sparkle(case))
        self.assertEqual(quest_row_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(module_blocks(case))
        self.assertTrue(native_store_candidate(case))
        self.assertFalse(may_clear_lootable(case))
        still_needs = replace(case, live_has_quest=True)
        self.assertEqual(
            native_turn_versus_owner_expectation(still_needs),
            "NON_HOLDER_WHILE_HOLDER_STILL_NEEDS",
        )
        self.assertTrue(module_blocks(still_needs))

    def test_personal_copy_freeforall_policy_is_unselected(self):
        self.assertEqual(personal_copy_policy(), "UNSELECTED")
        cpp = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("OnPlayerBeforeFillQuestLootItem", cpp)
        self.assertNotIn("item.freeforall =", cpp)
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("UNSELECTED", text)
        self.assertIn("H09", text)
        self.assertIn("H10", text)
        self.assertIn("quest_items[i]", text)
        self.assertIn("OnPlayerBeforeFillQuestLootItem", text)

    def test_v07_release_refuses_clear_and_refuses_deny(self):
        case = ViewCase(rr_active=False)
        self.assertFalse(may_clear_lootable(case))
        self.assertFalse(module_blocks(case))

    def test_v08_skinning_and_stale_snapshot_refuse_clear(self):
        skin = ViewCase(loot_type_skinning=True, skinnable_for_viewer=True)
        self.assertFalse(may_clear_lootable(skin))
        stale = ViewCase(stale_snapshot_says_clear=True)
        live = ViewCase(stale_snapshot_says_clear=False)
        self.assertFalse(may_clear_lootable(stale))
        self.assertTrue(may_clear_lootable(live))
        abandoned = ViewCase(live_has_quest=False)
        left = ViewCase(live_same_group=False)
        self.assertFalse(may_clear_lootable(abandoned))
        self.assertFalse(may_clear_lootable(left))

    def test_dynamic_flags_position_on_fresh_and_cached_layouts(self):
        for big_endian in (False, True):
            with self.subTest(big_endian=big_endian):
                cached, outgoing, pos = build_update(cache_pos=10, big_endian=big_endian, flags=LOOTABLE | DEAD)
                self.assertEqual(pos, 10 + 2)
                self.assertEqual(outgoing.read_u32(pos, big_endian), LOOTABLE | DEAD)
                absent = apply_offset({"UnitDynamicFlagsPos": -1}, 10)
                self.assertEqual(absent["UnitDynamicFlagsPos"], -1)
                self.assertEqual(cached.wpos(), 2 + 4)

    def test_clear_is_false_positive_only_on_a_copy(self):
        for big_endian in (False, True):
            cached, outgoing, pos = build_update(7, big_endian, LOOTABLE | DEAD)
            template = bytearray(cached.storage)
            global_flags = LOOTABLE | DEAD
            self.assertTrue(safe_clear_lootable(outgoing, pos, big_endian, True))
            self.assertEqual(outgoing.read_u32(pos, big_endian), DEAD)
            self.assertEqual(cached.storage, template)
            self.assertEqual(global_flags, LOOTABLE | DEAD)
            self.assertFalse(safe_clear_lootable(outgoing, pos, big_endian, True))
            self.assertFalse(safe_clear_lootable(outgoing, -1, big_endian, True))
            short = OutgoingBuffer(b"\x01\x02")
            before = bytearray(short.storage)
            self.assertFalse(safe_clear_lootable(short, 0, big_endian, True))
            self.assertEqual(short.storage, before)

    def test_clear_does_not_set_a_missing_lootable_bit(self):
        cached, outgoing, pos = build_update(0, False, DEAD)
        self.assertFalse(safe_clear_lootable(outgoing, pos, False, True))
        self.assertEqual(outgoing.read_u32(pos, False), DEAD)
        self.assertEqual(cached.storage[2:6], store_u32(DEAD, False))

    def test_skinning_flag_word_is_not_the_dynamic_flags_word(self):
        self.assertEqual(SKINNABLE & LOOTABLE, 0)
        flags_word = SKINNABLE
        dynamic = LOOTABLE | DEAD
        buf = OutgoingBuffer(store_u32(dynamic, False) + store_u32(flags_word, False))
        self.assertTrue(safe_clear_lootable(buf, 0, False, True))
        self.assertEqual(buf.read_u32(4, False), SKINNABLE)

    def test_already_sent_buffer_keeps_sparkle_until_rebuild(self):
        _cached, sent, pos = build_update(4, False, LOOTABLE | DEAD)
        sent_copy = bytearray(sent.storage)
        rebuilt_cached, rebuilt, rebuilt_pos = build_update(4, False, LOOTABLE | DEAD)
        self.assertTrue(safe_clear_lootable(rebuilt, rebuilt_pos, False, True))
        self.assertEqual(sent.storage, sent_copy)
        self.assertEqual(rebuilt.read_u32(rebuilt_pos, False), DEAD)
        self.assertNotEqual(rebuilt_cached.storage, rebuilt.storage[4:])

    def test_bot_dispatch_bypasses_the_human_guard(self):
        self.assertEqual(worldsession_dispatch(True), "stopped")
        self.assertEqual(playerbots_dispatch(True), "handler")
        self.assertEqual(worldsession_dispatch(False), "handler")

    def test_allowed_for_player_hook_is_item_blind_and_denies_on_true(self):
        item_argument = None
        self.assertIsNone(item_argument)
        self.assertFalse(allowed_after_global_hook(True))
        self.assertTrue(allowed_after_global_hook(False))

    def test_module_source_is_still_packet_only(self):
        cpp = SOURCE.read_text(encoding="utf-8")
        for snippet in (
            "SERVERHOOK_CAN_PACKET_RECEIVE",
            "CMSG_AUTOSTORE_LOOT_ITEM",
            "if (requestedSlot < normalCount)",
            "!loot.roundRobinPlayer",
            "if (!item.needs_quest || item.count != 1",
            "item.freeforall",
            "item.follow_loot_rules",
            "ITEM_FLAG_MULTI_DROP",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, cpp)
        self.assertEqual(cpp.count("return false"), 1)
        self.assertNotIn("UNITHOOK_ON_PATCH_VALUES_UPDATE", cpp)
        self.assertNotIn("OnPatchValuesUpdate", cpp)
        self.assertNotIn("OnAllowedForPlayerLootCheck", cpp)

    def test_research_doc_keeps_both_reports_and_drops_the_personal_name(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("owner's reported corpse", text)
        self.assertNotIn("Michael", text)
        for token in (
            "H01", "H02", "H03", "H04", "H05", "H09", "H10",
            "V01", "V02", "V03", "V04", "V05", "V06", "V07", "V08",
        ):
            self.assertIn(token, text)
        self.assertIn("ALLOW_LOOT", text)
        self.assertIn("RESTRICTED_PERMISSION", text)
        self.assertIn("only the master looter", text)
        self.assertIn("design prohibition", text)
        self.assertIn("does not call `hasItemForAll`", text)
        self.assertIn("5632118504", text)
        self.assertIn("6370796678", text)
        self.assertIn("6371087087", text)
        self.assertIn("OnPatchValuesUpdate", text)
        self.assertIn("opHandle->Call", text)
        self.assertIn("c1d5b39898d212f04b789e30723bca5126f1bcbf", text)

    def test_workflow_is_read_only_and_uploads_nothing(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"', text)
        for banned in ("upload-artifact", "actions/upload", "softprops/action-gh-release", "actions/download"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
