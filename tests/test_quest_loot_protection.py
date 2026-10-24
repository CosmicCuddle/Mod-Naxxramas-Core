"""Quest Loot Protection: source contract and conservative decision model.

Mocks are not actual Grimfeather/Playerbots runtime. Full pinned compilation
and owner-approved in-game tests are needed before activating the feature.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/QuestLootProtection.cpp").read_text("utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text("utf-8")
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text("utf-8")
DOC = (ROOT / "docs/QUEST-LOOT-PROTECTION.md").read_text("utf-8")
WORKFLOW = (ROOT / ".github/workflows/quest-loot-protection-pinned.yml").read_text("utf-8")

# Whitespace, then one '=' that is not the first half of '=='.
ROUND_ROBIN_ASSIGNMENT = re.compile(r"roundRobinPlayer\s*=(?!=)")
# Defect from draft PR #25: a raw string with a doubled backslash matches
# a literal backslash, so `roundRobinPlayer = x;` was invisible to it.
BROKEN_ROUND_ROBIN_ASSIGNMENT = re.compile(r"roundRobinPlayer\\s*=(?!=)")

NOT_TESTED_CLAIMS = (
    "NOT TESTED: in-game human or Altbot loot",
    "NOT TESTED: direct Player::StoreLootItem callers",
    "NOT TESTED: native DoLootRelease and corpse expiry",
    "NOT TESTED: live database, SQL, or inventory mutation",
    "NOT TESTED: headless Playerbots sessions",
    "NOT TESTED: client loot-window icon state",
    "NOT TESTED: packet bytes on a live session",
)

OWNER_LOOKUP = (
    "        Player* owner = ObjectAccessor::FindPlayer(loot.roundRobinPlayer);"
)

# Each snippet is a fail-open permit. Denial (return false) must come later.
PRESENCE_FAIL_OPEN = (
    "if (!owner || owner->GetGroup() != group)\n            return true;",
    "if (!owner->IsInWorld())\n            return true;",
    "if (ownerMap != looterMap || ownerMap != corpseMap ||\n"
    "            ownerMap->GetId() != looterMap->GetId() ||\n"
    "            ownerMap->GetId() != corpseMap->GetId())\n"
    "            return true;",
    "if (owner->GetInstanceId() != player->GetInstanceId() ||\n"
    "            owner->GetInstanceId() != creature->GetInstanceId() ||\n"
    "            ownerMap->GetInstanceId() != looterMap->GetInstanceId() ||\n"
    "            ownerMap->GetInstanceId() != corpseMap->GetInstanceId())\n"
    "            return true;",
)


def presence_fail_open(source):
    """Verify the LEGACY quest-slot guard, not an earlier ordinary-slot deny.

    A04's new independently gated ordinary-slot branch may have its own
    SendLootError before the legacy owner lookup. Anchor every check to
    that owner lookup, or the old tests accidentally reject a safe extra
    branch without actually checking the legacy fail-open semantics.
    """
    at_owner = source.find(OWNER_LOOKUP)
    if at_owner < 0 or source.count(OWNER_LOOKUP) != 1:
        return False
    locked = source.find(
        "player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", at_owner
    )
    deny = source.find("return false;", locked)
    if locked < at_owner or deny < locked:
        return False
    for snippet in PRESENCE_FAIL_OPEN:
        at = source.find(snippet, at_owner)
        if at < 0 or at >= locked:
            return False
    return "Distance and death are not extra denies" in source


def flags_round_robin_write(source, pattern=ROUND_ROBIN_ASSIGNMENT):
    return pattern.search(source) is not None


def mutated_source_with_assignment():
    """In-memory copy only. The repository source is not rewritten."""
    if CPP.count(OWNER_LOOKUP) != 1:
        raise AssertionError("owner lookup anchor missing from QuestLootProtection.cpp")
    return CPP.replace(
        OWNER_LOOKUP,
        "        loot.roundRobinPlayer = x;\n" + OWNER_LOOKUP,
        1,
    )


COMPARISON_FIXTURE = """
if (!loot.roundRobinPlayer || loot.roundRobinPlayer == player->GetGUID())
    return true;
