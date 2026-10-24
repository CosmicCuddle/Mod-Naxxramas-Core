"""Synthetic SQLite witnesses for A04 source mapping examples.

In-memory, disposable tables only. No owner database, credentials, server,
network or game world is contacted. These are SQL join tests, not proof of
live eligibility, a client loot slot, or a user's reported wrong pickup.
"""
from pathlib import Path
import re
import sqlite3
import unittest

DOC = (Path(__file__).resolve().parents[1] /
       "docs/research/A04-READ-ONLY-ITEM-LOOT-PREFLIGHT.md").read_text(encoding="utf-8")


def source_queries():
    blocks = re.findall(r"```sql\n(.*?)\n```", DOC, flags=re.DOTALL)
    assert len(blocks) == 6, "source queries must retain stable six-block layout"
    return blocks[4:6]


class A04SQLSourceMappingWitness(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE creature_template (entry INTEGER, name TEXT, lootid INTEGER);
            CREATE TABLE creature_loot_template
                (Entry INTEGER, Item INTEGER, Reference INTEGER, QuestRequired INTEGER);
            CREATE TABLE gameobject_template
                (entry INTEGER, name TEXT, type INTEGER, Data1 INTEGER);
            CREATE TABLE gameobject_loot_template
                (Entry INTEGER, Item INTEGER, Reference INTEGER, QuestRequired INTEGER);
            CREATE TABLE reference_loot_template
                (Entry INTEGER, Item INTEGER, Reference INTEGER, QuestRequired INTEGER);
        """)
        self.db.executemany("INSERT INTO creature_template VALUES (?, ?, ?)", [
            (101, "direct creature", 501),
            (102, "reference creature", 502),
            (103, "unrelated creature", 503),
        ])
        self.db.executemany("INSERT INTO creature_loot_template VALUES (?, ?, ?, ?)", [
            (501, 7777, 0, 1),
            (502, 0, 900, 0),
            (503, 8888, 0, 0),
        ])
        self.db.executemany("INSERT INTO gameobject_template VALUES (?, ?, ?, ?)", [
            (201, "chest", 3, 601),
            (202, "fishing hole", 25, 602),
            (203, "quest giver sharing Data1", 2, 601),
            (204, "nested-only chest", 3, 603),
        ])
        self.db.executemany("INSERT INTO gameobject_loot_template VALUES (?, ?, ?, ?)", [
            (601, 7777, 0, 1),
            (602, 0, 901, 0),
            (603, 0, 903, 0),
        ])
        self.db.executemany("INSERT INTO reference_loot_template VALUES (?, ?, ?, ?)", [
            (900, 7777, 0, 1),
            (901, 7777, 902, 1),
            (903, 0, 904, 0),
            (904, 7777, 0, 1),
        ])

    def query(self, index, item=7777):
        query = source_queries()[index]
        return self.db.execute(query, {"a04_item_id": item}).fetchall()

    def test_creature_direct_and_reference_templates(self):
        self.assertEqual({row[0] for row in self.query(0)}, {101, 102})

    def test_creature_reference_keeps_outer_and_inner_flags(self):
        referenced = next(row for row in self.query(0) if row[0] == 102)
        self.assertEqual(referenced[5], 0)  # outer QuestRequired
        self.assertEqual(referenced[8], 1)  # referenced QuestRequired

    def test_chest_and_fishing_hole_are_included(self):
        self.assertEqual({row[0] for row in self.query(1)}, {201, 202})

    def test_other_go_type_with_matching_data1_is_excluded(self):
        self.assertNotIn(203, {row[0] for row in self.query(1)})

    def test_deeper_reference_id_retained_but_not_followed(self):
        gameobjects = {row[0]: row for row in self.query(1)}
        self.assertEqual(gameobjects[202][9], 902)  # one-hop row points deeper
        self.assertNotIn(204, gameobjects)  # target only two levels deep

    def test_item_id_scoping_on_both_sources(self):
        self.assertEqual(self.query(0, item=123456), [])
        self.assertEqual(self.query(1, item=123456), [])

    def test_no_external_database_name_or_sql_write_in_queries(self):
        for query in source_queries():
            self.assertNotRegex(query.upper(), r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b")
            self.assertNotIn("characters.", query.lower())


if __name__ == "__main__":
    unittest.main()
