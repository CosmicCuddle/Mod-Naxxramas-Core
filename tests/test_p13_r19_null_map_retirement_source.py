#!/usr/bin/env python3
"""P13-R19 original source conditional null-map logout retirement, NONPRODUCTION.
python3 -I tests/test_p13_r19_null_map_retirement_source.py . pinned-core
No real Player, map, deregistration, runtime, money or owner-host execution.
"""
import pathlib
import subprocess
import sys
import re

MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD = "src/Systems/HonorOverflow.cpp"
SESSION = "src/server/game/Server/WorldSession.cpp"
MAP = "src/server/game/Maps/Map.cpp"
PLAYER = "src/server/game/Entities/Player/Player.cpp"
ACCESS = "src/server/game/Globals/ObjectAccessor.cpp"
MISC = "src/server/game/Scripting/ScriptDefines/MiscScript.cpp"
BLOBS = {
 MOD: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
 SESSION: "fc96398079b50984ed0b82183d713c666af6939b",
 MAP: "ba4c57ed8e095aef76de9b36e708924cb2c51a09",
 PLAYER: "138e7eab4905ec366338a54cc18e6cfe749a3670",
 ACCESS: "8b15ce734d8f6624a29fe12e23c6917d77e1919d",
 MISC: "a41a3f0d9f48d0c4319a585c591ba7ec722fc37b",
}

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def method(src, anchor):
    idx = src.index(anchor)
    start = src.index("{",idx)
    depth = 0
    for i in range(start,len(src)):
        if src[i] == "{": depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0: return src[idx:i+1]
    raise AssertionError("unbalanced method " + anchor)

def order(text, *fragments):
    idx=[]
    for fragment in fragments:
        assert fragment in text, "missing original fragment " + fragment
        idx.append(text.index(fragment))
    assert idx == sorted(idx) and len(set(idx)) == len(idx), "unexpected source ordering"
    return True

def contract(mod, session, map_src, player, accessor, misc):
    logout = method(session,"void WorldSession::LogoutPlayer(bool save, bool redirecting)")
    sess_dtor = method(session,"WorldSession::~WorldSession()")
    session_set = method(session,"void WorldSession::SetPlayer(Player* player)")
    cleanup = method(player,"void Player::CleanupsBeforeDelete(bool finalCleanup)")
    player_dtor = method(player,"Player::~Player()")
    map_remove = method(map_src,"void Map::RemovePlayerFromMap(Player* player, bool remove)")
    map_delete = method(map_src,"void Map::DeleteFromWorld(Player* player)")
    unregister = method(accessor,"void ObjectAccessor::RemoveObject(Player* player)")
    misc_destruct = method(misc,"void ScriptMgr::OnDestructPlayer(Player* origin)")
    module_logout = method(mod,"    void OnPlayerLogout(Player* player) override")
    module_login = method(mod,"    void OnPlayerLogin(Player* player) override")

    order(logout, "sScriptMgr->OnPlayerBeforeLogout(_player);",
          "_player->LeaveBattleground();",
          "sScriptMgr->OnPlayerLogout(_player);",
          "_player->CleanupsBeforeDelete();",
          "if (Map* _map = _player->FindMap())",
          "_map->RemovePlayerFromMap(_player, true);",
          "SetPlayer(nullptr); // pointer already deleted")
    assert "the player may not be in the world when logging out" in logout
    assert "if he got disconnected during a transfer to another map" in logout
    assert re.search(r"if \(!redirecting\)\s*\{\s*//! Broadcast a logout message to the player's friends[\s\S]*?sScriptMgr->OnPlayerLogout\(_player\);\s*\}",logout), "redirect guard changed"
    assert re.search(r"if \(Map\* _map = _player->FindMap\(\)\)\s*\{\s*_map->RemovePlayerFromMap\(_player, true\);\s*_map->AfterPlayerUnlinkFromMap\(\);\s*\}",logout), "map found branch changed"
    assert "delete _player;" not in logout and "ObjectAccessor::RemoveObject(_player);" not in logout
    assert logout.index("_map->RemovePlayerFromMap(_player, true);") < logout.index("SetPlayer(nullptr);")
    assert "if (_player)\n        LogoutPlayer(true);" in sess_dtor
    assert "_player = player;" in session_set and "delete player;" not in session_set
    assert "if (_player)\n        m_GUIDLow = _player->GetGUID().GetCounter();" in session_set

    order(cleanup,"TradeCancel(false);","DuelComplete(DUEL_INTERRUPTED);","Unit::CleanupsBeforeDelete(finalCleanup);")
    assert "delete this" not in cleanup and "ObjectAccessor::RemoveObject" not in cleanup
    order(map_remove,"player->RemoveFromWorld();","sScriptMgr->OnPlayerLeaveMap(this, player);","DeleteFromWorld(player);")
    assert re.search(r"if \(remove\)\s*\{\s*DeleteFromWorld\(player\);\s*\}",map_remove)
    order(map_delete,"ObjectAccessor::RemoveObject(player);","delete player;")
    order(unregister,"HashMapHolder<Player>::Remove(player);","PlayerNameMapHolder::Remove(player);")
    assert "sScriptMgr->OnDestructPlayer(this);" in player_dtor
    assert "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_DESTRUCT_PLAYER, script->OnDestructPlayer(origin));" in misc_destruct
    order(module_logout,"HonorSnapshots.erase(guid);","BattlegroundHonorSummaries.erase(guid);")
    assert "BattlegroundHonorSummaries.erase(" in module_login and "StoreHonorSnapshot(player);" in module_login
    return True

