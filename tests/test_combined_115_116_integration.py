"""Integration contract for the review-only #115 + #116 combination.

CS01 #116 review 5637833818: both PRs edit the same invalid-location
cleanup block in BotRaidConsumables.cpp. In the combined source the path
must be exactly:
  same-player tracker lookup (Player::CustomData, #115)
  -> ClearTrackedAuras(player, tracker, IsCrossMapAuraSafetyEnabled()) (#116)
  -> EraseRaidConsumableTracker(player) (#115)
  -> return, with no use of the invalidated tracker reference.

Source-level only.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"


def strip_comments(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def function_body(code, signature):
    start = code.index(signature)
    return code[start:code.index("\n    }\n", start)]


class CombinedCleanupPath(unittest.TestCase):
    def setUp(self):
        self.code = strip_comments(SOURCE.read_text(encoding="utf-8"))
        self.update = function_body(self.code, "void OnPlayerUpdate(")

    def test_no_shared_tracker_map_remains(self):
        self.assertNotRegex(self.code, r"\bRaidConsumableTrackers\b")
        self.assertIn("RaidConsumableTracker* FindRaidConsumableTracker(", self.code)

    def test_invalid_location_sequence(self):
        block = self.update[self.update.index("if (!IsProfileLocationValid("):]
        block = block[:block.index("return;\n        }") + len("return;")]

        lookup = self.update.index("FindRaidConsumableTracker(")
        clear = block.index("ClearTrackedAuras(")
        erase = block.index("EraseRaidConsumableTracker(player);")
        self.assertLess(lookup, self.update.index("if (!IsProfileLocationValid("))
        self.assertLess(clear, erase)

        call = block[clear:block.index(");", clear) + 2]
        self.assertEqual(re.sub(r"\s+", "", call),
                         "ClearTrackedAuras(player,tracker,IsCrossMapAuraSafetyEnabled());")

        after_erase = block[erase + len("EraseRaidConsumableTracker(player);"):]
        self.assertNotRegex(after_erase, r"\btracker\b")
        self.assertIn("return;", after_erase)

    def test_exactly_one_deferred_clear(self):
        calls = re.findall(r"ClearTrackedAuras\(([^;]*?)\);", self.code, re.S)
        deferred = [c for c in calls if "IsCrossMapAuraSafetyEnabled()" in c]
        self.assertEqual(len(deferred), 1)

    def test_both_features_present(self):
        # #115: CustomData state + locked cooldown.
        self.assertIn("std::mutex ConsumableCooldownLock;", self.code)
        self.assertIn("struct RaidConsumableTracker final : DataMap::Base", self.code)
        # #116: default-off flag, queue and world drain.
        self.assertIn("std::atomic<bool> CrossMapAuraSafetyEnabled{ false };", self.code)
        self.assertIn("NaxxramasCrossMapAura::RemovalQueue CrossMapAuraRemovals;", self.code)
        self.assertIn("new NaxxramasCoreBotRaidConsumablesWorld();", self.code)


if __name__ == "__main__":
    unittest.main()
