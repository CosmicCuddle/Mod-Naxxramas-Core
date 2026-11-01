"""P4-H Master Loot quest-slot give: source contract, pinned seam facts, harness.

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
sys.path.insert(0, str(ROOT / "tests" / "p4_h_master_loot"))
import build_master_loot  # noqa: E402

EXPECTED_CHECKS = 30
REQUIRED = [
    "FIXTURE.D3_leader_sees_Q1_at_N1_recipient_at_N0",
    "STOCK.D3_A_told_to_remove_slot_it_does_not_have",
    "GIVE.D3_only_A_gets_Q1", "GIVE.D3_each_viewer_told_own_slot", "GIVE.D3_item_marked_and_count_lowered",
    "FIXTURE.D1_leader_sees_only_Q1_at_N0", "STOCK.D1_A_gets_Q0_not_the_clicked_Q1",
    "GIVE.D1_A_gets_the_clicked_Q1", "GIVE.D1_each_viewer_told_own_slot", "GIVE.D1_Q0_still_lootable_by_A",
    "STOCK.D2_same_copy_given_again", "GIVE.D2_refused_already_looted",
    "ERRORS.inventory_full", "ERRORS.target_cannot_use", "ERRORS.full_and_cannot_use",
    "PASS.normal_slot_left_to_core", "FFA.copy_refused_not_a_master_row", "FFA.both_copies_still_lootable",
    "STOCK.ROW_gives_an_item_the_leader_is_not_shown", "ROW.leader_without_row_refused",
    "FIXTURE.leader_at_fill_gets_every_quest_row", "SAME.prefix_case_matches_stock",
    "GIVE.zero_count_unlooted_refused_no_effects",
]

SCRIPT = (ROOT / "src" / "Systems" / "MasterLootQuestGive.cpp").read_text()
HEADER = (ROOT / "src" / "Systems" / "MasterLootQuestGive.h").read_text()
LOADER = (ROOT / "src" / "NaxxramasCore_loader.cpp").read_text()
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text()

PINNED = {
    "src/server/game/Handlers/LootHandler.cpp": (build_master_loot.LOOT_HANDLER_BLOB, [
        # The handler's own checks, in order; the module passes any failure through.
        "    if (!_player->GetGroup() || _player->GetGroup()->GetMasterLooterGuid() != _player->GetGUID() || "
        "_player->GetGroup()->GetLootMethod() != MASTER_LOOT)\n",
        "    Player* target = ObjectAccessor::GetPlayer(*_player, target_playerguid);\n",
        "    if (_player->GetLootGUID() != lootguid)\n",
        "    if (!_player->IsInRaidWith(target) || target->HasPlayerFlag(PLAYER_FLAGS_NO_PLAY_TIME))\n",
        "    if (slotid >= loot->items.size() + loot->quest_items.size())\n",
        # D1: global quest index; D2: no looted check before the award; D3: leader's slot to everyone.
        "    LootItem& item = slotid >= loot->items.size() ? loot->quest_items[slotid - loot->items.size()] : loot->items[slotid];\n"
        "\n    ItemPosCountVec dest;\n",
        "    item.count = 0;\n    item.is_looted = true;\n\n    loot->NotifyItemRemoved(slotid);\n    --loot->unlootedCount;\n}\n",
    ]),
    "src/server/game/Loot/LootMgr.cpp": ("a103aab09b8f93aaef8ddd58239893ec9fb91184", [
        # Each viewer's quest slot is its position in its OWN list.
        "                    b << uint8(l.items.size() + (qi - q_list->begin()));\n                    b << item;\n"
        "                    b << uint8(lv.permission == MASTER_PERMISSION ? LOOT_SLOT_TYPE_MASTER : LOOT_SLOT_TYPE_LOCKED);\n",
        # The master looter at fill time gets a row for every quest item.
        "        if (!allowed && !isMasterLooter)\n            continue;\n\n        ql->push_back(QuestItem(i));\n",
        "                if (j < pql.size())\n                    player->SendNotifyLootItemRemoved(items.size() + j);\n",
    ]),
    "src/server/game/Entities/Player/Player.cpp": ("138e7eab4905ec366338a54cc18e6cfe749a3670", [
        "                loot->NotifyQuestItemRemoved(qitem->index);\n",
    ]),
    "src/server/game/Server/WorldSession.cpp": ("fc96398079b50984ed0b82183d713c666af6939b", [
        "                    else if (_player->IsInWorld())\n                    {\n"
        "                        if (!sScriptMgr->CanPacketReceive(this, *packet))\n                            break;\n\n"
        "                        opHandle->Call(this, *packet);\n",
        "    if (opHandle->ProcessingPlace == PROCESS_THREADUNSAFE)\n        return false;\n",
    ]),
    "src/server/game/Server/Protocol/Opcodes.cpp": ("c2d99161e6220ac6012e4a63cf293278a22660a5", [
        "DEFINE_HANDLER(CMSG_LOOT_MASTER_GIVE,                                                 STATUS_LOGGEDIN,   PROCESS_THREADSAFE,",
    ]),
}


def strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


class SourceContract(unittest.TestCase):
    def test_default_off(self):
        self.assertEqual(CONF.count("NaxxramasCore.MasterLootQuestGive.Enabled"), 1)
        self.assertIn("\nNaxxramasCore.MasterLootQuestGive.Enabled = 0\n", CONF)
        self.assertIn('GetOption<bool>("NaxxramasCore.MasterLootQuestGive.Enabled", false)', SCRIPT)
        self.assertEqual(SCRIPT.count("sConfigMgr"), 1)
        self.assertIn("{SERVERHOOK_CAN_PACKET_RECEIVE}", SCRIPT)
        self.assertIn("packet.GetOpcode() != CMSG_LOOT_MASTER_GIVE", SCRIPT)

    def test_handler_checks_pass_through_in_order(self):
        code = strip_comments(SCRIPT)
        body = code[code.index("bool PermitMasterGive("):code.index("NaxxramasMasterLootQuestGive::GiveQuestSlot(")]
        checks = [
            "group->GetMasterLooterGuid() != leader->GetGUID() || group->GetLootMethod() != MASTER_LOOT",
            "ObjectAccessor::GetPlayer(*leader, targetGuid)",
            "leader->GetLootGUID() != lootGuid",
            "!leader->IsInRaidWith(target) || target->HasPlayerFlag(PLAYER_FLAGS_NO_PLAY_TIME)",
            "slot >= loot->items.size() + loot->quest_items.size()",
        ]
        positions = [body.index(c) for c in checks]
        self.assertEqual(positions, sorted(positions))
        # Every early exit before the give lets the core run.
        self.assertNotIn("return false", body)
        self.assertEqual(code.count("return false;"), 3)

    def test_header_only_touches_the_given_item(self):
        code = strip_comments(HEADER)
        writes = re.findall(r"\b([\w.>\-\[\]]+)\s*=\s*[^=;]+;", code)
        state = [w for w in writes if "." in w or "->" in w]
        self.assertEqual(state, ["item.count", "item.is_looted"])
        self.assertEqual(code.count("--loot.unlootedCount;"), 1)
        self.assertEqual(code.count("loot.NotifyQuestItemRemoved(row.index);"), 1)
        self.assertNotIn("NotifyItemRemoved(", code)
        self.assertIsNone(re.search(r"\b(roundRobinPlayer|is_blocked|is_counted|rollWinnerGUID)\s*=[^=]", code))
        self.assertLess(code.index("if (slot < loot.items.size())"), code.index("questLists.find(leader->GetGUID())"))

    def test_loader(self):
        self.assertEqual(LOADER.count("void AddMasterLootQuestGiveScripts();"), 1)
        self.assertIn("    AddQuestLootSparkleGuardScripts();\n    AddMasterLootQuestGiveScripts();\n", LOADER)


class PinnedSeamFacts(unittest.TestCase):
    def test_pinned_blobs_and_text(self):
        if not os.environ.get("A04_CORE"):
            raise AssertionError("A04_CORE is not set")
        core = Path(os.environ["A04_CORE"])
        for path, (sha, snippets) in PINNED.items():
            data = (core / path).read_bytes()
            self.assertEqual(hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(), sha, path)
            text = data.decode()
            for snippet in snippets:
                self.assertEqual(text.count(snippet), 1, (path, snippet[:80]))


class HarnessOnPinnedBodies(unittest.TestCase):
    def test_stock_red_module_green(self):
        core = os.environ.get("A04_CORE")
        if not core:
            raise AssertionError("A04_CORE is not set")
        with tempfile.TemporaryDirectory(prefix="p4-h-") as tmp:
            compiled, rc, output = build_master_loot.run(Path(core), Path(tmp))
        print(output)
        self.assertTrue(compiled, output[-4000:])
        checks = build_master_loot.parse_checks(output)
        if len(checks) != EXPECTED_CHECKS:
            self.fail(f"COUNT DRIFT: {len(checks)} checks, expected {EXPECTED_CHECKS}")
        self.assertEqual([c for v, c in checks if v == "FAIL"], [])
        self.assertEqual(rc, 0)
        for cid in REQUIRED:
            self.assertIn(("PASS", cid), checks)


if __name__ == "__main__":
    unittest.main()
