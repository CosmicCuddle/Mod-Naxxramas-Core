import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "Systems" / "AltMailDelay.cpp"


class AltMailDelaySourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SRC.read_text(encoding="utf-8")

    def test_only_normal_player_mail_is_considered(self):
        self.assertIn("sender.GetMailMessageType() != MAIL_NORMAL", self.text)

    def test_returned_and_cod_payment_keep_core_behavior(self):
        self.assertIn("MAIL_CHECK_MASK_RETURNED", self.text)
        self.assertIn("MAIL_CHECK_MASK_COD_PAYMENT", self.text)

    def test_same_account_only(self):
        self.assertIn("if (senderAccount != receiverAccount)", self.text)

    def test_attachment_guard_precedes_delay_assignment(self):
        guard = self.text.index("if (!mailDraft || !mailDraft->HasItems())")
        delay = self.text.index("deliverDelay = sWorld->getIntConfig(CONFIG_MAIL_DELIVERY_DELAY);")
        self.assertLess(guard, delay)

    def test_no_gold_or_body_based_delay_condition(self):
        # The custom rule is attachment-only. Gold/body may coexist with an item,
        # but must never independently cause the same-account delay.
        delay_region = self.text[
            self.text.index("// Only change mail sent between alts on the same account.") :
            self.text.index("deliverDelay = sWorld->getIntConfig(CONFIG_MAIL_DELIVERY_DELAY);")
        ]
        self.assertNotIn("GetMoney()", delay_region)
        self.assertNotIn("GetBody()", delay_region)

    def test_has_items_is_the_only_positive_attachment_gate(self):
        self.assertEqual(self.text.count("HasItems()"), 1)
        self.assertRegex(
            self.text,
            re.compile(
                r"if \(!mailDraft \|\| !mailDraft->HasItems\(\)\)\s*return;\s*"
                r"deliverDelay = sWorld->getIntConfig\(CONFIG_MAIL_DELIVERY_DELAY\);",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