def mutation_guard(inputs):
    cases=[
        ("missing map-null gate",1,"if (Map* _map = _player->FindMap())","if (true)"),
        ("map remove bypassed",1,"_map->RemovePlayerFromMap(_player, true);","/* no remove */"),
        ("session still retains Player",1,"SetPlayer(nullptr); // pointer already deleted","/* no detach */"),
        ("map branch moved after session detach",1,"_player->CleanupsBeforeDelete();","/* no original cleanup */"),
        ("redirecting no longer suppresses logout",1,
         "if (!redirecting)\n        {\n            //! Broadcast a logout message to the player's friends",
         "if (true)\n        {\n            //! Broadcast a logout message to the player's friends"),
        ("logout hook removed",1,"sScriptMgr->OnPlayerLogout(_player);","/* no event */"),
        ("session destructor unconditional logout",1,"if (_player)\n        LogoutPlayer(true);","LogoutPlayer(true);"),
        ("session setter no detach",1,"_player = player;","/* old pointer retained */"),
        ("player cleanup no longer calls unit cleanup",3,"Unit::CleanupsBeforeDelete(finalCleanup);","/* cleanup skipped */"),
        ("map remove skips leave hook",2,"sScriptMgr->OnPlayerLeaveMap(this, player);","/* hook skipped */"),
        ("map remove skips deletion",2,"DeleteFromWorld(player);","/* no delete */"),
        ("map delete skips unregister",2,"ObjectAccessor::RemoveObject(player);","/* no unregister */"),
        ("map delete skips Player destruction",2,"delete player;","/* no delete */"),
        ("accessor no longer unregisters",4,"HashMapHolder<Player>::Remove(player);","/* no registry removal */"),
        ("Player destructor hook removed",3,"sScriptMgr->OnDestructPlayer(this);","/* no destructor dispatch */"),
        ("MiscScript destructor callback bypass",5,
         "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_DESTRUCT_PLAYER, script->OnDestructPlayer(origin));",
         "/* disabled */"),
        ("HonorOverflow ordinary logout no snapshot erase",0,
         "HonorSnapshots.erase(guid);","/* snapshot retained */"),
    ]
    for label,i,old,new in cases:
        assert old in inputs[i], "missing mutant anchor "+label
        modified=list(inputs)
        modified[i]=modified[i].replace(old,new,1)
        try:
            contract(*modified)
        except (ValueError,AssertionError):
            print("CAUGHT R19 SOURCE DRIFT: "+label)
        else:
            raise AssertionError("mutant survived: "+label)
    assert len(cases)==17
    print("PASS: R19 seventeen deliberate source-drift mutants caught")

def scenarios():
    # Only branch membership, NOT a real Player lifecycle reproduction.
    for redirecting,has_map in [(False,True),(True,True),(False,False),(True,False)]:
        normal_hook=not redirecting
        map_remove=has_map
        unregister=has_map
        destruct=has_map
        detached=True
        assert detached
        assert normal_hook == (not redirecting)
        assert map_remove == has_map and unregister == has_map and destruct == has_map
        print("SYNTHETIC R19 path redirecting="+str(redirecting).lower()+
              " map_found="+str(has_map).lower()+
              " normal_logout_hook="+str(normal_hook).lower()+
              " direct_map_delete="+str(destruct).lower())
    print("PASS: R19 four synthetic branch-only timelines, no live cleanup inference")

def main(argv):
    if len(argv)!=3:
        print(__doc__)
        return 2
    mod,core=map(pathlib.Path,argv[1:])
    assert git(core,"rev-parse","HEAD")==CORE
    git(mod,"merge-base","--is-ancestor",MAIN,"HEAD")
    for p,blob in BLOBS.items():
        folder,rev=(mod,MAIN) if p==MOD else (core,CORE)
        assert git(folder,"rev-parse",rev+":"+p)==blob,p
    assert git(mod,"rev-parse","HEAD:"+MOD)==BLOBS[MOD]
    sources=[(mod/MOD).read_text()]+[(core/p).read_text() for p in
              (SESSION,MAP,PLAYER,ACCESS,MISC)]
    contract(*sources)
    print("PASS: R19 six exact original source blobs and conditional map/no-map logout cleanup order")
    mutation_guard(sources)
    scenarios()
    print("LIMIT: no-map branch not shown calling registry removal/destructor DIRECTLY; other callbacks/ownership not excluded")
    print("LIMIT: no host memory leak proof, UAF, real logout, Worldserver, SQL/DBC, DB/client, money or gameplay")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError,ValueError,subprocess.CalledProcessError) as e:
        print("FAIL: "+str(e))
        sys.exit(1)
