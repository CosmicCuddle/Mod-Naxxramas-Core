"""P4 H1 pickup authorization: source contract, pinned seam facts, harness.

Requires A04_CORE (pinned Grimfeather 8daffda checkout); FAILS, not skips,
when it is missing.
"""
import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "p4_h1_pickup"))
import build_pickup  # noqa: E402

EXPECTED_CHECKS = 36
REQUIRED = [
    "STOCK.O2_hidden_round_robin_slot_awarded_to_B",
    "AUTH.O2_hidden_slot_refused_B_gets_nothing",
    "AUTH.O2_owner_A_still_awarded",
    "AUTH.O2_after_release_B_sees_and_takes_unchanged",
    "STOCK.H1_quest_class_item_hidden_from_B_still_awarded_to_B",
    "AUTH.H1_quest_class_item_refused_for_B",
    "AUTH.H1_A_awarded_and_quest_completes",
    "POLICY.H1_after_release_visible_to_B_and_allowed_unchanged",
    "POLICY.T4a_both_entitled_first_taker_unchanged",
    "AUTH.check_has_no_shared_side_effect",
    "AUTH.ffa_both_copies_allowed",
    "AUTH.master_row_passed_to_core_core_denies_A_awarded",
    "MATRIX.both_off.T1_A_awarded_iff_view_guard", "MATRIX.both_off.hidden_slot_refused_iff_pickup_check",
    "MATRIX.view_only.T1_A_awarded_iff_view_guard", "MATRIX.view_only.hidden_slot_refused_iff_pickup_check",
    "MATRIX.pickup_only.T1_A_awarded_iff_view_guard", "MATRIX.pickup_only.hidden_slot_refused_iff_pickup_check",
    "MATRIX.both_on.T1_A_awarded_iff_view_guard", "MATRIX.both_on.hidden_slot_refused_iff_pickup_check",
    "FOOTPRINT.view_off_check_changes_no_flag", "FOOTPRINT.view_off_A_still_awarded_after_check",
]

SCRIPT = (ROOT / "src" / "Systems" / "QuestLootPickupAuthorization.cpp").read_text()
HEADER = (ROOT / "src" / "Systems" / "QuestLootPickupAuthorization.h").read_text()
LOADER = (ROOT / "src" / "NaxxramasCore_loader.cpp").read_text()
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text()

# Pinned source facts the module relies on (blob SHA, then exact text).
PINNED = {
    "src/server/game/Entities/Player/Player.cpp": ("138e7eab4905ec366338a54cc18e6cfe749a3670", [
        # SendLoot creature-corpse permission switch mirrored by CorpsePermission().
        "                    if (GetGroup() == recipientGroup)\n                    {\n"
        "                        switch (recipientGroup->GetLootMethod())\n                        {\n"
        "                            case MASTER_LOOT:\n"
        "                                permission = recipientGroup->GetMasterLooterGuid() == GetGUID() ? MASTER_PERMISSION : RESTRICTED_PERMISSION;\n"
        "                                break;\n                            case FREE_FOR_ALL:\n"
        "                                permission = ALL_PERMISSION;\n                                break;\n"
        "                            case ROUND_ROBIN:\n                                permission = ROUND_ROBIN_PERMISSION;\n"
        "                                break;\n                            default:\n"
        "                                permission = GROUP_PERMISSION;\n                                break;\n"
        "                        }\n                    }\n                    else\n"
        "                        permission = NONE_PERMISSION;\n                }\n"
        "                else if (recipient == this)\n                    permission = OWNER_PERMISSION;\n"
        "                else\n                    permission = NONE_PERMISSION;\n",
    ]),
    "src/server/game/Handlers/LootHandler.cpp": ("a18781f0e9b24b9d35ea587e48baf6829ba917fa", [
        "    LootItem* lootItem = player->StoreLootItem(lootSlot, loot, msg);\n",
    ]),
    "src/server/game/Server/WorldSession.cpp": ("fc96398079b50984ed0b82183d713c666af6939b", [
        # STATUS_LOGGEDIN branch (CMSG_AUTOSTORE_LOOT_ITEM): the hook runs right before the handler.
        "                    else if (_player->IsInWorld())\n                    {\n"
        "                        if (!sScriptMgr->CanPacketReceive(this, *packet))\n                            break;\n\n"
        "                        opHandle->Call(this, *packet);\n",
    ]),
    "src/server/game/Server/Protocol/Opcodes.cpp": ("c2d99161e6220ac6012e4a63cf293278a22660a5", [
        "DEFINE_HANDLER(CMSG_AUTOSTORE_LOOT_ITEM,                                              STATUS_LOGGEDIN,   PROCESS_INPLACE,",
    ]),
}


