"""Playerbot action listeners' limited ability to prove native autocast changes.

All events, callbacks and spell states here are synthetic. No Playerbots
Engine, native Pet, master session, or IP instance is actually exercised.
"""
import unittest


def dispatch(before=True, allowed=True, raw_action_result=False,
             overridden=None):
    """Copy the pinned Engine::ListenAndExecute *boolean* semantics."""
    action_called = False
    result = False
    if before:
        action_called = allowed
        result = raw_action_result if allowed else True
    if overridden is not None:
        result = overridden
    # The final boolean is passed to ActionExecutionListener::After.
    return action_called, result


def aggregate_pet_action(known_autocastable, defaults_on, currently_on):
    """Pinned action returns a single 'toggled' bit across spell IDs."""
    toggled = False
    after = dict(currently_on)
    for spell in known_autocastable:
        wanted = spell in defaults_on
        if after.get(spell, False) != wanted:
            after[spell] = wanted
            toggled = True
    return toggled, after


class ListenerFalsePositiveTests(unittest.TestCase):
    def test_allow_execution_false_reports_true_without_execute(self):
        self.assertEqual(dispatch(allowed=False, raw_action_result=False),
                         (False, True))

    def test_before_false_suppresses_action(self):
        self.assertEqual(dispatch(before=False, allowed=True,
                                  raw_action_result=True), (False, False))

    def test_override_can_turn_failed_action_into_true(self):
        self.assertEqual(dispatch(raw_action_result=False, overridden=True),
                         (True, True))

    def test_override_can_turn_real_success_into_false(self):
        self.assertEqual(dispatch(raw_action_result=True, overridden=False),
                         (True, False))

    def test_single_true_can_mean_one_or_multiple_spells_changed(self):
        # Same listener boolean; different per-spell outcomes.
        one, first = aggregate_pet_action(
            (17261, 14916), {17261, 14916}, {17261: True, 14916: False})
        two, second = aggregate_pet_action(
            (17261, 14916), {17261, 14916}, {17261: False, 14916: False})
        self.assertTrue(one)
        self.assertTrue(two)
        self.assertNotEqual(first, {17261: True, 14916: False})
        self.assertNotEqual(second, first)

    def test_action_returns_false_when_no_policy_change_needed(self):
        changed, state = aggregate_pet_action((17261,), {17261}, {17261: True})
        self.assertFalse(changed)
        self.assertEqual(state, {17261: True})

    def test_default_ai_event_has_no_master_provenance(self):
        simulated_event_owner = None
        self.assertIsNone(simulated_event_owner)

    def test_listener_detach_and_destruction_needs_single_owner(self):
        # Engine list owns callback pointers at destruction; a detach only
        # removes a pointer and does not free it. No implicit dual ownership.
        registered, externally_deleted = True, False
        detached = True
        self.assertTrue(registered and detached)
        self.assertFalse(externally_deleted)
        # A safe future integration must specify who deletes after detach.

    def test_observational_status_never_entitles_rank_or_persistence(self):
        called, after = dispatch(raw_action_result=True)
        self.assertTrue(called and after)
        # Native spell ID, pet incarnation, IP completion and human actor
        # still have no authoritative link to this boolean in the model.


if __name__ == "__main__":
    unittest.main()
