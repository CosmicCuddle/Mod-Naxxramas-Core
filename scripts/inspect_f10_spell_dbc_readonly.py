#!/usr/bin/env python3
"""Read-only 3.3.5a Spell.dbc probe for F10 Hallow's End spell metadata.

Only inspects the exact file the operator selects. NEVER modifies, creates,
replaces, uploads, or installs a DBC. The CLI is not invoked by CI; CI uses
synthetic WDBC test fixtures ONLY. Values do not prove runtime ordering,
stock splash behavior, owner game/client parity, or an accepted bucket hit.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import struct

MAGIC = b"WDBC"
EXPECTED_FIELD_COUNT = 234  # Wrath 3.3.5a Spell.dbc, not earlier expansions
FIELD_ID = 0
FIELD_SPEED = 47        # f32, 3.3.5a Spell.dbc (AzerothCore DBC field map)
FIELD_EFFECT0 = 71     # uint32 SPELL_EFFECT_DUMMY = 3
FIELD_EFFECT1 = 72
FIELD_EFFECT2 = 73
SPELL_EFFECT_DUMMY = 3
EXPECTED_SPELL_IDS = (42074, 42339, 42348)
MAX_FILE_BYTES = 128 * 1024 * 1024


class DBCInspectionError(ValueError):
    """Invalid/unsupported input: fail closed instead of guessing layout."""


@dataclass(frozen=True)
class SpellObservation:
    spell_id: int
    speed: float
    effects: tuple[int, int, int]


def inspect_spell_dbc(path: Path) -> tuple[str, dict[int, SpellObservation]]:
    """Parse only verified columns; return SHA-256 and matching spell rows.

    A WDBC header contains 4 bytes magic followed by four little-endian
    uint32 values: number of records, field count, record byte size, and
    string-block size. Rows are contiguous fixed-width records, then strings.
    """
    if not path.is_file():
        raise DBCInspectionError("DBC file does not exist or is not a regular file")
    file_size = path.stat().st_size
    if file_size < 20 or file_size > MAX_FILE_BYTES:
        raise DBCInspectionError("Invalid/oversized WDBC file; no scan performed")
    raw = path.read_bytes()  # The supplied DBC is NEVER opened for writing.
    if len(raw) != file_size or raw[:4] != MAGIC:
        raise DBCInspectionError("Not a complete WDBC file")
    record_count, field_count, record_size, string_bytes = struct.unpack_from(
        "<4I", raw, 4
    )
    if field_count != EXPECTED_FIELD_COUNT:
        raise DBCInspectionError(
            f"Unsupported Spell.dbc field count {field_count}; expected "
            f"{EXPECTED_FIELD_COUNT} for 3.3.5a, no generic layout inference"
        )
    if record_count == 0 or record_size != field_count * 4:
        raise DBCInspectionError("Invalid record count or unexpected record width")
    end_of_records = 20 + record_count * record_size
    if end_of_records + string_bytes != file_size or string_bytes == 0:
        raise DBCInspectionError("Truncated or padded records/string block")
    if raw[end_of_records] != 0:
        raise DBCInspectionError("Unexpected string block prefix")
    selected: dict[int, SpellObservation] = {}
    for row in range(record_count):
        offset = 20 + row * record_size
        spell_id = struct.unpack_from("<I", raw, offset + FIELD_ID * 4)[0]
        if spell_id not in EXPECTED_SPELL_IDS:
            continue
        if spell_id in selected:
            raise DBCInspectionError(f"Duplicate spell {spell_id}; ambiguous DBC")
        speed = struct.unpack_from("<f", raw, offset + FIELD_SPEED * 4)[0]
        if not math.isfinite(speed) or speed < 0:
            raise DBCInspectionError(f"Invalid missile speed for {spell_id}")
        effects = tuple(
            struct.unpack_from("<I", raw, offset + field * 4)[0]
            for field in (FIELD_EFFECT0, FIELD_EFFECT1, FIELD_EFFECT2)
        )
        selected[spell_id] = SpellObservation(spell_id, speed, effects)
    absent = sorted(set(EXPECTED_SPELL_IDS) - set(selected))
    if absent:
        raise DBCInspectionError(f"Missing spell IDs {absent}; no timing conclusion")
    if selected[42339].effects[0] != SPELL_EFFECT_DUMMY:
        raise DBCInspectionError(
            "42339 effect 0 is not SPELL_EFFECT_DUMMY (3): "
            "review runtime hook path before testing the feature"
        )
    digest = hashlib.sha256(raw).hexdigest()
    return digest, selected


def format_observations(digest: str,
                        records: dict[int, SpellObservation]) -> str:
    lines = [f"LOCAL_INPUT_SHA256={digest}", "FORMAT=WDBC 3.3.5a, 234 fields"]
    for spell_id in EXPECTED_SPELL_IDS:
        row = records[spell_id]
        lines.append(
            f"SPELL_{spell_id}_SPEED={row.speed:.6g} "
            f"EFFECTS={row.effects[0]},{row.effects[1]},{row.effects[2]}"
        )
    category = "ZERO" if records[42348].speed == 0 else "POSITIVE"
    lines.extend([
        f"F10_42348_DBC_SPEED_CATEGORY={category}",
        "INTERPRETATION=Spell.dbc speed field only; core ordering, "
        "other timing and stock 42348 splash effects are NOT TESTED",
        "OWNER_CLIENT_SERVER_DBC_PARITY=UNVERIFIED",
        "F10_DBC_INSPECTION_COMPLETED_READ_ONLY",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbc", type=Path, required=True,
                        help="Path to existing privately backed-up Spell.dbc")
    args = parser.parse_args()
    try:
        digest, records = inspect_spell_dbc(args.dbc)
    except (DBCInspectionError, OSError) as error:
        parser.exit(2, f"F10_DBC_FAIL_CLOSED: {error}\n")
    print(format_observations(digest, records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
