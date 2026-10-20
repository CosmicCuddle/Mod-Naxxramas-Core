"""Policy tests for the A02 S1 hunter-pet autocast source model.

These tests do not compile AzerothCore and do not restore a pet. They pin
the control-flow claims in docs/research/a02-s1-hunter-pet-autocast.md.
Citation checks run only when the pinned trees are available in the
environment; the GitHub workflow runs them as a separate step.
"""

import os
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from a02_s1_hunter_pet_autocast import (  # noqa: E402
    ACT_DISABLED,
    ACT_ENABLED,
    CORE_NEW,
    CORE_OLD,
    IP_SHA,
    PET_SCRIPT_HOOKS,
    PLAYERBOTS_SHA,
    SUMMON_EVENT_ORDER,
    SavedPet,
    hook_between_ip_unlearn_and_learn,
    ip_reconcile,
    levelup_decision,
    cleanup_action_bar,
    load_saved_spell,
    native_rank_up,
    verify_citations,
)

BITE = 1
CLAW = 2
BITE_LOW = 17253
BITE_HIGH = 27050
BITE_KEEP_DUMMY = 617253
CLAW_HIGH = 27049


def human(**overrides):
    args = dict(
        knows_dummy={BITE_KEEP_DUMMY},
        chains={BITE_LOW: BITE, BITE_HIGH: BITE, CLAW_HIGH: CLAW},
        autocastable={BITE_LOW, BITE_HIGH, CLAW_HIGH},
        is_bot=False,
        is_hunter=True,
        vanilla_pets=True,
        passed_t5=False,
    )
    args.update(overrides)
    return args


def pet_with(spell_id, chain, active, slot=0):
    pet = SavedPet(pet_number=10)
    load_saved_spell(pet, spell_id, chain, active)
    # load places the spell in the first empty slot; move it if requested
    if slot != 0:
        pet.bar[slot].action = pet.bar[0].action
        pet.bar[slot].chain = pet.bar[0].chain
        pet.bar[slot].kind = pet.bar[0].kind
        pet.bar[0] = type(pet.bar[0])()
    return pet


class NativePreferenceTests(unittest.TestCase):
    def test_load_keeps_explicit_on_and_off(self):
        on_pet = SavedPet(1)
        off_pet = SavedPet(2)
        self.assertEqual(load_saved_spell(on_pet, BITE_LOW, BITE, ACT_ENABLED), "loaded")
        self.assertEqual(load_saved_spell(off_pet, BITE_LOW, BITE, ACT_DISABLED), "loaded")
        self.assertEqual(on_pet.spells[BITE_LOW].active, ACT_ENABLED)
        self.assertEqual(on_pet.autospells, [BITE_LOW])
        self.assertEqual(off_pet.spells[BITE_LOW].active, ACT_DISABLED)
        self.assertEqual(off_pet.autospells, [])
        self.assertEqual(on_pet.bar[0].kind, ACT_ENABLED)
        self.assertEqual(off_pet.bar[0].kind, ACT_DISABLED)

    def test_higher_rank_copies_on_and_off(self):
        # The stand-in for SpellInfo::IsHighRankOf is a larger spell id.
        for active in (ACT_ENABLED, ACT_DISABLED):
            pet = pet_with(BITE_LOW, BITE, active)
            self.assertEqual(native_rank_up(pet, BITE_HIGH, BITE), "copied")
            self.assertNotIn(BITE_LOW, pet.spells)
            self.assertEqual(pet.spells[BITE_HIGH].active, active)
            self.assertEqual(pet.bar[0].action, BITE_HIGH)
            self.assertEqual(pet.bar[0].kind, active)
            if active == ACT_ENABLED:
                self.assertEqual(pet.autospells, [BITE_HIGH])
            else:
                self.assertEqual(pet.autospells, [])

    def test_lower_rank_is_rejected_and_does_not_change_active(self):
        pet = pet_with(BITE_HIGH, BITE, ACT_ENABLED)
        self.assertEqual(native_rank_up(pet, BITE_LOW, BITE), "rejected_lower")
        self.assertEqual(pet.spells[BITE_HIGH].active, ACT_ENABLED)
        self.assertNotIn(BITE_LOW, pet.spells)

    def test_cleanup_reapplies_bar_over_saved_active(self):
        pet = pet_with(BITE_LOW, BITE, ACT_DISABLED)
        pet.bar[0].kind = ACT_ENABLED
        cleanup_action_bar(pet)
        self.assertEqual(pet.spells[BITE_LOW].active, ACT_ENABLED)
        self.assertEqual(pet.autospells, [BITE_LOW])

    def test_false_unlearn_hook_still_learns(self):
        self.assertEqual(levelup_decision(20, 10, hook_returns_true=False), "learn")
        self.assertEqual(levelup_decision(20, 10, hook_returns_true=True), "unlearn")
        self.assertEqual(levelup_decision(10, 10, hook_returns_true=True), "learn")


