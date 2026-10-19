"""Synthetic positive/negative controls, never a server or loot test."""
import importlib.util
from pathlib import Path
import sys
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/check_quest_loot_playerbots_packet_chain_pinned.py"
spec = importlib.util.spec_from_file_location("ql_chain", path)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def fixture():
    bot = """bool StoreLootAction::Execute(Event event) {
    WorldPacket* packet = new WorldPacket(CMSG_AUTOSTORE_LOOT_ITEM, 1);
    *packet << itemindex;
    bot->GetSession()->QueuePacket(packet);
    // bot->GetSession()->HandleAutostoreLootItemOpcode(packet);
    return true; }
    bool StoreLootAction::IsLootAllowed(uint32 itemid, PlayerbotAI* ai) {}"""
    session = """void WorldSession::QueuePacket(WorldPacket* new_packet) {
        _recvQueue.add(new_packet);
    }
    void WorldSession::LogUnexpectedOpcode() {}
    case STATUS_LOGGEDIN:
      if (!_player) {}
      else if (_player->IsInWorld()) {
          if (!sScriptMgr->CanPacketReceive(this, *packet))
              break;
          opHandle->Call(this, *packet);
      }
    case STATUS_LOGGEDIN_OR_RECENTLY_LOGGOUT:"""
    opcodes = """DEFINE_HANDLER(CMSG_AUTOSTORE_LOOT_ITEM, STATUS_LOGGEDIN,
       PROCESS_INPLACE, &WorldSession::HandleAutostoreLootItemOpcode);"""
    module = """class Guard {
      SERVERHOOK_CAN_PACKET_RECEIVE
      bool CanPacketReceive(WorldSession* session, Packet const& packet) {
        if (packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM) return true;
        WorldPacket copy(packet);
        copy.rpos(0);
        return NaxxramasQuestLootProtection::PermitPickup(player, requestedSlot);
      }
      player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED);
      return false;
    };"""
    return [bot, session, opcodes, module]


class PacketChainTests(unittest.TestCase):
    def test_positive_pinned_shape(self):
        audit.verify(*fixture())

    def test_comment_only_queued_packet_does_not_pass(self):
        f = fixture()
        f[0] = f[0].replace("bot->GetSession()->QueuePacket(packet);",
                            "// bot->GetSession()->QueuePacket(packet);")
        with self.assertRaisesRegex(ValueError, "QueuePacket"):
            audit.verify(*f)

    def test_unrelated_money_queue_before_autostore_does_not_confuse_guard(self):
        f = fixture()
        f[0] = f[0].replace(
            "WorldPacket* packet = new WorldPacket(CMSG_AUTOSTORE_LOOT_ITEM, 1);",
            "WorldPacket* money = new WorldPacket(CMSG_LOOT_MONEY, 0);\n"
            "    bot->GetSession()->QueuePacket(packet);\n"
            "    WorldPacket* packet = new WorldPacket(CMSG_AUTOSTORE_LOOT_ITEM, 1);")
        # Only the queue after the client itemindex validates the claim.
        audit.verify(*f)
        f[0] = f[0].replace(
            "    bot->GetSession()->QueuePacket(packet);\n    //",
            "    // bot->GetSession()->QueuePacket(packet);\n    //")
        with self.assertRaisesRegex(ValueError, "QueuePacket order changed"):
            audit.verify(*f)

    def test_direct_inventory_or_handler_bypass_fails(self):
        for code in ("StoreLootItem(slot);",
                     "bot->GetSession()->HandleAutostoreLootItemOpcode(packet);"):
            f = fixture()
            f[0] = f[0].replace("return true;", code + "\nreturn true;")
            with self.assertRaisesRegex(ValueError, "direct store/handler bypass"):
                audit.verify(*f)

    def test_wrong_slot_or_order_fails(self):
        f = fixture()
        f[0] = f[0].replace("*packet << itemindex;", "*packet << otherSlot;")
        with self.assertRaisesRegex(ValueError, "QueuePacket order changed"):
            audit.verify(*f)
        f = fixture()
        f[0] = f[0].replace("*packet << itemindex;\n    bot->GetSession()->QueuePacket(packet);",
                            "bot->GetSession()->QueuePacket(packet);\n    *packet << itemindex;")
        with self.assertRaisesRegex(ValueError, "QueuePacket order changed"):
            audit.verify(*f)

    def test_native_veto_after_dispatch_fails(self):
        f = fixture()
        f[1] = f[1].replace("opHandle->Call(this, *packet);",
             "opHandle->Call(this, *packet);")
        f[1] = f[1].replace("if (!sScriptMgr->CanPacketReceive(this, *packet))\n              break;\n          opHandle->Call(this, *packet);",
             "opHandle->Call(this, *packet);\n          if (!sScriptMgr->CanPacketReceive(this, *packet)) break;")
        with self.assertRaisesRegex(ValueError, "no longer precedes"):
            audit.verify(*f)

    def test_wrong_native_opcode_status_and_receive_queue_fail(self):
        f = fixture()
        f[2] = f[2].replace("STATUS_LOGGEDIN", "STATUS_NEVER")
        with self.assertRaisesRegex(ValueError, "opcode registration changed"):
            audit.verify(*f)
        f = fixture()
        f[1] = f[1].replace("_recvQueue.add(new_packet);", "discard(new_packet);")
        with self.assertRaisesRegex(ValueError, "_recvQueue"):
            audit.verify(*f)

    def test_module_receive_hook_must_remain(self):
        f = fixture()
        f[3] = f[3].replace("SERVERHOOK_CAN_PACKET_RECEIVE", "SERVERHOOK_CAN_PACKET_SEND")
        with self.assertRaisesRegex(ValueError, "SERVERHOOK_CAN_PACKET_RECEIVE"):
            audit.verify(*f)


if __name__ == "__main__":
    unittest.main()
