#!/usr/bin/env python3
"""P13-R18 original pinned Player admission/retirement ordering guards.

No Worldserver, Player lifetime operation, actual money or production change.
Use: python3 -I tests/test_p13_r18_admission_retirement_source.py . pinned-core
"""
from __future__ import annotations
import pathlib
import re
import subprocess
import sys

MOD_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD = "src/Systems/HonorOverflow.cpp"
HANDLER = "src/server/game/Handlers/CharacterHandler.cpp"
MAP = "src/server/game/Maps/Map.cpp"
SESSION = "src/server/game/Server/WorldSession.cpp"
ACCESSOR = "src/server/game/Globals/ObjectAccessor.cpp"
PLAYER = "src/server/game/Entities/Player/Player.cpp"
MISC = "src/server/game/Scripting/ScriptDefines/MiscScript.cpp"
BLOBS = {
    MOD: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
    HANDLER: "d7123a9c503c3363ff2ea08b2d24eec7d07c5643",
    MAP: "ba4c57ed8e095aef76de9b36e708924cb2c51a09",
    SESSION: "fc96398079b50984ed0b82183d713c666af6939b",
    ACCESSOR: "8b15ce734d8f6624a29fe12e23c6917d77e1919d",
    PLAYER: "138e7eab4905ec366338a54cc18e6cfe749a3670",
    MISC: "a41a3f0d9f48d0c4319a585c591ba7ec722fc37b",
}

def git(root: pathlib.Path, *args: str):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def method(src: str, anchor: str):
    start = src.index(anchor)
    opening = src.index("{", start)
    depth = 0
    for pos in range(opening, len(src)):
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
            if depth == 0:
                return src[start:pos + 1]
    raise AssertionError("unbalanced original method " + anchor)

def assert_order(body: str, *anchors):
    positions = []
    for anchor in anchors:
        assert anchor in body, "missing exact original source statement " + anchor
        positions.append(body.index(anchor))
    assert positions == sorted(positions) and len(set(positions)) == len(positions), (
        "original code order changed: " + repr(anchors))
    return True

def verify(parts):
    mod, handler, map_src, session_src, acc, player, misc = parts
    login = method(handler, "void WorldSession::HandlePlayerLoginFromDB(LoginQueryHolder const& holder)")
    map_add = method(map_src, "bool Map::AddPlayerToMap(Player* player)")
    logout = method(session_src, "void WorldSession::LogoutPlayer(bool save, bool redirecting)")
    map_remove = method(map_src, "void Map::RemovePlayerFromMap(Player* player, bool remove)")
    map_delete = method(map_src, "void Map::DeleteFromWorld(Player* player)")
    access_add = method(acc, "void ObjectAccessor::AddObject(Player* player)")
    access_remove = method(acc, "void ObjectAccessor::RemoveObject(Player* player)")
    connected = method(acc, "Player* ObjectAccessor::FindConnectedPlayer(ObjectGuid const guid)")
    player_dtor = method(player, "Player::~Player()")
    misc_dtor = method(misc, "void ScriptMgr::OnDestructPlayer(Player* origin)")
    module_login = method(mod, "    void OnPlayerLogin(Player* player) override")
    module_logout = method(mod, "    void OnPlayerLogout(Player* player) override")

    assert_order(login,
        "Player* pCurrChar = new Player(this);",
        "if (!pCurrChar->LoadFromDB(playerGuid, holder))",
        "ObjectAccessor::AddObject(pCurrChar);",
        "pCurrChar->GetMap()->AddPlayerToMap(pCurrChar)",
        "sScriptMgr->OnPlayerLogin(pCurrChar);")
    assert "delete pCurrChar; // delete it manually" in login
    fail_start = login.index("if (!pCurrChar->LoadFromDB(playerGuid, holder))")
    fail_end = login.index("pCurrChar->GetMotionMaster()->Initialize();",fail_start)
    assert "delete pCurrChar; // delete it manually" in login[fail_start:fail_end]
    assert "return;" in login[fail_start:fail_end]
    assert "ObjectAccessor::AddObject(pCurrChar);" not in login[fail_start:fail_end]
    assert "sScriptMgr->OnPlayerLogin(pCurrChar);" not in login[fail_start:fail_end]

    assert_order(map_add, "AddToGrid(player, cell);",
                 "player->AddToWorld();", "sScriptMgr->OnPlayerEnterMap(this, player);", "return true;")
    assert "if (!cellCoord.IsCoordValid())" in map_add and "return false;" in map_add
    assert "bool Map::AddPlayerToMap" in map_add

    assert_order(logout,
        "sScriptMgr->OnPlayerBeforeLogout(_player);",
        "_player->LeaveBattleground();",
        "sScriptMgr->OnPlayerLogout(_player);",
        "_map->RemovePlayerFromMap(_player, true);",
        "SetPlayer(nullptr); // pointer already deleted")
    assert re.search(r"if \(!redirecting\)\s*\{\s*//! Broadcast a logout message to the player's friends[\s\S]*?sScriptMgr->OnPlayerLogout\(_player\);\s*\}",logout), (
        "normal logout event no longer gated by redirecting")
    assert "if (Map* _map = _player->FindMap())" in logout
    assert "sScriptMgr->OnPlayerLogout(_player);" not in logout[logout.index("if (Map* _map"):]

    assert_order(map_remove,
        "player->RemoveFromWorld();", "sScriptMgr->OnPlayerLeaveMap(this, player);",
        "DeleteFromWorld(player);")
    assert re.search(r"if \(remove\)\s*\{\s*DeleteFromWorld\(player\);\s*\}",map_remove)
    assert_order(map_delete, "ObjectAccessor::RemoveObject(player);", "delete player;")
    assert_order(access_remove, "HashMapHolder<Player>::Remove(player);", "PlayerNameMapHolder::Remove(player);")
    assert_order(access_add, "HashMapHolder<Player>::Insert(player);", "PlayerNameMapHolder::Insert(player);")
    assert "return HashMapHolder<Player>::Find(guid);" in connected
    assert "sScriptMgr->OnDestructPlayer(this);" in player_dtor
    assert "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_DESTRUCT_PLAYER, script->OnDestructPlayer(origin));" in misc_dtor
    assert "StoreHonorSnapshot(player);" in module_login
    assert "BattlegroundHonorSummaries.erase(" in module_login
    assert_order(module_logout, "HonorSnapshots.erase(guid);", "BattlegroundHonorSummaries.erase(guid);")
    return True