if (roundRobinPlayer == owner)
    return true;
if (roundRobinPlayer==viewer)
    return true;
if (roundRobinPlayer >= 1 || roundRobinPlayer != 0)
    return true;
ObjectGuid kept = loot.roundRobinPlayer;
"""


def modeled_pickup(
    enabled=True, packet=True, malformed=False, grouped=True,
    method="GROUP_LOOT", corpse=True, same_recipient=True,
    owner="owner", viewer="viewer", slot=4, normal_count=4,
    personal=None, quest_index=0, quest_count=1,
    needs_quest=True, looted=False, shared=False,
    follow_rules=False, blocked=False, roll_winner=False,
    item_template=True, owner_online=True, owner_in_group=True,
    owner_has_slot=True, owner_needs=True, owner_eligible=True,
    owner_personal=None, count=1, in_range=True, creature_dead=True,
    padded=False, viewer_is_altbot=False,
    owner_in_world=True, owner_same_map=True, owner_same_instance=True,
    enforce_in_world=True, enforce_same_map=True, enforce_same_instance=True,
):
    """Model conditions in PermitPickup, not independent proof of source.

    padded and viewer_is_altbot are accepted so callers can state that
    trailing bytes and an Altbot viewer are not exemptions. Neither flag
    permits a pickup that the other conditions would deny.

    owner_in_world, owner_same_map and owner_same_instance default to a
    present owner. Setting enforce_* to False is a mutation that drops
    that fail-open guard. A dropped guard can block a case that must permit.
    """
    if padded not in (True, False) or viewer_is_altbot not in (True, False):
        raise AssertionError("padded and viewer_is_altbot are booleans")
    presence_flags = (
        owner_in_world, owner_same_map, owner_same_instance,
        enforce_in_world, enforce_same_map, enforce_same_instance,
    )
    if any(flag not in (True, False) for flag in presence_flags):
        raise AssertionError("owner presence flags are booleans")
    if not enabled or not packet or malformed or not grouped or not corpse:
        return True
    if not creature_dead or not in_range:
        return True
    if method not in ("GROUP_LOOT", "ROUND_ROBIN", "NEED_BEFORE_GREED"):
        return True
    if not same_recipient or owner is None or owner == viewer:
        return True
    if slot < normal_count:
        return True
    if personal is None:
        personal = [quest_index]
    mapped_slot = slot - normal_count
    if mapped_slot < 0 or mapped_slot >= len(personal):
        return True
    # Translate client's viewer-specific SLOT to the underlying index.
    # This model considers one specified underlying quest item.
    mapped_index = personal[mapped_slot]
    if mapped_index < 0 or mapped_index >= quest_count:
        return True
    if mapped_index != quest_index:
        return True
    if (not needs_quest or count != 1 or looted or shared or
            follow_rules or blocked or roll_winner):
        return True
    if not item_template or not owner_online or not owner_in_group or not owner_has_slot:
        return True
    # Fail open unless the owner is in world on this live map and instance.
    # enforce_* = False models a source mutation that deleted that guard.
    if enforce_in_world and not owner_in_world:
        return True
    if enforce_same_map and not owner_same_map:
        return True
    if enforce_same_instance and not owner_same_instance:
        return True
    if owner_personal is not None:
        # Match SAME quest_items index, with an unlooted owner view.
        if not any(item_index == mapped_index and not was_looted
                   for item_index, was_looted in owner_personal):
            return True
    if not owner_needs or not owner_eligible:
        return True
    return False


class QuestLootProtectionContract(unittest.TestCase):
    def test_disabled_default_and_no_database(self):
        self.assertEqual(CONFIG.count(
            "NaxxramasCore.QuestLootProtection.Enabled = 0"), 1)
        self.assertEqual(CONFIG.count(
            "NaxxramasCore.QuestLootProtection.Debug = 0"), 1)
        self.assertIn('GetOption<bool>', CPP)
        self.assertNotIn("CharacterDatabase", CPP)
        self.assertNotIn("WorldDatabase", CPP)

    def test_packet_hook_and_original_cursor(self):
        self.assertIn("ServerScript", CPP)
        self.assertIn("SERVERHOOK_CAN_PACKET_RECEIVE", CPP)
        self.assertIn("CMSG_AUTOSTORE_LOOT_ITEM", CPP)
        self.assertIn("packet.size() < 1", CPP)
        self.assertNotIn("packet.size() != 1", CPP)
        self.assertIn("WorldPacket copy(packet)", CPP)
        self.assertIn("copy.rpos(0)", CPP)
        self.assertIn("copy >> requestedSlot", CPP)
        self.assertNotIn("packet >> requestedSlot", CPP)
        self.assertIn("AddQuestLootProtectionScripts();", LOADER)
        self.assertIn("new NaxxramasQuestLootProtectionScript();", CPP)

    def test_quest_slot_indirection_and_bounds(self):
        for required in (
            "loot.items.size()", "requestedSlot - normalCount",
            "loot.GetPlayerQuestItems()", "personal.find(player->GetGUID())",
            "personalSlot >= found->second->size()",
            "view.index >= loot.quest_items.size()",
            "loot.quest_items[view.index]",
        ):
            with self.subTest(required=required):
                self.assertIn(required, CPP)

    def test_only_narrow_creature_corpse_and_group_loot(self):
        for required in (
            "sourceGuid.IsCreatureOrVehicle()",
            "creature->isDead()", "LOOT_CORPSE", "GROUP_LOOT",
            "ROUND_ROBIN", "NEED_BEFORE_GREED",
            "creature->GetLootRecipientGroup() != group",
            "item.count != 1", "!item.needs_quest",
            "item.freeforall", "ITEM_FLAG_MULTI_DROP",
            "item.follow_loot_rules", "item.is_blocked",
            "item.rollWinnerGUID",
        ):
            with self.subTest(required=required):
                self.assertIn(required, CPP)

    def test_no_round_robin_mutation_or_item_award(self):
        for forbidden in (
            "roundRobinPlayer.Clear(",
            "LootItemInSlot(", "StoreLootItem(", "StoreNewItem(",
            "NotifyQuestItemRemoved(", "SendNotifyLootItemRemoved(",
            "SetLootGUID(", "item.is_looted =",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CPP)
        self.assertFalse(flags_round_robin_write(CPP))
        self.assertNotRegex(CPP, r"roundRobinPlayer\s*=(?!=)")
        self.assertIn("owner->HasQuestForItem(item.itemid)", CPP)
        self.assertIn("personal.find(owner->GetGUID())", CPP)
        self.assertIn("ownerItem.index == view.index && !ownerItem.is_looted", CPP)
        self.assertIn("item.AllowedForPlayer(owner", CPP)
        self.assertIn("player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", CPP)
        self.assertIn("QuestLootProtection.Enabled = 0", DOC)

    def test_non_owner_cannot_collect_single_copy(self):
        self.assertFalse(modeled_pickup())

    def test_owner_and_release(self):
        self.assertTrue(modeled_pickup(owner="viewer"))
        self.assertTrue(modeled_pickup(owner=None))
        self.assertFalse(modeled_pickup(owner="another"))

    def test_owner_no_longer_needs_or_is_ineligible(self):
        self.assertTrue(modeled_pickup(owner_needs=False))
        self.assertTrue(modeled_pickup(owner_eligible=False))
        self.assertTrue(modeled_pickup(owner_online=False))
        self.assertTrue(modeled_pickup(owner_in_group=False))
        self.assertTrue(modeled_pickup(owner_has_slot=False))

    def test_view_slot_must_map_to_the_exact_quest_item(self):
        self.assertTrue(modeled_pickup(personal=[1, 0], slot=4,
                                       quest_index=0, quest_count=2))
        self.assertFalse(modeled_pickup(personal=[1, 0], slot=5,
                                        quest_index=0, quest_count=2))
        self.assertTrue(modeled_pickup(personal=[-1],
                                       quest_index=0, quest_count=2))
        self.assertTrue(modeled_pickup(personal=[2],
                                       quest_index=0, quest_count=2))

    def test_owner_needs_same_underlying_unlooted_view(self):
        self.assertTrue(modeled_pickup(owner_personal=[(1, False)]))
        self.assertTrue(modeled_pickup(owner_personal=[(0, True)]))
        self.assertTrue(modeled_pickup(owner_personal=[]))
        self.assertFalse(modeled_pickup(owner_personal=[(1, False),
                                                       (0, False)]))
        self.assertTrue(modeled_pickup(owner_personal=[(1, False),
                                                      (0, True)]))

    def test_personal_view_and_owner_guards_present_in_real_cpp(self):
        for expression in (
            "QuestItem const& view = found->second->at(personalSlot);",
            "LootItem const& item = loot.quest_items[view.index];",
            "ownerItem.index == view.index && !ownerItem.is_looted",
            "owner->HasQuestForItem(item.itemid)",
            "item.AllowedForPlayer(owner, loot.sourceWorldObjectGUID)",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, CPP)

    def test_operator_acceptance_plan_identifies_real_gameplay_gates(self):
        for marker in ("QL-01", "QL-05", "QL-10", "QL-15",
                       "read-only", "restorable", "Random Bots"):
            with self.subTest(marker=marker):
                self.assertIn(marker, DOC)

    def test_native_loot_modes(self):
        for method in ("FREE_FOR_ALL", "MASTER_LOOT", "UNKNOWN"):
            with self.subTest(method=method):
                self.assertTrue(modeled_pickup(method=method))
        for method in ("ROUND_ROBIN", "GROUP_LOOT", "NEED_BEFORE_GREED"):
            with self.subTest(method=method):
                self.assertFalse(modeled_pickup(method=method))

    def test_shared_follow_rules_roll_and_nonquest(self):
        for param in (
            "shared", "follow_rules", "blocked", "roll_winner",
            "looted"
        ):
            with self.subTest(param=param):
                self.assertTrue(modeled_pickup(**{param: True}))
        self.assertTrue(modeled_pickup(needs_quest=False))
        self.assertTrue(modeled_pickup(item_template=False))

    def test_packet_and_corpse_scope(self):
        for keyword in ("enabled", "packet", "grouped", "corpse",
                        "same_recipient"):
            with self.subTest(keyword=keyword):
                self.assertTrue(modeled_pickup(**{keyword: False}))
        self.assertTrue(modeled_pickup(malformed=True))

    def test_normal_slot_and_bad_indices(self):
        self.assertTrue(modeled_pickup(slot=3, normal_count=4))
        self.assertTrue(modeled_pickup(slot=5, normal_count=4))
        self.assertTrue(modeled_pickup(personal=[], slot=4))
        self.assertTrue(modeled_pickup(personal=[6], quest_index=6,
                                       quest_count=2))
        self.assertFalse(modeled_pickup(personal=[1], quest_index=1,
                                        quest_count=2))

    def test_hallows_end_config_and_loader_are_preserved(self):
        for line in (
            "NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0",
            "NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier = 3",
            "NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 0",
            "NaxxramasCore.HallowsEnd.SoloFire.DisableSpread = 0",
            "NaxxramasCore.QuestLootProtection.Enabled = 0",
            "NaxxramasCore.QuestLootProtection.Debug = 0",
        ):
            with self.subTest(line=line):
                self.assertEqual(CONFIG.count(line), 1)
        self.assertIn("AddHallowsEndShadeOfTheHorsemanScripts();", LOADER)
        self.assertEqual(LOADER.count("AddQuestLootProtectionScripts();"), 2)

    def test_assignment_mutation_fixture_is_flagged(self):
        mutated = mutated_source_with_assignment()
        self.assertNotEqual(mutated, CPP)
        self.assertIn("loot.roundRobinPlayer = x;", mutated)
        self.assertNotIn("roundRobinPlayer = x;", CPP)
        self.assertTrue(flags_round_robin_write(mutated))
        self.assertTrue(flags_round_robin_write("roundRobinPlayer = x;"))
        self.assertTrue(flags_round_robin_write("roundRobinPlayer=x;"))
        self.assertTrue(flags_round_robin_write("roundRobinPlayer\t= x;"))
        # Differential: the doubled-backslash pattern misses the same write.
        self.assertFalse(flags_round_robin_write(
            mutated, BROKEN_ROUND_ROBIN_ASSIGNMENT))
        self.assertFalse(flags_round_robin_write(
            "roundRobinPlayer = x;", BROKEN_ROUND_ROBIN_ASSIGNMENT))
        self.assertTrue(flags_round_robin_write(
            "roundRobinPlayer\\s=1;", BROKEN_ROUND_ROBIN_ASSIGNMENT))

    def test_comparison_fixture_is_not_flagged(self):
        self.assertIn("loot.roundRobinPlayer == player->GetGUID()", CPP)
        self.assertFalse(flags_round_robin_write(CPP))
        self.assertFalse(flags_round_robin_write(COMPARISON_FIXTURE))
        self.assertFalse(flags_round_robin_write(
            COMPARISON_FIXTURE, BROKEN_ROUND_ROBIN_ASSIGNMENT))
        self.assertFalse(flags_round_robin_write("roundRobinPlayer == owner"))
        self.assertFalse(flags_round_robin_write("roundRobinPlayer==viewer"))

    def test_loot_eligibility_boundaries(self):
        self.assertFalse(modeled_pickup())
        self.assertTrue(modeled_pickup(count=2))
        self.assertTrue(modeled_pickup(needs_quest=False))
        self.assertTrue(modeled_pickup(owner_needs=False))
        self.assertTrue(modeled_pickup(owner_eligible=False))
        self.assertTrue(modeled_pickup(owner_has_slot=False))
        self.assertTrue(modeled_pickup(in_range=False))
        self.assertTrue(modeled_pickup(creature_dead=False))
        self.assertTrue(modeled_pickup(item_template=False))
        for required in (
            "item.count != 1",
            "owner->HasQuestForItem(item.itemid)",
            "item.AllowedForPlayer(owner, loot.sourceWorldObjectGUID)",
            "creature->IsWithinDistInMap(player, INTERACTION_DISTANCE)",
            "creature->isDead()",
        ):
            with self.subTest(required=required):
                self.assertIn(required, CPP)

    def test_group_and_round_robin_boundaries(self):
        for method in ("GROUP_LOOT", "ROUND_ROBIN", "NEED_BEFORE_GREED"):
            with self.subTest(method=method):
                self.assertFalse(modeled_pickup(method=method))
        for method in ("FREE_FOR_ALL", "MASTER_LOOT", "GROUP_LOOT_THRESHOLD", ""):
            with self.subTest(method=method):
                self.assertTrue(modeled_pickup(method=method))
        self.assertTrue(modeled_pickup(grouped=False))
        self.assertTrue(modeled_pickup(same_recipient=False))
        self.assertTrue(modeled_pickup(owner="viewer", viewer="viewer"))
        self.assertFalse(modeled_pickup(owner="someone-else", viewer="viewer"))
        self.assertIn("case GROUP_LOOT:", CPP)
        self.assertIn("case ROUND_ROBIN:", CPP)
        self.assertIn("case NEED_BEFORE_GREED:", CPP)
        self.assertIn("creature->GetLootRecipientGroup() != group", CPP)

    def test_packet_ordering_assumptions_in_module_source(self):
        start = CPP.index("bool CanPacketReceive")
        body = CPP[start:]
        opcode = body.index("packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM")
        size = body.index("packet.size() < 1")
        legacy = body.index("NaxxramasQuestLootProtection::Enabled()")
        hidden = body.index("NaxxramasQuestLootProtection::RestrictHiddenOrdinarySlots()")
        reject_off = body.index("if (!legacyQuestTurnEnabled && !hiddenOrdinarySlotEnabled)")
        copy = body.index("WorldPacket copy(packet)")
        read = body.index("copy >> requestedSlot")
        self.assertLess(opcode, size)
        self.assertLess(size, legacy)
        self.assertLess(legacy, hidden)
        self.assertLess(hidden, reject_off)
        self.assertLess(reject_off, copy)
        self.assertLess(copy, read)
        # New pilot is independent: ON alone must never arm the older
        # quest-turn denial, and either switch OFF remains stock in its
        # own branch.
        self.assertIn("if (!legacyQuestTurnEnabled)\\n            return true;", CPP)
        self.assertIn("if (!hiddenOrdinarySlotEnabled)\\n                return true;", CPP)
        self.assertNotIn("packet >> requestedSlot", CPP)
        # Trailing bytes are not a model bypass. Live packet bytes are not sent.
        self.assertFalse(modeled_pickup(padded=True))
        self.assertTrue(modeled_pickup(malformed=True))
        self.assertIn("packet.size() < 1", CPP)
        self.assertNotIn("packet.size() != 1", CPP)

    def test_release_and_empty_or_incorrect_owner(self):
        self.assertTrue(modeled_pickup(owner=None))
        self.assertTrue(modeled_pickup(owner_online=False))
        self.assertTrue(modeled_pickup(owner_in_group=False))
        self.assertTrue(modeled_pickup(owner_personal=[(1, False)]))
        self.assertTrue(modeled_pickup(owner_personal=[(0, True)]))
        self.assertTrue(modeled_pickup(owner_personal=[]))
        self.assertFalse(modeled_pickup(owner_personal=[(0, False)]))
        self.assertIn("!loot.roundRobinPlayer", CPP)
        self.assertIn("owner->GetGroup() != group", CPP)
        self.assertNotIn("roundRobinPlayer.Clear(", CPP)
        self.assertFalse(flags_round_robin_write(CPP))

    def test_altbot_has_no_source_exemption(self):
        # Synthetic model only. Real Altbot sessions are NOT TESTED.
        self.assertFalse(modeled_pickup(viewer_is_altbot=True))
        self.assertFalse(modeled_pickup(viewer_is_altbot=True, padded=True))
        self.assertTrue(modeled_pickup(viewer_is_altbot=True, owner=None))
        for absent in ("IsAltBot", "PlayerbotAI", "IsRandomBot", "StoreLootItem("):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, CPP)

    def test_not_tested_boundaries_are_documented(self):
        for claim in NOT_TESTED_CLAIMS:
            with self.subTest(claim=claim):
                self.assertIn(claim, DOC)

    def test_workflow_pins_exact_head_and_does_not_upload(self):
        self.assertIn("8daffdabe9202c228e45d833c9a1d399597a15cd", WORKFLOW)
        self.assertIn("037c01418b5d01506917a3db9b44fd56ac5f965c", WORKFLOW)
        self.assertIn("4ff4b5fcc1480348f058c632573143e62d4e3a41", WORKFLOW)
        self.assertIn("github.event.pull_request.head.sha", WORKFLOW)
        self.assertNotIn("actions/upload-artifact", WORKFLOW)
        self.assertNotIn("actions/upload-pages-artifact", WORKFLOW)
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            text = path.read_text("utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotIn("actions/upload-artifact", text)
                self.assertNotIn("actions/upload-pages-artifact", text)

    def test_present_owner_blocks_and_absent_owner_permits(self):
        # Eligible owner, in world, same live map and instance: still blocks.
        self.assertFalse(modeled_pickup(
            owner_in_world=True, owner_same_map=True, owner_same_instance=True))
        self.assertFalse(modeled_pickup())
        # Offline / not found, not in world, other map, other instance: permit.
        self.assertTrue(modeled_pickup(owner=None))
        self.assertTrue(modeled_pickup(owner_online=False))
        self.assertTrue(modeled_pickup(owner_in_world=False))
        self.assertTrue(modeled_pickup(owner_same_map=False))
        self.assertTrue(modeled_pickup(
            owner_same_map=True, owner_same_instance=False))
        self.assertTrue(modeled_pickup(
            owner_in_world=False, owner_same_map=False,
            owner_same_instance=False))

    def test_presence_guards_are_fail_open_in_source(self):
        self.assertTrue(presence_fail_open(CPP))
        start = CPP.index(OWNER_LOOKUP)
        body = CPP[start:]
        order = [
            body.index("if (!owner || owner->GetGroup() != group)"),
            body.index("if (!owner->IsInWorld())"),
            body.index("ownerMap->GetId() != looterMap->GetId()"),
            body.index("owner->GetInstanceId() != player->GetInstanceId()"),
            body.index("ownerMap->GetInstanceId() != corpseMap->GetInstanceId()"),
            body.index("item.AllowedForPlayer(owner, loot.sourceWorldObjectGUID)"),
            body.index("player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)"),
            body.index("return false;"),
        ]
        self.assertEqual(order, sorted(order))
        self.assertIn("Distance and death are not extra denies", CPP)
        self.assertIn("Distance and death are not extra denies", DOC)
        for absent in ("owner->isAlive()", "owner->IsAlive()", "owner->IsWithinDist"):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, CPP)

    def test_presence_guard_mutations_fail_the_contract(self):
        """In-memory edits only. The repository source is not rewritten."""
        self.assertTrue(presence_fail_open(CPP))
        mutations = {
            "not_found_no_longer_permits": (
                "if (!owner || owner->GetGroup() != group)\n"
                "            return true;",
                "if (owner->GetGroup() != group)\n            return true;",
            ),
            "not_in_world_denies": (
                "if (!owner->IsInWorld())\n            return true;",
                "if (!owner->IsInWorld())\n            return false;",
            ),
            "map_guard_removed": (
                "ownerMap->GetId() != looterMap->GetId()",
                "false",
            ),
            "instance_guard_removed": (
                "owner->GetInstanceId() != player->GetInstanceId()",
                "false",
            ),
            "live_map_object_removed": (
                "ownerMap != looterMap || ownerMap != corpseMap",
                "false",
            ),
        }
        for name, (old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertEqual(CPP.count(old), 1)
                mutated = CPP.replace(old, new, 1)
                self.assertNotEqual(mutated, CPP)
                self.assertNotIn(old, mutated)
                self.assertFalse(presence_fail_open(mutated))
        # Model mutations: dropping a guard would block the case that must permit.
        self.assertFalse(modeled_pickup(
            owner_in_world=False, enforce_in_world=False))
        self.assertFalse(modeled_pickup(
            owner_same_map=False, enforce_same_map=False))
        self.assertFalse(modeled_pickup(
            owner_same_map=True, owner_same_instance=False,
            enforce_same_instance=False))
        # The unmutated model still permits those same facts.
        self.assertTrue(modeled_pickup(owner_in_world=False))
        self.assertTrue(modeled_pickup(owner_same_map=False))
        self.assertTrue(modeled_pickup(owner_same_instance=False))

    def test_apt_update_drops_microsoft_source_before_update(self):
        # Run 39778331884 failed apt-get update on packages.microsoft.com 403
        # before CMake. These two jobs drop that source first. No uploads.
        for name in (
            "quest-loot-protection-pinned.yml",
            "ep-module-grimfeather-worldserver-link.yml",
        ):
            text = (ROOT / ".github/workflows" / name).read_text("utf-8")
            with self.subTest(workflow=name):
                self.assertIn("packages.microsoft.com", text)
                self.assertLess(
                    text.index("packages.microsoft.com"),
                    text.index("sudo apt-get update"),
                )
                self.assertIn("sudo rm -f", text)
                self.assertNotIn("actions/upload-artifact", text)
                self.assertNotIn("actions/upload-pages-artifact", text)


if __name__ == "__main__":
    unittest.main()
