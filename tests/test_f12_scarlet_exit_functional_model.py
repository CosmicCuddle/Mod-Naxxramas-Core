"""F12 Scarlet Monastery Cathedral/Armory exits: S1 synthetic model only.

Geometry uses public baseline rows (Grimfeather AzerothCore 8daffda) and
Vanilla-core reference rows (MaNGOS Zero database 325948a, cMaNGOS
classic-db 4e3d118). The decision model mirrors the PROPOSED handler in
docs/research/F12-SCARLET-EXIT-FUNCTIONAL-S1.md. Nothing here calls
AzerothCore, launches a server or reads the owner's database.
"""
from dataclasses import dataclass, replace
import math
import unittest

# Outdoor entrance triggers on map 0: (x, y, z, radius). areatrigger.sql.
ENTRANCES = {
    45: (2924.38, -798.429, 161.611, 8.0),   # Graveyard
    610: (2925.18, -820.545, 161.634, 8.0),  # Cathedral
    612: (2877.98, -839.267, 163.049, 6.0),  # Armory
    614: (2859.73, -824.91, 162.083, 8.0),   # Library
}
EXIT_TO_ENTRANCE = {602: 45, 604: 610, 606: 612, 608: 614}

# AzerothCore baseline exit rows (areatrigger_teleport.sql L71-74).
AC_ROWS = {
    602: (0, 2913.92, -802.404, 160.333, 3.50405),
    604: (0, 2906.14, -813.772, 160.333, 1.95739),
    606: (0, 2884.45, -822.01, 160.333, 1.95268),
    608: (0, 2870.9, -820.164, 160.333, 0.387856),
}
# Vanilla-core reference rows (identical in both MaNGOS-lineage sources).
VANILLA_ROWS = {
    602: (0, 2915.34, -801.58, 160.333, 3.49066),
    604: (0, 2915.13, -823.637, 160.327, 3.49066),
    606: (0, 2885.96, -835.802, 160.327, 0.349066),
    608: (0, 2869.32, -820.818, 160.333, 0.349066),
}
HANDLED_TRIGGERS = (604, 606)
SAFETY_MARGIN_YD = 1.0


def dist3(a, b):
    return math.dist(a[:3], b[:3])


def facing_error_deg(row, entrance):
    """Degrees between the landing facing and 'directly away from door'."""
    _, x, y, _, o = row
    ex, ey, _, _ = entrance
    away = math.atan2(y - ey, x - ex)
    diff = math.degrees(o - away)
    return abs((diff + 180.0) % 360.0 - 180.0)


def target_is_safe(trigger, row, entrances=ENTRANCES):
    """Proposed step-5 validation: map 0, outside own entrance + margin,
    and nearest its own entrance (no wing swap)."""
    if row is None or row[0] != 0:
        return False
    own = EXIT_TO_ENTRANCE[trigger]
    if own not in entrances:
        return False
    point = row[1:4]
    own_d = dist3(point, entrances[own])
    if own_d <= entrances[own][3] + SAFETY_MARGIN_YD:
        return False
    return all(own_d < dist3(point, e)
               for k, e in entrances.items() if k != own)


@dataclass(frozen=True)
class Scenario:
    trigger: int = 604
    enabled: bool = True
    use_vanilla_targets: bool = True
    route_lfg: bool = True
    has_player: bool = True
    packet_bytes: int = 4
    in_flight: bool = False
    trigger_known: bool = True
    in_radius: bool = True
    bound_script: bool = False
    quest_trigger: bool = False
    tavern: bool = False
    battleground_active: bool = False
    outdoor_pvp: bool = False
    row_exists: bool = True
    row_map: int = 0
    already_on_exit_map: bool = False
    entry_denied: bool = False
    gm_debug_areatriggers: bool = False
    lfg_in_dungeon: bool = False
    vanilla_target_valid: bool = True
    teleport_accepted: bool = True


def decide(s: Scenario) -> str:
    """Returns 'stock', 'door_target' or 'live_row'. 'door_target' and
    'live_row' mean the module requested that teleport and blocked the
    stock handler; they never mean the player arrived."""
    if not s.enabled or not s.has_player or s.packet_bytes < 4:
        return "stock"
    if s.trigger not in HANDLED_TRIGGERS:
        return "stock"
    if (s.in_flight or s.gm_debug_areatriggers or not s.trigger_known
            or not s.in_radius or s.bound_script or s.quest_trigger
            or s.tavern or s.battleground_active or s.outdoor_pvp
            or not s.row_exists or s.row_map != 0
            or s.already_on_exit_map or s.entry_denied):
        return "stock"
    use_door = s.use_vanilla_targets and s.vanilla_target_valid
    if s.lfg_in_dungeon:
        if not s.route_lfg:
            return "stock"
    elif not use_door:
        # Normal party: the live row is exactly what stock does anyway.
        return "stock"
    route = "door_target" if use_door else "live_row"
    # Fail closed: an eligible exit never falls back to the stock handler.
    return route if s.teleport_accepted else "blocked"


