#!/usr/bin/env python3
"""Read-only and fail-closed release-scope gate.

Manifest entries are manually reviewed GitHub evidence, NEVER live installed
state. This script does not query GitHub or edit any source or configuration.
A reported green source build is not permission to enable a feature.
"""
import argparse
import json
import re
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "docs/release-gates/1.0.6.8.5.json"
STAGES = tuple(f"S{i}" for i in range(8))
STATES = {"draft", "merged_main", "not_implemented"}
DEFAULTS = {"off", "existing_behavior", "unknown"}
REQUIRED_COMPONENTS = {
    "golemagg_diagnostic", "golemagg_movement_fix", "hunter_ammunition",
    "hunter_pet_autocast_observer", "hunter_pet_autocast_fix",
    "nt1_altbot_apply", "quest_loot_turn_guard",
    "ep_tower_lock", "ep_tower_announcements", "existing_module_regression",
}
COMBINED_THREE = {
    "golemagg_diagnostic", "hunter_ammunition", "hunter_pet_autocast_observer",
}
MATURE_THREE = {"hunter_ammunition", "quest_loot_turn_guard", "ep_tower_announcements"}
# NT1 is also a draft gameplay component, but belongs to neither certified
# integration family. Any mixed unsupported set must fail rather than
# assuming independently linked Worldservers constitute one valid build.
INTEGRATION_SENSITIVE = COMBINED_THREE | MATURE_THREE | {"nt1_altbot_apply"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _bool(entry: dict, field: str) -> None:
    if type(entry.get(field)) is not bool:
        raise ValueError(f"{entry.get('id', '<release>')}: {field} must be boolean")


def validate(document: dict) -> None:
    if document.get("schema_version") != 1 or document.get("release") != "1.0.6.8.5":
        raise ValueError("Unexpected manifest version or release")
    combined = document.get("combined_candidate")
    if not isinstance(combined, dict) or combined.get("draft_pr") != 33 or not FULL_SHA.fullmatch(combined.get("exact_head", "")):
        raise ValueError("Combined candidate must be draft PR #33 at an exact SHA")
    for key in ("source_built", "full_worldserver_built", "owner_approved"):
        _bool(combined, key)
    if combined["full_worldserver_built"] and not combined["source_built"]:
        raise ValueError("Combined candidate cannot have full Worldserver link without source build")
    mature = document.get("mature_three_candidate")
    if (not isinstance(mature, dict) or mature.get("draft_pr") != 46 or
            not isinstance(mature.get("exact_head"), str) or
            not FULL_SHA.fullmatch(mature["exact_head"])):
        raise ValueError("Mature combined candidate must identify draft PR #46 at an exact SHA")
    for key in ("source_built", "full_worldserver_built", "owner_approved"):
        _bool(mature, key)
    if mature["full_worldserver_built"] and not mature["source_built"]:
        raise ValueError("Mature candidate cannot claim full Worldserver link without source build")
    rows = document.get("components")
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_COMPONENTS):
        raise ValueError("Active-feature inventory missing or changed")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(set(ids)) != len(rows) or set(ids) != REQUIRED_COMPONENTS:
        raise ValueError("Missing/duplicate active-workstream ID")
    for row in rows:
        key = row["id"]
        if not row.get("name") or not row.get("track") or not row.get("limitation"):
            raise ValueError(f"{key}: no name, master stage or known limitation")
        if row.get("stage") not in STAGES or row.get("source_state") not in STATES:
            raise ValueError(f"{key}: unrecognised stage/source state")
        if row.get("default_behavior") not in DEFAULTS:
            raise ValueError(f"{key}: default must be off/existing_behavior/unknown")
        for flag in ("in_combined_candidate", "full_build_verified", "live_accepted",
                     "backup_restore_verified", "include_in_release", "owner_approved"):
            _bool(row, flag)
        if row["in_combined_candidate"] != (key in COMBINED_THREE):
            raise ValueError(f"{key}: does not match the three actual combined candidate features")
        sha = row.get("exact_head")
        pr = row.get("draft_pr")
        if row["source_state"] == "draft":
            if type(pr) is not int or pr < 1 or not isinstance(sha, str) or not FULL_SHA.fullmatch(sha):
                raise ValueError(f"{key}: draft must identify exact 40-char Git SHA and PR")
        elif sha is not None or pr is not None:
            raise ValueError(f"{key}: non-draft features must not invent a draft ref")
        if row["source_state"] == "not_implemented" and row["full_build_verified"]:
            raise ValueError(f"{key}: cannot claim built unimplemented feature")
        if row["live_accepted"] and not row["backup_restore_verified"]:
            raise ValueError(f"{key}: can't accept a live test without restorable backup evidence")
        # The milestone label must not outrun its own evidence. These checks
        # validate the authored manifest; they do not claim actual server proof.
        stage_number = int(row["stage"][1])
        if row["source_state"] == "not_implemented" and (
                stage_number > 1 or row["live_accepted"] or row["include_in_release"]):
            raise ValueError(f"{key}: unimplemented work cannot claim delivery or acceptance")
        if row["source_state"] == "draft" and stage_number == 7:
            raise ValueError(f"{key}: an unmerged draft cannot be marked released")
        if stage_number >= 4 and not row["full_build_verified"]:
            raise ValueError(f"{key}: S4+ requires exact-source full-build evidence")
        if row["full_build_verified"] and stage_number < 4:
            raise ValueError(f"{key}: full-build evidence must be classified at S4 or later")
        if stage_number >= 5 and not row["backup_restore_verified"]:
            raise ValueError(f"{key}: S5+ requires restorable backup evidence")
        if stage_number >= 6 and not row["live_accepted"]:
            raise ValueError(f"{key}: S6+ requires actual in-game acceptance")
        if row["live_accepted"] and stage_number < 6:
            raise ValueError(f"{key}: gameplay acceptance must be classified at S6 or later")

    # Top-level release controls MUST exist so a single feature cannot
    # substitute for approval of the selected combined release.
    for key in ("release_approved", "installed_shas_verified", "release_backup_restore_verified"):
        _bool(document, key)


