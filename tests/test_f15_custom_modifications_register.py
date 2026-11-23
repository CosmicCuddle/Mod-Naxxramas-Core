import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "F15_CUSTOM_MODIFICATIONS_REGISTER.md"

REQUIRED_FIELDS = (
    "Intended behaviour",
    "Owning component",
    "Source ref/version",
    "Config/SQL/DBC/client dependencies",
    "Known risks",
    "Tests",
    "Live status",
    "Rollback requirements",
)


class F15RegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REGISTER.read_text(encoding="utf-8")

    def entries(self):
        parts = re.split(r"^## (F15-[A-Z0-9-]+)$", self.text, flags=re.MULTILINE)
        return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}

    def test_expected_feature_ids_are_unique(self):
        ids = re.findall(r"^## (F15-[A-Z0-9-]+)$", self.text, flags=re.MULTILINE)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            set(ids),
            {
                "F15-OPERATIONAL-CLI-20261113",
                "F15-STAGING-PREFLIGHT-20261113",
                "F15-STAGING-BACKUP-ROLLBACK-20261113",
            },
        )

    def test_every_entry_has_required_safety_fields(self):
        for feature_id, body in self.entries().items():
            with self.subTest(feature_id=feature_id):
                for field in REQUIRED_FIELDS:
                    self.assertRegex(
                        body,
                        rf"\| {re.escape(field)} \| .+ \|",
                        msg=f"{feature_id} missing {field}",
                    )

    def test_no_entry_claims_live_or_deployed_state(self):
        for feature_id, body in self.entries().items():
            live = re.search(r"\| Live status \| (.+?) \|", body)
            self.assertIsNotNone(live, feature_id)
            value = live.group(1).lower()
            self.assertTrue(
                any(token in value for token in ("not installed", "uninstalled", "planning only")),
                msg=f"{feature_id} has unsafe live-status wording: {live.group(1)}",
            )

    def test_register_scope_is_explicitly_component_only(self):
        self.assertIn("F15 crash/log preservation and operational tooling only", self.text)
        self.assertIn("not a claim that all server customisations are catalogued here", self.text)


if __name__ == "__main__":
    unittest.main()
