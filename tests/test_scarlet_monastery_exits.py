"""Source contract for the F12 Scarlet Monastery exits prototype.

Static checks of src/Systems/ScarletMonasteryExits.cpp, ScarletExitPolicy.h,
the loader and conf.dist. Behaviour of the policy itself is covered by the
native tests in tests/scarlet_exit_policy.cpp. Nothing here runs a server.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/ScarletMonasteryExits.cpp").read_text(encoding="utf-8")
POLICY = (ROOT / "src/Systems/ScarletExitPolicy.h").read_text(encoding="utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")


def function_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:i + 1]
    raise AssertionError("unbalanced braces for " + signature)


class ConfigAndLoader(unittest.TestCase):
    def test_master_switch_defaults_off(self):
        self.assertRegex(CONF, r"(?m)^NaxxramasCore\.ScarletExits\.Enabled = 0$")

    def test_sub_switches_present(self):
        self.assertRegex(CONF, r"(?m)^NaxxramasCore\.ScarletExits\.UseVanillaDoorTargets = 1$")
        self.assertRegex(CONF, r"(?m)^NaxxramasCore\.ScarletExits\.RouteDungeonFinderExits = 0$")

    def test_dungeon_finder_routing_defaults_off_everywhere(self):
        # Owner scope (#48 6386621902): Dungeon Finder is out of scope and
        # must not change just because the master switch is on.
        self.assertIn('"NaxxramasCore.ScarletExits.RouteDungeonFinderExits", false', CPP)
        self.assertIn("bool RouteDungeonFinderExits = false;", POLICY)
        self.assertNotIn('"NaxxramasCore.ScarletExits.RouteDungeonFinderExits", true', CPP)

    def test_code_default_matches_conf(self):
        self.assertIn('"NaxxramasCore.ScarletExits.Enabled", false', CPP)

    def test_loader_declares_and_calls_once(self):
        self.assertEqual(LOADER.count("void AddScarletMonasteryExitScripts();"), 1)
        self.assertEqual(LOADER.count("    AddScarletMonasteryExitScripts();"), 1)


class StartupOnlyConfig(unittest.TestCase):
    """Same fix as #133 / #144: no ConfigMgr read on the packet path."""

    def test_config_manager_only_in_reader(self):
        reader = function_body(CPP, "ExitsConfig ReadConfig()")
        self.assertEqual(reader.count("sConfigMgr->"), 3)
        self.assertEqual(CPP.count("sConfigMgr->"), 3)
        self.assertEqual(CPP.count("ReadConfig()"), 2)  # definition + the hook

    def test_snapshot_written_once_at_startup(self):
        hook = function_body(CPP, "void OnAfterConfigLoad(bool reload) override")
        self.assertIn("ExitsConfig const loaded = ReadConfig();", hook)
        self.assertIn("if (!reload)", hook)
        self.assertEqual(len(re.findall(r"StartupConfig\s*=[^=]", CPP)), 1)
        self.assertIn('WorldScript("NaxxramasScarletExitsConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD })', CPP)

    def test_packet_path_reads_snapshot_only(self):
        for name in ("bool Enabled()", "bool UseDoorTargets()", "bool RouteDungeonFinderExits()"):
            with self.subTest(name=name):
                self.assertNotIn("sConfigMgr", function_body(CPP, name))
        self.assertNotIn("sConfigMgr", function_body(CPP, "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override"))

    def test_both_scripts_registered_once(self):
        add = function_body(CPP, "void AddScarletMonasteryExitScripts()")
        self.assertEqual(add.count("new NaxxramasScarletExitsConfig();"), 1)
        self.assertEqual(add.count("new NaxxramasScarletExitsScript();"), 1)


class PacketHook(unittest.TestCase):
    BODY = function_body(CPP, "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override")

    def test_registers_only_the_packet_hook(self):
        self.assertIn("{ SERVERHOOK_CAN_PACKET_RECEIVE }", CPP)

    def test_fast_exit_for_other_opcodes_comes_first(self):
        first = self.BODY.index("packet.GetOpcode() != CMSG_AREATRIGGER")
        self.assertLess(first, self.BODY.index("Enabled()"))
        self.assertLess(first, self.BODY.index("GetPlayer()"))

    def test_short_packet_is_left_to_the_core(self):
        self.assertIn("packet.size() < 4", self.BODY)

    def test_reads_from_a_copy_without_moving_native_cursor(self):
        self.assertIn("WorldPacket copy(packet);", self.BODY)
        self.assertIn("copy.rpos(0);", self.BODY)
        self.assertNotIn("packet >>", self.BODY)
        self.assertNotIn("packet.rpos(", self.BODY)

    def test_hook_returns_false_only_when_handled(self):
        self.assertIn("return !NaxxramasScarletExits::Handle(player, triggerId);", self.BODY)


