#!/usr/bin/env python3
"""Offline read-only summary of opt-in GolemaggActionAudit Worldserver log lines.

Uses only operator-supplied local text, never contacts the realm, never modifies
bots or logs, and never attributes causal AI movement from recent action tails.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import math
import re

MARKER = "GolemaggActionAudit READ ONLY:"
FIELDS = re.compile(r"(?<!\S)([a-zA-Z0-9_]+)=([^\s]+)")


@dataclass(frozen=True)
class Sample:
    bot: str
    number: int
    stacks: int
    lookup: bool
    hp: float | None
    distance: float | None
    at_stacks: bool
    inside_distance: bool | None
    explicit_thresholds: bool
    mentions_back_off: bool
    unavailable_recent_action_history: bool


def boolean(value: str | None) -> bool | None:
    if value is None:
        return None
    return {"true": True, "false": False, "1": True, "0": False}.get(value.lower())


def read_sample(line: str) -> Sample | None:
    if MARKER not in line:
        return None
    # Duplicated fields can silently replace a real value, while only one
    # explicit threshold flag makes the sample neither new nor legacy.
    pairs = FIELDS.findall(line.split(" recent_actions=", 1)[0].split(MARKER, 1)[1])
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)):
        return None
    fields = dict(pairs)
    if ("retreat_stacks_20" in fields) != ("inside_retreat_12yd" in fields):
        return None
    try:
        name = fields["bot"]
        number = int(fields["samples"].split("/", 1)[0])
        stacks = int(fields["splash_stacks"])
        lookup = boolean(fields.get("boss_lookup_present"))
        hp = float(fields["boss_hp_pct"])
        distance = float(fields["boss_distance_yards"])
        # Malformed log values must never be counted as genuine telemetry.
        if not math.isfinite(hp) or not math.isfinite(distance):
            return None
        if not name or number < 1 or stacks < 0 or lookup is None:
            return None
        if not lookup:
            hp, distance = None, None
        elif hp < 0 or distance < 0:
            return None

        has_both = "retreat_stacks_20" in fields and "inside_retreat_12yd" in fields
        at_stacks = boolean(fields.get("retreat_stacks_20")) if has_both else stacks >= 20
        inside = boolean(fields.get("inside_retreat_12yd")) if has_both else (
            distance < 12.0 if distance is not None else None
        )
        if at_stacks is None or (has_both and inside is None):
            return None
        if has_both:
            # The exact module observer computes both booleans from these
            # metrics. Reject contradictory/corrupted lines, not just gaps.
            if at_stacks != (stacks >= 20):
                return None
            if inside != (lookup and distance is not None and distance < 12.0):
                return None
        if not lookup:
            inside = None
        tail = line.split(" recent_actions=", 1)[1].strip().lower() if " recent_actions=" in line else ""
        # Optional proposed observer PR #40 explicitly uses this sentinel.
        # It does NOT establish that no bot action occurred; history is unknown.
        missing_history = tail == "(no recent action)"
        return Sample(
            bot=name, number=number, stacks=stacks, lookup=lookup,
            hp=hp, distance=distance, at_stacks=at_stacks,
            inside_distance=inside, explicit_thresholds=has_both,
            mentions_back_off="mc golemagg back off" in tail,
            unavailable_recent_action_history=missing_history,
        )
    except (ValueError, KeyError, OverflowError):
        return None


def summarize(lines):
    counters = defaultdict(int)
    last = {}
    bots = set()
    for line in lines:
        if MARKER not in line:
            continue
        counters["candidate_lines"] += 1
        sample = read_sample(line)
        if sample is None:
            counters["unparsed_lines"] += 1
            continue
        bots.add(sample.bot)
        counters["parsed_samples"] += 1
        if sample.unavailable_recent_action_history:
            counters["unavailable_recent_action_history_samples"] += 1
        if not sample.explicit_thresholds:
            counters["legacy_without_explicit_thresholds"] += 1
        if not sample.lookup:
            counters["lookup_missing"] += 1
        if sample.hp is not None and sample.hp <= 10:
            counters["burn_phase_samples"] += 1
        # Observer is already scoped to melee DPS. Only call this a
        # sampled *condition*, not proof a native back-off action executed.
        condition_seen = (
            sample.lookup and sample.at_stacks and
            sample.inside_distance is True and sample.hp is not None and
            sample.hp > 10.0
        )
        if condition_seen:
            counters["sampled_retreat_condition_met"] += 1
        if sample.mentions_back_off:
            counters["recent_back_off_mentions"] += 1
            if condition_seen:
                counters["back_off_mentions_with_condition"] += 1
            else:
                counters["back_off_mentions_without_confirmed_condition"] += 1
        if sample.at_stacks:
            counters["at_or_over_20_stacks"] += 1

        previous = last.get(sample.bot)
        if previous is not None and sample.number <= previous.number:
            counters["sample_counter_reset_or_replay"] += 1
            previous = None
        if previous is not None:
            if sample.at_stacks != previous.at_stacks:
                counters["sampled_stack_bucket_changes"] += 1
            if (sample.inside_distance is not None and
                    previous.inside_distance is not None and
                    sample.inside_distance != previous.inside_distance):
                counters["sampled_distance_bucket_changes"] += 1
        last[sample.bot] = sample
    return dict(counters), len(bots)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", type=Path, help="local, optionally redacted Worldserver log")
    args = parser.parse_args()
    try:
        with args.logfile.open("r", encoding="utf-8", errors="replace") as stream:
            counts, bots = summarize(stream)
    except OSError:
        print("ERROR: log is missing or unreadable. No server action taken.")
        return 2
    print("Offline Golemagg observer summary (no bot names or recent actions shown)")
    print(f"Unique sampled character names (count only): {bots}")
    for key in (
        "candidate_lines", "parsed_samples", "unparsed_lines",
        "legacy_without_explicit_thresholds", "lookup_missing",
        "burn_phase_samples", "at_or_over_20_stacks",
        "sampled_stack_bucket_changes", "sampled_distance_bucket_changes",
        "recent_back_off_mentions", "sampled_retreat_condition_met",
        "unavailable_recent_action_history_samples",
        "back_off_mentions_with_condition",
        "back_off_mentions_without_confirmed_condition",
        "sample_counter_reset_or_replay",
    ):
        print(f"{key}: {counts.get(key, 0)}")
    print("CAUTION: sampled retreat condition means boss >10% HP, 20+ stacks, "
          "distance <12yd with boss lookup; not proof of an action.")
    print("Back-off mentions are RECENT tails, not time-aligned executions.")
    print("CAUTION: logs are sampled/limited recent action tails, not execution causality.")
    print("No raid result, bot movement fix, 100% event capture or stack timing proof.")
    print("No server, bot, configuration, source, database or log content modified.")
    return 0 if counts.get("parsed_samples") else 1


if __name__ == "__main__":
    raise SystemExit(main())
