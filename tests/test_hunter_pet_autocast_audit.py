"""Offline source checks for Hunter pet autocast research-only observer.

These are NOT runtime tests. Never mistake them for evidence of safe
restoration, persistence, client state or IP completion.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/HunterPetAutocastAudit.cpp").read_text("utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text("utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text("utf-8")
PLAN = (ROOT / "docs/HUNTER-PET-AUTOCAST-FEASIBILITY.md").read_text("utf-8")


class HunterAutocastAuditSafety(unittest.TestCase):
    def test_off_by_default(self):
        self.assertEqual(
            CONF.count("NaxxramasCore.HunterPetAutocast.AuditEnabled = 0"), 1
        )
        self.assertIn('GetOption<bool>', SOURCE)
        self.assertIn('AuditEnabled()', SOURCE)

    def test_packet_only_observer_never_blocks_native(self):
        self.assertIn('CMSG_PET_SPELL_AUTOCAST', SOURCE)
        self.assertIn('SERVERHOOK_CAN_PACKET_RECEIVE', SOURCE)
        self.assertIn('WorldPacket copy(packet)', SOURCE)
        self.assertIn('copy.rpos(0)', SOURCE)
        self.assertIn('return true; // never intercept', SOURCE)
        packet_hook = SOURCE.split('bool CanPacketReceive(', 1)[1].split(
            'class HunterPetAutocastUpdateObserver', 1
        )[0]
        self.assertNotIn('return false;', packet_hook)


    def test_action_bar_packet_requires_same_slot_spell_and_native_result(self):
        action = SOURCE.split(
            'class HunterPetAutocastActionBarObserver', 1
        )[1].split('class HunterPetAutocastUpdateObserver', 1)[0]
        for expected in (
            'CMSG_PET_SET_ACTION',
            'packet.size() != 16',
            'ACTION_BAR_INDEX_PET_SPELL_START',
            'ACTION_BAR_INDEX_PET_SPELL_END',
            'UNIT_ACTION_BUTTON_ACTION',
            'UNIT_ACTION_BUTTON_TYPE',
            'beforeBar->GetAction() != spellId',
            'beforeBar->GetType()',
            'beforeEnabled == requestedEnabled',
            'QueuePendingChoice(owner, pet, spellId, requestedEnabled,',
            'return true; // read-only',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, action)
        self.assertNotIn('return false;', action)
        self.assertIn('bar->GetAction() != choice.spellId', SOURCE)
        self.assertIn('bar->GetType() !=', SOURCE)
        self.assertIn('new HunterPetAutocastActionBarObserver();', SOURCE)

    def test_multiple_independent_toggle_candidates_are_not_overwritten(self):
        self.assertIn('struct PendingChoiceQueue final : DataMap::Base', SOURCE)
        self.assertIn('std::vector<PendingChoice> choices;', SOURCE)
        self.assertIn('MAX_TOGGLE_AUDIT_QUEUE = 32', SOURCE)
        self.assertIn('queue->choices.push_back(item);', SOURCE)
        self.assertIn('candidate.spellId == item.spellId', SOURCE)
        self.assertIn('candidate.requestedEnabled == item.requestedEnabled', SOURCE)
        self.assertIn('observations.swap(queue->choices);', SOURCE)
        self.assertIn('for (PendingChoice const& choice : observations)', SOURCE)
        self.assertIn('queue->overflowed = true;', SOURCE)
        self.assertIn('queue->overflowed = false;', SOURCE)
        self.assertIn('actor not attributable; no mutation', SOURCE)
        self.assertNotIn('PendingChoice* pending', SOURCE)

    def test_pet_clock_observation_is_one_shot_not_restoration(self):
        self.assertIn('#include "Duration.h"', SOURCE)
        self.assertIn('eventClockProbeScheduled', SOURCE)
        self.assertIn('pet->m_Events.AddEventAtOffset([pet]()', SOURCE)
        self.assertIn('Milliseconds(2500)', SOURCE)
        self.assertIn('PET-EVENT-CLOCK audit', SOURCE)
        self.assertIn('NOT proof IP completed', SOURCE)
        # The marker must not mutate spells or set a successful-ready flag.
        self.assertNotIn('probe->ready = true', SOURCE)

    def test_native_intent_is_verified_later(self):
        self.assertIn('PLAYERHOOK_ON_AFTER_UPDATE', SOURCE)
        self.assertIn('MAX_TOGGLE_AUDIT_QUEUE = 32', SOURCE)
        self.assertIn('observations.swap(queue->choices);', SOURCE)
        self.assertIn('for (PendingChoice const& choice : observations)', SOURCE)
        self.assertIn('beforeEnabled == (enabledByte != 0)', SOURCE)
        self.assertIn('confirmedEnabled != choice.requestedEnabled', SOURCE)
        self.assertIn('pet->isBeingLoaded()', SOURCE)
        self.assertIn('pet->GetGUID() != choice.petGuid', SOURCE)
        self.assertIn('GetPetNumber() != choice.petNumber', SOURCE)

    def test_generic_autocast_snapshot_bounded_and_never_mutates(self):
        self.assertIn('DescribeHunterPetAutocast(Pet* pet)', SOURCE)
        self.assertIn('GetFirstSpellInChain(id)', SOURCE)
        self.assertIn('info->IsAutocastable()', SOURCE)
        self.assertIn('std::sort(known.begin(), known.end())', SOURCE)
        self.assertIn('size_t(64)', SOURCE)
        self.assertIn('sample->initialGenericAutocast', SOURCE)
        self.assertIn('GENERIC audit: pet-clock', SOURCE)
        self.assertIn('GENERIC audit: later', SOURCE)
        self.assertIn('ObserveLightningBreathBar', SOURCE)

    def test_class_and_pet_scope(self):
        self.assertIn('owner->getClass() != CLASS_HUNTER', SOURCE)
        self.assertIn('pet->getPetType() != HUNTER_PET', SOURCE)
        self.assertIn('info->IsAutocastable()', SOURCE)

    def test_learn_packet_is_read_only_and_checked_again(self):
        self.assertIn('SERVERHOOK_ON_PACKET_SENT', SOURCE)
        self.assertIn('SMSG_PET_LEARNED_SPELL', SOURCE)
        self.assertIn('class HunterPetAutocastLearnPacketObserver', SOURCE)
        self.assertIn('WorldPacket copy(packet)', SOURCE)
        self.assertIn('packet.size() != 4', SOURCE)
        self.assertNotIn('spellId != 25011 && spellId != 25012', SOURCE)
        self.assertIn('MAX_LEARNED_AUDIT_QUEUE = 32', SOURCE)
        self.assertIn('sample->pendingSpells.push_back(spellId)', SOURCE)
        self.assertIn('pet->HasSpell(spellId)', SOURCE)
        self.assertIn('learned->pendingSpells.clear();', SOURCE)
        self.assertIn('for (uint32 const spellId : learned->pendingSpells)', SOURCE)
        self.assertIn('no autocast restoration', SOURCE)

    def test_lifecycle_probe_is_finite_and_nonmutating(self):
        self.assertIn('PETHOOK_ON_PET_ADD_TO_WORLD', SOURCE)
        self.assertIn('class HunterPetAutocastLifecycleObserver', SOURCE)
        self.assertIn('pet->CustomData.GetDefault<LifecycleProbe>', SOURCE)
        self.assertIn('pet->isBeingLoaded()', SOURCE)
        self.assertIn('sample->initialBarSpell', SOURCE)
        self.assertIn('ObserveLightningBreathBar', SOURCE)
        self.assertIn('sample->elapsedMs < 3000', SOURCE)
        self.assertIn('sample->elapsedMs < 10000', SOURCE)
        self.assertIn('sample->reported = true;', SOURCE)
        self.assertIn('NOT proof IP reconciliation has run', SOURCE)
        self.assertIn('NO IP completion asserted; no change applied', SOURCE)

    def test_revive_path_without_new_pet_add_is_bounded_and_read_only(self):
        self.assertIn('struct ReviveProbe final : DataMap::Base', SOURCE)
        self.assertIn('void ObserveRevival(Player* owner)', SOURCE)
        self.assertIn('ObserveRevival(owner);', SOURCE)
        self.assertIn('probe->lastAlive == alive', SOURCE)
        self.assertIn('if (!probe->initialized)', SOURCE)
        self.assertIn('RecordObservedPetDeath(pet);', SOURCE)
        self.assertIn('probe->observations >= 4', SOURCE)
        self.assertIn('probe->revivalSequence', SOURCE)
        self.assertIn('++state->revivalSequence;', SOURCE)
        self.assertIn('uint32 const sequence = probe->revivalSequence;', SOURCE)
        self.assertIn('pet->m_Events.AddEventAtOffset([pet, sequence]()', SOURCE)
        self.assertIn('currentOwner->GetPet() != pet', SOURCE)
        self.assertIn('REVIVE audit: pet-clock', SOURCE)
        self.assertIn('NOT proof IP completed; no autocast change', SOURCE)

    def test_lethal_death_hook_avoids_missing_between_player_updates(self):
        self.assertIn('UNITHOOK_ON_UNIT_DEATH', SOURCE)
        self.assertIn('class HunterPetAutocastDeathObserver final : public UnitScript',
                      SOURCE)
        self.assertIn('void OnUnitDeath(Unit* victim, Unit* /*killer*/) override',
                      SOURCE)
        self.assertIn('Pet* pet = victim->ToPet();', SOURCE)
        self.assertIn('owner->GetPet() != pet', SOURCE)
        self.assertIn('RecordObservedPetDeath(pet);', SOURCE)
        self.assertIn('new HunterPetAutocastDeathObserver();', SOURCE)
        self.assertIn('state->initialized && !state->lastAlive && state->sawDeath',
                      SOURCE)
        self.assertIn('state->beforeRevive = DescribeHunterPetAutocast(pet);',
                      SOURCE)
        self.assertIn('++state->revivalSequence;', SOURCE)

    def test_no_mutation_or_persistence(self):
        for forbidden in (
            'pet->ToggleAutocast(',
            'pet->learnSpell(',
            'pet->addSpell(',
            'pet->unlearnSpell(',
            'pet->removeSpell(',
            'SetSpellAutocast(',
            'PetSpellInitialize(',
            'CharacterDatabase.',
            'WorldDatabase.',
            'sIndividualProgression->',
            'SavePetToDB(',
            'ChatHandler(',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, SOURCE)

    def test_loader_and_documented_limitations(self):
        self.assertEqual(LOADER.count('AddHunterPetAutocastAuditScripts();'), 2)
        self.assertIn('CMSG_PET_SET_ACTION', PLAN)
        self.assertIn('NOT YET CODE', PLAN)
        self.assertIn('not', PLAN.lower())


if __name__ == "__main__":
    unittest.main()
