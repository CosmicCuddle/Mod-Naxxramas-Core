"""P4-H follow-on: gameobject loot and packet-hook pass-through / interop.

Requires A04_CORE (pinned Grimfeather 8daffda), PB_DIR (pinned Playerbots
037c014) and IP_DIR (pinned Individual Progression 4ff4b5f) checkouts; FAILS,
not skips, when any is missing. Changes no module source: it tests #272.
"""
import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "p4_h_interop"))
import build_interop  # noqa: E402

SEAM_CHECKS = 28
GO_CHECKS = 15
SEAM_REQUIRED = [
    "SEAM.no_group", "SEAM.not_master_looter", "SEAM.group_loot_method", "SEAM.need_before_greed_method",
    "SEAM.free_for_all_method", "SEAM.target_missing", "SEAM.loot_guid_mismatch", "SEAM.not_in_raid",
    "SEAM.target_no_play_time", "SEAM.creature_missing", "SEAM.gameobject_missing",
    "SEAM.creature_quest_slot_reaches_tail", "SEAM.creature_normal_slot_reaches_tail",
    "SEAM.gameobject_quest_slot_reaches_tail", "SEAM.gameobject_normal_slot_reaches_tail",
    "SEAM.slot_out_of_range_reaches_range_check",
    "REPLY.pass_through_lets_core_run", "REPLY.given_consumes_silently", "REPLY.already_looted_equip_error",
    "REPLY.error_inv_full_with_loot_guid", "FILTER.disabled_lets_core_run", "FILTER.other_opcode_untouched",
    "FILTER.short_packet_left_to_core", "FILTER.reads_loot_slot_target_in_handler_order",
]
GO_REQUIRED = [
    "GO.FIXTURE.group_rules_leader_every_row_recipient_own_row", "GO.STOCK.D3_A_told_slot_it_does_not_have",
    "GO.GIVE.D3_only_A_gets_Q1_each_told_own_slot", "GO.STOCK.D2_second_copy_given", "GO.GIVE.D2_refused_already_looted",
    "GO.FIXTURE.personal_only_opener_has_rows", "GO.GIVE.personal_same_award_only_row_holder_notified",
    "GO.FIXTURE.personal_other_opener_leader_has_no_row", "GO.STOCK.crafted_slot_gives_item_leader_not_shown",
    "GO.GIVE.crafted_slots_refused_no_row", "GO.GIVE.A_still_loots_own_row", "GO.PASS.normal_slot_left_to_core",
    "GO.FIXTURE.zero_count_both_unlooted", "GO.GIVE.zero_count_refused_without_side_effects",
]

SEAM_ENV = (ROOT / "tests" / "p4_h_interop" / "seam_env.h").read_text()
HEADER = (ROOT / "src" / "Systems" / "MasterLootQuestGive.h").read_text()

