"""Source contract for #114: no unsynchronised shared per-player maps.

Player hooks (OnPlayerUpdate, OnPlayerBeforeUpdate, OnPlayerAfterUpdate,
OnPlayerUpdateZone, battleground hooks) run on parallel map threads when
MapUpdate.Threads > 1. Per-player state must live in Player::CustomData,
and the one genuinely cross-player map (the consumables command cooldown)
must only be touched under its mutex.

This is a source-level contract. It does not prove the absence of data
races at runtime.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "src/Systems/HonorOverflow.cpp": [
        "NaxxramasCore.HonorOverflow.Snapshot",
        "NaxxramasCore.HonorOverflow.BattlegroundSummary",
    ],
    "src/Systems/ForcedPvP.cpp": [
        "NaxxramasCore.ForcedPvP.State",
    ],
    "src/Systems/BotRaidConsumables.cpp": [
        "NaxxramasCore.BotRaidConsumables.Tracker",
        "NaxxramasCore.BotRaidConsumables.AliveState",
    ],
    "src/Class/Warrior/WarriorRendFlurryBots.cpp": [
        "NaxxramasCore.RendFlurryBots.UpdateTimer",
    ],
    "src/Class/Warlock/WarlockWrackBots.cpp": [
        "NaxxramasCore.WrackBots.UpdateTimer",
    ],
}

REMOVED_CONTAINERS = [
    "HonorSnapshots",
    "BattlegroundHonorSummaries",
    "ForcedPvPStates",
    "RaidConsumableTrackers",
    "UpdateTimers",
]

LOCKED_MAP = "ConsumableCooldownUntil"
LOCK_NAME = "ConsumableCooldownLock"
CONSUMABLES = "src/Systems/BotRaidConsumables.cpp"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def strip_comments(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def enclosing_function(source, pos):
    """Return (start, end) of the 4-space-indented function holding pos."""
    starts = [m.start() for m in re.finditer(r"\n    [A-Za-z][^\n;]*\(\n", source)]
    starts += [m.start() for m in re.finditer(r"\n    [A-Za-z][^\n;]*\([^\n;]*\)\n    \{", source)]
    start = max(s for s in starts if s < pos)
    end = source.index("\n    }\n", pos)
    return start, end


class PerPlayerStateContract(unittest.TestCase):
    def test_no_guid_keyed_namespace_map_except_locked_one(self):
        for rel in FILES:
            code = strip_comments(read(rel))
            maps = re.findall(
                r"std::unordered_map<\s*ObjectGuid::LowType\s*,[^>]*>\s*(\w+)\s*;",
                code)
            expected = [LOCKED_MAP] if rel == CONSUMABLES else []
            self.assertEqual(maps, expected, rel)

    def test_removed_containers_are_gone(self):
        for rel in FILES:
            code = strip_comments(read(rel))
            for name in REMOVED_CONTAINERS:
                self.assertNotRegex(code, r"\b%s\b" % name, (rel, name))

    def test_state_uses_player_custom_data(self):
        for rel, keys in FILES.items():
            code = strip_comments(read(rel))
            self.assertIn("CustomData.", code, rel)
            self.assertRegex(code, r"struct \w+ final : DataMap::Base", rel)
            for key in keys:
                self.assertEqual(code.count('"%s"' % key), 1, (rel, key))

    def test_custom_data_keys_are_unique_across_module(self):
        seen = {}
        for path in (ROOT / "src").rglob("*.cpp"):
            for key in re.findall(r'"(NaxxramasCore\.[A-Za-z.]+)"',
                                  strip_comments(path.read_text(encoding="utf-8"))):
                if "CustomData" not in path.read_text(encoding="utf-8"):
                    continue
                seen.setdefault(key, set()).add(path.name)
        for keys in FILES.values():
            for key in keys:
                self.assertEqual(len(seen.get(key, ())), 1, key)

    def test_logout_still_drops_per_player_state(self):
        for rel in FILES:
            code = strip_comments(read(rel))
            logout = re.search(r"void OnPlayer(?:Before)?Logout\(.*?\n    }\n", code, re.S)
            self.assertIsNotNone(logout, rel)
            body = logout.group(0)
            self.assertTrue(
                "CustomData.Erase(" in body
                or "EraseRaidConsumableTracker(" in body
                or "LeaveForcedPvP(player, true)" in body,
                rel)


def function_body(code, signature):
    """Text of the function starting at 'signature' up to its closing brace."""
    start = code.index(signature)
    return code[start:code.index("\n    }\n", start)]


class SemanticGateContract(unittest.TestCase):
    """CS01 #114 review gates G1-G5: presence must stay distinct from a
    default-constructed value, so GetDefault is only used where the old
    code created an entry."""

    def test_g1_first_honor_snapshot_seeds_without_payout(self):
        code = strip_comments(read("src/Systems/HonorOverflow.cpp"))
        body = function_body(code, "void ProcessHonorOverflow(")
        self.assertNotIn("GetDefault", body)
        seed = body.index("if (!stored)")
        block = body[seed:body.index("}", seed)]
        self.assertIn("StoreHonorSnapshot(player);", block)
        self.assertIn("return;", block)
        self.assertLess(seed, body.index("ModifyMoney"))
        login = function_body(code, "void OnPlayerLogin(")
        self.assertIn("StoreHonorSnapshot(player);", login)
        self.assertIn("CustomData.Erase(BG_SUMMARY_KEY)", login)

    def test_g2_forced_pvp_captures_preference_only_on_first_entry(self):
        code = strip_comments(read("src/Systems/ForcedPvP.cpp"))
        enter = function_body(code, "void EnterForcedPvP(")
        guard = enter.index("if (!player->CustomData.Get<ForcedPvPState>")
        block = enter[guard:enter.index("}", guard)]
        self.assertEqual(enter.count("GetDefault"), 1)
        self.assertIn("GetDefault<ForcedPvPState>", block)
        self.assertIn("WasManuallyPvP = player->HasPlayerFlag(PLAYER_FLAGS_IN_PVP)", block)
        self.assertIn("inserted = true;", block)
        self.assertIn("if (inserted && ForcedPvPNotify", enter)
        leave = function_body(code, "void LeaveForcedPvP(")
        self.assertNotIn("GetDefault", leave)
        self.assertIn("if (!state)", leave)
        self.assertLess(leave.index("CustomData.Erase(FORCED_PVP_STATE_KEY)"),
                        leave.index("RemovePlayerFlag"))
        self.assertIn("LeaveForcedPvP(player, true);",
                      function_body(code, "void OnPlayerBeforeLogout("))

    def test_g3_tracker_absent_is_not_an_empty_tracker(self):
        code = strip_comments(read(CONSUMABLES))
        self.assertEqual(code.count("GetDefault<RaidConsumableTracker>"), 1)
        reset = function_body(code, "ResetTracker(")
        self.assertLess(reset.index("ClearTrackedAuras("),
                        reset.index("GetDefault<RaidConsumableTracker>"))
        status = function_body(code, "static bool HandleStatusCommand(")
        self.assertIn("if (!trackerPtr)", status)
        self.assertIn("No consumable profile is currently being tracked.", status)
        clear = function_body(code, "static bool HandleClearCommand(")
        self.assertLess(clear.index("ClearTrackedAuras("),
                        clear.index("EraseRaidConsumableTracker("))
        update = function_body(code, "void OnPlayerUpdate(")
        self.assertIn("if (!trackerPtr)", update)
        self.assertLess(update.index("ClearTrackedAuras(player, tracker);"),
                        update.index("EraseRaidConsumableTracker(player);"))

    def test_g5_bot_timers_start_at_zero_and_keep_interval(self):
        for rel, interval in (("src/Class/Warrior/WarriorRendFlurryBots.cpp", 200),
                              ("src/Class/Warlock/WarlockWrackBots.cpp", 100)):
            code = strip_comments(read(rel))
            self.assertIn("uint32 Timer = 0;", code, rel)
            self.assertIn("constexpr uint32 UPDATE_INTERVAL_MS = %d;" % interval, code, rel)
            self.assertEqual(code.count("GetDefault<UpdateTimerState>"), 1, rel)
            self.assertIn("timer = UPDATE_INTERVAL_MS;", code, rel)


class CrossPlayerCooldownLockContract(unittest.TestCase):
    def setUp(self):
        self.code = strip_comments(read(CONSUMABLES))

    def test_mutex_declared(self):
        self.assertIn("#include <mutex>", read(CONSUMABLES))
        self.assertIn("std::mutex %s;" % LOCK_NAME, self.code)

    def test_every_access_is_under_the_lock(self):
        accesses = [m.start() for m in re.finditer(r"\b%s\s*(?:\.|\[)" % LOCKED_MAP, self.code)]
        self.assertGreaterEqual(len(accesses), 5)
        for pos in accesses:
            start, _ = enclosing_function(self.code, pos)
            body = self.code[start:pos]
            self.assertRegex(
                body,
                r"std::lock_guard<std::mutex>\s+lock\(\s*%s\s*\)" % LOCK_NAME,
                self.code[start:start + 120])

    def test_no_game_calls_while_holding_the_lock(self):
        for m in re.finditer(r"std::lock_guard<std::mutex>\s+lock\(\s*%s\s*\)\s*;" % LOCK_NAME,
                             self.code):
            _, end = enclosing_function(self.code, m.start())
            locked = self.code[m.end():end]
            calls = [c for c in re.findall(r"(\w+)->", locked) if c != "itr"]
            self.assertEqual(calls, [], locked)
            self.assertNotIn("ChatHandler", locked)
            self.assertNotIn("GetGroup", locked)
            self.assertNotIn("GetConsumableNow(", locked)
            self.assertNotIn("return itr", locked)
            self.assertNotIn("&", re.sub(r"&&", "", locked))

    def test_group_reset_still_clears_every_member(self):
        section = self.code.split("void ResetConsumableCooldownForGroup(", 1)[1]
        section = section.split("\n    }\n", 1)[0]
        self.assertIn("group->GetFirstMember()", section)
        self.assertIn("deadPlayer->GetGUID()", section)
        self.assertIn("for (ObjectGuid::LowType guid : guids)", section)
        self.assertLess(section.index("GetFirstMember"), section.index("lock_guard"))

    def test_cooldown_survives_logout(self):
        logout = re.search(r"void OnPlayerLogout\(.*?\n    }\n", self.code, re.S).group(0)
        self.assertNotIn(LOCKED_MAP, logout)


if __name__ == "__main__":
    unittest.main()
