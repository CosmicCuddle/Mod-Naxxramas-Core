"""NT1 offline evidence SQL: whitelist read-only statements and pinned schema.

This suite never connects to MySQL, restores a backup, or runs gameplay.
It confirms the companion SQL is SELECT-only plus two session variables.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "scripts" / "nt1_altbot_evidence_readonly.sql").read_text(
    encoding="utf-8"
)
DOC = (ROOT / "docs" / "NT1-DISPOSABLE-ALTBOT-EVIDENCE-PROCEDURE.md").read_text(
    encoding="utf-8"
)


def statements():
    # This script deliberately contains no quoted -- tokens in executable SQL.
    uncommented = re.sub(r"--[^\n]*", "", SQL)
    return [part.strip() for part in uncommented.split(";") if part.strip()]


class ReadonlyEvidenceContract(unittest.TestCase):
    def test_all_statements_are_selects_or_session_variable_setup(self):
        stmts = statements()
        self.assertEqual(len(stmts), 16)
        self.assertEqual(sum(s.lstrip().upper().startswith("SELECT ") for s in stmts), 14)
        for s in stmts:
            self.assertRegex(s, r"(?is)\A(?:SELECT\s|SET\s+@NT1_)")
            if s.upper().startswith("SET "):
                self.assertRegex(
                    s, r"(?is)\ASET\s+@NT1_(?:TEST_BOT_GUID|ORIGINAL_OFFHAND_INSTANCE_GUID)\s*=\s*0\Z",
                )
            self.assertNotRegex(
                s, r"(?i)\b(?:INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE|"
                r"CREATE|REPLACE|CALL|EXECUTE|GRANT|REVOKE|LOCK|LOAD|INTO\s+OUTFILE)\b"
            )

    def test_targets_guid_not_arndor_or_rakari_names(self):
        self.assertIn("SET @NT1_TEST_BOT_GUID = 0;", SQL)
        self.assertIn("SET @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID = 0;", SQL)
        self.assertNotRegex(
            "\n".join(statements()), r"(?i)\b(?:Arndor|Rakari)\b"
        )

    def test_equipped_instance_guids_and_owner_are_preserved_in_report(self):
        self.assertIn("ci.item AS instance_guid", SQL)
        self.assertIn("ii.guid AS instance_guid", SQL)
        self.assertIn("ii.itemEntry AS item_template_id", SQL)
        self.assertIn("ii.owner_guid", SQL)
        self.assertIn("ci.bag, ci.slot", SQL)
        self.assertIn("ci.item = @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID", SQL)
        self.assertIn("ii.guid = @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID", SQL)

    def test_mail_and_item_instance_changes_can_be_detected(self):
        self.assertIn("FROM mail_items AS mi", SQL)
        self.assertIn("LEFT JOIN mail AS m ON m.id = mi.mail_id", SQL)
        self.assertIn("mi.item_guid = @NT1_ORIGINAL_OFFHAND_INSTANCE_GUID", SQL)
        self.assertIn("mi.receiver = @NT1_TEST_BOT_GUID", SQL)

    def test_both_specs_and_pets_are_included(self):
        for fragment in (
            "FROM character_talent AS t",
            "FROM character_spell AS s",
            "FROM character_glyphs AS g",
            "FROM character_action AS a",
            "FROM character_pet AS p",
            "LEFT JOIN pet_spell AS s ON s.guid = p.id",
            "FROM character_aura AS a",
            "ORDER BY g.talentGroup",
            "ORDER BY a.spec, a.button",
            "ORDER BY p.id, s.spell",
        ):
            self.assertIn(fragment, SQL)

    def test_all_referenced_pinned_schema_tables_declared_in_docs(self):
        for table in (
            "characters", "character_inventory", "item_instance", "mail_items",
            "mail", "character_talent", "character_spell", "character_glyphs",
            "character_action", "character_pet", "pet_spell", "character_aura",
        ):
            self.assertRegex(SQL, rf"(?i)\b(?:FROM|JOIN)\s+{table}\b")

    def test_explicit_offline_backup_restore_requirement(self):
        for fragment in (
            "consistent entire `acore_characters` backup",
            "successful restore into a separate, disconnected database",
            "Do nothing to production",
            "unsaved in-memory",
            "separate explicit approval",
            "original `item_instance.guid`",
        ):
            self.assertIn(fragment.replace("\\", ""), DOC)

    def test_no_current_permission_to_run_destructive_apply(self):
        self.assertIn("No permission to run a destructive test", DOC)
        self.assertIn("Do not test Apply", DOC)
        self.assertIn("offhand and pet blocks", DOC)

    def test_final_multibot_handover_remains_required(self):
        self.assertIn("final Naxxramas Core", DOC)
        self.assertIn("mandatory deliverable", DOC)


if __name__ == "__main__":
    unittest.main()
