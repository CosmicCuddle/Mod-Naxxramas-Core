"""F14 P16: where a player's race reaches other clients, outside /who.

Usage: python3 -I tests/f14_race_exposure_facts.py <azerothcore checkout>

Checks the checkout is Grimfeather 8daffda, then each fact in
docs/research/F14-P16-RACE-EXPOSURE.md at its cited lines. Facts marked
EXPOSES are paths that send race (or the model/appearance that shows it);
NO-RACE facts are surfaces checked and found not to send it. Every fact is
also run against a mutated copy of its source (negative fixture) and must
fail there. Friends and guild roster are P14 facts C9/C10.
"""
from pathlib import Path
import subprocess
import sys

PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
G = "src/server/game/"
QUERY = G + "Handlers/QueryHandler.cpp"
OPCODES = G + "Server/Protocol/Opcodes.cpp"
UNIT = G + "Entities/Unit/Unit.cpp"
PLAYER = G + "Entities/Player/Player.cpp"
PSTORE = G + "Entities/Player/PlayerStorage.cpp"
UFLAGS = G + "Entities/Object/Updates/UpdateFieldFlags.cpp"
SPELL = G + "Handlers/SpellHandler.cpp"
LFG = G + "DungeonFinding/LFGMgr.cpp"
GROUP = G + "Handlers/GroupHandler.cpp"
BG = G + "Battlegrounds/Battleground.cpp"
BGSCORE = G + "Battlegrounds/BattlegroundScore.h"
ARENASCORE = G + "Battlegrounds/ArenaScore.h"
ARENATEAM = G + "Battlegrounds/ArenaTeam.cpp"
CALENDAR = G + "Handlers/CalendarHandler.cpp"
FILES = (QUERY, OPCODES, UNIT, PLAYER, PSTORE, UFLAGS, SPELL, LFG, GROUP, BG, BGSCORE,
         ARENASCORE, ARENATEAM, CALENDAR)


def lines(src, path, first, last):
    chunk = src[path].splitlines()[first - 1:last]
    return " ".join(" ".join(chunk).split())


def has(src, path, first, last, *needles):
    text = lines(src, path, first, last)
    return all(n in text for n in needles)


def lacks(src, path, first, last, *needles):
    text = lines(src, path, first, last)
    return all(n not in text for n in needles)


def whole(src, path):
    return len(src[path].splitlines())