CORE_FACTS = {
    # Hook aggregation: scripts are appended in registration order; the first false ends the loop.
    "src/server/game/Scripting/ScriptMgrMacros.h": ("80895976796c2cc0219256b5b653d3e05c7c908c", [
        "    for (auto const& script : ScriptRegistry<scriptType>::EnabledHooks[hookType]) { if (action) return false; } \\\n"
        "    return true;\n",
    ]),
    "src/server/game/Scripting/ScriptMgr.h": ("7f0f30d3ca46cb290636c33ca8e1b2b9c0ffa1f8", [
        "            for (uint16 v : enabledHooks)\n                EnabledHooks[v].emplace_back(script);\n",
    ]),
    "src/server/game/Scripting/ScriptDefines/ServerScript.cpp": ("30b7156039da386fe0bfc20031ce096c27346f78", [
        "    CALL_ENABLED_BOOLEAN_HOOKS(ServerScript, SERVERHOOK_CAN_PACKET_RECEIVE, !script->CanPacketReceive(session, packet));\n",
    ]),
    # Gameobject loot: filled at first open, personal unless a group-rules chest; Master Loot rights for any grouped viewer.
    "src/server/game/Entities/Player/Player.cpp": ("138e7eab4905ec366338a54cc18e6cfe749a3670", [
        "                bool groupRules = (group && go->GetGOInfo()->type == GAMEOBJECT_TYPE_CHEST && go->GetGOInfo()->chest.groupLootRules);\n",
        "                loot->FillLoot(lootid, LootTemplates_Gameobject, this, !groupRules, false, go->GetLootMode(), go);\n",
        "                                loot->FillNotNormalLootFor(allowedPlayer);\n",
        "                        permission = group->GetMasterLooterGuid() == GetGUID() ? MASTER_PERMISSION : RESTRICTED_PERMISSION;\n",
    ]),
    "src/server/game/Loot/LootMgr.cpp": ("a103aab09b8f93aaef8ddd58239893ec9fb91184", [
        "    if (!personal && group)\n    {\n        roundRobinPlayer = lootOwner->GetGUID();\n",
        "                if (player->IsAtLootRewardDistance(lootSource ? lootSource : lootOwner))\n",
        "    // ... for personal loot\n    else\n        FillNotNormalLootFor(lootOwner);\n",
    ]),
    # Values mirrored by seam_env.h.
    "src/server/game/Loot/LootMgr.h": ("62b2adc6055843810e310b3b43b3f571d76f42c5", [
        "    FREE_FOR_ALL                        = 0,\n    ROUND_ROBIN                         = 1,\n"
        "    MASTER_LOOT                         = 2,\n    GROUP_LOOT                          = 3,\n"
        "    NEED_BEFORE_GREED                   = 4\n",
        "    LOOT_ERROR_DIDNT_KILL               = 0,", "    LOOT_ERROR_PLAYER_NOT_FOUND         = 10,",
        "    LOOT_ERROR_MASTER_INV_FULL          = 12,", "    LOOT_ERROR_MASTER_UNIQUE_ITEM       = 13,",
        "    LOOT_ERROR_MASTER_OTHER             = 14,",
    ]),
    "src/server/game/Entities/Player/Player.h": ("5a29ac7b40ade7a11f1fcf36623dc7530ea39595", [
        "    PLAYER_FLAGS_NO_PLAY_TIME      = 0x00002000,",
    ]),
    "src/server/game/Entities/Item/Item.h": ("590bc2fe5034c3c640f668bc900697926a2690f3", [
        "    EQUIP_ERR_ALREADY_LOOTED                     = 49,",
    ]),
    "src/server/game/Server/Protocol/Opcodes.h": ("0b34344c425c477833b28b7e3ab1f2537e40783e", [
        "    CMSG_AUTOSTORE_LOOT_ITEM                        = 0x108,", "    CMSG_LOOT_MASTER_GIVE                           = 0x2A3,",
    ]),
}

PB_FACTS = {
    "src/Script/Playerbots.cpp": ("669eefb1a1ea7168d72a5a4f7db8145274172d73", [
        "    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override\n    {\n"
        "        if (Player* player = session->GetPlayer())\n"
        "            if (PlayerbotMgr* playerbotMgr = GET_PLAYERBOT_MGR(player))\n"
        "                playerbotMgr->HandleMasterIncomingPacket(packet);\n\n        return true;\n    }\n",
    ]),
    "src/Script/PlayerbotsSecureLogin.cpp": ("92997b7d7682ea6ff0e306b51cbe34e44ef0e7dc", [
        "        if (packet.GetOpcode() != CMSG_PLAYER_LOGIN)\n            return true;\n",
    ]),
    "src/Script/PlayerbotsSelfBotAfk.cpp": ("b3e8e3a84653e3aeb68c7076a61756fb7bb2b9f0", [
        "        if (packet.GetOpcode() != CMSG_LOGOUT_REQUEST)\n            return true;\n",
    ]),
    # Bot sessions' own packets go straight to the handler, without CanPacketReceive.
    "src/Bot/PlayerbotMgr.cpp": ("848ba215676eb20f738a15bc2e2259a24a07d5c0", [
        "    while (std::unique_ptr<WorldPacket> packet = session->NextQueuedPacket())\n",
        "        opHandle->Call(session, *packet);\n",
    ]),
    "src/Bot/PlayerbotAI.cpp": ("67cf77ca97f65c5dd84b50fa3a3af7c8a87250f0", [
        "    if (handlers.find(packet.GetOpcode()) != handlers.end())\n        queue.push(WorldPacket(packet));\n",
        "void PlayerbotAI::HandleMasterIncomingPacket(WorldPacket const& packet)\n{\n"
        "    masterIncomingPacketHandlers.AddPacket(packet);\n}\n",
    ]),
}


def blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def required_dir(var: str) -> Path:
    value = os.environ.get(var)
    if not value:
        raise AssertionError(f"{var} is not set")
    return Path(value)


def sources(root: Path):
    for path in sorted(root.rglob("*")):
        if path.suffix in (".cpp", ".h") and path.is_file():
            yield path, path.read_text(errors="replace")


def strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


