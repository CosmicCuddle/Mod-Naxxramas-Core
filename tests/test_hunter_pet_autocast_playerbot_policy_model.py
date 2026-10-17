"""Synthetic Playerbot autocast-policy conflict cases; NO runtime code.

Simulates explicitly source-backed behaviour of pinned PetsAction:
for each known autocastable spell, policy is ON except disabledPetSpells.
This does not assert when or how often the real AI schedules that action.
"""
from dataclasses import dataclass
import unittest


@dataclass(frozen=True)
class Spell:
    spell_id: int
    autocastable: bool = True
    removed: bool = False


PROWL = 24450
COWER = 1742
BITE = 17261
GROWL = 14916
DISABLED_PET_SPELLS = frozenset({PROWL, COWER})


def bot_policy_run(spells, currently_on, disabled=DISABLED_PET_SPELLS):
    """Source-like local policy, never permission for Naxx to enforce."""
    on = set(currently_on)
    changes = []
    for known in spells:
        if known.removed or not known.autocastable:
            continue
        desired = known.spell_id not in disabled
        current = known.spell_id in on
        if desired == current:
            continue
        if desired:
            on.add(known.spell_id)
        else:
            on.discard(known.spell_id)
        changes.append((known.spell_id, desired))
    return frozenset(on), tuple(changes)


class PinnedPlayerbotPolicyCounterexamples(unittest.TestCase):
    def test_general_spell_default_on_but_specific_cower_off(self):
        known = [Spell(BITE), Spell(GROWL), Spell(COWER), Spell(PROWL)]
        after, changes = bot_policy_run(known, {COWER, PROWL})
        self.assertEqual(after, frozenset({BITE, GROWL}))
        self.assertIn((BITE, True), changes)
        self.assertIn((COWER, False), changes)

    def test_bot_policy_can_override_external_saved_off(self):
        # Hypothetical external store says BITE OFF. Running bot's own
        # action later reasserts its independent ON preference.
        after, changes = bot_policy_run([Spell(BITE)], set())
        self.assertEqual(after, frozenset({BITE}))
        self.assertEqual(changes, ((BITE, True),))

    def test_bot_policy_can_override_external_saved_on(self):
        after, changes = bot_policy_run([Spell(COWER)], {COWER})
        self.assertEqual(after, frozenset())
        self.assertEqual(changes, ((COWER, False),))

    def test_relearn_reset_off_then_bot_reassert_on(self):
        # IP re-learn can set autocast OFF. Bot policy can subsequently
        # enable Bite; neither action is necessarily a human choice.
        after, changes = bot_policy_run([Spell(BITE)], set())
        self.assertEqual((after, changes),
                         (frozenset({BITE}), ((BITE, True),)))

    def test_non_autocastable_or_removed_spells_unaffected(self):
        after, changes = bot_policy_run(
            [Spell(BITE, autocastable=False), Spell(COWER, removed=True)],
            {BITE, COWER})
        self.assertEqual(after, frozenset({BITE, COWER}))
        self.assertEqual(changes, ())

    def test_repeated_has_pet_policy_trigger_can_undo_user_override(self):
        # The pinned noncombat HunterPetStrategy can schedule the
        # policy action whenever its "has pet" trigger is active.
        known = [Spell(BITE)]
        master_wants_off = set()
        after_first, _ = bot_policy_run(known, master_wants_off)
        self.assertEqual(after_first, frozenset({BITE}))
        # A human/chat override of OFF can be undone on a later run.
        after_second, _ = bot_policy_run(known, master_wants_off)
        self.assertEqual(after_second, frozenset({BITE}))

    def test_idempotent_bot_policy_is_not_stable_human_intent(self):
        _, first = bot_policy_run([Spell(BITE)], set())
        _, second = bot_policy_run([Spell(BITE)], {BITE})
        self.assertEqual(first, ((BITE, True),))
        self.assertEqual(second, ())
        # Nothing proves bot's master requested the same ON state.

    def test_master_command_direct_toggle_can_conflict_with_default(self):
        known = [Spell(BITE)]
        # User-issued request in a bot command may be deliberate,
        # but current packet observer receives NO accepted packet.
        explicit_command_off = set()
        later, changes = bot_policy_run(known, explicit_command_off)
        self.assertEqual((later, changes),
                         (frozenset({BITE}), ((BITE, True),)))


if __name__ == "__main__":
    unittest.main()
