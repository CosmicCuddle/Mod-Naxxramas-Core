"""F12 Scarlet Monastery exit path: source-informed SYNTHETIC route model only.

Pinned public core: Grimfeather 8daffdabe9202c228e45d833c9a1d399597a15cd.
MiscHandler.cpp::HandleAreaTriggerOpcode, Player.cpp::TeleportToEntryPoint.
NOT an assertion about the owner's loaded acore_world, exact client DBC, or gameplay.
"""
from dataclasses import dataclass
import unittest

# Public baseline identifiers, never proposed new landing coordinates.
EXIT_TO_ENTRANCE = {604: 610, 606: 612}
EXIT_TO_TARGET_MAP = {604: 0, 606: 0}
SOURCE_MAP = 189


@dataclass(frozen=True)
class Scenario:
    trigger: int = 604
    current_map: int = SOURCE_MAP
    target_map: int = 0
    in_flight: bool = False
    dbc_trigger_exists: bool = True
    within_trigger_radius: bool = True
    script_intercepted: bool = False
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
    This model does NOT simulate preliminary teleport side effects.
    """
    if s.trigger not in EXIT_TO_ENTRANCE:
        return "outside_f12_scope"
    if s.in_flight or not s.dbc_trigger_exists or not s.within_trigger_radius:
        return "ignored_before_dispatch"
    if s.script_intercepted:
        return "script_handled"
    if s.tavern or s.active_battleground or s.outdoor_pvp_intercepted:
        return "other_handler"
    if not s.teleport_row_exists:
        return "no_teleport_row"
    if s.current_map != s.target_map:
        if s.target_entry_denied:
            return "entry_denied"
        if s.lfg_group and s.current_map_is_dungeon:
            if s.entry_point_teleport_succeeded:
                return ("lfg_saved_join_position" if s.saved_join_position_valid
                        else "lfg_homebind")
    return "normal_sql_destination"


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

    def test_lfg_non_dungeon_uses_sql(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, current_map_is_dungeon=False)),
            "normal_sql_destination")

    def test_same_map_destination_skips_lfg_branch(self):
        self.assertEqual(choose_exit_route(Scenario(
            lfg_group=True, target_map=SOURCE_MAP)), "normal_sql_destination")

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

    def test_predictions_never_contain_unapproved_coordinates(self):
        self.assertNotIn("2906.14", choose_exit_route(Scenario()))
        self.assertNotIn("2884.45", choose_exit_route(Scenario(lfg_group=True)))


if __name__ == "__main__":
    unittest.main()