class IpReconcileTests(unittest.TestCase):
    def test_rank_change_drops_explicit_on(self):
        pet = pet_with(BITE_HIGH, BITE, ACT_ENABLED)
        origin = ip_reconcile(pet, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human())
        self.assertEqual(origin, "default_off")
        self.assertEqual(pet.spells[BITE_LOW].active, ACT_DISABLED)
        self.assertNotIn(BITE_HIGH, pet.spells)
        self.assertNotIn(BITE_LOW, pet.autospells)
        self.assertIn(BITE_HIGH, pet.autospells)  # removeSpell does not clear this
        self.assertEqual(pet.bar[0].action, BITE_LOW)
        self.assertEqual(pet.bar[0].kind, ACT_DISABLED)

    def test_rank_change_explicit_off_matches_default_without_copy(self):
        pet = pet_with(BITE_HIGH, BITE, ACT_DISABLED)
        origin = ip_reconcile(pet, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human())
        self.assertEqual(origin, "default_off")
        self.assertEqual(pet.spells[BITE_LOW].active, ACT_DISABLED)
        self.assertEqual(pet.autospells, [])

    def test_same_rank_preserves_explicit_on_and_off(self):
        for active in (ACT_ENABLED, ACT_DISABLED):
            pet = pet_with(BITE_LOW, BITE, active)
            origin = ip_reconcile(pet, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human())
            self.assertEqual(origin, "already_known")
            self.assertEqual(pet.spells[BITE_LOW].active, active)
            self.assertEqual(pet.bar[0].kind, active)

    def test_empty_dummy_list_removes_the_spell(self):
        pet = pet_with(CLAW_HIGH, CLAW, ACT_ENABLED)
        origin = ip_reconcile(pet, [CLAW_HIGH], [], **human(knows_dummy=set()))
        self.assertEqual(origin, "removed_without_keep")
        self.assertNotIn(CLAW_HIGH, pet.spells)
        self.assertEqual(pet.bar[0].action, 0)

    def test_bot_hunter_is_not_rewritten(self):
        pet = pet_with(BITE_HIGH, BITE, ACT_ENABLED)
        origin = ip_reconcile(pet, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human(is_bot=True))
        self.assertEqual(origin, "skipped")
        self.assertEqual(pet.spells[BITE_HIGH].active, ACT_ENABLED)

    def test_non_hunter_and_post_t5_and_disabled_config_skip(self):
        for flag in (dict(is_hunter=False), dict(passed_t5=True), dict(vanilla_pets=False)):
            pet = pet_with(BITE_HIGH, BITE, ACT_DISABLED)
            self.assertEqual(
                ip_reconcile(pet, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human(**flag)),
                "skipped",
            )
            self.assertEqual(pet.spells[BITE_HIGH].active, ACT_DISABLED)

    def test_second_pet_is_untouched(self):
        current = pet_with(BITE_HIGH, BITE, ACT_ENABLED)
        current.pet_number = 10
        stable = pet_with(BITE_HIGH, BITE, ACT_ENABLED)
        stable.pet_number = 11
        ip_reconcile(current, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human())
        self.assertEqual(stable.spells[BITE_HIGH].active, ACT_ENABLED)
        self.assertNotEqual(current.pet_number, stable.pet_number)

    def test_earlier_empty_slot_receives_the_relearned_spell(self):
        pet = pet_with(BITE_HIGH, BITE, ACT_ENABLED, slot=3)
        ip_reconcile(pet, [BITE_LOW, BITE_HIGH], [BITE_KEEP_DUMMY], **human())
        self.assertEqual(pet.bar[0].action, BITE_LOW)
        self.assertEqual(pet.bar[0].kind, ACT_DISABLED)
        self.assertEqual(pet.bar[3].action, 0)


class HookWindowTests(unittest.TestCase):
    def test_no_petscript_hook_between_unlearn_and_learn(self):
        self.assertEqual(hook_between_ip_unlearn_and_learn(), ())
        unlearn = SUMMON_EVENT_ORDER.index("ip_delayed_event_unlearn")
        learn = SUMMON_EVENT_ORDER.index("ip_delayed_event_learn")
        self.assertEqual(learn, unlearn + 1)

    def test_spells_load_before_the_ip_event_and_after_add_to_world(self):
        order = SUMMON_EVENT_ORDER
        self.assertLess(order.index("OnPetAddToWorld"), order.index("_LoadSpells"))
        self.assertLess(order.index("_LoadSpells"), order.index("ip_delayed_event_unlearn"))
        self.assertLess(
            order.index("OnCalculateMaxTalentPointsForLevel_after_spells"),
            order.index("InitLevelupSpellsForLevel"),
        )

    def test_known_petscript_surface_has_no_autocast_hook(self):
        self.assertNotIn("OnPetSpellAutocast", PET_SCRIPT_HOOKS)
        self.assertNotIn("OnBeforePetUnlearnSpell", PET_SCRIPT_HOOKS)
        self.assertEqual(PET_SCRIPT_HOOKS[-1], "OnPetAddToWorld")


class PinIdentityTests(unittest.TestCase):
    def test_research_doc_names_the_pins_and_the_verdict(self):
        doc = Path(__file__).resolve().parents[1].joinpath(
            "docs/research/a02-s1-hunter-pet-autocast.md").read_text()
        for pin in (CORE_OLD, CORE_NEW, IP_SHA, PLAYERBOTS_SHA):
            self.assertIn(pin, doc)
        self.assertIn("NO SAFE MODULE HOOK", doc)
        self.assertIn("VERIFIED", doc)
        self.assertIn("NOT TESTED", doc)
        self.assertIn("POTENTIAL ISSUE", doc)
        self.assertIn("UNKNOWN", doc)
        self.assertIn("upstream IP change is indispensable", doc)

    def test_citations_against_local_checkouts_when_configured(self):
        if not os.environ.get("A02_CORE_OLD"):
            self.skipTest("pinned checkouts are not configured")
        failures = verify_citations()
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
