"""Negative A02 pinned-source mutations; no pet, SQL, worldserver or player writes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_a02_post_accepted_autocast_hooks import (  # noqa: E402
    PET_HOOKS, SourceContractChanged, body_of, check_accepted_autocast_paths,
)

ACTION = """
void WorldSession::HandlePetSetAction(WorldPacket& recvData)
{
    if (checkPet != _player->GetFirstControlled()) return;
    if (!pet->HasSpell(spell_id)) return;
    if (act_state == ACT_ENABLED)
        ((Pet*)pet)->ToggleAutocast(spellInfo, true);
    else if (act_state == ACT_DISABLED)
        ((Pet*)pet)->ToggleAutocast(spellInfo, false);
    charmInfo->SetActionBar(position[i], spell_id, ActiveStates(act_state));
}
"""
AUTOCAST = """
void WorldSession::HandlePetSpellAutocastOpcode(WorldPackets::Pet::PetSpellAutocast& packet)
{
    Creature* checkPet = ObjectAccessor::GetCreatureOrPetOrVehicle(*_player, packet.PetGUID);
    if (checkPet != _player->GetGuardianPet() && checkPet != _player->GetCharm()) return;
    if (!pet->HasSpell(packet.SpellID) || !spellInfo->IsAutocastable()) continue;
    summon->ToggleAutocast(spellInfo, packet.AutocastEnabled);
    charmInfo->SetSpellAutocast(spellInfo, packet.AutocastEnabled);
}
"""
PET_SCRIPT = (
    "enum PetHook\n{\n" +
    ",\n".join(PET_HOOKS) + "\n};\n"
    "class PetScript\n{\npublic:\n"
    "virtual void OnPetAddToWorld(Pet* /*pet*/) { }\n};\n"
)
REMOVE_PET = """
void Player::RemovePet(Pet* pet, PetSaveMode mode, bool returnreagent)
{
    pet->SavePetToDB(mode);
    SetMinion(pet, false);
}
"""


def inspect(action=ACTION, autocast=AUTOCAST, pet_script=PET_SCRIPT,
            remove=REMOVE_PET):
    return check_accepted_autocast_paths(action + autocast, pet_script, remove)


class AcceptedChoiceSourceContract(unittest.TestCase):
    def test_fixture_is_explicitly_an_unsafe_boundary(self):
        facts = inspect()
        self.assertTrue(facts["two_distinct_client_autocast_handlers_write_pet_state"])
        self.assertTrue(facts["public_pet_script_has_no_accepted_autocast_hook"])
        self.assertTrue(facts["remove_pet_directly_saves_before_detaching"])
        self.assertFalse(facts["module_only_post_accepted_choice_and_dismiss_gate_proven"])
        self.assertFalse(facts["safe_to_enable_hunter_pet_cache"])

    def test_both_methods_are_required(self):
        with self.assertRaises(SourceContractChanged):
            inspect(autocast="")
        with self.assertRaises(SourceContractChanged):
            inspect(action="")

    def test_ambiguous_duplicate_method_is_rejected(self):
        with self.assertRaises(SourceContractChanged):
            inspect(action=ACTION + ACTION)

    def test_changed_set_action_write_path_is_rejected(self):
        for changed in (
            ACTION.replace("((Pet*)pet)->ToggleAutocast(spellInfo, true);", "NoChange();"),
            ACTION.replace("((Pet*)pet)->ToggleAutocast(spellInfo, false);", "NoChange();"),
            ACTION.replace("GetFirstControlled()", "GetSomeOtherControlled()"),
            ACTION.replace("pet->HasSpell(spell_id)", "pet->HasOtherSpell(spell_id)"),
            ACTION.replace("ACT_DISABLED", "ACT_PASSIVE"),
        ):
            with self.subTest(changed=changed[-110:]):
                with self.assertRaises(SourceContractChanged):
                    inspect(action=changed)

    def test_changed_pet_spell_autocast_path_is_rejected(self):
        for changed in (
            AUTOCAST.replace("summon->ToggleAutocast", "summon->OtherToggle"),
            AUTOCAST.replace("charmInfo->SetSpellAutocast", "charmInfo->NewSetter"),
            AUTOCAST.replace("spellInfo->IsAutocastable()", "true"),
            AUTOCAST.replace("GetGuardianPet()", "GetUnprovenPet()"),
            AUTOCAST.replace("pet->HasSpell(packet.SpellID)", "pet->HasAnySpell()"),
        ):
            with self.subTest(changed=changed[-120:]):
                with self.assertRaises(SourceContractChanged):
                    inspect(autocast=changed)

    def test_new_post_accepted_pet_script_hook_forces_new_source_review(self):
        changed = PET_SCRIPT.replace(
            "PETHOOK_ON_PET_ADD_TO_WORLD,",
            "PETHOOK_ON_PET_ADD_TO_WORLD,\nPETHOOK_ON_ACCEPTED_AUTOCAST,")
        with self.assertRaises(SourceContractChanged):
            inspect(pet_script=changed)

    def test_renamed_pet_hook_or_new_signature_forces_review(self):
        for changed in (
            PET_SCRIPT.replace("PETHOOK_ON_PET_ADD_TO_WORLD",
                               "PETHOOK_ON_PET_SPELL_CHANGED"),
            PET_SCRIPT.replace("OnPetAddToWorld", "OnPetActivated"),
        ):
            with self.assertRaises(SourceContractChanged):
                inspect(pet_script=changed)

    def test_direct_dismiss_save_and_order_is_mandatory(self):
        for changed in (
            REMOVE_PET.replace("pet->SavePetToDB(mode);", "NoSave();"),
            REMOVE_PET.replace("pet->SavePetToDB(mode);\n    SetMinion(pet, false);",
                               "SetMinion(pet, false);\n    pet->SavePetToDB(mode);"),
        ):
            with self.assertRaises(SourceContractChanged):
                inspect(remove=changed)

    def test_missing_or_unclosed_handler_fails_closed(self):
        with self.assertRaises(SourceContractChanged):
            body_of("", "void WorldSession::HandlePetSetAction(")
        with self.assertRaises(SourceContractChanged):
            body_of("void WorldSession::HandlePetSetAction() {",
                    "void WorldSession::HandlePetSetAction(")

    def test_script_is_source_only(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "check_a02_post_accepted_autocast_hooks.py").read_text()
        self.assertNotIn("CharacterDatabase.Query", source)
        self.assertNotIn("CharacterDatabase.Execute", source)
        self.assertIn("safe_to_enable_hunter_pet_cache", source)


if __name__ == "__main__":
    unittest.main()
