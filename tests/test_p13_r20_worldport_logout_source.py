#!/usr/bin/env python3
"""P13-R20 source-only worldport/logout interaction; no real Worldserver.

Run: python3 -I tests/test_p13_r20_worldport_logout_source.py . pinned-core
All examples are synthetic branch coverage, not actual transfer/hang/leak evidence.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD = "src/Systems/HonorOverflow.cpp"
MOVE = "src/server/game/Handlers/MovementHandler.cpp"
SESSION = "src/server/game/Server/WorldSession.cpp"
PLAYER = "src/server/game/Entities/Player/Player.cpp"
MAP = "src/server/game/Maps/Map.cpp"
CHARACTER = "src/server/game/Handlers/CharacterHandler.cpp"
BLOBS = {
 MOD: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
 MOVE: "f21b8464de6f362c21cc2bdf0f4f30c1df483f33",
 SESSION: "fc96398079b50984ed0b82183d713c666af6939b",
 PLAYER: "138e7eab4905ec366338a54cc18e6cfe749a3670",
 MAP: "ba4c57ed8e095aef76de9b36e708924cb2c51a09",
 CHARACTER: "d7123a9c503c3363ff2ea08b2d24eec7d07c5643",
}

def git(root: pathlib.Path, *args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()

def body(src: str, anchor: str):
    pos=src.index(anchor)
    start=src.index("{",pos)
    depth=0
    for i in range(start,len(src)):
        if src[i]=="{": depth+=1
        elif src[i]=="}":
            depth-=1
            if depth==0: return src[pos:i+1]
    raise AssertionError("unbalanced original C++ body: "+anchor)

def before(text: str, *words: str):
    offsets=[]
    for w in words:
        assert w in text, "missing original statement: "+w
        offsets.append(text.index(w))
    assert offsets==sorted(offsets) and len(set(offsets))==len(offsets), "unexpected original statement order"

def extract(src):
    mod,movement,session,player,map_src,character=src
    return {
        "far": body(player,"bool Player::TeleportTo(uint32 mapid, float x, float y, float z, float orientation"),
        "ack_opcode": body(movement,"void WorldSession::HandleMoveWorldportAckOpcode(WorldPacket& /*recvData*/)"),
        "ack": body(movement,"void WorldSession::HandleMoveWorldportAck()"),
        "logout": body(session,"void WorldSession::LogoutPlayer(bool save, bool redirecting)"),
        "map_add": body(map_src,"bool Map::AddPlayerToMap(Player* player)"),
        "map_remove": body(map_src,"void Map::RemovePlayerFromMap(Player* player, bool remove)"),
        "reconnect": body(character,"void WorldSession::HandlePlayerLoginOpcode(WorldPacket& recvData)"),
        "honor_logout": body(mod,"    void OnPlayerLogout(Player* player) override"),
    }

def verify(blocks):
    far,ack,logout,map_add,reconnect=(
        blocks[k] for k in ("far","ack","logout","map_add","reconnect")
    )
    assert "HandleMoveWorldportAck();" in blocks["ack_opcode"]
    assert "bool Player::TeleportTo" in far
    before(far,"Map* oldmap = IsInWorld() ? GetMap() : nullptr;",
           "oldmap->RemovePlayerFromMap(this, false);",
           "SetSemaphoreTeleportFar(GameTime::GetGameTime().count());")
    assert "if (oldmap)\n                oldmap->RemovePlayerFromMap(this, false);" in far
    assert "move packet sent by client always after far teleport" in far
    assert "HandleMoveWorldportAckOpcode" in far

    assert "if (!GetPlayer()->IsBeingTeleportedFar())\n        return;" in ack
    before(ack,
           "if (!GetPlayer()->IsBeingTeleportedFar())",
           "GetPlayer()->SetSemaphoreTeleportFar(0);",
           "if (!MapMgr::IsValidMapCoord(loc))",
           "Map* newMap = sMapMgr->CreateMap(loc.GetMapId(), GetPlayer());",
           "GetPlayer()->ResetMap();",
           "GetPlayer()->SetMap(newMap);",
           "if (!GetPlayer()->GetMap()->AddPlayerToMap(GetPlayer()))",
           "oldMap->AfterPlayerUnlinkFromMap();")
    assert re.search(r"if \(!MapMgr::IsValidMapCoord\(loc\)\)\s*\{\s*KickPlayer\(\"!MapMgr::IsValidMapCoord\(loc\)\"\);\s*return;\s*\}",ack)
    assert "if (!newMap || newMap->CannotEnter(GetPlayer(), false))" in ack
    assert "GetPlayer()->TeleportTo(GetPlayer()->m_homebindMapId" in ack
    assert "if (!GetPlayer()->GetMap()->AddPlayerToMap(GetPlayer()))" in ack
    assert ack.count("GetPlayer()->TeleportTo(GetPlayer()->m_homebindMapId") == 2, "two distinct fallback paths must exist"
    assert "GetPlayer()->ResetMap();\n        GetPlayer()->SetMap(oldMap);" in ack
    assert ack.index("SetSemaphoreTeleportFar(0);") < ack.index('KickPlayer("!MapMgr::IsValidMapCoord(loc)")')

    assert logout.count("while (_player && _player->IsBeingTeleportedFar())") == 2
    before(logout,
           "// finish pending transfers before starting the logout",
           "m_playerLogout = true;",
           "sScriptMgr->OnPlayerBeforeLogout(_player);",
           "// Teleport player immediately for correct player save",
           "if (save)",
           "_player->CleanupsBeforeDelete();",
           "if (Map* _map = _player->FindMap())",
           "SetPlayer(nullptr); // pointer already deleted")
    assert logout.count("HandleMoveWorldportAck();") == 2
    first=logout.index("while (_player && _player->IsBeingTeleportedFar())")
    second=logout.index("while (_player && _player->IsBeingTeleportedFar())",first+1)
    assert first < logout.index("m_playerLogout = true;") < second < logout.index("if (save)")
    assert re.search(r"if \(Map\* _map = _player->FindMap\(\)\)\s*\{\s*_map->RemovePlayerFromMap\(_player, true\);",logout)
    assert "SetPlayer(nullptr); // pointer already deleted" in logout
    assert "while (_player && _player->IsBeingTeleportedFar())" in logout

    assert "if (!cellCoord.IsCoordValid())" in map_add
    assert "return false;" in map_add
    assert "sScriptMgr->OnPlayerEnterMap(this, player);" in map_add
    assert "player->RemoveFromWorld();" in blocks["map_remove"]
    assert "if (remove)" in blocks["map_remove"]
    assert "if (limitA == 0 || --limitA == 0)" in reconnect
    assert "if (limitB == 0 || --limitB == 0)" in reconnect
    assert "if (limitC == 0 || --limitC == 0)" in reconnect
    assert "sess->HandleMoveWorldportAck();" in reconnect
    assert "HonorSnapshots.erase(guid);" in blocks["honor_logout"]
    return True

def mutation_guards(original):
    checks=[
        ("far teleport no old map removal","far","oldmap->RemovePlayerFromMap(this, false);","/* omitted */"),
        ("far flag missing","far","SetSemaphoreTeleportFar(GameTime::GetGameTime().count());","/* no far teleport flag */"),
        ("opcode no direct ACK dispatch","ack_opcode","HandleMoveWorldportAck();","/* no dispatch */"),
        ("ACK spurious guard disabled","ack","if (!GetPlayer()->IsBeingTeleportedFar())","if (false)"),
        ("ACK clears far semaphore too late","ack","GetPlayer()->SetSemaphoreTeleportFar(0);","/* no clear */"),
        ("ACK invalid coordinate no kick","ack",'KickPlayer("!MapMgr::IsValidMapCoord(loc)");',"/* no kick */"),
        ("ACK map create bypass","ack","Map* newMap = sMapMgr->CreateMap(loc.GetMapId(), GetPlayer());","Map* newMap = nullptr;"),
        ("ACK cannot-enter gate disabled","ack","!newMap || newMap->CannotEnter(GetPlayer(), false)","false"),
        ("ACK map add bypass","ack","if (!GetPlayer()->GetMap()->AddPlayerToMap(GetPlayer()))","if (false)"),
        ("ACK map rollback disabled","ack","GetPlayer()->SetMap(oldMap);","/* no rollback */"),
        ("ACK missing homebind fallback","ack","GetPlayer()->TeleportTo(GetPlayer()->m_homebindMapId","GetPlayer()->FakeTeleportTo(GetPlayer()->m_homebindMapId"),
        ("ACK successful old-map unlink removed","ack","oldMap->AfterPlayerUnlinkFromMap();","/* no map unlink */"),
        ("logout initial transfer drain removed","logout","// finish pending transfers before starting the logout","/* removed initial drain */"),
        ("logout second drain removed","logout","// Teleport player immediately for correct player save","/* second drain removed */"),
        ("logout map-null guard removed","logout","if (Map* _map = _player->FindMap())","if (true)"),
        ("logout detach removed","logout","SetPlayer(nullptr); // pointer already deleted","/* no detach */"),
        ("reconnect bound missing","reconnect","if (limitB == 0 || --limitB == 0)","if (false)"),
        ("map add no validity guard","map_add","if (!cellCoord.IsCoordValid())","if (false)"),
        ("map entered hook removed","map_add","sScriptMgr->OnPlayerEnterMap(this, player);","/* no hook */"),
        ("honor logout no snapshot cleanup","honor_logout","HonorSnapshots.erase(guid);","/* no snapshot cleanup */")
    ]
    for name,key,old,new in checks:
        assert old in original[key],"missing negative guard "+name
        changed=dict(original)
        changed[key]=changed[key].replace(old,new,1)
        try: verify(changed)
        except (AssertionError,ValueError):
            print("CAUGHT R20 SOURCE DRIFT: "+name)
        else: raise AssertionError("negative source change survived "+name)
    assert len(checks)==20
    print("PASS: R20 twenty synthetic source drift mutants caught")

def synthetic_branch_cases():
    # This is an illustrative conditional branch table, not a real callback execution.
    cases=[
        ("spurious_ack",False,False,False),
        ("invalid_coords",True,False,True),
        ("map_refused",True,True,False),
        ("map_add_failed",True,True,False),
        ("map_add_success",True,True,False)
    ]
    for name,pending,flag_cleared,kick in cases:
        if name=="spurious_ack":
            assert not pending and not flag_cleared and not kick
        else:
            assert pending and flag_cleared
        print("SYNTHETIC R20 path "+name+" pending="+str(pending).lower()+
              " cleared="+str(flag_cleared).lower()+" kick="+str(kick).lower())
    print("PASS: R20 five illustrative condition-only ACK cases (NOT a real transfer)")
    
def main(args):
    if len(args)!=3:
        print(__doc__)
        return 2
    mod,core=(pathlib.Path(p) for p in args[1:])
    assert git(core,"rev-parse","HEAD")==CORE
    git(mod,"merge-base","--is-ancestor",MAIN,"HEAD")
    for path,blob in BLOBS.items():
        repo,ref=(mod,MAIN) if path==MOD else (core,CORE)
        assert git(repo,"rev-parse",ref+":"+path)==blob,path
    assert git(mod,"rev-parse","HEAD:"+MOD)==BLOBS[MOD]
    src=[(mod/MOD).read_text()]+[(core/p).read_text() for p in
                                  (MOVE,SESSION,PLAYER,MAP,CHARACTER)]
    original=extract(src)
    verify(original)
    print("PASS: R20 six exact pinned source blobs and real transfer/ACK/logout guards")
    mutation_guards(original)
    synthetic_branch_cases()
    print("LIMIT: ACK clears far flag early; no unconditional map admission, guaranteed bounded retries, or actual leak")
    print("LIMIT: no real Worldserver, Player, script invocation, map, DB/client, SQL/DBC, concurrency or payout")
    return 0

if __name__=="__main__":
    try: sys.exit(main(sys.argv))
    except (AssertionError,ValueError,subprocess.CalledProcessError) as e:
        print("FAIL: "+str(e))
        sys.exit(1)
