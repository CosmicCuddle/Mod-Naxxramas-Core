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

    def test_native_intent_is_verified_later(self):
        self.assertIn('PLAYERHOOK_ON_AFTER_UPDATE', SOURCE)
        self.assertIn('pending->pending = true;', SOURCE)
        self.assertIn('choice->pending = false;', SOURCE)
        self.assertIn('beforeEnabled == (enabledByte != 0)', SOURCE)
        self.assertIn('confirmedEnabled != choice->requestedEnabled', SOURCE)
        self.assertIn('pet->isBeingLoaded()', SOURCE)
        self.assertIn('pet->GetGUID() != choice->petGuid', SOURCE)
        self.assertIn('GetPetNumber() != choice->petNumber', SOURCE)

    def test_class_and_pet_scope(self):
        self.assertIn('owner->getClass() != CLASS_HUNTER', SOURCE)
        self.assertIn('pet->getPetType() != HUNTER_PET', SOURCE)
        self.assertIn('info->IsAutocastable()', SOURCE)

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