def core_dir() -> Path:
    value = os.environ.get("A04_CORE")
    if not value:
        raise AssertionError("A04_CORE is not set")
    return Path(value)


class SourceContract(unittest.TestCase):
    def test_default_off(self):
        self.assertEqual(CONF.count("NaxxramasCore.QuestLootPickupAuthorization.Enabled"), 1)
        self.assertIn("\nNaxxramasCore.QuestLootPickupAuthorization.Enabled = 0\n", CONF)
        self.assertIn('GetOption<bool>("NaxxramasCore.QuestLootPickupAuthorization.Enabled", false)', SCRIPT)
        self.assertIn("std::atomic<bool> s_pickupAuthorizationEnabled{false};", SCRIPT)

    def test_config_read_once_on_world_thread(self):
        self.assertEqual(SCRIPT.count("sConfigMgr"), 1)
        self.assertLess(SCRIPT.index("void OnAfterConfigLoad(bool /*reload*/) override"), SCRIPT.index("sConfigMgr"))
        self.assertIn("{SERVERHOOK_CAN_PACKET_RECEIVE}", SCRIPT)
        self.assertIn("{WORLDHOOK_ON_AFTER_CONFIG_LOAD}", SCRIPT)

    def test_only_autostore_and_creature_corpse(self):
        self.assertIn("packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM", SCRIPT)
        self.assertIn("if (!lootGuid.IsCreatureOrVehicle())", SCRIPT)
        self.assertIn("if (loot.loot_type != LOOT_CORPSE)", SCRIPT)
        # The only refusal path follows a failed server-view lookup.
        self.assertEqual(SCRIPT.count("return false;"), 1)
        refusal = SCRIPT.index("return false;")
        self.assertLess(SCRIPT.index("SlotVisibleInServerView(player, loot, permission, requestedSlot)"), refusal)

    def test_header_restores_what_the_helper_marks(self):
        code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", HEADER, flags=re.S))
        writes = re.findall(r"\b(\S+)\s*=\s*[^=;]+;", code)
        self.assertEqual([w for w in writes if "is_looted" in w], ["saved.first->is_looted"])
        self.assertIsNone(re.search(r"\b(unlootedCount|roundRobinPlayer|is_blocked)\s*=[^=]", code))
        helper = code.index("NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);")
        self.assertLess(code.index("savedRows.emplace_back(&row, row.is_looted);"), helper)
        self.assertLess(code.index("} restore{savedRows};"), helper)

    def test_loader_registers_once(self):
        self.assertEqual(LOADER.count("void AddQuestLootPickupAuthorizationScripts();"), 1)
        self.assertIn("    AddQuestLootViewGuardScripts();\n    AddQuestLootPickupAuthorizationScripts();\n", LOADER)


class PinnedSeamFacts(unittest.TestCase):
    def test_pinned_blobs_and_text(self):
        core = core_dir()
        for path, (sha, snippets) in PINNED.items():
            data = (core / path).read_bytes()
            self.assertEqual(hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(), sha, path)
            text = data.decode()
            for snippet in snippets:
                self.assertEqual(text.count(snippet), 1, (path, snippet[:80]))
        self.assertEqual((core / "src/server/game/Handlers/LootHandler.cpp").read_text()
                         .count("                loot->roundRobinPlayer.Clear();\n"), 2)


class HarnessOnPinnedBodies(unittest.TestCase):
    def test_stock_witness_then_authorization(self):
        with tempfile.TemporaryDirectory(prefix="p4-h1-") as tmp:
            compiled, rc, output = build_pickup.run(core_dir(), Path(tmp))
        print(output)
        self.assertTrue(compiled, output[-4000:])
        checks = build_pickup.parse_checks(output)
        if len(checks) != EXPECTED_CHECKS:
            self.fail(f"COUNT DRIFT: {len(checks)} checks, expected {EXPECTED_CHECKS}")
        self.assertEqual([c for v, c in checks if v == "FAIL"], [])
        self.assertEqual(rc, 0)
        for cid in REQUIRED:
            self.assertIn(("PASS", cid), checks)
        self.assertIn(f"CHECKS {EXPECTED_CHECKS} passed, 0 failed", output)


if __name__ == "__main__":
    unittest.main()