# (id, verdict, description, predicate, negative fixture (path, old, new))
FACTS = [
    ("E1", "EXPOSES", "name query response carries race, live or from the character cache (QueryHandler.cpp L49)",
     lambda s: has(s, QUERY, 49, 49, "nameQueryResponse.Race = player ? player->getRace() : playerData->Race;"),
     (QUERY, "nameQueryResponse.Race = player ? player->getRace() : playerData->Race;",
      "nameQueryResponse.Race = RACE_NONE;")),
    ("E2", "EXPOSES", "SendNameQueryOpcode checks nothing about the asker: no visibility, team, phase or "
     "distance test, offline characters answered from the cache (QueryHandler.cpp L32-L62)",
     lambda s: has(s, QUERY, 32, 62, "void WorldSession::SendNameQueryOpcode(ObjectGuid guid)",
                   "sCharacterCache->GetCharacterCacheByGuid(guid);",
                   "Player* player = ObjectAccessor::FindConnectedPlayer(guid);")
     and lacks(s, QUERY, 32, 62, "GetPlayer()", "_player", "CanSee", "IsVisible", "GetTeamId", "Phase",
               "GetDistance", "IsInMap", "HasPermission"),
     (QUERY, "    Player* player = ObjectAccessor::FindConnectedPlayer(guid);\n",
      "    Player* player = ObjectAccessor::FindConnectedPlayer(guid);\n"
      "    if (player && !_player->CanSeeOrDetect(player)) return;\n")),
    ("E3", "EXPOSES", "any logged-in client may send CMSG_NAME_QUERY for any GUID (Opcodes.cpp L211, "
     "QueryHandler.cpp L64-L70)",
     lambda s: has(s, OPCODES, 211, 211, "DEFINE_HANDLER(CMSG_NAME_QUERY,", "STATUS_LOGGEDIN", "PROCESS_INPLACE",
                   "&WorldSession::HandleNameQueryOpcode")
     and has(s, QUERY, 64, 70, "void WorldSession::HandleNameQueryOpcode(WorldPackets::Query::NameQuery& packet)",
             "SendNameQueryOpcode(packet.Guid);")
     and lacks(s, QUERY, 64, 70, "if (", "return;", "_player", "GetPlayer()"),
     (QUERY, "    SendNameQueryOpcode(packet.Guid);\n",
      "    if (packet.Guid != _player->GetGUID()) return;\n    SendNameQueryOpcode(packet.Guid);\n")),
    ("E4", "EXPOSES", "race is byte 0 of UNIT_FIELD_BYTES_0 (Unit.cpp L16695; Player.cpp L535-L537; "
     "PlayerStorage.cpp L5089-L5093)",
     lambda s: has(s, UNIT, 16695, 16695, "return GetByteValue(UNIT_FIELD_BYTES_0, 0);")
     and has(s, PLAYER, 535, 537, "uint32 RaceClassGender = (createInfo->Race)",
             "SetUInt32Value(UNIT_FIELD_BYTES_0, (RaceClassGender")
     and has(s, PSTORE, 5089, 5093, "bytes0 |= fields[3].Get<uint8>();", "SetUInt32Value(UNIT_FIELD_BYTES_0, bytes0);"),
     (UNIT, "    return GetByteValue(UNIT_FIELD_BYTES_0, 0);\n", "    return m_race;\n")),
    ("E5", "EXPOSES", "UNIT_FIELD_BYTES_0 is a PUBLIC update field: sent to every client the player is "
     "visible to (UpdateFieldFlags.cpp L187)",
     lambda s: has(s, UFLAGS, 187, 187, "UF_FLAG_PUBLIC,", "// UNIT_FIELD_BYTES_0"),
     (UFLAGS, "    UF_FLAG_PUBLIC,                                         // UNIT_FIELD_BYTES_0\n",
      "    UF_FLAG_PRIVATE,                                        // UNIT_FIELD_BYTES_0\n")),
    ("E6", "EXPOSES", "display ids and appearance bytes are PUBLIC: the model shows the race "
     "(UpdateFieldFlags.cpp L231-L232, L317-L319)",
     lambda s: has(s, UFLAGS, 231, 232, "UF_FLAG_PUBLIC, // UNIT_FIELD_DISPLAYID", "UF_FLAG_PUBLIC, // UNIT_FIELD_NATIVEDISPLAYID")
     and has(s, UFLAGS, 317, 319, "UF_FLAG_PUBLIC, // PLAYER_BYTES", "UF_FLAG_PUBLIC, // PLAYER_BYTES_2",
             "UF_FLAG_PUBLIC, // PLAYER_BYTES_3"),
     (UFLAGS, "    UF_FLAG_PUBLIC,                                         // UNIT_FIELD_DISPLAYID\n",
      "    UF_FLAG_PRIVATE,                                        // UNIT_FIELD_DISPLAYID\n")),
    ("E7", "EXPOSES", "a corpse stores the race in CORPSE_FIELD_BYTES_1, a PUBLIC field "
     "(Player.cpp L4705-L4720, UpdateFieldFlags.cpp L1562)",
     lambda s: has(s, PLAYER, 4705, 4720, "uint8 race = (uint8)(_uf);", "_cfb1 = ((0x00) | (race << 8)",
                   "corpse->SetUInt32Value(CORPSE_FIELD_BYTES_1, _cfb1);")
     and has(s, UFLAGS, 1562, 1562, "UF_FLAG_PUBLIC,", "// CORPSE_FIELD_BYTES_1"),
     (PLAYER, "    _cfb1 = ((0x00) | (race << 8)", "    _cfb1 = ((0x00) | (0 << 8)")),
    ("E8", "EXPOSES", "mirror-image data sends the copied player's race to any client that asks "
     "(SpellHandler.cpp L768-L771, Opcodes.cpp L1156)",
     lambda s: has(s, SPELL, 768, 771, "WorldPacket data(SMSG_MIRRORIMAGE_DATA, 68);", "data << uint8(creator->getRace());")
     and has(s, OPCODES, 1156, 1156, "DEFINE_HANDLER(CMSG_GET_MIRRORIMAGE_DATA,", "STATUS_LOGGEDIN"),
     (SPELL, "    data << uint8(creator->getRace());\n", "    data << uint8(0);\n")),
    ("E9", "EXPOSES", "the raid browser (LFR) list sends each listed player's race (LFGMgr.cpp L1343-L1353)",
     lambda s: has(s, LFG, 1343, 1353, "void LFGMgr::RBPacketAppendPlayer(RBInternalInfo const& info, ByteBuffer& buffer)",
                   "buffer << (uint8)info._race;"),
     (LFG, "            buffer << (uint8)info._race;\n", "            buffer << (uint8)0;\n")),
    ("N1", "NO-RACE", "party member stats carry no race (GroupHandler.cpp L817-L1136)",
     lambda s: has(s, GROUP, 817, 817, "void WorldSession::BuildPartyMemberStatsChangedPacket(Player* player, WorldPacket* data)")
     and has(s, GROUP, 1003, 1003, "void WorldSession::HandleRequestPartyMemberStatsOpcode(WorldPacket& recvData)")
     and lacks(s, GROUP, 817, 1136, "Race", "getRace"),
     (GROUP, "    if (mask & GROUP_UPDATE_FLAG_LEVEL)\n",
      "    *data << uint8(player->getRace());\n    if (mask & GROUP_UPDATE_FLAG_LEVEL)\n")),
    ("N2", "NO-RACE", "battleground and arena scoreboards carry no race (Battleground.cpp L1373-L1401, "
     "BattlegroundScore.h, ArenaScore.h)",
     lambda s: has(s, BG, 1373, 1373, "void Battleground::BuildPvPLogDataPacket(WorldPacket& data)")
     and lacks(s, BG, 1373, 1401, "Race", "getRace")
     and lacks(s, BGSCORE, 1, whole(s, BGSCORE), "Race", "getRace")
     and lacks(s, ARENASCORE, 1, whole(s, ARENASCORE), "Race", "getRace"),
     (BGSCORE, "    virtual void AppendToPacket(WorldPacket& data);",
      "    virtual void AppendToPacket(WorldPacket& data); uint8 Race = 0;")),
    ("N3", "NO-RACE", "arena team roster sends class, not race (ArenaTeam.cpp L447-L482)",
     lambda s: has(s, ARENATEAM, 447, 482, "void ArenaTeam::Roster(WorldSession* session)", "data << uint8(itr->Class);")
     and lacks(s, ARENATEAM, 447, 482, "Race", "getRace"),
     (ARENATEAM, "        data << uint8(itr->Class);                         // class\n",
      "        data << uint8(itr->Class);                         // class\n        data << uint8(player ? player->getRace() : 0);\n")),
    ("N4", "NO-RACE", "calendar reads race only to derive the invitee's team, never writes it "
     "(CalendarHandler.cpp L550 is its only use)",
     lambda s: has(s, CALENDAR, 550, 550, "inviteeTeamId = Player::TeamIdForRace(playerData->Race);")
     and [n for n, l in enumerate(s[CALENDAR].splitlines(), 1) if "Race" in l] == [550],
     (CALENDAR, "                inviteeGuildId = playerData->GuildId;\n",
      "                inviteeGuildId = playerData->GuildId;\n                data << uint8(playerData->Race);\n")),
]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    root = Path(argv[1])
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != PIN:
        print(f"WRONG PIN: {head} != {PIN}")
        return 1
    src = {p: (root / p).read_text(errors="replace") for p in FILES}
    bad = 0
    for fid, verdict, desc, pred, _ in FACTS:
        ok = bool(pred(src))
        print(f"{'OK  ' if ok else 'FAIL'} {fid} [{verdict}]: {desc}")
        bad += not ok
    caught = 0
    for fid, _, _, pred, (path, old, new) in FACTS:
        if src[path].count(old) != 1:
            print(f"FIXTURE {fid}: mutation anchor not unique in {path}")
            bad += 1
            continue
        if pred(dict(src, **{path: src[path].replace(old, new)})):
            print(f"FIXTURE {fid}: mutated source still passes")
            bad += 1
        else:
            caught += 1
    print(f"{caught}/{len(FACTS)} negative fixtures caught")
    if bad:
        print(f"FAILED: {bad}")
        return 1
    exposes = sum(1 for f in FACTS if f[1] == "EXPOSES")
    print(f"PASS: {len(FACTS)} pinned core facts at {PIN[:7]} ({exposes} exposing, {len(FACTS) - exposes} no-race)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
