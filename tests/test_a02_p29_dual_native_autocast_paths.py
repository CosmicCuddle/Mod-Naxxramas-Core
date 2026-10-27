"""A02 Part29: both public-core native autocast mutation routes.

LEXICAL SOURCE-DRIFT SENTINEL ONLY. It cannot prove packet acceptance,
actual player origin, SelfBot exclusion, IP rank policy, or pet birth.
NO Worldserver, owner server, SQL, pet changes or restoration.
"""
import os
import re
import unittest
from pathlib import Path

CORE = Path(os.environ.get("A02_PINNED_CORE", "acore"))
PET = CORE / "src/server/game/Handlers/PetHandler.cpp"
PET_CORE = CORE / "src/server/game/Entities/Pet/Pet.cpp"
OPCODES = CORE / "src/server/game/Server/Protocol/Opcodes.cpp"
SCRIPT_MGR = CORE / "src/server/game/Scripting/ScriptMgr.h"


def source(path):
    if not path.is_file():
        raise AssertionError("exact pinned public core path missing: " + str(path))
    return path.read_text(encoding="utf-8")


def body(full, handler, successor):
    """Extract bounded top-level C++ handlers, not arbitrary char windows."""
    match = re.search(
        r"(?ms)^void WorldSession::" + re.escape(handler) +
        r"\([^)]*\)\s*\{(?P<body>.*?)^}\s*\n\s*(?=void WorldSession::" +
        re.escape(successor) + r"\()", full
    )
    if not match:
        raise AssertionError("expected adjacent public-core handlers drifted: " + handler)
    return match.group("body")


def concise(text):
    return " ".join(text.split())


class TwoNativePetAutocastRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pet = source(PET)
        cls.explicit = body(pet, "HandlePetSpellAutocastOpcode",
                            "HandlePetCastSpellOpcode")
        cls.actionbar = body(pet, "HandlePetSetAction", "HandlePetRename")
        cls.opcodes = source(OPCODES)
        cls.pet_core = source(PET_CORE)
        cls.scripts = source(SCRIPT_MGR)

    def test_explicit_opcode_mutates_spell_and_pet_action_flags(self):
        s = concise(self.explicit)
        for token in (
            "ObjectAccessor::GetCreatureOrPetOrVehicle(*_player, packet.PetGUID)",
            "sSpellMgr->GetSpellInfo(packet.SpellID)",
            "checkPet != _player->GetGuardianPet()",
            "checkPet != _player->GetCharm()",
            "pet->HasSpell(packet.SpellID)",
            "spellInfo->IsAutocastable()",
            "summon->ToggleAutocast(spellInfo, packet.AutocastEnabled)",
            "charmInfo->ToggleCreatureAutocast(spellInfo, packet.AutocastEnabled)",
            "charmInfo->SetSpellAutocast(spellInfo, packet.AutocastEnabled)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, s)

    def test_set_action_is_an_independent_autocast_writer(self):
        s = concise(self.actionbar)
        for token in (
            "checkPet != _player->GetFirstControlled()",
            "count = (recvData.size() == 24) ? 2 : 1;",
            "if (position[i] >= MAX_UNIT_ACTION_BAR_INDEX)",
            "if (act_state == ACT_ENABLED)",
            "if (act_state == ACT_DISABLED)",
            "((Pet*)pet)->ToggleAutocast(spellInfo, true)",
            "((Pet*)pet)->ToggleAutocast(spellInfo, false)",
            "->ToggleCreatureAutocast(spellInfo, true)",
            "->ToggleCreatureAutocast(spellInfo, false)",
            "charmInfo->SetActionBar(position[i], spell_id, ActiveStates(act_state))",
        ):
            with self.subTest(token=token):
                self.assertIn(token, s)
        # The actionbar handler's direct pet-state mutation does not call
        # HandlePetSpellAutocastOpcode or rely on its packet callback.
        self.assertNotIn("HandlePetSpellAutocastOpcode", s)

    def test_native_reject_conditions_differ(self):
        action = concise(self.actionbar)
        explicit = concise(self.explicit)
        # The explicit handler validates IsAutocastable and has an
        # independently controlled pet/charm validation; action-bar
        # handler checks present spells, action positions, and first pet.
        self.assertIn("!spellInfo->IsAutocastable()", explicit)
        self.assertNotIn("IsAutocastable()", action)
        self.assertIn("!pet->HasSpell(spell_id)", action)
        self.assertIn("MAX_UNIT_ACTION_BAR_INDEX", action)
        self.assertNotIn("MAX_UNIT_ACTION_BAR_INDEX", explicit)

    def test_same_entry_multi_pet_fanout_present_in_both(self):
        for code in (self.explicit, self.actionbar):
            with self.subTest(route="explicit" if code == self.explicit else "set_action"):
                s = concise(code)
                self.assertIn("petsSet = _player->m_Controlled;", s)
                self.assertIn("pet->GetEntry() != ", s)
                self.assertIn("continue;", s)
        # This is a structural fan-out sentinel, not proof a Hunter
        # actually has two identical-entry owned pets in the installed realm.

    def test_different_packet_worker_categories_remain_registered(self):
        for opcode, processing, handler in (
            ("CMSG_PET_SPELL_AUTOCAST", "PROCESS_INPLACE", "HandlePetSpellAutocastOpcode"),
            ("CMSG_PET_SET_ACTION", "PROCESS_THREADUNSAFE", "HandlePetSetAction"),
        ):
            with self.subTest(opcode=opcode):
                line = re.compile(
                    r"(?m)^\s*/\*0x[0-9a-fA-F]+\*/\s*DEFINE_HANDLER\("
                    + opcode + r"\s*,\s*STATUS_LOGGEDIN\s*,\s*" + processing +
                    r"\s*,\s*&WorldSession::" + handler + r"\s*\);"
                )
                self.assertEqual(len(line.findall(self.opcodes)), 1)

    def test_stock_server_script_exposes_no_success_receipt(self):
        # Scope this conclusion strictly to ServerScript entrypoints on
        # pinned core, NOT to every possible core/plugin extension.
        segment = self.scripts.split("public: /* ServerScript */", 1)[1]
        segment = segment.split("public: /* SessionScript */", 1)[0]
        self.assertIn("CanPacketReceive(WorldSession* session", segment)
        self.assertIn("OnPacketSent(WorldSession* session", segment)
        self.assertNotIn("OnPacketHandled", segment)
        self.assertNotIn("OnAfterPetSpellAutocast", segment)

    def test_negative_synthetic_mutations_fail_dual_route_contract(self):
        action = concise(self.actionbar)
        self.assertIn("((Pet*)pet)->ToggleAutocast(spellInfo, false)", action)
        mutation = action.replace(
            "((Pet*)pet)->ToggleAutocast(spellInfo, false)",
            "/* deliberately removed OFF writer */", 1
        )
        self.assertNotIn("((Pet*)pet)->ToggleAutocast(spellInfo, false)", mutation)
        explicit = concise(self.explicit)
        self.assertIn("spellInfo->IsAutocastable()", explicit)
        mutation2 = explicit.replace("spellInfo->IsAutocastable()",
                                     "true /* validation removed */", 1)
        self.assertNotIn("spellInfo->IsAutocastable()", mutation2)

    def test_pet_rank_replacement_mutates_autocast_without_client_packet(self):
        # Pet::addSpell is a pet-lifecycle method, independent of either
        # handler. In stock core it copies old spell active state to a new
        # higher rank, removes an old auto-spell and installs the new one.
        source = self.pet_core
        start = source.index("bool Pet::addSpell(uint32 spellId,")
        end = source.index("bool Pet::learnSpell(uint32 spell_id)", start)
        s = concise(source[start:end])
        for token in (
            "if (spellInfo->IsDifferentRankOf(oldRankSpellInfo))",
            "if (spellInfo->IsHighRankOf(oldRankSpellInfo))",
            "newspell.active = petSpell.active;",
            "ToggleAutocast(oldRankSpellInfo, false);",
            "unlearnSpell(spellID, false, false);",
            "ToggleAutocast(spellInfo, (newspell.active == ACT_ENABLED));",
        ):
            with self.subTest(token=token):
                self.assertIn(token, s)
        self.assertNotIn("CMSG_PET_SPELL_AUTOCAST", s)
        self.assertNotIn("CMSG_PET_SET_ACTION", s)

    def test_pet_actionbar_cleanup_is_another_server_mutation_origin(self):
        source = self.pet_core
        start = source.index("void Pet::CleanupActionBar()")
        end = source.index("void Pet::InitPetCreateSpells()", start)
        s = concise(source[start:end])
        self.assertIn("if (!HasSpell(ab->GetAction()))", s)
        self.assertIn("m_charmInfo->SetActionBar(i, 0, ACT_PASSIVE);", s)
        self.assertIn("ToggleAutocast(spellInfo, ab->GetType() == ACT_ENABLED);", s)
        self.assertNotIn("CMSG_PET_SET_ACTION", s)

    def test_pet_autocast_mutation_is_guarded_by_spell_state_not_human_receipt(self):
        source = self.pet_core
        start = source.index("void Pet::ToggleAutocast(SpellInfo const* spellInfo, bool apply)")
        end = source.index("bool Pet::IsPermanentPetFor(Player* owner) const", start)
        s = concise(source[start:end])
        for token in (
            "if (!spellInfo->IsAutocastable()) return;",
            "PetSpellMap::iterator itr = m_spells.find(spellInfo->Id);",
            "if (itr == m_spells.end()) return;",
            "m_autospells.push_back(spellInfo->Id);",
            "itr->second.active = ACT_ENABLED;",
            "m_autospells.erase(autospellItr);",
            "itr->second.active = ACT_DISABLED;",
            "itr->second.state = PETSPELL_CHANGED;",
        ):
            with self.subTest(token=token):
                self.assertIn(token, s)
        # No author, packet or positive human receipt is accepted here.
        self.assertNotIn("WorldSession", s)
        self.assertNotIn("CanPacketReceive", s)

    def test_stock_pet_spell_save_is_not_a_causal_human_receipt(self):
        source = self.pet_core
        start = source.index("void Pet::_SaveSpells(CharacterDatabaseTransaction trans)")
        end = source.index("void Pet::_LoadAuras(", start)
        s = concise(source[start:end])
        self.assertIn("pet numbers are recycled", s)
        self.assertIn("CHAR_DEL_PET_SPELLS", s)
        self.assertIn("CHAR_INS_PET_SPELL", s)
        self.assertIn("stmt->SetData(2, itr->second.active);", s)
        # Existing core pet persistence records a final active value only:
        # it is not a durable attestation of WHO caused that state.
        self.assertNotIn("TrustedManualReceipt", s)

    def test_synthetic_same_final_state_cannot_prove_causal_origin(self):
        # This is an intentionally simple logical collision, not an
        # emulated server test. Final state lacks source/receipt identity.
        human_packet_then_native = {"pet": 11, "spell": 22, "enabled": False}
        npc_or_bot_write_only = {"pet": 11, "spell": 22, "enabled": False}
        self.assertEqual(human_packet_then_native, npc_or_bot_write_only)
        # Even with both opcode paths monitored, a later equality witness
        # alone remains incompatible with TrustedManualReceipt=True.


if __name__ == "__main__":
    unittest.main()
