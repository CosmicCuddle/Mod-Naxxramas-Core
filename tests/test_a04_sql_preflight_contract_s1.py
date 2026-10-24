"""Static contracts for read-only A04 item/loot-template preflight.

Never connects to DB or evaluates SQL. Verifies the research document's
examples are SELECT-only after a client-local SET and target one item ID.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/research/A04-READ-ONLY-ITEM-LOOT-PREFLIGHT.md").read_text("utf-8")


def sql_examples():
    return re.findall(r"```sql\n(.*?)\n```", DOC, flags=re.DOTALL)


class SQLPreflightContract(unittest.TestCase):
    def test_four_classification_queries_present(self):
        blocks = sql_examples()
        self.assertEqual(len(blocks), 4)
        for table in ("item_template", "creature_loot_template", "gameobject_loot_template"):
            self.assertTrue(any(f"FROM {table}" in q for q in blocks), table)

    def test_reference_join_is_one_hop_and_does_not_hide_outer_flags(self):
        reference = sql_examples()[3]
        self.assertEqual(reference.count("JOIN reference_loot_template AS r"), 2)
        self.assertEqual(reference.count("WHERE r.Item = @a04_item_id"), 2)
        self.assertIn("UNION ALL", reference)
        for name in (
            "outer_quest_required",
            "referenced_quest_required",
            "deeper_reference_id",
            "outer_loot_mode",
            "referenced_loot_mode",
        ):
            self.assertIn(name, reference)
        self.assertIn("one reference hop", DOC)
        self.assertIn("not a proven resolved runtime rule", DOC)

    def test_no_world_write_statement_in_examples(self):
        for block in sql_examples():
            sql = re.sub(r"--[^\n]*", "", block)
            with self.subTest(block=block[:45]):
                self.assertNotRegex(
                    sql.upper(),
                    r"\b(?:INSERT|REPLACE|UPDATE|DELETE|TRUNCATE|ALTER|DROP|CREATE|GRANT|REVOKE|CALL)\s+",
                )
                self.assertIn("SELECT", sql.upper())

    def test_all_queries_limit_by_requested_item(self):
        for block in sql_examples():
            with self.subTest(block=block[:45]):
                self.assertIn("WHERE", block)
                self.assertIn("@a04_item_id", block)

    def test_pinned_flag_bits_and_independence(self):
        self.assertIn("ITEM_FLAG_MULTI_DROP = 0x00000800", DOC)
        self.assertIn("ITEM_FLAGS_CU_IGNORE_QUEST_STATUS = 0x0002", DOC)
        self.assertIn("ITEM_FLAGS_CU_FOLLOW_LOOT_RULES = 0x0004", DOC)
        self.assertIn("(Flags & 2048)", DOC)
        self.assertIn("(flagsCustom & 2)", DOC)
        self.assertIn("(flagsCustom & 4)", DOC)
        self.assertIn("two independent bits of evidence", DOC)

    def test_no_claim_of_actual_owner_item_or_repro(self):
        for phrase in (
            "not executed against an owner database",
            "no confirmed item ID or quest ID",
            "not necessarily a creature entry",
            "do not rule out",
            "No matching direct source row",
            "does not modify the world database",
        ):
            self.assertIn(phrase.lower(), DOC.lower())


if __name__ == "__main__":
    unittest.main()
