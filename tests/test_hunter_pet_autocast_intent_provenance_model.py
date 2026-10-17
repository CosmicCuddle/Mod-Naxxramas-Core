"""Synthetic pre-handler / native actor ambiguous pet preference histories.

No actual sessions, Pet, SQL, bots, network or in-game tests are used.
"""
from dataclasses import dataclass
import unittest


@dataclass(frozen=True)
class Packet:
    pet: str
    spell: int
    enable: bool


class SyntheticPet:
    def __init__(self, name, spell=17261, enabled=False):
        self.name = name
        self.spell = spell
        self.enabled = enabled
        self.observed_packet = None
        self.handler_accepted = False
        self.actor = None

    def observe_pre_handler(self, packet):
        self.observed_packet = packet

    def handler(self, packet, valid):
        if not valid or packet.pet != self.name or packet.spell != self.spell:
            self.handler_accepted = False
            return
        self.enabled = packet.enable
        self.handler_accepted = True
        self.actor = "native-session"

    def direct_toggle(self, enabled, actor):
        self.enabled = enabled
        self.actor = actor

    def observer_matching_state_only(self):
        p = self.observed_packet
        return bool(p and p.pet == self.name
                    and p.spell == self.spell and p.enable == self.enabled)


def complete_proof(pet, human_attributed):
    return bool(pet.observed_packet
                and pet.handler_accepted
                and human_attributed
                and pet.actor == "native-session")


class NativeIntentBoundary(unittest.TestCase):
    def test_accepted_client_and_rejected_packet_plus_other_actor_look_same(self):
        request = Packet("Wolf-A", 17261, True)
        accepted = SyntheticPet("Wolf-A")
        rejected_then_other = SyntheticPet("Wolf-A")
        accepted.observe_pre_handler(request)
        accepted.handler(request, valid=True)
        rejected_then_other.observe_pre_handler(request)
        rejected_then_other.handler(request, valid=False)
        rejected_then_other.direct_toggle(True, "other-module")
        self.assertTrue(accepted.observer_matching_state_only())
        self.assertTrue(rejected_then_other.observer_matching_state_only())
        self.assertTrue(complete_proof(accepted, human_attributed=True))
        self.assertFalse(complete_proof(rejected_then_other, human_attributed=True))

    def test_accepted_packet_can_be_overridden_by_bot_in_same_update(self):
        request = Packet("Wolf-A", 17261, True)
        pet = SyntheticPet("Wolf-A")
        pet.observe_pre_handler(request)
        pet.handler(request, valid=True)
        pet.direct_toggle(False, "bot-ai")
        self.assertFalse(pet.observer_matching_state_only())
        self.assertFalse(complete_proof(pet, human_attributed=True))

    def test_pre_handler_packet_can_target_wrong_pet(self):
        request = Packet("Wolf-B", 17261, True)
        pet = SyntheticPet("Wolf-A")
        pet.observe_pre_handler(request)
        pet.handler(request, valid=False)
        self.assertFalse(pet.observer_matching_state_only())
        self.assertFalse(complete_proof(pet, human_attributed=True))

    def test_direct_toggle_without_packet_is_not_client_intent(self):
        pet = SyntheticPet("Wolf-A")
        pet.direct_toggle(True, "bot-ai")
        self.assertFalse(pet.observer_matching_state_only())
        self.assertFalse(complete_proof(pet, human_attributed=True))

    def test_same_native_session_result_can_have_unknown_human_origin(self):
        request = Packet("Wolf-A", 17261, True)
        bot_origin = SyntheticPet("Wolf-A")
        bot_origin.observe_pre_handler(request)
        bot_origin.handler(request, valid=True)
        self.assertTrue(bot_origin.observer_matching_state_only())
        self.assertTrue(bot_origin.handler_accepted)
        self.assertFalse(complete_proof(bot_origin, human_attributed=False))

    def test_explicit_off_is_distinct_from_unrequested_default_off(self):
        requested = Packet("Wolf-A", 17261, False)
        player_off = SyntheticPet("Wolf-A", enabled=True)
        default_off = SyntheticPet("Wolf-A", enabled=False)
        player_off.observe_pre_handler(requested)
        player_off.handler(requested, valid=True)
        self.assertFalse(player_off.enabled)
        self.assertFalse(default_off.enabled)
        self.assertTrue(complete_proof(player_off, human_attributed=True))
        self.assertFalse(complete_proof(default_off, human_attributed=True))

    def test_interleaved_two_abilities_require_independent_provenance(self):
        bite = SyntheticPet("Wolf-A", 17261, enabled=False)
        growl = SyntheticPet("Wolf-A", 14916, enabled=True)
        for pet, packet in (
            (bite, Packet("Wolf-A", 17261, True)),
            (growl, Packet("Wolf-A", 14916, False)),
        ):
            pet.observe_pre_handler(packet)
            pet.handler(packet, valid=True)
        self.assertTrue(complete_proof(bite, human_attributed=True))
        self.assertTrue(complete_proof(growl, human_attributed=True))
        # Same owner/pet doesn't let Bite certify Growl.

    def test_packet_duplicate_same_current_state_is_not_new_human_choice(self):
        request = Packet("Wolf-A", 17261, True)
        pet = SyntheticPet("Wolf-A", enabled=True)
        pet.observe_pre_handler(request)
        # A duplicate received while already ON should not create new
        # explicit preference just because its state later still matches.
        self.assertTrue(pet.observer_matching_state_only())
        self.assertFalse(complete_proof(pet, human_attributed=True))


if __name__ == "__main__":
    unittest.main()
