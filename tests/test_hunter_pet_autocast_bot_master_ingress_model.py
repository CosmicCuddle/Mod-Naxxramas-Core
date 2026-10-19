"""Synthetic bot command-origin / queue / application ambiguity.

No active Playerbots action, pet or database. All 'positive' proof flags
are hypothetical and NOT supplied by Naxx Core at runtime.
"""
from dataclasses import dataclass
from enum import Enum, auto
import unittest


class Origin(Enum):
    UNKNOWN = auto()
    HUMAN_CHAT = auto()
    AI_GENERATED = auto()


class Review(Enum):
    SKIP = auto()
    CANDIDATE_ONLY = auto()


@dataclass(frozen=True)
class Evidence:
    origin: Origin = Origin.UNKNOWN
    chat_arrived: bool = False
    sender_is_current_master: bool = False
    playerbots_security_accepted: bool = False
    command_executed: bool = False
    native_change_applied: bool = False
    exact_pet_instance: bool = False
    exact_ability_and_state: bool = False
    requested_state_still_current: bool = False
    current_ip_rank_legal: bool = False
    authenticated_post_ip_completion: bool = False
    bot_default_conflicts: bool = False
    bot_policy_coordinated: bool = False


def review(e):
    if (e.origin is not Origin.HUMAN_CHAT or not e.chat_arrived
            or not e.sender_is_current_master
            or not e.playerbots_security_accepted
            or not e.command_executed or not e.native_change_applied
            or not e.exact_pet_instance or not e.exact_ability_and_state
            or not e.requested_state_still_current
            or not e.current_ip_rank_legal
            or not e.authenticated_post_ip_completion
            or (e.bot_default_conflicts and not e.bot_policy_coordinated)):
        return Review.SKIP
    return Review.CANDIDATE_ONLY  # STILL NOT permission to persist or toggle


def complete():
    return Evidence(
        origin=Origin.HUMAN_CHAT, chat_arrived=True,
        sender_is_current_master=True, playerbots_security_accepted=True,
        command_executed=True, native_change_applied=True,
        exact_pet_instance=True, exact_ability_and_state=True,
        requested_state_still_current=True, current_ip_rank_legal=True,
        authenticated_post_ip_completion=True,
        bot_default_conflicts=False, bot_policy_coordinated=False,
    )


class MasterIngressBoundary(unittest.TestCase):
    def test_chat_before_security_is_not_applied_preference(self):
        e = Evidence(origin=Origin.HUMAN_CHAT, chat_arrived=True,
                     sender_is_current_master=True)
        self.assertEqual(review(e), Review.SKIP)

    def test_security_approved_but_deferred_or_dropped(self):
        a = complete()
        self.assertEqual(review(Evidence(**{**vars(a), "command_executed": False})),
                         Review.SKIP)

    def test_trigger_execution_without_native_pet_change(self):
        a = complete()
        self.assertEqual(review(Evidence(**{**vars(a), "native_change_applied": False})),
                         Review.SKIP)

    def test_internal_ai_command_with_sender_pointer(self):
        a = complete()
        self.assertEqual(review(Evidence(**{**vars(a), "origin": Origin.AI_GENERATED})),
                         Review.SKIP)

    def test_stale_pet_and_state_after_queued_command(self):
        a = complete()
        for change in ("exact_pet_instance", "requested_state_still_current"):
            with self.subTest(change=change):
                self.assertEqual(review(Evidence(**{**vars(a), change: False})),
                                 Review.SKIP)

    def test_playerbots_policy_conflict_requires_coordination(self):
        a = complete()
        b = Evidence(**{**vars(a), "bot_default_conflicts": True})
        self.assertEqual(review(b), Review.SKIP)
        c = Evidence(**{**vars(b), "bot_policy_coordinated": True})
        self.assertEqual(review(c), Review.CANDIDATE_ONLY)

    def test_only_hypothetically_complete_chain_is_candidate(self):
        a = complete()
        self.assertEqual(review(a), Review.CANDIDATE_ONLY)
        self.assertEqual(review(Evidence(**{**vars(a),
                         "authenticated_post_ip_completion": False})), Review.SKIP)
        # CANDIDATE_ONLY never instructs Naxx to restore or store preferences.

    def test_master_guids_need_independent_provenance(self):
        a = complete()
        self.assertEqual(review(Evidence(**{**vars(a),
                         "sender_is_current_master": False})), Review.SKIP)


if __name__ == "__main__":
    unittest.main()
