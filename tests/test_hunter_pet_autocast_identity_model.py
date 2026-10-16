"""Pure offline HPA-G3 counterexamples, NOT runtime pet/DB tests.

The allocator below mirrors the exact pinned Grimfeather source semantics:
LoadPetNumber() sets max(character_pet.id)+1, GeneratePetNumber()
pre-increments the counter. It demonstrates *why* pet numbers cannot be a
durable incarnation key. Does not contact or alter any database.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = (ROOT / "docs/HUNTER-PET-AUTOCAST-IDENTITY-GATE.md").read_text("utf-8")


def first_generated_number_after_restart(saved_pet_ids):
    hi = (max(saved_pet_ids) if saved_pet_ids else 0) + 1
    hi += 1  # ++_hiPetNumber
    return hi


def safe_to_restore(*, verified_incarnation, confirmed_explicit_choice,
                    legal_spell_already_known, post_ip_ready,
                    is_altbot):
    # Deliberately conservative decision model; NOT module code.
    return (verified_incarnation and confirmed_explicit_choice in ("ON", "OFF")
            and legal_spell_already_known and post_ip_ready and not is_altbot)


class PetAutocastIdentityCounterexamples(unittest.TestCase):
    def test_native_pet_number_can_be_reused_after_delete_restart(self):
        saved = {100, 102, 104}
        old_number = 104
        saved.remove(old_number)
        self.assertEqual(first_generated_number_after_restart(saved), old_number)

    def test_owner_pet_number_and_creature_entry_do_not_prove_incarnation(self):
        old = (42, 104, 1992)
        newly_tamed = (42, first_generated_number_after_restart({100, 102}), 1992)
        self.assertEqual(old, newly_tamed)
        self.assertNotEqual("old pet identity", "new pet identity")

    def test_gap_when_module_absent_defeats_sidecar_only_identity(self):
        # A sidecar persisted this prior identity. During a disabled period,
        # the old native row disappeared and the number was later reissued.
        stale_sidecar = (42, 104, 1992)
        after_gap = (42, 104, 1992)
        self.assertEqual(stale_sidecar, after_gap)
        self.assertFalse(safe_to_restore(
            verified_incarnation=False, confirmed_explicit_choice="ON",
            legal_spell_already_known=True, post_ip_ready=True,
            is_altbot=False))

    def test_explicit_off_is_not_unknown(self):
        self.assertTrue(safe_to_restore(
            verified_incarnation=True, confirmed_explicit_choice="OFF",
            legal_spell_already_known=True, post_ip_ready=True,
            is_altbot=False))
        self.assertFalse(safe_to_restore(
            verified_incarnation=True, confirmed_explicit_choice=None,
            legal_spell_already_known=True, post_ip_ready=True,
            is_altbot=False))

    def test_no_restore_when_ip_stage_spell_knowledge_or_identity_unknown(self):
        common = dict(verified_incarnation=True,
                      confirmed_explicit_choice="ON",
                      legal_spell_already_known=True,
                      post_ip_ready=True, is_altbot=False)
        self.assertTrue(safe_to_restore(**common))
        for key in ("verified_incarnation", "legal_spell_already_known",
                    "post_ip_ready"):
            case = dict(common)
            case[key] = False
            self.assertFalse(safe_to_restore(**case))

    def test_direct_playerbots_policy_is_not_user_choice(self):
        self.assertFalse(safe_to_restore(
            verified_incarnation=True, confirmed_explicit_choice="ON",
            legal_spell_already_known=True, post_ip_ready=True,
            is_altbot=True))

    def test_document_preserves_hard_blockers(self):
        for phrase in (
            "MAX(id) FROM character_pet",
            "CHAR_DEL_CHAR_PET_BY_ID",
            "same owner, pet number and creature type",
            "Unknown/ambiguous identity",
            "no verified public callback",
            "explicit OFF",
            "NO PERSISTENCE DESIGN APPROVED",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, GATE)


if __name__ == "__main__":
    unittest.main()