def release_blockers(document: dict) -> list[str]:
    validate(document)
    problems = []
    chosen = [x for x in document["components"] if x["include_in_release"]]
    if not chosen:
        problems.append("No explicitly selected/approved feature for this release.")
    # Compute the *actual* combination rather than assuming Hunter Ammo
    # always ships in historical #33. The two integration sets overlap on
    # Hunter Ammo; selecting a feature alone requires only its own exact S4,
    # while selecting two or more draft gameplay workstreams requires one
    # candidate covering every selected source. Any cross-family mixture
    # (including NT1) remains blocked until a separate exact integration.
    selected_sensitive = {row["id"] for row in chosen} & INTEGRATION_SENSITIVE
    if len(selected_sensitive) >= 2:
        if selected_sensitive <= COMBINED_THREE:
            candidate_name = "combined_candidate"
            label = "PR #33"
        elif selected_sensitive <= MATURE_THREE:
            candidate_name = "mature_three_candidate"
            label = "PR #46"
        else:
            candidate_name = None
            label = ""
            problems.append(
                "No exact-source combined Worldserver candidate covers every "
                "selected experimental workstream."
            )
        if candidate_name:
            candidate = document[candidate_name]
            if not candidate["source_built"]:
                problems.append(f"Combined candidate {label} has no verified source build.")
            if not candidate["full_worldserver_built"]:
                problems.append(f"Combined candidate {label} has no verified full Worldserver link.")
            if not candidate["owner_approved"]:
                problems.append(f"Combined candidate {label} has not been approved.")
    for row in chosen:
        name = row["id"]
        if row["source_state"] != "merged_main":
            problems.append(f"{name}: source is not merged/approved main.")
        if row["stage"] not in ("S6", "S7") or not row["full_build_verified"]:
            problems.append(f"{name}: lacks exact-source build plus in-game acceptance stage.")
        if not row["live_accepted"]:
            problems.append(f"{name}: no independently accepted in-game regression.")
        if not row["backup_restore_verified"]:
            problems.append(f"{name}: no verified restorable full backups.")
        if not row["owner_approved"]:
            problems.append(f"{name}: no explicit owner feature-inclusion approval.")
        if row["default_behavior"] == "unknown":
            problems.append(f"{name}: active default behavior not yet verified.")
    for key in ("release_approved", "installed_shas_verified", "release_backup_restore_verified"):
        if not document[key]:
            problems.append(f"Release-wide gate is not verified: {key}.")
    return problems


def report(document: dict) -> str:
    validate(document)
    lines = [f"Release {document['release']} — read-only evidence (NOT live verification)"]
    for row in document["components"]:
        selected = "INCLUDED" if row["include_in_release"] else "EXCLUDED"
        lines.append(f"{row['name']} [{row['id']}]: {row['stage']} {selected} "
                     f"source={row['source_state']} full_build={row['full_build_verified']} "
                     f"live={row['live_accepted']} — {row['limitation']}")
    blockers = release_blockers(document)
    lines.append(f"RELEASE GATE: {'BLOCKED' if blockers else 'PASS'} ({len(blockers)} blockers)")
    lines.extend(" - " + x for x in blockers)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT)
    parser.add_argument("--mode", choices=("report", "release-gate"), default="report")
    args = parser.parse_args()
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(report(doc))
    if args.mode == "release-gate" and release_blockers(doc):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
