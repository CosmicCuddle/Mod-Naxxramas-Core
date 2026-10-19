#!/usr/bin/env python3
"""Read-only, aggregate summary of owner-supplied Hunter pet autocast audit lines.

No source, server, database, configuration, pet or log write is performed.
This cannot attribute intent to native state, identify IP completion or prove
any pet autocast ON/OFF persistence fix.
"""
import argparse
from collections import Counter
from pathlib import Path
import re

MARKER = "HunterPetAutocast "
CHOICE = re.compile(
    r"HunterPetAutocast AUDIT ONLY: owner=(\d+) petnumber=(\d+) "
    r"spell=(\d+) requested=(ON|OFF) "
    r"source=(CMSG_PET_SPELL_AUTOCAST|CMSG_PET_SET_ACTION) "
    r"native=matching-state-only; actor not attributable; no mutation"
)
LATER = re.compile(
    r"HunterPetAutocast GENERIC audit: later owner=(\d+) "
    r"before=(bar\[[^\]]*\] known\[[^\]]*\]) "
    r"after=(bar\[[^\]]*\] known\[[^\]]*\]) \(not IP completion\)"
)
LEARN = re.compile(
    r"HunterPetAutocast LEARN-PACKET audit: owner=(\d+) "
    r"petnumber=(\d+) learnedSpell=(\d+) observed;"
)
STABILITY = re.compile(
    r"HunterPetAutocast STABILITY audit: owner=(\d+) family=(\d+) "
    r"before=(\S+) after=(\S+) loading=(true|false);"
)


def known_families(snapshot):
    """Family -> (native rank spell ID, numeric native active, in autocast list).

    Return None rather than treat truncated/ambiguous snapshots as complete.
    The m_autospells marker is NOT explicit human ON/OFF preference evidence.
    """
    part = snapshot.split(" known[", 1)
    if len(part) != 2 or not part[1].endswith("]") or "truncated" in part[1]:
        return None
    entries = {}
    for item in part[1][:-1].split(","):
        if not item:
            continue
        pieces = item.split("/")
        if len(pieces) != 4:
            return None
        try:
            spell, family, active, listed = map(int, pieces)
        except ValueError:
            return None
        if spell <= 0 or family <= 0 or active < 0 or listed not in (0, 1):
            return None
        if family in entries:
            return None
        entries[family] = (spell, active, listed)
    return entries


def summarize(lines):
    counts = Counter()
    owners = set()
    for line in lines:
        if MARKER not in line:
            continue
        counts["audit_lines"] += 1
        choice = CHOICE.search(line)
        if choice:
            owners.add(choice.group(1))
            counts["next_update_native_matches"] += 1
            counts["native_match_requested_on" if choice.group(4) == "ON"
                   else "native_match_requested_off"] += 1
            counts["native_match_from_spell_opcode" if
                   choice.group(5) == "CMSG_PET_SPELL_AUTOCAST"
                   else "native_match_from_actionbar_opcode"] += 1
            continue
        later = LATER.search(line)
        if later:
            owners.add(later.group(1))
            counts["paired_generic_snapshot_lines"] += 1
            old, new = known_families(later.group(2)), known_families(later.group(3))
            if old is None or new is None:
                counts["ambiguous_or_truncated_snapshots"] += 1
                continue
            counts["comparable_generic_snapshots"] += 1
            for family in old.keys() | new.keys():
                before, after = old.get(family), new.get(family)
                if before is None or after is None:
                    counts["family_added_or_removed_in_snapshot"] += 1
                else:
                    if before[0] != after[0]:
                        counts["rank_id_changes_in_snapshot"] += 1
                    if before[1] != after[1]:
                        counts["native_active_flag_changes_in_snapshot"] += 1
                    if before[2] != after[2]:
                        counts["autocast_list_membership_changes_in_snapshot"] += 1
            continue
        learn = LEARN.search(line)
        if learn:
            owners.add(learn.group(1))
            counts["learn_packets_observed_unattributed"] += 1
            continue
        stable = STABILITY.search(line)
        if stable:
            owners.add(stable.group(1))
            counts["family_stability_change_lines"] += 1
            continue
        counts["other_audit_lines"] += 1
    return dict(counts), len(owners)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", type=Path,
                        help="operator-held LOCAL redacted/copied log; never uploaded")
    args = parser.parse_args()
    try:
        with args.logfile.open("r", encoding="utf-8", errors="replace") as fh:
            counts, owners = summarize(fh)
    except OSError:
        print("ERROR: log unavailable/unreadable. No server or pet action taken.")
        return 2
    print("Hunter pet autocast OFFLINE evidence SUMMARY (no IDs/spells/raw actions shown)")
    print(f"Distinct owner IDs seen in recognized audit lines (COUNT ONLY): {owners}")
    for key in (
        "audit_lines", "next_update_native_matches",
        "native_match_requested_on", "native_match_requested_off",
        "native_match_from_spell_opcode", "native_match_from_actionbar_opcode",
        "paired_generic_snapshot_lines", "comparable_generic_snapshots",
        "ambiguous_or_truncated_snapshots",
        "family_added_or_removed_in_snapshot", "rank_id_changes_in_snapshot",
        "native_active_flag_changes_in_snapshot",
        "autocast_list_membership_changes_in_snapshot",
        "learn_packets_observed_unattributed", "family_stability_change_lines",
        "other_audit_lines",
    ):
        print(f"{key}: {counts.get(key, 0)}")
    print("CAUTION: native matching state is NOT proof of which actor toggled.")
    print("Snapshot or learn packet is NOT proof Individual Progression completed.")
    print("NO proof of explicit intent surviving relog, legal rank, or restoration.")
    print("No server, pet, source, configuration, database or log modified.")
    return 0 if counts.get("audit_lines") else 1


if __name__ == "__main__":
    raise SystemExit(main())
