#!/usr/bin/env python3
"""P13-R17 exact original source-only lifecycle pre-initialization guard.

No live Player and NO execution of GetGUID on preinitialized Object.
Usage: python3 -I tests/test_p13_r17_player_preinit_source.py . pinned-core
"""
import pathlib
import subprocess
import sys

MOD = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
HONOR = "src/Systems/HonorOverflow.cpp"
OBJECT_CPP = "src/server/game/Entities/Object/Object.cpp"
OBJECT_H = "src/server/game/Entities/Object/Object.h"
UNIT = "src/server/game/Entities/Unit/Unit.cpp"
PLAYER = "src/server/game/Entities/Player/Player.cpp"
HANDLER = "src/server/game/Handlers/CharacterHandler.cpp"
MISC_CPP = "src/server/game/Scripting/ScriptDefines/MiscScript.cpp"
MISC_H = "src/server/game/Scripting/ScriptDefines/MiscScript.h"
BLOBS = {
    HONOR: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
    OBJECT_CPP: "39a24ef072321c567892d4257bfc7a9ba9f30791",
    OBJECT_H: "ac391a9975b43f89fd84b8336b2b57db1e8d189e",
    UNIT: "ce188c543c00aa020a593641cb5491a48fb12ffa",
    PLAYER: "138e7eab4905ec366338a54cc18e6cfe749a3670",
    HANDLER: "d7123a9c503c3363ff2ea08b2d24eec7d07c5643",
    MISC_CPP: "a41a3f0d9f48d0c4319a585c591ba7ec722fc37b",
    MISC_H: "9ed20ab2304fed3bceb20a7e8dc704e529897365",
}

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def body(src, signature):
    first = src.index(signature)
    opened = src.index("{", first)
    count = 0
    for i in range(opened, len(src)):
        if src[i] == "{":
            count += 1
        elif src[i] == "}":
            count -= 1
            if not count:
                return src[first:i + 1]
    raise AssertionError("unbalanced original function: " + signature)

def verify(parts):
    mod, obj, obj_h, unit, player, handler, misc, misc_h = parts
    oc = body(obj, "Object::Object()")
    wc = body(obj, "WorldObject::WorldObject()")
    uc = body(unit, "Unit::Unit()")
    pc = body(player, "Player::Player(WorldSession* session)")
    pd = body(player, "Player::~Player()")
    create = body(player, "bool Player::Create(ObjectGuid::LowType guidlow, CharacterCreateInfo* createInfo)")
    init = body(obj, "void Object::_Create(ObjectGuid guid)")
    values = body(obj, "void Object::_InitValues()")
    read = body(obj, "ObjectGuid Object::GetGuidValue(uint16 index) const")
    db_login = body(handler, "void WorldSession::HandlePlayerLoginFromDB(LoginQueryHolder const& holder)")
    construct = body(misc, "void ScriptMgr::OnConstructPlayer(Player* origin)")
    destruct = body(misc, "void ScriptMgr::OnDestructPlayer(Player* origin)")
    hook_login = body(mod, "    void OnPlayerLogin(Player* player) override")

    assert "m_uint32Values      = nullptr;" in oc
    assert "m_valuesCount       = 0;" in oc
    assert "_InitValues(" not in wc and "_Create(" not in wc
    assert "_InitValues(" not in uc and "_Create(" not in uc
    assert "m_valuesCount = PLAYER_END;" in pc
    assert "sScriptMgr->OnConstructPlayer(this);" in pc
    assert "_InitValues(" not in pc and "_Create(" not in pc
    assert "sScriptMgr->OnDestructPlayer(this);" in pd
    assert "Object::_Create(guidlow, 0, HighGuid::Player);" in create
    assert "if (!m_uint32Values) _InitValues();" in init
    assert init.index("_InitValues();") < init.index("SetGuidValue(OBJECT_FIELD_GUID, guid);")
    assert "m_uint32Values = new uint32[m_valuesCount];" in values
    assert "ObjectGuid GetGUID() const { return GetGuidValue(OBJECT_FIELD_GUID); }" in obj_h
    assert "return *((ObjectGuid*) &(m_uint32Values[index]));" in read
    assert "ASSERT(index + 1 < m_valuesCount" in read
    assert "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_CONSTRUCT_PLAYER, script->OnConstructPlayer(origin));" in construct
    assert "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_DESTRUCT_PLAYER, script->OnDestructPlayer(origin));" in destruct
    assert "MISCHOOK_ON_CONSTRUCT_PLAYER," in misc_h
    assert "MISCHOOK_ON_DESTRUCT_PLAYER," in misc_h

    new_char = handler.index("std::shared_ptr<Player> newChar(new Player(this)")
    create_call = handler.index("newChar->Create(sObjectMgr->GetGenerator<HighGuid::Player>().Generate()", new_char)
    assert new_char < create_call
    assert "Player* pCurrChar = new Player(this);" in db_login
    assert "pCurrChar->LoadFromDB(playerGuid, holder)" in db_login
    assert db_login.index("Player* pCurrChar = new Player(this);") < db_login.index("pCurrChar->LoadFromDB(playerGuid, holder)")
    assert db_login.index("pCurrChar->LoadFromDB(playerGuid, holder)") < db_login.index("delete pCurrChar;")
    assert "ObjectAccessor::AddObject(pCurrChar);" in db_login
    assert db_login.index("pCurrChar->LoadFromDB(playerGuid, holder)") < db_login.index("ObjectAccessor::AddObject(pCurrChar);")
    assert "sScriptMgr->OnPlayerLogin(pCurrChar);" in db_login
    assert db_login.index("ObjectAccessor::AddObject(pCurrChar);") < db_login.index("sScriptMgr->OnPlayerLogin(pCurrChar);")
    assert "StoreHonorSnapshot(player);" in hook_login
    assert "BattlegroundHonorSummaries.erase(" in hook_login
    return True