def lfg_join_position_sequence(events, enabled=True, route_lfg=True):
    """Join-position lifecycle model (LFGMgr TeleportPlayer, MiscHandler).

    State: whether a stored join position exists. Returns the list of
    destinations requested. Events:
      'exit'        - step on 604/606 from inside, in an LFG group
      'ui_out'      - Dungeon Finder "teleport out" from inside
      'ui_in'       - Dungeon Finder "teleport in" from outside
      'walk_in'     - walk back in through the door
    """
    stored = True
    out = []
    for event in events:
        if event == "exit":
            if enabled and route_lfg:
                out.append("door_target")      # stored position untouched
            else:
                out.append("join_position" if stored else "homebind")
                stored = False                  # TeleportToEntryPoint clears it
        elif event == "ui_out":
            out.append("join_position" if stored else "homebind")
            stored = False
        elif event == "ui_in":
            stored = True                       # SetEntryPoint() outside a dungeon
            out.append("dungeon")
        elif event == "walk_in":
            out.append("dungeon")
        else:
            raise ValueError(event)
    return out


class GeometryEvidence(unittest.TestCase):
    def test_control_wings_follow_door_pattern_in_both_sources(self):
        for rows in (AC_ROWS, VANILLA_ROWS):
            for trig in (602, 608):
                with self.subTest(trig=trig):
                    own = ENTRANCES[EXIT_TO_ENTRANCE[trig]]
                    self.assertLess(dist3(rows[trig][1:4], own), 13.0)
                    self.assertLess(facing_error_deg(rows[trig], own), 5.0)

    def test_baseline_cathedral_and_armory_break_the_pattern(self):
        for trig in HANDLED_TRIGGERS:
            with self.subTest(trig=trig):
                own = ENTRANCES[EXIT_TO_ENTRANCE[trig]]
                self.assertGreater(dist3(AC_ROWS[trig][1:4], own), 18.0)
                self.assertGreater(facing_error_deg(AC_ROWS[trig], own), 40.0)

    def test_vanilla_cathedral_and_armory_follow_the_pattern(self):
        for trig in HANDLED_TRIGGERS:
            with self.subTest(trig=trig):
                own = ENTRANCES[EXIT_TO_ENTRANCE[trig]]
                self.assertLess(dist3(VANILLA_ROWS[trig][1:4], own), 11.0)
                self.assertLess(facing_error_deg(VANILLA_ROWS[trig], own), 5.0)

    def test_vanilla_targets_pass_proposed_validation(self):
        for trig in HANDLED_TRIGGERS:
            with self.subTest(trig=trig):
                self.assertTrue(target_is_safe(trig, VANILLA_ROWS[trig]))

    def test_validation_rejects_point_inside_own_entrance(self):
        ex, ey, ez, _ = ENTRANCES[610]
        self.assertFalse(target_is_safe(604, (0, ex + 2.0, ey, ez, 0.0)))

    def test_validation_rejects_swapped_wings(self):
        self.assertFalse(target_is_safe(604, VANILLA_ROWS[606]))
        self.assertFalse(target_is_safe(606, VANILLA_ROWS[604]))

    def test_validation_rejects_wrong_map_and_missing(self):
        self.assertFalse(target_is_safe(604, (1,) + VANILLA_ROWS[604][1:]))
        self.assertFalse(target_is_safe(604, None))

    def test_validation_fails_closed_when_entrance_row_missing(self):
        partial = {k: v for k, v in ENTRANCES.items() if k != 610}
        self.assertFalse(target_is_safe(604, VANILLA_ROWS[604], partial))