def mutations(parts):
    cases = [
        ("registration moved behind map add", 1,
         "ObjectAccessor::AddObject(pCurrChar);", "/* deferred global registration */"),
        ("map add moved behind ordinary login", 1,
         "sScriptMgr->OnPlayerLogin(pCurrChar);", "/* no login dispatch */"),
        ("failed load no delete", 1, "delete pCurrChar; // delete it manually", "/* no delete */"),
        ("map enter hook missing", 2, "sScriptMgr->OnPlayerEnterMap(this, player);", "/* hook removed */"),
        ("world admission no Player AddToWorld", 2, "player->AddToWorld();", "/* not in world */"),
        ("redirecting guard removed from logout", 3,
         "if (!redirecting)\n        {\n            //! Broadcast a logout message to the player's friends",
         "if (true)\n        {\n            //! Broadcast a logout message to the player's friends"),
        ("normal logout hook removed", 3, "sScriptMgr->OnPlayerLogout(_player);", "/* no logout hook */"),
        ("map removal skipped", 3, "_map->RemovePlayerFromMap(_player, true);", "/* no map remove */"),
        ("map leave hook missing", 2, "sScriptMgr->OnPlayerLeaveMap(this, player);", "/* no leave hook */"),
        ("map unregister missing", 2, "ObjectAccessor::RemoveObject(player);", "/* no unregister */"),
        ("delete replaced with retention", 2, "delete player;", "/* retained Player */"),
        ("registry remove missing", 4, "HashMapHolder<Player>::Remove(player);", "/* registry not cleared */"),
        ("connected lookup no longer raw holder", 4, "return HashMapHolder<Player>::Find(guid);", "return nullptr;"),
        ("Player destruct signal missing", 5, "sScriptMgr->OnDestructPlayer(this);", "/* no Player destructor callback */"),
        ("MiscScript actual dispatch bypassed", 6,
         "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_DESTRUCT_PLAYER, script->OnDestructPlayer(origin));",
         "/* dispatch disabled */"),
        ("HonorOverflow normal logout no snapshot erase", 0,
         "HonorSnapshots.erase(guid);", "/* no snapshot erase */"),
    ]
    for label,index,old,new in cases:
        src=list(parts)
        assert old in src[index], "missing mutation anchor " + label
        src[index]=src[index].replace(old,new,1)
        try:
            verify(src)
        except (ValueError, AssertionError):
            print("CAUGHT R18 SOURCE DRIFT: " + label)
        else:
            raise AssertionError("R18 source mutation survived: " + label)
    assert len(cases)==16
    print("PASS: R18 sixteen negative source-drift mutations caught")

def synthetic_ordering():
    # Synthetic event order only, not an executing Worldserver callback chain.
    ordinary_login=["construct", "load_success", "register", "enter_world", "on_enter_map","on_login"]
    failed_load=["construct","load_failure","destruct"]
    ordinary_logout=["on_before_logout","leave_battleground","on_logout",
                     "remove_world","on_leave_map","unregister","destruct"]
    redirect_logout=["on_before_logout","leave_battleground",
                     "remove_world","on_leave_map","unregister","destruct"]
    assert ordinary_login.index("register") < ordinary_login.index("on_enter_map") < ordinary_login.index("on_login")
    assert "on_login" not in failed_load and "register" not in failed_load
    assert ordinary_logout.index("on_logout") < ordinary_logout.index("destruct")
    assert "on_logout" not in redirect_logout and redirect_logout.index("on_leave_map") < redirect_logout.index("destruct")
    print("PASS: R18 four synthetic conditional lifecycle timelines (NOT live executions)")

def main(argv):
    if len(argv)!=3:
        print(__doc__)
        return 2
    mod,core=[pathlib.Path(x) for x in argv[1:]]
    assert git(core,"rev-parse","HEAD")==CORE_SHA
    git(mod,"merge-base","--is-ancestor",MOD_SHA,"HEAD")
    for path,blob in BLOBS.items():
        repo,ref=(mod,MOD_SHA) if path==MOD else (core,CORE_SHA)
        assert git(repo,"rev-parse",ref+":"+path)==blob,path
    assert git(mod,"rev-parse","HEAD:"+MOD)==BLOBS[MOD]
    src=[(mod/MOD).read_text()]+[(core/p).read_text() for p in
                                 (HANDLER,MAP,SESSION,ACCESSOR,PLAYER,MISC)]
    verify(src)
    print("PASS: R18 seven pinned original C++ blobs and ordinary admission, logout, redirect and retire source order")
    mutations(src)
    synthetic_ordering()
    print("LIMIT: redirect map removal requires FindMap, map enter requires valid cell; no unconditional world/login proof")
    print("LIMIT: no real hook/Worldserver/concurrency/Player identity token, host, money, client/DB/SQL/DBC")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError,ValueError,subprocess.CalledProcessError) as err:
        print("FAIL: "+str(err))
        sys.exit(1)
