"""F14 P14: pinned core source facts behind the /who identity seam.

Usage: python3 -I tests/f14_visibility_seam_facts.py <azerothcore checkout>

Checks the checkout is Grimfeather 8daffda, then that each fact in
docs/research/F14-P14-VISIBILITY-SEAM.md holds at the cited lines. Each fact
is also run against a mutated copy of its source (negative fixture) and must
fail there.
"""
from pathlib import Path
import subprocess
import sys

PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
G = "src/server/game/"
WORLD = G + "World/World.cpp"
MAPMGR = G + "Maps/MapMgr.cpp"
OPCODES = G + "Server/Protocol/Opcodes.cpp"
MISC = G + "Handlers/MiscHandler.cpp"
WHOCACHE = G + "Cache/WhoListCacheMgr.cpp"
WHOCACHE_H = G + "Cache/WhoListCacheMgr.h"
QUERY = G + "Handlers/QueryHandler.cpp"
SOCIAL_H = G + "Entities/Player/SocialMgr.h"
GUILD = G + "Guilds/Guild.cpp"
GUILD_PK = G + "Server/Packets/GuildPackets.h"
SERVER_H = G + "Scripting/ScriptDefines/ServerScript.h"
SESSION = G + "Server/WorldSession.cpp"
FILES = (WORLD, MAPMGR, OPCODES, MISC, WHOCACHE, WHOCACHE_H, QUERY, SOCIAL_H, GUILD,
         GUILD_PK, SERVER_H, SESSION)


def lines(src, path, first, last):
    chunk = src[path].splitlines()[first - 1:last]
    return " ".join(" ".join(chunk).split())


def has(src, path, first, last, *needles):
    text = lines(src, path, first, last)
    return all(n in text for n in needles)


def lacks(src, path, first, last, *needles):
    text = lines(src, path, first, last)
    return all(n not in text for n in needles)


def world_order(s):
    """Line numbers of the four World::Update steps, in source order."""
    want = ("sWhoListCacheMgr->Update();", "sWorldSessionMgr->UpdateSessions(diff);",
            "sMapMgr->Update(diff);", "sScriptMgr->OnWorldUpdate(diff);")
    found = []
    for needle in want:
        hits = [n for n, l in enumerate(s[WORLD].splitlines(), 1) if needle in l]
        if len(hits) != 1:
            return None
        found.append(hits[0])
    return found


