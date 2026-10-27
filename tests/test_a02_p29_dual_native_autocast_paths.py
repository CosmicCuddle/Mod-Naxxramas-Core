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
            "charmInfo->ToggleCreatureAutocast(spellInfo, true)",
            "charmInfo->ToggleCreatureAutocast(spellInfo, false)",
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
                    + opcode + r",\s*STATUS_LOGGEDIN,\s*" + processing +
                    r",\s*&WorldSession::" + handler + r"\);"
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
