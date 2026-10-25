"""#155 source contract: Bot Consumables touches no shared container unguarded.

Static source checks only. Native thread tests live in
tests/consumable_cooldown_store.cpp. A pinned Worldserver link is separate.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/BotRaidConsumables.cpp").read_text(encoding="utf-8")
STORE = (ROOT / "src/Systems/ConsumableCooldownStore.h").read_text(encoding="utf-8")


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
    raise ValueError(signature)


class NoUnguardedSharedContainers(unittest.TestCase):
    def test_old_global_maps_are_gone(self):
        for name in ("RaidConsumableTrackers", "ConsumableCooldownUntil",
                     "ConsumableAliveState"):
            with self.subTest(name=name):
                self.assertNotIn(name, SOURCE)

    def test_no_guid_keyed_global_container_remains(self):
        # Any process-wide map/set keyed by player guid is the #155 shape.
        self.assertIsNone(re.search(
            r"std::(unordered_)?(map|set)<\s*ObjectGuid::LowType", SOURCE))

    def test_per_player_state_lives_on_the_player(self):
        self.assertIn("struct RaidConsumableTrackerData : DataMap::Base", SOURCE)
        self.assertIn("struct ConsumableAliveData : DataMap::Base", SOURCE)
        self.assertIn("player->CustomData.Get<RaidConsumableTrackerData>(", SOURCE)
        self.assertIn("master->CustomData.GetDefault<RaidConsumableTrackerData>(", SOURCE)
        self.assertIn("player->CustomData.Get<ConsumableAliveData>(", SOURCE)
        # Keys are std::string constants, so the hot path does not build a
        # temporary string on every player update.
        self.assertIn("std::string const RAID_TRACKER_KEY", SOURCE)
        self.assertIn("std::string const CONSUMABLE_ALIVE_KEY", SOURCE)

    def test_on_player_update_uses_only_its_own_player(self):
        body = function_body(SOURCE, "void OnPlayerUpdate(")
        self.assertIn("player->CustomData.Get<ConsumableAliveData>(", body)
        self.assertIn("FindTracker(player)", body)
        self.assertIn("EraseTracker(player);", body)
        self.assertNotIn("std::lock_guard", body)
        self.assertNotIn("std::mutex", body)

    def test_logout_still_clears_tracker_and_alive_state(self):
        body = function_body(SOURCE, "void OnPlayerLogout(")
        self.assertIn("EraseTracker(player);", body)
        self.assertIn("CONSUMABLE_ALIVE_KEY", body)
        self.assertIn("Keep an unexpired cooldown across logout", body)
        self.assertNotIn("ConsumableCooldowns", body)

    def test_cooldowns_only_through_the_locked_store(self):
        self.assertIn("NaxxramasConsumables::CooldownStore", SOURCE)
        uses = re.findall(r"ConsumableCooldowns\.(\w+)\(", SOURCE)
        self.assertEqual(sorted(set(uses)), ["Remaining", "Reset", "Start"])

    def test_group_reset_collects_guids_before_locking(self):
        body = function_body(SOURCE, "void ResetConsumableCooldownForGroup(")
        self.assertIn("std::vector<ObjectGuid::LowType> reset;", body)
        self.assertLess(body.index("GetFirstMember()"),
                        body.index("ConsumableCooldowns.Reset("))
        self.assertEqual(body.count("ConsumableCooldowns."), 1)
        self.assertTrue(body.rstrip("}").rstrip().endswith("reset);"))

    def test_command_paths_keep_their_semantics(self):
        status = function_body(SOURCE, "static bool HandleStatusCommand(")
        self.assertIn("No consumable profile is currently being tracked.", status)
        clear = function_body(SOURCE, "static bool HandleClearCommand(")
        self.assertLess(clear.index("ClearTrackedAuras("), clear.index("EraseTracker(master);"))
        reset = function_body(SOURCE, "ResetTracker(")
        self.assertLess(reset.index("FindTracker(master)"), reset.index("GetDefault<RaidConsumableTrackerData>"))
        self.assertIn("tracker.FireProtectionOneShots.clear();", reset)


class CooldownStoreHeader(unittest.TestCase):
    def test_every_public_operation_takes_the_lock(self):
        for method in ("uint32_t Remaining(", "void Start(", "void Reset(", "std::size_t Size("):
            with self.subTest(method=method):
                body = function_body(STORE, method)
                self.assertTrue(body.lstrip("{").lstrip().startswith(
                    "std::lock_guard<std::mutex> guard(_lock);"))

    def test_header_is_dependency_free(self):
        includes = re.findall(r'#include [<"]([^>"]+)[>"]', STORE)
        self.assertEqual(sorted(includes),
                         ["cstddef", "cstdint", "mutex", "unordered_map", "vector"])
        for denied in ("Player", "Group", "ChatHandler", "sConfigMgr"):
            self.assertNotIn(denied + "*", STORE)
            self.assertNotIn(denied + "->", STORE)


if __name__ == "__main__":
    unittest.main()
