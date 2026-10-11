#!/usr/bin/env python3
"""Offline NT1L1-vs-NT1 final-rank equivalence check; not a DBC validator.

This script NEVER invents a talent spend order. A human supplies a priority
plan, then this checker verifies its final ranks exactly match an NT1 build.
No database access, bot changes, or in-game claims.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict

ERA_POINTS = {"vanilla": 51, "tbc": 61, "wotlk": 71}
CLASSES = {
    "warrior", "paladin", "hunter", "rogue", "priest", "deathknight",
    "shaman", "mage", "warlock", "druid",
}
TOKEN = re.compile(r"([0-9a-z]+)-([1-5])\Z")
MAX_LENGTH = 2048
MAX_ENTRIES = 120


class InvalidPlan(ValueError):
    """A plan cannot be safely compared."""


def parse_code(code: str, version: str) -> tuple[str, str, list[tuple[int, int]]]:
    if not code or len(code) > MAX_LENGTH:
        raise InvalidPlan("Empty or oversized code")
    fields = code.split(":")
    if len(fields) != 4 or fields[0] != version:
        raise InvalidPlan(f"Expected {version}:<era>:<class>:<talents>")
    _, era, cls, body = fields
    if era not in ERA_POINTS or cls not in CLASSES:
        raise InvalidPlan("Unknown expansion or class")
    if cls == "deathknight" and era != "wotlk":
        raise InvalidPlan("Death Knights require WotLK")
    if not body:
        raise InvalidPlan("Missing talent entries")
    entries = body.split(".")
    if len(entries) > MAX_ENTRIES:
        raise InvalidPlan("Too many talent entries")
    result: list[tuple[int, int]] = []
    for pair in entries:
        match = TOKEN.fullmatch(pair)
        if not match:
            raise InvalidPlan(f"Invalid talent entry {pair!r}")
        id_text, rank_text = match.groups()
        talent_id = int(id_text, 36)
        if talent_id == 0 or talent_id > (2**32 - 1):
            raise InvalidPlan("Invalid Talent.dbc ID")
        result.append((talent_id, int(rank_text)))
    return era, cls, result


def totals(entries: list[tuple[int, int]], *, allow_repeats: bool) -> dict[int, int]:
    result: dict[int, int] = defaultdict(int)
    for talent_id, added in entries:
        if not allow_repeats and talent_id in result:
            raise InvalidPlan(f"Duplicate final-rank NT1 talent ID {talent_id}")
        result[talent_id] += added
        if result[talent_id] > 5:
            raise InvalidPlan(f"Talent {talent_id} would exceed five ranks")
    return dict(result)


def compare(expected: str, priority: str, level: int) -> tuple[int, dict[int, int]]:
    era, cls, original_entries = parse_code(expected, "NT1")
    p_era, p_cls, ordered_entries = parse_code(priority, "NT1L1")
    if (era, cls) != (p_era, p_cls):
        raise InvalidPlan("Source NT1 and NT1L1 expansion/class differ")

    final = totals(original_entries, allow_repeats=False)
    priority_final = totals(ordered_entries, allow_repeats=True)
    if sum(final.values()) != ERA_POINTS[era]:
        raise InvalidPlan("Original NT1 is not a complete expansion-level build")
    if sum(priority_final.values()) != ERA_POINTS[era]:
        raise InvalidPlan("NT1L1 is not a complete expansion-level plan")
    if final != priority_final:
        raise InvalidPlan("NT1L1 final talent ranks do not match original NT1")
    if level < 10 or level > ERA_POINTS[era] + 9:
        raise InvalidPlan("Target level is outside this expansion")

    budget = level - 9  # Ordinary 3.3.5a talent budget; real server is authoritative.
    projected: dict[int, int] = defaultdict(int)
    points = 0
    for talent_id, added in ordered_entries:
        for _ in range(added):
            if points >= budget:
                break
            projected[talent_id] += 1
            points += 1
        if points >= budget:
            break
    if points != budget:
        raise InvalidPlan("Priority cannot fill target level budget")
    return budget, dict(projected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True, help="Reviewed full NT1 build")
    parser.add_argument("--priority", required=True, help="Human-authored NT1L1 rank order")
    parser.add_argument("--level", required=True, type=int, help="Bot's level")
    args = parser.parse_args()
    try:
        points, ranks = compare(args.expected, args.priority, args.level)
    except InvalidPlan as exc:
        print(f"REJECTED: {exc}")
        return 1
    print(f"OFFLINE MATCH: {points}/{points} points at level {args.level}; {len(ranks)} selected talents")
    print("Projected Talent.dbc IDs/ranks (not server/DBC validated):")
    print(" ".join(f"{talent_id}:{rank}" for talent_id, rank in sorted(ranks.items())))
    print("IMPORTANT: this check does not prove that talent-row ordering, DBC prerequisites, or in-game Apply will succeed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