class HandleFailsClosed(unittest.TestCase):
    BODY = function_body(CPP, "bool Handle(Player* player, uint32 triggerId)")

    def test_only_door_target_triggers_are_considered(self):
        self.assertIn("FindDoorTarget(triggerId)", self.BODY)

    def test_stock_route_returns_false(self):
        self.assertIn("if (route == Route::Stock || !row)\n            return false;", self.BODY)

    def test_teleport_uses_native_option_and_exit_map(self):
        self.assertIn("player->TeleportTo(EXIT_MAP,", self.BODY)
        self.assertIn("TELE_TO_NOT_LEAVE_TRANSPORT", self.BODY)

    def test_refused_teleport_still_blocks_native_handler(self):
        after = self.BODY[self.BODY.index("player->TeleportTo("):]
        self.assertRegex(after, r"Tell\(player, \"[^\"]+\"\);\s*\n\s*return true;\s*\}$")
        self.assertNotIn("return player->TeleportTo", CPP)
        self.assertNotIn("return !player->TeleportTo", CPP)


class Gathering(unittest.TestCase):
    BODY = function_body(CPP, "Facts Gather(Player* player, uint32 triggerId, DoorTarget const& door,")

    def test_mirrors_native_early_exits(self):
        for needle in ("IsInFlight()", "isDebugAreaTriggers", "GetAreaTrigger(triggerId)",
                       "IsTavernAreaTrigger", "IsInAreaTriggerRadius(at, 0.f)",
                       "GetAreaTriggerScriptId(triggerId)", "GetQuestForAreaTrigger(triggerId)",
                       "STATUS_IN_PROGRESS", "GetOutdoorPvP()", "GetAreaTriggerTeleport(triggerId)",
                       "PlayerCannotEnter(row->target_mapId, player, false)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.BODY)

    def test_dungeon_finder_detection_matches_native(self):
        self.assertIn("group->isLFGGroup()", self.BODY)
        self.assertIn("player->GetMap()->IsDungeon()", self.BODY)

    def test_door_target_validated_against_live_rows(self):
        self.assertIn("DoorTargetIsSafe(door)", self.BODY)
        safe = function_body(CPP, "bool DoorTargetIsSafe(DoorTarget const& door)")
        self.assertIn("MapMgr::IsValidMapCoord(EXIT_MAP", safe)
        # The witness loop lives in the policy header, where the native
        # tests execute it with a fake lookup (CS02 #125 review).
        self.assertIn("return DoorTargetIsSafeWith(door, ShapeOf);", safe)
        self.assertNotIn("TargetIsSafe(p,", safe)
        loop = function_body(POLICY, "inline bool DoorTargetIsSafeWith(DoorTarget const& door, ShapeLookup&& shapeOf)")
        self.assertIn("for (uint32_t entrance : SM_ENTRANCES)", loop)
        self.assertIn("return TargetIsSafe(door.Where, own, others, count);", loop)


class Boundaries(unittest.TestCase):
    def test_no_database_or_sql_access(self):
        for needle in ("Database", "Execute(", "Query(", "PreparedStatement"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, CPP)
                self.assertNotIn(needle, POLICY)

    def test_no_rejected_seams(self):
        for needle in ("ALEScript", "CanAreaTrigger", "OnPlayerBeforeTeleport",
                       "TeleportToEntryPoint", "SetEntryPoint"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, CPP)

    def test_policy_is_dependency_free(self):
        includes = re.findall(r'#include [<"]([^>"]+)[>"]', POLICY)
        self.assertEqual(sorted(includes), ["cmath", "cstddef", "cstdint"])

    def test_door_targets_are_the_reviewed_vanilla_points(self):
        self.assertIn("{ 604, 610, { 2915.13f, -823.637f, 160.327f, 3.49066f } }", POLICY)
        self.assertIn("{ 606, 612, { 2885.96f, -835.802f, 160.327f, 0.349066f } }", POLICY)
        self.assertEqual(POLICY.count("{ 60"), 2)

    def test_every_other_entrance_is_a_required_witness(self):
        body = function_body(POLICY, "inline bool TargetIsSafe(Point const& target, TriggerShape const& own,")
        self.assertIn("if (!other.Present || other.Map != EXIT_MAP)\n                return false;", body)
        self.assertNotIn("continue;", body)

    def test_entrances_cover_all_four_wings(self):
        self.assertIn("SM_ENTRANCES[] = { 45, 610, 612, 614 }", POLICY)


if __name__ == "__main__":
    unittest.main()
