"""Source contract for the A02 S2c addon opt-in protocol.

Native behaviour is tests/hunter_pet_autocast_addon.cpp. These checks lock
the C++ gate and the protocol text. Nothing here starts a worldserver.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/HunterPetAutocast.cpp").read_text(encoding="utf-8")
ADDON = (ROOT / "src/Systems/HunterPetAutocastAddon.h").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")
DOC = (ROOT / "docs/A02-ADDON-PROTOCOL.md").read_text(encoding="utf-8")
PROTOCOL_START = DOC.index("```text\n") + len("```text\n")
PROTOCOL_END = DOC.index("```", PROTOCOL_START)
PROTOCOL = DOC[PROTOCOL_START:PROTOCOL_END]


class ProtocolText(unittest.TestCase):
    def test_final_block_matches_the_addon_inputs(self):
        for needle in (
            'SendAddonMessage("NXCPAK", payload, "WHISPER", UnitName("player"))',
            "v1|<seq>|<n>/<total>|<pairs>",
            "v1|clear",
            "v1|7|1/1|1742=0,17259=1",
            "233",
            "255",
            "GetFirstSpellInChain",
            "8 NXCPAK messages per 10000 milliseconds",
            "NaxxramasCore.HunterPetAutocast.AddonOptIn = 0",
            "NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0",
            "no pet identifier",
            "The server sends no reply.",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, PROTOCOL)

    def test_doc_uses_the_review_labels_and_does_not_claim_a_game_pass(self):
        for label in ("VERIFIED", "POTENTIAL ISSUE", "UNKNOWN", "NOT TESTED"):
            with self.subTest(label=label):
                self.assertIn(label, DOC)
        self.assertNotIn("passed in game", DOC.lower())
        self.assertIn("OnPlayerBeforeSendChatMessage", DOC)
        self.assertIn("ChatHandler.cpp:364", DOC)
        self.assertIn("Opcodes.cpp:280", DOC)
        self.assertIn("World.cpp:1227", DOC)


class ServerGate(unittest.TestCase):
    def test_config_defaults_off(self):
        self.assertEqual(CONF.count("NaxxramasCore.HunterPetAutocast.AddonOptIn = 0"), 1)
        self.assertNotIn("NaxxramasCore.HunterPetAutocast.AddonOptIn = 1", CONF)
        self.assertIn('GetOption<bool>("NaxxramasCore.HunterPetAutocast.AddonOptIn", false)', CPP)
        self.assertIn("AddonOptInEnabled{false}", CPP)

    def test_writer_requires_opt_in_and_does_not_answer(self):
        self.assertIn("if (!optIn)", CPP)
        self.assertNotIn("IsRealPlayer(", CPP)
        self.assertNotIn("Playerbots.h", CPP)
        self.assertNotIn("_playerbotsAIMap", ADDON)
        for forbidden in ("Whisper(", "SendPacket(", "BuildChatPacket(", "SendAddonMessage("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CPP)

    def test_parser_bounds_are_the_documented_ones(self):
        self.assertIn("kMaxRawBytes = 255", ADDON)
        self.assertIn("kAddonPayloadBudget = 233", ADDON)
        self.assertIn("kRateLimitCount = 8", ADDON)
        self.assertIn("kRateLimitWindowMs = 10000", ADDON)
        self.assertIn("kMaxChunks = 8", ADDON)
        self.assertIn("kMaxPairs = 64", ADDON)


if __name__ == "__main__":
    unittest.main()
