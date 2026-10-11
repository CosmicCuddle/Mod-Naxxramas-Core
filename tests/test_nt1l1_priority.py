"""Tests for the offline NT1L1 final-rank equivalence guard (not game logic)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_nt1l1_priority import InvalidPlan, compare  # noqa: E402


MAGE = "NT1:vanilla:mage:11-5.12-2.1p-3.1q-3.1r-2.1s-2.1u-3.1v-3.1w-3.1x-1.1z-1.20-1.21-3.22-2.23-5.24-3.2d-1.kl-2.19t-3.1f9-3"
# Source-order replay deliberately tests final-rank equality ONLY. The order
# has NOT been checked against real Talent.dbc row/prerequisite constraints.
NOT_A_GAME_READY_ORDER = MAGE.replace("NT1:", "NT1L1:", 1)


class PriorityComparisonTests(unittest.TestCase):
    def test_full_allocation_equivalence(self):
        points, ranks = compare(MAGE, NOT_A_GAME_READY_ORDER, 60)
        self.assertEqual(points, 51)
        self.assertEqual(sum(ranks.values()), 51)

    def test_level_thirty_budget_projection(self):
        points, ranks = compare(MAGE, NOT_A_GAME_READY_ORDER, 30)
        self.assertEqual(points, 21)
        self.assertEqual(sum(ranks.values()), 21)

    def test_split_rank_increments(self):
        # Splitting 5 ranks of talent 37 into 3+2 must not change final ranks.
        split = NOT_A_GAME_READY_ORDER.replace("11-5.", "11-3.11-2.", 1)
        points, ranks = compare(MAGE, split, 60)
        self.assertEqual(points, 51)
        self.assertEqual(ranks[37], 5)

    def test_mismatched_rank_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "not match|complete"):
            compare(MAGE, NOT_A_GAME_READY_ORDER.replace("11-5.", "11-4.", 1), 60)

    def test_wrong_expansion_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "differ"):
            compare(MAGE, NOT_A_GAME_READY_ORDER.replace("NT1L1:vanilla", "NT1L1:tbc", 1), 30)

    def test_class_mismatch_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "differ"):
            compare(MAGE, NOT_A_GAME_READY_ORDER.replace(":mage:", ":priest:", 1), 30)

    def test_over_rank_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "five ranks"):
            compare(MAGE, NOT_A_GAME_READY_ORDER.replace("11-5.", "11-5.11-1.", 1), 60)

    def test_duplicate_final_nt1_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "Duplicate final-rank"):
            compare(MAGE + ".11-1", NOT_A_GAME_READY_ORDER, 60)

    def test_wrong_source_budget_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "complete"):
            compare(MAGE.replace("11-5.", "11-4.", 1), NOT_A_GAME_READY_ORDER, 60)

    def test_invalid_level_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "outside"):
            compare(MAGE, NOT_A_GAME_READY_ORDER, 61)

    def test_malformed_step_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "Invalid talent entry"):
            compare(MAGE, NOT_A_GAME_READY_ORDER + ".", 60)

    def test_unknown_version_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "Expected NT1L1"):
            compare(MAGE, NOT_A_GAME_READY_ORDER.replace("NT1L1", "NT1L2", 1), 60)


if __name__ == "__main__":
    unittest.main()
