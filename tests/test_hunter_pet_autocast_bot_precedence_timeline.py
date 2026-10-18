"""Synthetic timeline counterexamples for pinned Playerbot autocast policy.

No runnable Worldserver bot, active IP event, Pet, SQL or autocast mutation.
These tests do not infer the actual cadence of a live Hunter's AI.
"""
import unittest


def ip_relearn(known_rank, previous_state):
    """Synthetic IP remove+relearn returns legal known rank with native OFF."""
    assert known_rank
    return False


def playerbot_policy(native_on, bot_default_on, policy_action_runs):
    """Absent an actual AI action, preserve the current native state."""
    return bot_default_on if policy_action_runs else native_on


class BotPrecedenceTimelines(unittest.TestCase):
    def test_ip_relearn_off_before_next_bot_action(self):
        native_on = ip_relearn(True, True)
        self.assertFalse(native_on)
        self.assertTrue(playerbot_policy(native_on, True, policy_action_runs=True))

    def test_master_off_for_bite_can_be_overridden_by_bot_policy(self):
        master_off = False
        later = playerbot_policy(master_off, True, policy_action_runs=True)
        self.assertTrue(later)

    def test_master_on_for_cower_can_be_overridden_by_bot_policy(self):
        master_on = True
        later = playerbot_policy(master_on, False, policy_action_runs=True)
        self.assertFalse(later)

    def test_unverified_strategy_activation_cannot_be_assumed(self):
        master_off = False
        self.assertFalse(playerbot_policy(master_off, True, policy_action_runs=False))
        self.assertTrue(playerbot_policy(master_off, True, policy_action_runs=True))

    def test_unknown_or_missing_rank_cannot_be_granted_by_policy(self):
        known_legal_rank = False
        self.assertFalse(known_legal_rank)
        # The actual native bot policy visits existing known eligible spells.
        # This is NEVER a license to teach or select an unavailable rank.


if __name__ == "__main__":
    unittest.main()
