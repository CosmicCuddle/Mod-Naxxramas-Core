"""Source-faithful synthetic model of pinned IP Hunter pet rank reconciliation.

This is NOT imported by Worldserver and never touches actual spells, SQL,
player progression, or pet preferences. A no-op under hypothetical frozen
inputs is NOT an event completion signal or authorization to restore ON/OFF.
"""
from dataclasses import dataclass
import unittest


@dataclass(frozen=True)
class Reconcile:
    wipe: tuple[int, ...]
    dummy: tuple[int, ...]


def execute_ip_calls(calls, pet_known, hunter_dummies):
    """Copy pinned checkHunterPetSpells inner reconcile semantics exactly.

    Returns the final simulated spellbook, every remove/learn action, and
    selected legal ranks (if any). An empty action log is stronger than
    comparing only final state because intermediate churn can reset autocast.
    """
    known = set(pet_known)
    actions = []
    selected = []
    for call in calls:
        keep = 0
        for dummy in reversed(call.dummy):
            if dummy in hunter_dummies:
                keep = dummy - 600000
                break
        if keep:
            selected.append(keep)
        for spell_id in call.wipe:
            if spell_id != keep and spell_id in known:
                known.remove(spell_id)
                actions.append(("unlearn", spell_id))
        if keep and keep not in known:
            known.add(keep)
            actions.append(("learn", keep))
    return frozenset(known), tuple(actions), tuple(selected)


def family_noop_under_frozen_inputs(calls, family_ranks, candidate,
                                   pet_known, hunter_dummies):
    """Synthetic per-family no-op condition, NOT runtime IP readiness.

    All applicable calls for the SAME family must be represented.
    Reject ambiguity, empty dummy-only justification and other ranks.
    """
    if candidate not in family_ranks:
        return False
    if set(pet_known) & set(family_ranks) != {candidate}:
        return False
    touching = tuple(call for call in calls
                     if set(call.wipe) & set(family_ranks))
    if not touching:
        return False
    _, actions, selected = execute_ip_calls(
        touching, pet_known, hunter_dummies)
    if any(spell in family_ranks for _, spell in actions):
        return False
    # At least one active IP reconciler must positively select THIS rank.
    # No dummy list => cannot establish entitlement from a no-op.
    if candidate not in selected:
        return False
    return True


BITE_RANKS = frozenset({17260, 17261, 27050})  # example R7, R8, R9
BITE = Reconcile(
    wipe=(17260, 17261, 27050),
    dummy=(617260, 617261, 627050),
)


class PetIPFixedPointModel(unittest.TestCase):
    def test_selected_known_bite_rank_is_noop_if_all_inputs_frozen(self):
        self.assertTrue(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 17261, {17261}, {617261}))
        final, operations, keep = execute_ip_calls(
            (BITE,), {17261}, {617261})
        self.assertEqual(final, frozenset({17261}))
        self.assertEqual(operations, ())
        self.assertEqual(keep, (17261,))

    def test_older_rank_present_makes_reconcile_mutating(self):
        self.assertFalse(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 17261, {17260, 17261}, {617261}))
        _, actions, _ = execute_ip_calls(
            (BITE,), {17260, 17261}, {617261})
        self.assertIn(("unlearn", 17260), actions)

    def test_missing_legal_rank_requires_learn_and_is_not_noop(self):
        self.assertFalse(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 17261, {17260}, {617261}))
        _, actions, _ = execute_ip_calls((BITE,), {17260}, {617261})
        self.assertIn(("learn", 17261), actions)

    def test_new_hunter_dummy_breaks_previous_fixed_point(self):
        self.assertTrue(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 17261, {17261}, {617261}))
        self.assertFalse(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 17261, {17261}, {617261, 627050}))
        _, actions, _ = execute_ip_calls(
            (BITE,), {17261}, {617261, 627050})
        self.assertIn(("unlearn", 17261), actions)
        self.assertIn(("learn", 27050), actions)

    def test_remove_only_call_does_not_prove_permitted_rank(self):
        removal_only = Reconcile(wipe=(35290, 35291), dummy=())
        self.assertFalse(family_noop_under_frozen_inputs(
            (removal_only,), {35290, 35291}, 35290,
            {35290}, set()))
        final, actions, keep = execute_ip_calls(
            (removal_only,), set(), set())
        self.assertEqual((final, actions, keep),
                         (frozenset(), (), ()))
        # Empty stable results cannot prove any permitted learned rank.

    def test_mutually_exclusive_boar_gore_progression_is_not_one_call(self):
        gore_ranks = {35290, 35291}
        pre_tbc = Reconcile(wipe=(35290, 35291), dummy=())
        later_tbc = Reconcile(wipe=(35290, 35291),
                              dummy=(635290, 635291))
        self.assertFalse(family_noop_under_frozen_inputs(
            (pre_tbc,), gore_ranks, 35291, {35291}, {635291}))
        self.assertTrue(family_noop_under_frozen_inputs(
            (later_tbc,), gore_ranks, 35291, {35291}, {635291}))
        # Which call actually runs depends on the Hunter's progression.

    def test_conflicting_calls_cannot_pass_even_if_net_state_same(self):
        first = Reconcile(wipe=(17261,), dummy=(617261,))
        second = Reconcile(wipe=(17261,), dummy=())
        third = Reconcile(wipe=(17261,), dummy=(617261,))
        final, operations, _ = execute_ip_calls(
            (first, second, third), {17261}, {617261})
        self.assertEqual(final, frozenset({17261}))
        self.assertEqual(operations,
                         (("unlearn", 17261), ("learn", 17261)))
        self.assertFalse(family_noop_under_frozen_inputs(
            (first, second, third), {17261}, 17261,
            {17261}, {617261}))

    def test_unknown_or_unmapped_spell_not_approved_by_noop(self):
        self.assertFalse(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 1, {1}, {617261}))
        self.assertFalse(family_noop_under_frozen_inputs(
            (), BITE_RANKS, 17261, {17261}, {617261}))

    def test_isolated_family_not_authority_to_restore_preference(self):
        self.assertTrue(family_noop_under_frozen_inputs(
            (BITE,), BITE_RANKS, 17261, {17261}, {617261}))
        # This says ONLY the hypothetical future IP operation is a no-op
        # while hunter dummies, effective stage and pet ranks stay fixed.
        # No human intent, active IP event, exact pet or DBC legality proof.


if __name__ == "__main__":
    unittest.main()
