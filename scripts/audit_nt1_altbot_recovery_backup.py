#!/usr/bin/env python3
"""Audit the structural coverage of an OFFLINE characters-database SQL backup.

READ-ONLY: never connects to a DB, restores a dump, alters a character,
or logs any SQL row contents. Full coverage/CRC checks are prerequisites,
NOT proof that a character can actually be recovered.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# Core AzerothCore character state is spread across separate tables.
# Do not accept talent-only dumps as a full recovery checkpoint.
REQUIRED_TABLES = frozenset({
    "characters",
    "character_talent",
    "character_spell",
    "character_glyphs",
    "character_action",
    "character_aura",
    "character_inventory",
    "character_stats",
    "item_instance",
    "character_pet",
    "pet_spell",
    "pet_aura",
})
# The table name may be backtick-quoted; a normal SQL dump emits CREATE TABLE.
CREATE_TABLE = re.compile(
    rb'^\s*CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+'
    rb'[\x60"]?([A-Za-z0-9_]+)[\x60"]?\s*\(',
    re.IGNORECASE,
)
BLOCK_SIZE = 1024 * 1024


class BackupAuditError(Exception):
    """Input is not a verified structural recovery checkpoint."""


def audit_backup(path: Path) -> dict:
    """Stream entire file; validate gzip CRC and required table declarations."""
    path = Path(path)
    if not path.is_file():
        raise BackupAuditError("Backup file does not exist or is not a regular file")
    if path.name.endswith(".sql.gz"):
        compressed = True
    elif path.name.endswith(".sql"):
        compressed = False
    else:
        raise BackupAuditError("Expected a full .sql or .sql.gz database dump")

    sha256 = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as fh:
        if compressed and fh.read(2) != b"\x1f\x8b":
            raise BackupAuditError("File is not a gzip-compressed SQL dump")
        fh.seek(0)
        while True:
            block = fh.read(BLOCK_SIZE)
            if not block:
                break
            sha256.update(block)
            byte_count += len(block)
    if byte_count == 0:
        raise BackupAuditError("Backup file is empty")

    seen: set[str] = set()
    rows_scanned = 0
    opener = gzip.open if compressed else open
    try:
        with opener(path, "rb") as source:
            for row in source:
                rows_scanned += 1
                match = CREATE_TABLE.match(row)
                if match:
                    seen.add(match.group(1).decode("ascii").lower())
    except (OSError, EOFError, ValueError) as exc:
        raise BackupAuditError(
            "Cannot fully read SQL dump (gzip CRC/truncation/corruption check failed)"
        ) from exc

    missing = sorted(REQUIRED_TABLES - seen)
    if missing:
        raise BackupAuditError(
            "Full recovery table coverage FAILED. Missing CREATE TABLE "
            "declarations: " + ", ".join(missing)
        )

    return {
        "result": "STRUCTURAL_AUDIT_PASSED_NOT_RESTORE_TESTED",
        "file_basename": path.name,
        "file_bytes": byte_count,
        "sha256": sha256.hexdigest(),
        "sql_lines_scanned": rows_scanned,
        "required_tables_present": sorted(REQUIRED_TABLES),
        "optional_nt1_profile_table_seen": (
            "mod_naxxramas_bot_talent_import" in seen
        ),
        "restore_verified": False,
        "warning": (
            "This checks file integrity and core table declarations ONLY. "
            "It does NOT establish a consistent live database snapshot, "
            "that all rows were exported, that SQL can be imported, or "
            "that character/talent/inventory state can be restored. "
            "Worldserver must be stopped during the source backup; "
            "perform an isolated test-database restoration before repair."
        ),
    }


def write_new_private_manifest(path: Path, report: dict) -> None:
    """Never overwrite an existing recovery manifest."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, help="Create a private JSON audit manifest (never overwrite)"
    )
    args = parser.parse_args()
    try:
        report = audit_backup(args.dump)
        if args.manifest:
            write_new_private_manifest(args.manifest, report)
    except (BackupAuditError, OSError) as exc:
        print(f"NOT READY FOR REPAIR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    print("NEXT GATE: restore this backup into a separate TEST database; "
          "confirm character and item state matches. Do not enable repair.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
