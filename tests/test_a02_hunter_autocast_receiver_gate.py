#!/usr/bin/env python3
"""Pinned AzerothCore receiver-aware A02 chat-hook source contract.

These are SOURCE structural assertions, NOT a simulation of real client packets,
the PlayerScript dispatcher, or proof of a human clicking pet autocast.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/HunterPetAutocast.cpp").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/hunter-pet-autocast-pinned-worldserver.yml").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")
CLASS = CPP[CPP.index("class NaxxramasHunterPetAutocastAddonScript final")
            :CPP.index("\n    };", CPP.index("class NaxxramasHunterPetAutocastAddonScript final"))]


class ReceiverGateSourceTests(unittest.TestCase):
    def test_receiver_aware_hook_is_registered_instead_of_pre_target_hook(self):
        self.assertIn("PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT", CLASS)
        self.assertNotIn("PLAYERHOOK_ON_BEFORE_SEND_CHAT_MESSAGE", CLASS)
        self.assertNotIn("OnPlayerBeforeSendChatMessage", CLASS)

    def test_receiver_is_explicit_and_proven_same_player(self):
        self.assertRegex(CLASS, r"bool\s+OnPlayerCanUseChat\(Player\* player, uint32 type, uint32 lang,")
        self.assertIn("std::string& msg, Player* receiver) override", CLASS)
        self.assertIn("!player || !receiver || receiver != player", CLASS)

    def test_message_scope_is_addon_whisper_only(self):
        self.assertIn("type != CHAT_MSG_WHISPER || lang != LANG_ADDON", CLASS)
        self.assertIn("using PlayerScript::OnPlayerCanUseChat;", CLASS)

    def test_no_send_on_disabled_feature_and_no_chat_policy_mutation(self):
        self.assertRegex(CLASS, r"if \(!AddonOptInEnabled\.load\(std::memory_order_acquire\)\)\s+return true;")
        self.assertRegex(CLASS, r"AddonStore\(\)\.Accept\(\s*player->GetGUID\(\)\.GetCounter\(\)")
        self.assertGreaterEqual(CLASS.count("return true;"), 3)
        self.assertNotIn("return false;", CLASS)
        self.assertNotRegex(CLASS, r"msg\s*(?:=|\+=)")

    def test_server_switches_remain_default_off(self):
        for key in ("NaxxramasCore.HunterPetAutocast.RestoreHumanChain",
                    "NaxxramasCore.HunterPetAutocast.AddonOptIn"):
            self.assertIn(key + " = 0", CONF)

    def test_actual_full_link_audits_new_symbol(self):
        self.assertIn("NaxxramasHunterPetAutocastAddonScript::OnPlayerCanUseChat", WORKFLOW)
        self.assertNotIn("NaxxramasHunterPetAutocastAddonScript::OnPlayerBeforeSendChatMessage", WORKFLOW)

    def test_hunter_addon_writer_is_unchanged_not_v2_integration(self):
        self.assertIn("AddonStore().Accept(", CLASS)
        self.assertIn("NowMs(),", CLASS)
        self.assertNotIn("IntentFence::Decide", CPP)
        self.assertNotIn("HunterPetAutocastIntentFence.h", CPP)


if __name__ == "__main__":
    unittest.main()