# (id, description, predicate, negative fixture as (path, old, new))
FACTS = [
    ("C1", "who cache is rebuilt every 5 s (World.cpp L934)",
     lambda s: has(s, WORLD, 934, 934, "_timers[WUPDATE_WHO_LIST].SetInterval(5 * IN_MILLISECONDS);"),
     (WORLD, "_timers[WUPDATE_WHO_LIST].SetInterval(5 * IN_MILLISECONDS);",
      "_timers[WUPDATE_WHO_LIST].SetInterval(1 * IN_MILLISECONDS);")),
    ("C2", "World::Update order: who cache L1170, sessions L1227, maps L1254, OnWorldUpdate L1355",
     lambda s: world_order(s) == [1170, 1227, 1254, 1355],
     (WORLD, "        sScriptMgr->OnWorldUpdate(diff);\n", "")),
    ("C3", "MapMgr::Update waits for every map worker (MapMgr.cpp L280)",
     lambda s: has(s, MAPMGR, 280, 280, "m_updater.wait();"),
     (MAPMGR, "        m_updater.wait();\n", "\n")),
    ("C4", "CMSG_WHO is STATUS_LOGGEDIN, PROCESS_THREADSAFE (Opcodes.cpp L229)",
     lambda s: has(s, OPCODES, 229, 229, "DEFINE_HANDLER(CMSG_WHO,", "STATUS_LOGGEDIN", "PROCESS_THREADSAFE",
                   "&WorldSession::HandleWhoOpcode"),
     (OPCODES, "STATUS_LOGGEDIN,   PROCESS_THREADSAFE,     &WorldSession::HandleWhoOpcode",
      "STATUS_LOGGEDIN,   PROCESS_THREADUNSAFE,   &WorldSession::HandleWhoOpcode")),
    ("C5", "the stock handler reads the cache, not live players (MiscHandler.cpp L294)",
     lambda s: has(s, MISC, 294, 294, "for (auto const& target : sWhoListCacheMgr->GetWhoList())"),
     (MISC, "for (auto const& target : sWhoListCacheMgr->GetWhoList())",
      "for (auto const& target : ObjectAccessor::GetPlayers())")),
    ("C6", "cache rows carry the player GUID and race (WhoListCacheMgr.cpp L58-L61)",
     lambda s: has(s, WHOCACHE, 58, 61, "_whoListStorage.emplace_back(player->GetGUID(),", "player->getRace()"),
     (WHOCACHE, "_whoListStorage.emplace_back(player->GetGUID(),", "_whoListStorage.emplace_back(ObjectGuid::Empty,")),
    ("C7", "row GUID accessor exists for a board lookup (WhoListCacheMgr.h L44)",
     lambda s: has(s, WHOCACHE_H, 44, 44, "ObjectGuid GetGuid() const { return _guid; }"),
     (WHOCACHE_H, "ObjectGuid GetGuid() const { return _guid; }", "")),
    ("C8", "name query response sends race (QueryHandler.cpp L49)",
     lambda s: has(s, QUERY, 49, 49, "nameQueryResponse.Race = player ? player->getRace() : playerData->Race;"),
     (QUERY, "nameQueryResponse.Race = player ? player->getRace() : playerData->Race;",
      "nameQueryResponse.Race = 0;")),
    ("C9", "friend list entries carry no race (SocialMgr.h L47-L55)",
     lambda s: has(s, SOCIAL_H, 47, 55, "struct FriendInfo", "uint8 Level;", "uint8 Class;")
     and lacks(s, SOCIAL_H, 47, 55, "Race"),
     (SOCIAL_H, "    uint8 Class;\n    std::string Note;", "    uint8 Class;\n    uint8 Race;\n    std::string Note;")),
    ("C10", "guild roster entries carry no race (GuildPackets.h L105-L120, Guild.cpp L1234-L1248)",
     lambda s: has(s, GUILD_PK, 105, 120, "struct GuildRosterMemberData", "uint8 ClassID", "uint8 Gender")
     and lacks(s, GUILD_PK, 105, 120, "Race")
     and has(s, GUILD, 1234, 1248, "memberData.ClassID = member.GetClass();")
     and lacks(s, GUILD, 1234, 1248, "Race"),
     (GUILD, "        memberData.Gender = member.GetGender();\n",
      "        memberData.Gender = member.GetGender();\n        memberData.Race = member.GetRace();\n")),
    ("C11", "packet hooks exist: CanPacketSend / CanPacketReceive (ServerScript.h L65, L75)",
     lambda s: has(s, SERVER_H, 65, 65, "virtual bool CanPacketSend(WorldSession*")
     and has(s, SERVER_H, 75, 75, "virtual bool CanPacketReceive(WorldSession*"),
     (SERVER_H, "virtual bool CanPacketSend(WorldSession*", "virtual bool CanPacketSent(WorldSession*")),
    ("C12", "every outgoing packet passes CanPacketSend (WorldSession.cpp L351)",
     lambda s: has(s, SESSION, 351, 351, "if (!sScriptMgr->CanPacketSend(this, *packet))"),
     (SESSION, "if (!sScriptMgr->CanPacketSend(this, *packet))", "if (false)")),
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
    for fid, desc, pred, _ in FACTS:
        ok = bool(pred(src))
        print(f"{'OK  ' if ok else 'FAIL'} {fid}: {desc}")
        bad += not ok
    caught = 0
    for fid, _, pred, (path, old, new) in FACTS:
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
    print(f"PASS: {len(FACTS)} pinned core facts at {PIN[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