class DecisionModel(unittest.TestCase):
    def test_s01_flag_off_is_stock(self):
        self.assertEqual(decide(Scenario(enabled=False)), "stock")

    def test_s02_other_triggers_are_stock(self):
        for trig in (602, 608, 610, 612, 614, 45, 4436, 9999):
            with self.subTest(trig=trig):
                self.assertEqual(decide(Scenario(trigger=trig)), "stock")

    def test_s03_native_early_exits_stay_stock(self):
        for key, val in (("in_flight", True), ("trigger_known", False),
                         ("in_radius", False), ("has_player", False),
                         ("packet_bytes", 3)):
            with self.subTest(key=key):
                self.assertEqual(decide(Scenario(**{key: val})), "stock")

    def test_s04_s05_s06_other_handlers_and_rows_stay_stock(self):
        for key, val in (("bound_script", True), ("quest_trigger", True),
                         ("tavern", True), ("battleground_active", True),
                         ("outdoor_pvp", True), ("row_exists", False),
                         ("row_map", 189)):
            with self.subTest(key=key):
                self.assertEqual(decide(Scenario(**{key: val})), "stock")

    def test_s07_normal_party_uses_door_target(self):
        for trig in HANDLED_TRIGGERS:
            with self.subTest(trig=trig):
                self.assertEqual(decide(Scenario(trigger=trig)), "door_target")

    def test_s08_normal_party_targets_off_is_stock(self):
        self.assertEqual(decide(Scenario(use_vanilla_targets=False)), "stock")

    def test_s09_lfg_routes_to_door(self):
        self.assertEqual(decide(Scenario(lfg_in_dungeon=True)), "door_target")

    def test_s09b_lfg_with_targets_off_uses_live_row(self):
        self.assertEqual(decide(Scenario(
            lfg_in_dungeon=True, use_vanilla_targets=False)), "live_row")

    def test_s03b_more_native_early_exits_stay_stock(self):
        for key in ("already_on_exit_map", "entry_denied",
                    "gm_debug_areatriggers"):
            with self.subTest(key=key):
                self.assertEqual(decide(Scenario(**{key: True})), "stock")

    def test_s10_lfg_routing_off_is_stock(self):
        self.assertEqual(decide(Scenario(
            lfg_in_dungeon=True, route_lfg=False)), "stock")

    def test_s11_second_lfg_exit_still_door(self):
        first = Scenario(lfg_in_dungeon=True)
        second = replace(first)  # join position is irrelevant to the module
        self.assertEqual((decide(first), decide(second)),
                         ("door_target", "door_target"))

    def test_s12_invalid_door_target_uses_live_row_for_lfg(self):
        self.assertEqual(decide(Scenario(
            lfg_in_dungeon=True, vanilla_target_valid=False)), "live_row")

    def test_s12b_invalid_door_target_normal_party_is_stock(self):
        self.assertEqual(decide(Scenario(vanilla_target_valid=False)), "stock")

    def test_s13_refused_teleport_fails_closed(self):
        for lfg in (False, True):
            with self.subTest(lfg=lfg):
                self.assertEqual(decide(Scenario(
                    lfg_in_dungeon=lfg, teleport_accepted=False)), "blocked")

    def test_s13b_refusal_never_reaches_join_position_or_homebind(self):
        result = decide(Scenario(lfg_in_dungeon=True, teleport_accepted=False))
        self.assertNotIn(result, ("stock", "join_position", "homebind"))

    def test_s13c_ineligible_inputs_still_stock_when_teleport_would_fail(self):
        for key, val in (("enabled", False), ("trigger", 602),
                         ("in_radius", False), ("route_lfg", False)):
            with self.subTest(key=key):
                self.assertEqual(decide(Scenario(
                    lfg_in_dungeon=True, teleport_accepted=False,
                    **{key: val})), "stock")


class JoinPositionLifecycle(unittest.TestCase):
    def test_s18_exit_reenter_exit_stays_at_door(self):
        self.assertEqual(
            lfg_join_position_sequence(["exit", "walk_in", "exit"]),
            ["door_target", "dungeon", "door_target"])

    def test_s19_ui_teleport_out_after_module_exit_uses_queue_spot(self):
        self.assertEqual(
            lfg_join_position_sequence(["exit", "walk_in", "ui_out"]),
            ["door_target", "dungeon", "join_position"])

    def test_s20_ui_teleport_in_refreshes_stored_position(self):
        self.assertEqual(
            lfg_join_position_sequence(
                ["exit", "ui_in", "ui_out"]),
            ["door_target", "dungeon", "join_position"])

    def test_s21_switch_off_returns_to_stock_lifecycle(self):
        self.assertEqual(
            lfg_join_position_sequence(["exit", "walk_in", "exit"],
                                       enabled=False),
            ["join_position", "dungeon", "homebind"])

    def test_stock_baseline_second_exit_goes_home(self):
        self.assertEqual(
            lfg_join_position_sequence(["exit", "walk_in", "exit"],
                                       route_lfg=False),
            ["join_position", "dungeon", "homebind"])


class EraScope(unittest.TestCase):
    def test_s22_decision_has_no_era_input(self):
        # The proposed handler is era-independent by design (doc, Era scope).
        self.assertNotIn("era", Scenario.__dataclass_fields__)
        self.assertNotIn("vanilla_stage", Scenario.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
