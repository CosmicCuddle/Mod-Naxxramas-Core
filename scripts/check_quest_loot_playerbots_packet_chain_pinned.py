#!/usr/bin/env python3
"""Read-only pinned normal Playerbots autostore -> AzerothCore script veto check."""
import argparse
from pathlib import Path
import re


def strip_comments(value):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", value, flags=re.DOTALL)


def section(value, start, end):
    pos = value.find(start)
    endpos = value.find(end, pos + len(start))
    if pos < 0 or endpos < 0:
        raise ValueError("pinned source section missing: " + start)
    return strip_comments(value[pos:endpos])


def required(value, needle):
    if needle not in value:
        raise ValueError("source contract missing: " + needle)


def verify(bot_source, session_source, opcode_source, module_source):
    bot = section(bot_source, "bool StoreLootAction::Execute(Event event)",
                  "bool StoreLootAction::IsLootAllowed")
    create = "new WorldPacket(CMSG_AUTOSTORE_LOOT_ITEM, 1)"
    slot = "*packet << itemindex;"
    queued = "bot->GetSession()->QueuePacket(packet);"
    for item in (create, slot, queued):
        required(bot, item)
    if not (bot.index(create) < bot.index(slot) < bot.index(queued)):
        raise ValueError("packet/slot/queue order changed")
    if "HandleAutostoreLootItemOpcode(" in bot or "StoreLootItem(" in bot:
        raise ValueError("direct store/handler bypass found in normal bot path")

    queue = section(session_source,
                    "void WorldSession::QueuePacket(WorldPacket* new_packet)",
                    "void WorldSession::LogUnexpectedOpcode")
    required(queue, "_recvQueue.add(new_packet);")
    logged_in = section(session_source, "case STATUS_LOGGEDIN:",
                        "case STATUS_LOGGEDIN_OR_RECENTLYLOGGOUT:")
    guard = "if (!sScriptMgr->CanPacketReceive(this, *packet))"
    dispatch = "opHandle->Call(this, *packet);"
    for item in ("else if (_player->IsInWorld())", guard, dispatch):
        required(logged_in, item)
    if not (logged_in.index("else if (_player->IsInWorld())") <
            logged_in.index(guard) < logged_in.index(dispatch)):
        raise ValueError("receive guard no longer precedes packet dispatch")
    between_guard_and_call = logged_in[logged_in.index(guard):logged_in.index(dispatch)]
    required(between_guard_and_call, "break;")

    opcodes = strip_comments(opcode_source)
    match = re.search(
        r"DEFINE_HANDLER\(\s*CMSG_AUTOSTORE_LOOT_ITEM\s*,"
        r"\s*STATUS_LOGGEDIN\s*,\s*PROCESS_INPLACE\s*,"
        r"\s*&WorldSession::HandleAutostoreLootItemOpcode\s*\)",
        opcodes)
    if not match:
        raise ValueError("native autostore opcode registration changed")

    module = strip_comments(module_source)
    for item in ("SERVERHOOK_CAN_PACKET_RECEIVE",
                 "bool CanPacketReceive(WorldSession* session,",
                 "packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM",
                 "WorldPacket copy(packet);", "copy.rpos(0);",
                 "NaxxramasQuestLootProtection::PermitPickup(",
                 "player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED);",
                 "return false;"):
        required(module, item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("playerbots", "session", "opcodes", "module"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(*(getattr(args, name).read_text(encoding="utf-8")
                 for name in ("playerbots", "session", "opcodes", "module")))
    except (ValueError, OSError) as error:
        print("FAIL: cannot certify this pinned normal loot path: " + str(error))
        return 1
    print("PASS: normal Playerbots queued autostore reaches native pre-dispatch hook.")
    print("LIMIT: source-only; other loot routes and real gameplay unproven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
