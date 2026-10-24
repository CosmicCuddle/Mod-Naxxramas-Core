"""F12 Scarlet Monastery exit path: source-informed SYNTHETIC route model only.

Pinned public core: Grimfeather 8daffdabe9202c228e45d833c9a1d399597a15cd.
MiscHandler.cpp::HandleAreaTriggerOpcode, Player.cpp::TeleportToEntryPoint.
NOT an assertion about the owner's loaded acore_world, exact client DBC, or gameplay.
"""
from dataclasses import dataclass, replace
from typing import Optional
import unittest

# Public baseline identifiers, never proposed new landing coordinates.
EXIT_TO_ENTRANCE = {604: 610, 606: 612}
EXIT_TO_TARGET_MAP = {604: 0, 606: 0}
SOURCE_MAP = 189


@dataclass(frozen=True)
class Scenario:
    trigger: int = 604
    current_map: int = SOURCE_MAP
    # None means the pinned SQL destination, not a guessed map.
    target_map: Optional[int] = None
    in_flight: bool = False
    dbc_trigger_exists: bool = True
    within_trigger_radius: bool = True
    script_intercepted: bool = False
    is_gm: bool = False
    debug_area_triggers: bool = False
    tavern: bool = False
    active_battleground: bool = False
    outdoor_pvp_intercepted: bool = False
    teleport_row_exists: bool = True
    target_entry_denied: bool = False
    lfg_group: bool = False
    current_map_is_dungeon: bool = True
    saved_join_position_valid: bool = True
    entry_point_teleport_succeeded: bool = True


def choose_exit_route(s: Scenario) -> str:
    """Predict only the branch taken, without server calls or world mutation.

    LFG TeleportToEntryPoint returns join position or homebind, but if
    TeleportTo returns false the handler falls through to the SQL target.
    Result labels identify an attempted destination/handler, never arrival;
    a true TeleportTo return can represent a scheduled far teleport.
    This model does NOT simulate preliminary teleport side effects.
    """
    if s.trigger not in EXIT_TO_ENTRANCE:
        return "outside_f12_scope"
    if s.in_flight or not s.dbc_trigger_exists or not s.within_trigger_radius:
        return "ignored_before_dispatch"
    # Core skips AreaTrigger scripts for a GM unless debug is enabled.
    if s.script_intercepted and (not s.is_gm or s.debug_area_triggers):
        return "script_handled"
    if s.tavern or s.active_battleground or s.outdoor_pvp_intercepted:
        return "other_handler"
    if not s.teleport_row_exists:
        return "no_teleport_row"
    target_map = (EXIT_TO_TARGET_MAP[s.trigger]
                  if s.target_map is None else s.target_map)
    if s.current_map != target_map:
        # Pinned map 0 is normally always enterable; this is a generic
        # negative-control branch, not a realistic denial for 604/606.
        if s.target_entry_denied and not s.is_gm:
            return "entry_denied"
        if s.lfg_group and s.current_map_is_dungeon:
            if s.entry_point_teleport_succeeded:
                return ("lfg_saved_join_position" if s.saved_join_position_valid
                        else "lfg_homebind")
    return "normal_sql_destination"


def two_lfg_exits_after_reentry(s: Scenario) -> tuple:
    """Source-informed state sequence, not execution of server teleport.

    On first LFG exit, TeleportToEntryPoint clears the stored join-map ID.
    Assuming the player walks back in without a fresh LFG SetEntryPoint,
    the second exit requests homebind instead. Assumes both teleports
    return true; does not claim either landing actually completed.
    """
    if not s.lfg_group or not s.saved_join_position_valid:
        raise ValueError("Requires an LFG scenario with a saved join point")
    first = choose_exit_route(s)
    second = choose_exit_route(replace(s, saved_join_position_valid=False))
    return first, second


