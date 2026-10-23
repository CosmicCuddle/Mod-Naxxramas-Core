"""B03/B04 DBC documentation source contract: no DBC or SQL edits.

This tests whether the docs list verified *source dependencies*. It cannot
establish whether the actual server/client Spell.dbc contains correct rows.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "docs/DBC-CHANGES.md"
README = ROOT / "README.md"
WRACK = ROOT / "src/Class/Warlock/WarlockWrack.cpp"
WRACK_BOTS = ROOT / "src/Class/Warlock/WarlockWrackBots.cpp"
ROCKBITER = ROOT / "src/Class/Shaman/ShamanRockbiter.cpp"
MANA_SQL = ROOT / "data/sql/db-world/2026_09_20_02_blood_elf_mana_tap.sql"


class DbcReleaseManifestSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = (DBC, README, WRACK, WRACK_BOTS, ROCKBITER, MANA_SQL)
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            raise AssertionError("Missing repository files: " + ", ".join(missing))
        cls.doc = DBC.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")
        cls.wrack = WRACK.read_text(encoding="utf-8")
        cls.wrack_bots = WRACK_BOTS.read_text(encoding="utf-8")
        cls.rock = ROCKBITER.read_text(encoding="utf-8")
        cls.mana_sql = MANA_SQL.read_text(encoding="utf-8")

    def test_wrack_source_dependency_is_documented(self):
        self.assertIn("SPELL_WARLOCK_WRACK = 90058", self.wrack)
        self.assertIn("SPELL_WRACK = 90058", self.wrack_bots)
        self.assertIn("### 90058", self.doc)

    def test_rockbiter_hidden_aura_is_documented(self):
        self.assertIn("SPELL_ROCKBITER_THREAT_AURA = 90059", self.rock)
        self.assertIn("### 90059", self.doc)

    def test_rockbiter_helper_seven_rank_formula_exists(self):
        self.assertIn("SPELL_ROCKBITER_AP_RANK_1 = 90060", self.rock)
        self.assertIn("SPELL_ROCKBITER_AP_RANK_7 = 90066", self.rock)
        self.assertIn("SPELL_ROCKBITER_AP_RANK_1 + (rank - 1)", self.rock)
        self.assertIn("GetSpellInfo(helperSpellId)", self.rock)

    def test_release_backup_inventory_lists_all_nine_new_spells_once(self):
        index = self.doc.index("## Backup checklist")
        inventory = self.doc[index:].split("Spell.dbc\n", 1)[1].split("\nTalent.dbc", 1)[0]
        for spell_id in range(90058, 90067):
            with self.subTest(spell_id=spell_id):
                rows = re.findall(r"^\s*" + str(spell_id) + r"\s+-", inventory, flags=re.M)
                self.assertEqual(len(rows), 1)

    def test_extra_900xx_dependencies_are_not_stated_as_real_dbc_validation(self):
        self.assertIn("have **not** been independently inspected", self.doc)
        self.assertIn("not** proof that any current server or client file contains", self.doc)
        self.assertIn("Do **not** invent missing Spell.dbc effect fields", self.doc)

    def test_no_enchantment_dbc_change_is_required_by_rockbiter_source(self):
        self.assertIn("SpellItemEnchantment.dbc is intentionally NOT modified", self.rock)
        self.assertIn("explicitly **not** modified", self.doc)

    def test_mana_tap_sql_uses_optional_custom_spells_table(self):
        self.assertIn("playercreateinfo_spell_custom", self.mana_sql)
        self.assertIn("28734", self.mana_sql)
        self.assertIn("PlayerStart.CustomSpells = 1", self.readme)
        self.assertIn("Player::LearnCustomSpells()", self.readme)

    def test_docs_do_not_claim_owner_active_config_or_gameplay(self):
        self.assertIn("The owner's current setting has not been checked", self.readme)
        self.assertIn("no row editing", self.doc.lower())

    def test_release_preserves_backup_warning(self):
        self.assertIn("back up the original rows", self.doc)
        self.assertIn("client and server", self.doc)

if __name__ == "__main__":
    unittest.main()
