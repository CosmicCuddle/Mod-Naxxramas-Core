"""Pure offline model for generic Hunter pet autocast preference resolution.

This is a SPECIFICATION / SAFETY COUNTEREXAMPLE, not deployed C++.
All IDs below are intentionally synthetic, NOT World of Warcraft spells.
Neither AzerothCore nor Individual Progression is instantiated here.
The model assumes an independently VERIFIED durable incarnation token;
the repository has NOT established how to obtain one.
"""
from dataclasses import dataclass
import unittest

BITE_R7, BITE_R8 = 101, 102
GROWL_R1, GROWL_R2 = 201, 202
DASH_R1 = 301
LIGHTNING_R5, LIGHTNING_R6 = 401, 402
PASSIVE_BUFF = 900
FAMILY_BY_ID = {
    BITE_R7: "bite", BITE_R8: "bite",
    GROWL_R1: "growl", GROWL_R2: "growl",
    DASH_R1: "dash",
    LIGHTNING_R5: "lightning", LIGHTNING_R6: "lightning",
}
AUTOCASTABLE = set(FAMILY_BY_ID)


@dataclass(frozen=True)
class VerifiedPet:
    owner_guid: int
    incarnation: str  # A hypothetical NON-REUSABLE proof, not PetNumber.


def proposed_restore_plan(*, pet, incarnation_verified, remembered,
                          known_spells, legal_spells, ip_reconciled,
                          is_playerbot=False):
    """Return eligible proposed (spell ID, ON/OFF) pairs. Never mutate."""
    if not incarnation_verified or not ip_reconciled or is_playerbot:
        return ()

    planned = []
    for (saved_pet, family), choice in remembered.items():
        if saved_pet != pet or choice not in ("ON", "OFF"):
            continue  # includes unknown/unselected preference

        # No rank guesses: use only the spells actually known by this pet.
        # If any ambiguous ranked spells are currently known, fail closed.
        current = sorted(
            spell for spell in known_spells
            if FAMILY_BY_ID.get(spell) == family)
        if len(current) != 1:
            continue

        spell = current[0]
        if spell not in legal_spells or spell not in AUTOCASTABLE:
            continue
        planned.append((spell, choice))
    return tuple(sorted(planned))


class GenericAutocastSafetyModel(unittest.TestCase):
    def setUp(self):
        self.pet = VerifiedPet(42, "unique-incarnation-A")
        self.other = VerifiedPet(42, "unique-incarnation-B")
        self.known = {BITE_R8, GROWL_R2, DASH_R1, LIGHTNING_R5}

    def run_plan(self, remembered, **overrides):
        values = dict(pet=self.pet, incarnation_verified=True,
                      remembered=remembered, known_spells=self.known,
                      legal_spells=set(self.known), ip_reconciled=True)
        values.update(overrides)
        return proposed_restore_plan(**values)

    def test_independent_on_and_off_for_all_spell_families(self):
        preferences = {
            (self.pet, "bite"): "ON",
            (self.pet, "growl"): "OFF",
            (self.pet, "dash"): "ON",
            (self.pet, "lightning"): "OFF",
        }
        self.assertEqual(self.run_plan(preferences), (
            (BITE_R8, "ON"), (GROWL_R2, "OFF"),
            (DASH_R1, "ON"), (LIGHTNING_R5, "OFF")))

    def test_different_pet_never_inherits_ability_family_preference(self):
        remembered = {(self.other, "bite"): "ON"}
        self.assertEqual(self.run_plan(remembered), ())

    def test_explicit_off_is_distinct_from_absent_choice(self):
        self.assertEqual(self.run_plan({(self.pet, "bite"): "OFF"}),
                         ((BITE_R8, "OFF"),))
        self.assertEqual(self.run_plan({}), ())
        self.assertEqual(self.run_plan({(self.pet, "bite"): None}), ())

    def test_legal_rank_upgrade_keeps_the_family_choice(self):
        remembered = {(self.pet, "bite"): "ON"}
        self.assertEqual(self.run_plan(
            remembered, known_spells={BITE_R7},
            legal_spells={BITE_R7}), ((BITE_R7, "ON"),))
        self.assertEqual(self.run_plan(
            remembered, known_spells={BITE_R8},
            legal_spells={BITE_R8}), ((BITE_R8, "ON"),))

    def test_illegal_or_unlearned_rank_not_selected(self):
        remembered = {(self.pet, "lightning"): "ON"}
        self.assertEqual(self.run_plan(
            remembered, known_spells={LIGHTNING_R6},
            legal_spells={LIGHTNING_R5}), ())
        self.assertEqual(self.run_plan(
            remembered, known_spells=set(),
            legal_spells={LIGHTNING_R6}), ())

    def test_conflicting_multiple_known_ranks_fail_closed(self):
        remembered = {(self.pet, "bite"): "ON"}
        self.assertEqual(self.run_plan(
            remembered, known_spells={BITE_R7, BITE_R8},
            legal_spells={BITE_R8}), ())

    def test_passive_or_unmapped_spell_never_gets_a_preference(self):
        remembered = {(self.pet, "unmapped-passive"): "ON"}
        self.assertEqual(self.run_plan(
            remembered, known_spells={PASSIVE_BUFF},
            legal_spells={PASSIVE_BUFF}), ())

    def test_not_ready_or_identity_unverified_skips_everything(self):
        saved = {(self.pet, "bite"): "ON"}
        self.assertEqual(self.run_plan(saved, ip_reconciled=False), ())
        self.assertEqual(self.run_plan(
            saved, incarnation_verified=False), ())

    def test_playerbot_direct_ai_policy_is_not_explicit_preference(self):
        remembered = {(self.pet, "bite"): "OFF"}
        self.assertEqual(self.run_plan(remembered, is_playerbot=True), ())

    def test_reused_pet_number_cannot_stand_in_for_incarnation(self):
        # A new pet may have the same native PetNumber and same spell set,
        # but must have a different verified incarnation marker.
        old = VerifiedPet(42, "old")
        new = VerifiedPet(42, "new")
        self.assertNotEqual(old, new)
        saved = {(old, "bite"): "ON"}
        self.assertEqual(self.run_plan(saved, pet=new), ())


if __name__ == "__main__":
    unittest.main()
