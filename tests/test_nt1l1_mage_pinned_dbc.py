"""Pinned Mage Talent.dbc-snapshot regression tests for the *read-only* NT1L1 prototype.

These tests verify each rank step of one deliberately reviewed Frost-first
priority against the 2026-10-08 Resource Hub DBC snapshot. They do NOT compile
AzerothCore or confirm that the running server has identical DBC data.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_nt1l1_priority import InvalidPlan, compare  # noqa: E402

FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "nt1l1_vanilla_frost_mage_2026_10_08.json").read_text(
        encoding="utf-8"
    )
)
TALENTS = {int(k, 36): v for k, v in FIXTURE["talents"].items()}
FINAL = FIXTURE["expected_nt1"]
PRIORITY = FIXTURE["explicit_priority_nt1l1"]


def validate_priority_against_pinned_dbc(code: str) -> list[dict[int, int]]:
    """Reproduce source row/prerequisite legality after EVERY rank purchase.

    Only the 20 Mage talents in the pinned snapshot are supported. A future
    snapshot refresh must update this fixture deliberately and be reviewed.
    """
    fields = code.split(":")
    if len(fields) != 4 or fields[:3] != ["NT1L1", "vanilla", "mage"]:
        raise InvalidPlan("Incorrect NT1L1 source class/era")
    current: dict[int, int] = defaultdict(int)
    history: list[dict[int, int]] = []

    for entry in fields[3].split("."):
        try:
            base36, count = entry.split("-")
            talent_id = int(base36, 36)
            additional = int(count)
        except (ValueError, TypeError) as exc:
            raise InvalidPlan("Malformed rank step") from exc
        if not 1 <= additional <= 5 or talent_id not in TALENTS:
            raise InvalidPlan("Unknown Talent.dbc ID or invalid increment")
        talent = TALENTS[talent_id]
        for _ in range(additional):
            if current[talent_id] >= talent["max_rank"]:
                raise InvalidPlan("Talent rank exceeds pinned Spell.dbc ranks")

            tree, row = talent["tree"], talent["row"]
            earlier = sum(
                points
                for spent_id, points in current.items()
                if TALENTS[spent_id]["tree"] == tree
                and TALENTS[spent_id]["row"] < row
            )
            if earlier < 5 * row:
                raise InvalidPlan("Talent row not unlocked at this rank step")

            required = talent["requires"]
            if required:
                dep_id = int(required["talent_id"], 36)
                if current[dep_id] < required["rank"]:
                    raise InvalidPlan("Talent prerequisite is not yet learned")

            current[talent_id] += 1
            history.append(dict(current))

    if len(history) != FIXTURE["full_points"]:
        raise InvalidPlan("Rank-priority source must have 51 points")
    return history


class ReviewedFrostMageLevelProjection(unittest.TestCase):
    def test_exact_original_final_ranks(self):
        full = validate_priority_against_pinned_dbc(PRIORITY)
        expected = {
            int(item.split("-")[0], 36): int(item.split("-")[1])
            for item in FINAL.split(":")[-1].split(".")
        }
        self.assertEqual(full[-1], expected)
        self.assertEqual(sum(full[-1].values()), 51)

    def test_offline_equivalence_guard(self):
        points, ranks = compare(FINAL, PRIORITY, 60)
        self.assertEqual((points, ranks), (51, validate_priority_against_pinned_dbc(PRIORITY)[-1]))

    def test_level_30_is_21_legal_frost_points(self):
        history = validate_priority_against_pinned_dbc(PRIORITY)
        points, derived = compare(FINAL, PRIORITY, 30)
        self.assertEqual(points, 21)
        self.assertEqual(derived, history[20])
        self.assertEqual(
            sum(v for id_, v in derived.items() if TALENTS[id_]["tree"] == "Frost"),
            21,
        )

    def test_level_40_is_31_legal_frost_points(self):
        history = validate_priority_against_pinned_dbc(PRIORITY)
        points, derived = compare(FINAL, PRIORITY, 40)
        self.assertEqual((points, derived), (31, history[30]))

    def test_level_50_is_37_frost_plus_4_arcane(self):
        _, derived = compare(FINAL, PRIORITY, 50)
        tree_points = defaultdict(int)
        for talent_id, ranks in derived.items():
            tree_points[TALENTS[talent_id]["tree"]] += ranks
        self.assertEqual((tree_points["Frost"], tree_points["Arcane"]), (37, 4))

    def test_every_eligible_level_is_budget_limited(self):
        history = validate_priority_against_pinned_dbc(PRIORITY)
        for level in range(10, 61):
            with self.subTest(level=level):
                points, derived = compare(FINAL, PRIORITY, level)
                self.assertEqual(points, level - 9)
                self.assertEqual(derived, history[level - 10])

    def test_full_chat_command_is_under_255_characters(self):
        command = ".naxxbot talents project Castin " + PRIORITY
        self.assertLessEqual(len(command), 255)

    def test_snapshot_has_named_and_ranked_expected_talents(self):
        self.assertEqual(FIXTURE["snapshot"]["blob_sha"],
                         "9a11c998850b3069ca15d42f5c6c24b124e5ec21")
        self.assertEqual(len(TALENTS), 20)
        self.assertEqual(TALENTS[int("1z", 36)]["requires"]["talent_id"], "20")

    def test_illegal_high_row_first_is_rejected(self):
        entries = PRIORITY.split(":")[-1].split(".")
        reordered = ["1w-3"] + [x for x in entries if x != "1w-3"]
        invalid = PRIORITY.rsplit(":", 1)[0] + ":" + ".".join(reordered)
        with self.assertRaisesRegex(InvalidPlan, "row not unlocked"):
            validate_priority_against_pinned_dbc(invalid)
        # Offline final-rank comparison still matches, proving its limitations.
        self.assertEqual(compare(FINAL, invalid, 60)[0], 51)

    def test_ice_barrier_before_cold_snap_is_rejected(self):
        original = ".20-1.1s-2.1w-3.1z-1."
        switched = ".1s-2.1w-3.1z-1.20-1."
        self.assertIn(original, PRIORITY)
        with self.assertRaisesRegex(InvalidPlan, "prerequisite"):
            validate_priority_against_pinned_dbc(PRIORITY.replace(original, switched))

    def test_overrank_cold_snap_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "exceeds"):
            validate_priority_against_pinned_dbc(PRIORITY.replace(".20-1.", ".20-2."))

    def test_incomplete_priority_rejected(self):
        with self.assertRaisesRegex(InvalidPlan, "51 points"):
            validate_priority_against_pinned_dbc(PRIORITY.rsplit(".", 1)[0])

    def test_old_nt1_final_entry_order_is_not_valid_priority(self):
        old_as_priority = FINAL.replace("NT1:", "NT1L1:", 1)
        with self.assertRaisesRegex(InvalidPlan, "row not unlocked"):
            validate_priority_against_pinned_dbc(old_as_priority)


if __name__ == "__main__":
    unittest.main()