class StubContract(unittest.TestCase):
    def test_recorder_mirrors_header_outcomes(self):
        want = re.search(r"enum class Result : uint8\s*\{([^}]*)\}", strip_comments(HEADER)).group(1)
        got = re.search(r"enum class Result : uint8 \{([^}]*)\}", SEAM_ENV).group(1)
        names = lambda s: [n.strip() for n in s.split(",") if n.strip()]  # noqa: E731
        self.assertEqual(names(got), names(want))
        self.assertIn("inline Outcome GiveQuestSlot(Player* leader, Player* target, Loot& loot, uint8 slot)", HEADER)


class PinnedCoreFacts(unittest.TestCase):
    def test_core(self):
        core = required_dir("A04_CORE")
        for rel, (sha, snippets) in CORE_FACTS.items():
            self.assertEqual(blob(core / rel), sha, rel)
            text = (core / rel).read_text()
            for snippet in snippets:
                self.assertEqual(text.count(snippet), 1, (rel, snippet[:80]))


class PacketHookNeighbours(unittest.TestCase):
    """Every CanPacketReceive in the pinned build, and what it does with CMSG_LOOT_MASTER_GIVE."""

    def implementers(self, root: Path):
        return [p.relative_to(root).as_posix() for p, t in sources(root) if "bool CanPacketReceive(" in t]

    def test_core_has_no_packet_scripts(self):
        core = required_dir("A04_CORE")
        # Core content scripts must be present, or this check would pass on a partial checkout.
        self.assertTrue((core / "src/server/scripts/Northrend").is_dir())
        self.assertTrue((core / "src/server/scripts/World").is_dir())
        found = [p for p in self.implementers(core / "src") if not p.startswith("server/game/Scripting/")]
        self.assertEqual(found, [])

    def test_playerbots(self):
        pb = required_dir("PB_DIR")
        self.assertEqual(self.implementers(pb / "src"), [
            "Script/Playerbots.cpp", "Script/PlayerbotsSecureLogin.cpp", "Script/PlayerbotsSelfBotAfk.cpp"])
        for rel, (sha, snippets) in PB_FACTS.items():
            self.assertEqual(blob(pb / rel), sha, rel)
            text = (pb / rel).read_text()
            for snippet in snippets:
                self.assertEqual(text.count(snippet), 1, (rel, snippet[:80]))
        # No bot handler (or anything else) refers to the Master Loot give opcode.
        self.assertEqual([p for p, t in sources(pb / "src") if "CMSG_LOOT_MASTER_GIVE" in t], [])

    def test_individual_progression(self):
        ip = required_dir("IP_DIR")
        self.assertEqual(self.implementers(ip / "src"), [])
        self.assertEqual([p for p, t in sources(ip / "src") if "CMSG_LOOT_MASTER_GIVE" in t], [])

    def test_this_module(self):
        found = sorted(self.implementers(ROOT / "src"))
        self.assertEqual(found, ["Systems/MasterLootQuestGive.cpp", "Systems/QuestLootPickupAuthorization.cpp",
                                 "Systems/QuestLootProtection.cpp"])
        for rel, opcode in (("Systems/QuestLootPickupAuthorization.cpp", "CMSG_AUTOSTORE_LOOT_ITEM"),
                            ("Systems/QuestLootProtection.cpp", "CMSG_AUTOSTORE_LOOT_ITEM"),
                            ("Systems/MasterLootQuestGive.cpp", "CMSG_LOOT_MASTER_GIVE")):
            self.assertIn(f"packet.GetOpcode() != {opcode} ||", (ROOT / "src" / rel).read_text(), rel)


class Harnesses(unittest.TestCase):
    def run_harness(self, fn, expected, required):
        core = required_dir("A04_CORE")
        with tempfile.TemporaryDirectory(prefix="p4-hi-") as tmp:
            compiled, rc, output = fn(core, Path(tmp))
        print(output)
        self.assertTrue(compiled, output[-4000:])
        checks = build_interop.parse_checks(output)
        if len(checks) != expected:
            self.fail(f"COUNT DRIFT: {len(checks)} checks, expected {expected}")
        self.assertEqual([c for v, c in checks if v == "FAIL"], [])
        self.assertEqual(rc, 0)
        for cid in required:
            self.assertIn(("PASS", cid), checks)

    def test_seam_matrix_on_original_bodies(self):
        self.run_harness(build_interop.run_seam, SEAM_CHECKS, SEAM_REQUIRED)

    def test_gameobject_loot_on_original_bodies(self):
        self.run_harness(build_interop.run_go, GO_CHECKS, GO_REQUIRED)


if __name__ == "__main__":
    unittest.main()
