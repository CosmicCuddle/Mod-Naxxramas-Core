"""Offline tests: backup audit is read-only, streaming, and never claims recovery."""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_nt1_altbot_recovery_backup import (  # noqa: E402
    BackupAuditError,
    REQUIRED_TABLES,
    audit_backup,
    write_new_private_manifest,
)


def sql_ddl(tables):
    lines = [
        "-- OFFLINE SYNTHETIC TEST FIXTURE, not a real player dump",
        "CREATE DATABASE IF NOT EXISTS acore_characters;",
    ]
    for table in sorted(tables):
        lines.extend([
            "-- Table structure for table",
            "CREATE TABLE " + chr(96) + table + chr(96) +
            " (id int unsigned NOT NULL);",
            "INSERT INTO " + chr(96) + table + chr(96) +
            " VALUES (1);",
        ])
    lines.append("-- Dump completed on SYNTHETIC FIXTURE")
    return "\n".join(lines).encode("ascii") + b"\n"


class AltBotBackupAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_dump(self, tables=REQUIRED_TABLES, compressed=True):
        path = self.root / ("characters.sql.gz" if compressed else "characters.sql")
        if compressed:
            with gzip.open(path, "wb") as out:
                out.write(sql_ddl(tables))
        else:
            path.write_bytes(sql_ddl(tables))
        return path

    def test_full_gzip_audit_passes_but_never_claims_restore(self):
        r = audit_backup(self.make_dump())
        self.assertEqual(r["result"], "STRUCTURAL_AUDIT_PASSED_NOT_RESTORE_TESTED")
        self.assertFalse(r["restore_verified"])
        self.assertEqual(r["required_tables_present"], sorted(REQUIRED_TABLES))
        self.assertEqual(len(r["sha256"]), 64)

    def test_uncompressed_sql_supported(self):
        self.assertFalse(audit_backup(self.make_dump(compressed=False))["restore_verified"])

    def test_talent_only_dump_fails_closed(self):
        p = self.make_dump(tables={"character_talent"})
        with self.assertRaisesRegex(BackupAuditError, "Missing CREATE TABLE"):
            audit_backup(p)

    def test_missing_item_instance_is_not_accepted(self):
        p = self.make_dump(tables=REQUIRED_TABLES - {"item_instance"})
        with self.assertRaisesRegex(BackupAuditError, "item_instance"):
            audit_backup(p)

    def test_missing_glyphs_and_spells_is_rejected(self):
        p = self.make_dump(tables=REQUIRED_TABLES - {"character_spell", "character_glyphs"})
        with self.assertRaisesRegex(BackupAuditError, "character_glyphs"):
            audit_backup(p)

    def test_truncated_gzip_is_rejected(self):
        p = self.make_dump()
        content = p.read_bytes()
        p.write_bytes(content[:-10])
        with self.assertRaisesRegex(BackupAuditError, "CRC/truncation"):
            audit_backup(p)

    def test_invalid_gzip_magic_is_rejected(self):
        p = self.root / "not_a_backup.sql.gz"
        p.write_bytes(b"not gzip")
        with self.assertRaisesRegex(BackupAuditError, "not a gzip"):
            audit_backup(p)

    def test_unknown_extension_is_rejected(self):
        p = self.root / "characters.zip"
        p.write_bytes(sql_ddl(REQUIRED_TABLES))
        with self.assertRaisesRegex(BackupAuditError, r"\.sql"):
            audit_backup(p)

    def test_missing_file_rejected(self):
        with self.assertRaisesRegex(BackupAuditError, "does not exist"):
            audit_backup(self.root / "does-not-exist.sql")

    def test_new_manifest_is_private_and_never_overwritten(self):
        manifest = self.root / "manifest.json"
        report = audit_backup(self.make_dump())
        write_new_private_manifest(manifest, report)
        self.assertEqual(json.loads(manifest.read_text())["sha256"], report["sha256"])
        with self.assertRaises(FileExistsError):
            write_new_private_manifest(manifest, report)
        self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)

    def test_optional_nt1_table_is_reported_but_not_required(self):
        without = audit_backup(self.make_dump())
        self.assertFalse(without["optional_nt1_profile_table_seen"])
        with_table = audit_backup(self.make_dump(
            tables=REQUIRED_TABLES | {"mod_naxxramas_bot_talent_import"}
        ))
        self.assertTrue(with_table["optional_nt1_profile_table_seen"])

    def test_audit_does_not_include_sql_row_data(self):
        report = audit_backup(self.make_dump())
        raw = json.dumps(report)
        self.assertNotIn("INSERT INTO", raw)
        self.assertNotIn("VALUES (1)", raw)
        self.assertFalse(report["restore_verified"])


if __name__ == "__main__":
    unittest.main()
