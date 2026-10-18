"""Synthetic per-family pet autocast stability counterexamples.

NO runtime Pet, IP, Worldserver, database, DBC or restoration.
Identical observed values never authorize changing an ability.
"""
import unittest


def changed_families(previous, current):
    return tuple(sorted(
        family for family in set(previous) | set(current)
        if previous.get(family) != current.get(family)
    ))


def inspect_sequence(states):
    """Return per-step changes and unchanged streak; NEVER readiness."""
    previous = None
    unchanged = 0
    out = []
    for state in states:
        changes = () if previous is None else changed_families(previous, state)
        unchanged = (unchanged + 1 if previous == state else 0)
        out.append((changes, unchanged))
        previous = dict(state)
    return out


class AbilityStabilityReadOnlyModel(unittest.TestCase):
    def test_bite_and_growl_tracked_independently(self):
        before = {"bite": ("rank7", "OFF"), "growl": ("rank2", "ON")}
        after = {"bite": ("rank8", "OFF"), "growl": ("rank2", "ON")}
        self.assertEqual(changed_families(before, after), ("bite",))

    def test_removed_family_and_added_family_both_visible(self):
        self.assertEqual(changed_families(
            {"lightning": ("rank5", "ON")},
            {"bite": ("rank8", "OFF")}),
            ("bite", "lightning"))

    def test_all_unchanged_samples_can_still_precede_delayed_ip_relearn(self):
        stable_off = {"lightning": ("rank5", "OFF")}
        after_ip = {"lightning": ("rank5", "ON")}
        observations = inspect_sequence(
            [stable_off, stable_off, stable_off, stable_off, after_ip])
        self.assertEqual(observations[3], ((), 3))
        self.assertEqual(observations[4], (("lightning",), 0))
        # Four matching observations cannot prove that an IP event completed.

    def test_two_ranks_same_family_do_not_look_identical(self):
        a = {"bite": ("rank7/ON,",)}
        b = {"bite": ("rank7/ON,rank8/OFF,",)}
        self.assertEqual(changed_families(a, b), ("bite",))

    def test_empty_and_unknown_both_do_not_mean_ip_complete(self):
        states = inspect_sequence([{}, {}, {}])
        self.assertEqual(states[-1], ((), 2))
        self.assertNotIn("ip_ready", str(states).lower())


if __name__ == "__main__":
    unittest.main()