class ScarletExitF12ReadOnly(unittest.TestCase):
    def test_distinct_wing_exits_are_not_swapped(self):
        self.assertEqual(EXIT_TO_ENTRANCE, {604: 610, 606: 612})
        self.assertEqual(EXIT_TO_TARGET_MAP, {604: 0, 606: 0})
        self.assertEqual(SOURCE_MAP, 189)

    def test_cathedral_normal_group_uses_sql(self):
        self.assertEqual(choose_exit_route(Scenario(trigger=604)),
                         "normal_sql_destination")

    def test_armory_normal_group_uses_its_own_sql(self):
        self.assertEqual(choose_exit_route(Scenario(trigger=606)),
                         "normal_sql_destination")

    def test_lfg_dungeon_saved_join_preempts_sql(self):
        self.assertEqual(choose_exit_route(Scenario(lfg_group=True)),
                         "lfg_saved_join_position")

    def test_lfg_invalid_saved_join_uses_homebind(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, saved_join_position_valid=False)), "lfg_homebind")

    def test_failed_entry_point_teleport_falls_back_to_sql(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, entry_point_teleport_succeeded=False)),
            "normal_sql_destination")

    def test_failed_homebind_teleport_can_fall_back_to_sql(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, saved_join_position_valid=False,
            entry_point_teleport_succeeded=False)), "normal_sql_destination")

    # Synthetic mutation only: real 604/606 require map 189 (a dungeon).
    def test_lfg_non_dungeon_uses_sql(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, current_map_is_dungeon=False)),
            "normal_sql_destination")

    def test_same_map_destination_skips_lfg_branch(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, target_map=SOURCE_MAP)), "normal_sql_destination")

    # Generic negative path only: pinned 604/606 target continent map 0.
    def test_entry_denied_precedes_lfg(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, target_entry_denied=True)), "entry_denied")

    def test_script_intercept_precedes_lfg(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, script_intercepted=True)), "script_handled")

    def test_invalid_or_out_of_radius_trigger_never_teleports(self):
        self.assertEqual(choose_exit_route(Scenario(in_flight=True)),
                         "ignored_before_dispatch")
        for key in ("dbc_trigger_exists", "within_trigger_radius"):
            with self.subTest(key=key):
                self.assertEqual(choose_exit_route(Scenario(**{key: False})),
                                 "ignored_before_dispatch")

    def test_earlier_handlers_can_take_control(self):
        for key in ("tavern", "active_battleground", "outdoor_pvp_intercepted"):
            with self.subTest(key=key):
                self.assertEqual(choose_exit_route(Scenario(**{key: True})),
                                 "other_handler")

    def test_missing_teleport_row_prevents_lfg_and_sql(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, teleport_row_exists=False)), "no_teleport_row")

    def test_other_trigger_ids_are_not_reclassified_as_exits(self):
        for trigger in (602, 608, 610, 612, 614, 9999):
            with self.subTest(trigger=trigger):
                self.assertEqual(choose_exit_route(Scenario(trigger=trigger)),
                                 "outside_f12_scope")

    def test_pinned_target_is_used_when_no_override_supplied(self):
        for trigger in (604, 606):
            with self.subTest(trigger=trigger):
                self.assertEqual(EXIT_TO_TARGET_MAP[trigger], 0)
                self.assertEqual(choose_exit_route(Scenario(
                    trigger=trigger, lfg_group=True)),
                    "lfg_saved_join_position")

    def test_gm_skips_normal_areatrigger_script(self):
        self.assertEqual(choose_exit_route(Scenario(
            is_gm=True, script_intercepted=True)), "normal_sql_destination")

    def test_gm_debug_reenables_areatrigger_script(self):
        self.assertEqual(choose_exit_route(Scenario(
            is_gm=True, debug_area_triggers=True,
            script_intercepted=True)), "script_handled")

    def test_gm_skips_generic_map_entry_denial(self):
        self.assertEqual(choose_exit_route(Scenario(
            is_gm=True, target_entry_denied=True)), "normal_sql_destination")

    def test_lfg_reentry_second_exit_uses_homebind(self):
        # Assumes same LFG group, no intervening SetEntryPoint, and the
        # first request was successful. This is not a gameplay assertion.
        self.assertEqual(two_lfg_exits_after_reentry(Scenario(lfg_group=True)),
                         ("lfg_saved_join_position", "lfg_homebind"))

    def test_lfg_sequence_rejects_missing_first_join_point(self):
        with self.assertRaises(ValueError):
            two_lfg_exits_after_reentry(Scenario(
                lfg_group=True, saved_join_position_valid=False))


if __name__ == "__main__":
    unittest.main()