def mutants(srcs):
    edits = [
        ("Object initial values now allocated", 1, "m_uint32Values      = nullptr;", "m_uint32Values = new uint32[2];"),
        ("WorldObject ctor allocates values early", 1, "WorldObject::WorldObject() : WorldLocation(),",
         "WorldObject::WorldObject() : WorldLocation(),"),
        ("Unit ctor now creates Object", 3, "m_objectType |= TYPEMASK_UNIT;", "Object::_Create(15, 0, HighGuid::Player);\n    m_objectType |= TYPEMASK_UNIT;"),
        ("Player ctor initializes fields early", 4, "sScriptMgr->OnConstructPlayer(this);",
         "Object::_Create(15, 0, HighGuid::Player);\n    sScriptMgr->OnConstructPlayer(this);"),
        ("Player construct hook absent", 4, "sScriptMgr->OnConstructPlayer(this);", "/* removed */"),
        ("character creation no longer calls Create", 5, "newChar->Create(", "newChar->FakeCreate("),
        ("ordinary DB login order changed", 5, "Player* pCurrChar = new Player(this);", "Player* pCurrChar = new Player(this);"),
        ("Object guid setter missing", 1, "SetGuidValue(OBJECT_FIELD_GUID, guid);", "/* removed */"),
        ("GetGUID no longer reads fields", 2, "GetGuidValue(OBJECT_FIELD_GUID)", "ObjectGuid::Empty"),
        ("MiscScript constructor dispatch missing", 6,
         "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_CONSTRUCT_PLAYER, script->OnConstructPlayer(origin));",
         "/* bypass */"),
        ("failed LoadFromDB no delete", 5, "delete pCurrChar; // delete it manually", "/* deleted disabled */"),
        ("HonorOverflow normal login no snapshot", 0,
         "void OnPlayerLogin(Player* player) override\n    {\n        StoreHonorSnapshot(player);",
         "void OnPlayerLogin(Player* player) override\n    {\n        /* no snapshot */"),
    ]
    count = 0
    for name, index, old, changed in edits:
        local = list(srcs)
        if name == "WorldObject ctor allocates values early":
            old = "sScriptMgr->OnWorldObjectCreate(this);"
            changed = "_InitValues();\n    sScriptMgr->OnWorldObjectCreate(this);"
        if name == "ordinary DB login order changed":
            old = "pCurrChar->LoadFromDB(playerGuid, holder)"
            changed = "pCurrChar->FakeLoadFromDB(playerGuid, holder)"
        assert old in local[index], "negative fixture anchor missing: " + name
        local[index] = local[index].replace(old, changed, 1)
        try:
            verify(local)
        except (ValueError, AssertionError):
            count += 1
            print("CAUGHT R17 SOURCE DRIFT: " + name)
        else:
            raise AssertionError("failed to catch original source change: " + name)
    assert count == len(edits) == 12
    print("PASS: R17 twelve synthetic source-drift guards caught")

def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    mod, core = [pathlib.Path(x) for x in argv[1:]]
    assert git(core, "rev-parse", "HEAD") == CORE
    git(mod, "merge-base", "--is-ancestor", MOD, "HEAD")
    for path, blob in BLOBS.items():
        root, rev = (mod, MOD) if path == HONOR else (core, CORE)
        assert git(root, "rev-parse", rev + ":" + path) == blob, path
    assert git(mod, "rev-parse", "HEAD:" + HONOR) == BLOBS[HONOR]
    sources = [(mod / HONOR).read_text()] + [(core / p).read_text() for p in
        (OBJECT_CPP, OBJECT_H, UNIT, PLAYER, HANDLER, MISC_CPP, MISC_H)]
    assert verify(sources)
    print("PASS: R17 eight original source blob pins, pre-GUID construct hook, failed DB load destruction, normal login registration order")
    mutants(sources)
    print("FINDING: Original Object value storage null at construction; MiscScript Player ctor hook precedes normal GUID allocation and DB-load path")
    print("LIMIT: no call to GetGUID on uninitialized Player, no real null dereference, no live callbacks/Worldserver/SQL/DBC/client")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError, ValueError, subprocess.CalledProcessError) as exc:
        print("FAIL: " + str(exc))
        sys.exit(1)
