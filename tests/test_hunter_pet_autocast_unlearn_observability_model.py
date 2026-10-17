"""Synthetic observational-equivalence proof for Hunter pet IP callbacks.

Do not mistake observations of a snapshot or a learned-spell packet
for evidence that IP completed. No native Pet or IP event is run.
"""
from dataclasses import dataclass, field
import unittest


@dataclass
class SyntheticPet:
    known: set[int] = field(default_factory=set)
    enabled: set[int] = field(default_factory=set)
    loading: bool = True
    learned_packets: list[int] = field(default_factory=list)

    def learn(self, spell):
        if spell in self.known:
            return
        self.known.add(spell)
        # Native ACT_DECIDE defaults autocastable fresh spell OFF.
        if not self.loading:
            self.learned_packets.append(spell)

    def unlearn(self, spell):
        self.known.discard(spell)
        self.enabled.discard(spell)
        # Pinned Pet::unlearnSpell never emits its commented notification.

    def observe(self):
        return (tuple(sorted(self.known)), tuple(sorted(self.enabled)),
                tuple(self.learned_packets))


class PetSpellObservability(unittest.TestCase):
    def test_no_change_and_hidden_loading_churn_have_identical_samples(self):
        no_change = SyntheticPet({25011}, set(), loading=True)
        churn = SyntheticPet({25011}, set(), loading=True)
        before = no_change.observe()
        churn.unlearn(25011)
        churn.learn(25011)
        self.assertEqual(no_change.observe(), before)
        self.assertEqual(churn.observe(), before)
        # A module sampling before and after, including packet observations,
        # cannot distinguish these histories in this legal synthetic case.

    def test_ip_retry_cap_does_not_require_loading_to_be_cleared(self):
        def ip_retry(loading, attempts):
            return loading and attempts < 10
        self.assertTrue(ip_retry(True, 9))
        self.assertFalse(ip_retry(True, 10))
        # At cap the check can proceed while m_loading is still true.

    def test_known_spell_without_rank_change_emits_no_learning_packet(self):
        pet = SyntheticPet({17261}, {17261}, loading=False)
        before = pet.observe()
        pet.learn(17261)
        self.assertEqual(pet.observe(), before)

    def test_after_loading_learn_packet_proves_learn_not_ip_origin(self):
        ip_path = SyntheticPet({25011}, set(), loading=False)
        external_path = SyntheticPet({25011}, set(), loading=False)
        for pet in (ip_path, external_path):
            pet.unlearn(25011)
            pet.learn(25011)
        self.assertEqual(ip_path.observe(), external_path.observe())
        self.assertEqual(ip_path.learned_packets, [25011])
        # Packet has no source-of-learning, nor a complete-IP marker.

    def test_off_default_after_unlearn_relearn_not_human_off(self):
        explicit_off = SyntheticPet({25011}, set(), loading=False)
        newly_off = SyntheticPet({25011}, {25011}, loading=True)
        newly_off.unlearn(25011)
        newly_off.learn(25011)
        self.assertEqual(explicit_off.known, newly_off.known)
        self.assertEqual(explicit_off.enabled, newly_off.enabled)
        # Identical ACT_DISABLED can represent two different histories.

    def test_unlearn_cannot_be_inferred_from_next_same_rank(self):
        stable = SyntheticPet({17261}, set(), loading=True)
        churned = SyntheticPet({17261}, set(), loading=True)
        before = stable.observe()
        churned.unlearn(17261)
        churned.learn(17261)
        self.assertEqual(stable.observe(), churned.observe())
        self.assertEqual(churned.observe(), before)


if __name__ == "__main__":
    unittest.main()
