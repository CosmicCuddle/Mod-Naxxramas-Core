"""Synthetic WDBC fixtures only; never read or modify the owner's DBC."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from inspect_f10_spell_dbc_readonly import (  # noqa: E402
    DBCInspectionError, EXPECTED_FIELD_COUNT, FIELD_SPEED, MAGIC,
    format_observations, inspect_spell_dbc,
)

def make_dbc(entries: tuple[tuple[int, float, int], ...],
             *, fields: int = EXPECTED_FIELD_COUNT,
             string_block: bytes = b"\0",
             suffix: bytes = b"") -> bytes:
    rows: list[bytes] = []
    for sid, speed, effect0 in entries:
        row = bytearray(fields * 4)
        struct.pack_into("<I", row, 0, sid)
        if fields > FIELD_SPEED:
            struct.pack_into("<f", row, FIELD_SPEED * 4, speed)
        if fields > 71:
            struct.pack_into("<I", row, 71 * 4, effect0)
        rows.append(bytes(row))
    return (MAGIC + struct.pack("<4I", len(rows), fields, fields * 4,
                                len(string_block)) +
            b"".join(rows) + string_block + suffix)


GOOD = ((42074, 0.0, 6), (42339, 0.0, 3), (42348, 12.5, 3))


class F10ReadOnlyDBCContract(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "Spell.dbc"

    def inspect(self, data: bytes):
        self.path.write_bytes(data)   # synthetic test fixture ONLY
        before = self.path.read_bytes()
        result = inspect_spell_dbc(self.path)
        self.assertEqual(before, self.path.read_bytes())
        return result

    def assert_rejects(self, data: bytes):
        self.path.write_bytes(data)
        before = self.path.read_bytes()
        with self.assertRaises(DBCInspectionError):
            inspect_spell_dbc(self.path)
        self.assertEqual(before, self.path.read_bytes())

    def test_good_three_spells_and_speed_nonzero(self):
        data = make_dbc(GOOD)
        digest, result = self.inspect(data)
        self.assertEqual(digest, hashlib.sha256(data).hexdigest())
        self.assertEqual(tuple(sorted(result)), (42074, 42339, 42348))
        self.assertEqual(result[42339].effects[0], 3)
        self.assertAlmostEqual(result[42348].speed, 12.5)
        view = format_observations(digest, result)
        self.assertIn("F10_42348_DBC_SPEED_CATEGORY=POSITIVE", view)
        self.assertIn("OWNER_CLIENT_SERVER_DBC_PARITY=UNVERIFIED", view)
        self.assertIn("core ordering, other timing", view)

    def test_zero_speed_category_not_runtime_proof(self):
        entries = ((42074, 0.0, 6), (42339, 0.0, 3), (42348, 0.0, 3))
        digest, parsed = self.inspect(make_dbc(entries))
        view = format_observations(digest, parsed)
        self.assertIn("F10_42348_DBC_SPEED_CATEGORY=ZERO", view)
        self.assertIn("NOT TESTED", view)

    def test_extra_irrelevant_record_allowed(self):
        entries = GOOD + ((1234, 6.5, 3),)
        _, found = self.inspect(make_dbc(entries))
        self.assertEqual(len(found), 3)

    def test_missing_and_duplicate_critical_spell_refused(self):
        self.assert_rejects(make_dbc(GOOD[:2]))
        self.assert_rejects(make_dbc(GOOD + (GOOD[1],)))

    def test_missing_effect0_dummy_refused(self):
        entries = ((42074, 0, 6), (42339, 0, 9), (42348, 0, 3))
        self.assert_rejects(make_dbc(entries))

    def test_nonfinite_and_negative_speed_refused(self):
        for speed in (float("inf"), float("-inf"), float("nan"), -4.0):
            with self.subTest(speed=speed):
                self.assert_rejects(make_dbc(
                    ((42074, 0, 6), (42339, 0, 3), (42348, speed, 3))
                ))

    def test_truncated_extra_padding_and_corrupt_magic(self):
        good = make_dbc(GOOD)
        self.assert_rejects(good[:-1])
        self.assert_rejects(good + b"\0")
        self.assert_rejects(b"FAIL" + good[4:])

    def test_rejects_unknown_layout_instead_of_guessing_index(self):
        self.assert_rejects(make_dbc(GOOD, fields=233))
        self.assert_rejects(make_dbc(GOOD, fields=235))
        good = bytearray(make_dbc(GOOD))
        struct.pack_into("<I", good, 12, 4)  # bogus row byte width
        self.assert_rejects(bytes(good))

    def test_empty_and_invalid_string_block(self):
        self.assert_rejects(make_dbc(GOOD, string_block=b""))
        self.assert_rejects(make_dbc(GOOD, string_block=b"A"))

    def test_missing_and_nonfile_paths_fails_closed(self):
        with self.assertRaises(DBCInspectionError):
            inspect_spell_dbc(self.path)
        with self.assertRaises(DBCInspectionError):
            inspect_spell_dbc(Path(self.temp.name))

    def test_reader_has_no_write_or_mutation_path(self):
        code = (Path(__file__).resolve().parents[1] /
                "scripts/inspect_f10_spell_dbc_readonly.py").read_text()
        self.assertIn("raw = path.read_bytes()", code)
        for forbidden in (".write_bytes(", ".write_text(", ".unlink(",
                          ".rename(", "subprocess.", "requests.",
                          "urllib.", "open(path, 'w'", 'open(path, "w"'):
            self.assertNotIn(forbidden, code)
        self.assertIn("F10_DBC_INSPECTION_COMPLETED_READ_ONLY", code)


if __name__ == "__main__":
    unittest.main()
