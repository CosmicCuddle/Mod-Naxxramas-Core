#!/usr/bin/env python3
"""P13-R15 literal original Player/session reconnect transfer witness (test-only).

  python3 -I tests/test_p13_r15_reconnect_transfer_source.py . pinned-core

No real server, socket, WorldSession, account or DB; two dummy sessions share
a dummy Player, executing original core transfer, original Player/session setters,
and original module login/logout callbacks. Core guards are source-checked.
"""
from __future__ import annotations
import pathlib
import subprocess
import sys
import tempfile

MOD_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MODULE = "src/Systems/HonorOverflow.cpp"
HANDLER = "src/server/game/Handlers/CharacterHandler.cpp"
SESSION = "src/server/game/Server/WorldSession.cpp"
SESS_MGR = "src/server/game/Server/WorldSessionMgr.cpp"
PLAYER_H = "src/server/game/Entities/Player/Player.h"
BLOBS = {
    MODULE: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
    HANDLER: "d7123a9c503c3363ff2ea08b2d24eec7d07c5643",
    SESSION: "fc96398079b50984ed0b82183d713c666af6939b",
    SESS_MGR: "50598d3913404a6f74ec87fe1e0892d216a969b8",
    PLAYER_H: "5a29ac7b40ade7a11f1fcf36623dc7530ea39595",
}

def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def block(src: str, anchor: str) -> str:
    first = src.index(anchor)
    start = src.index("{", first)
    level = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            level += 1
        elif src[i] == "}":
            level -= 1
            if level == 0:
                return src[first:i + 1]
    raise AssertionError("unbalanced source body: " + anchor)

TRANSFER_START = "            sess->SetPlayer(nullptr);"
TRANSFER_CALL = "            HandlePlayerLoginToCharInWorld(p);"
TRANSFER_END = "            return;"
ORIGINAL_INLINE = "void SetSession(WorldSession* sess) { m_session = sess; }"

def check_contract(mod: str, handler: str, sess: str, manager: str, player: str):
    login = block(handler, "void WorldSession::HandlePlayerLoginOpcode(WorldPacket& recvData)")
    to_world = block(handler, "void WorldSession::HandlePlayerLoginToCharInWorld(Player* pCurrChar)")
    fresh_login = block(handler, "void WorldSession::HandlePlayerLoginFromDB(LoginQueryHolder const& holder)")
    offline = block(manager, "void WorldSessionMgr::UpdateSessions(uint32 const diff)")
    closed = block(sess, "bool WorldSession::HandleSocketClosed()")
    setter = block(sess, "void WorldSession::SetPlayer(Player* player)")
    mod_login = block(mod, "    void OnPlayerLogin(Player* player) override")
    mod_logout = block(mod, "    void OnPlayerLogout(Player* player) override")
    mod_store = block(mod, "    void StoreHonorSnapshot(Player* player)")
    assert ORIGINAL_INLINE in player, "Player::SetSession no longer simple rebind"

    must = [
        "FindOfflineSessionForCharacterGUID(playerGuid.GetCounter())",
        "sess->GetAccountId() != GetAccountId()",
        "FindOfflineSession(GetAccountId())",
        "p->GetGUID() != playerGuid",
        "!sWorld->getBoolConfig(CONFIG_ENABLE_LOGIN_AFTER_DC)",
        "!p->FindMap() || !p->IsInWorld() || sess->IsKicked()",
    ]
    for anchor in must:
        assert anchor in login, "reattach eligibility guard source drift: " + anchor
    a = login.index(TRANSFER_START)
    b = login.index(TRANSFER_CALL, a)
    c = login.index(TRANSFER_END, b)
    assert a < b < c, "reattach source order changed"
    sequence = login[a:c + len(TRANSFER_END)]
    assert "SetPlayer(p);" in sequence and "p->SetSession(this);" in sequence
    assert "delete p->PlayerTalkClass;" in sequence
    assert "p->PlayerTalkClass = new PlayerMenu(p->GetSession());" in sequence
    assert "sScriptMgr->OnPlayerLogin(" not in sequence, "new normal login hook in shortcut"
    assert "sScriptMgr->OnPlayerLogout(" not in sequence, "logout hook in shortcut"
    assert "sScriptMgr->OnPlayerLogin(" not in to_world, "reconnect helper now invokes normal login"
    assert "sScriptMgr->OnPlayerLogout(" not in to_world, "reconnect helper now invokes logout"
    assert "sScriptMgr->OnPlayerLogin(pCurrChar);" in fresh_login, "fresh database login event changed"
    assert "pSession->HandleSocketClosed()" in offline
    assert "_offlineSessions[pSession->GetAccountId()] = pSession;" in offline
    assert "!pSession->GetPlayer() || pSession->GetOfflineTime() + 60 < currTime || pSession->IsKicked()" in offline
    assert "GetPlayer() && !PlayerLogout()" in closed
    assert "GetPlayer()->IsInWorld()" in closed
    assert "_player = player;" in setter
    assert "if (_player)" in setter and "m_GUIDLow = _player->GetGUID().GetCounter();" in setter
    assert "StoreHonorSnapshot(player);" in mod_login
    assert "BattlegroundHonorSummaries.erase(" in mod_login
    assert "HonorSnapshots.erase(guid);" in mod_logout and "BattlegroundHonorSummaries.erase(guid);" in mod_logout
    assert "HonorSnapshots[player->GetGUID().GetCounter()] =" in mod_store
    return sequence, setter, mod_store, mod_login, mod_logout

def negative_guards(srcs):
    mod, handler, session, manager, player = srcs
    cases = [
        ("no detach old session", 1, "sess->SetPlayer(nullptr);", "/* old retains player */"),
        ("different player attached to new session", 1, "SetPlayer(p);", "SetPlayer(new Player(nullptr));"),
        ("session pointer not rebound", 1, "p->SetSession(this);", "p->SetSession(sess);"),
        ("unwanted fresh-login callback in reuse path", 1,
         "HandlePlayerLoginToCharInWorld(p);\n            return;",
         "HandlePlayerLoginToCharInWorld(p);\n            sScriptMgr->OnPlayerLogin(p);\n            return;"),
        ("unconditional reconnect config", 1,
         "!sWorld->getBoolConfig(CONFIG_ENABLE_LOGIN_AFTER_DC)", "false /* no config guard */"),
        ("no same-account offline check", 1, "sess->GetAccountId() != GetAccountId()", "false /* no account check */"),
        ("session low GUID reset to zero on detach", 2, "if (_player)\n        m_GUIDLow", "else\n        m_GUIDLow"),
        ("no module BG summary reset at normal login", 0,
         "BattlegroundHonorSummaries.erase(\n            player->GetGUID().GetCounter());",
         "/* summary erase on normal login removed */"),
    ]
    for name, index, original, changed in cases:
        assert original in srcs[index], "missing negative guard anchor: " + name
        mutated = list(srcs)
        mutated[index] = mutated[index].replace(original, changed, 1)
        try:
            check_contract(*mutated)
        except (AssertionError, ValueError):
            print("CAUGHT R15 SOURCE DRIFT: " + name)
        else:
            raise AssertionError("Source drift unexpectedly accepted: " + name)

PREFIX = r"""
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
using uint32 = std::uint32_t;
namespace {
constexpr int PLAYER_FIELD_TODAY_CONTRIBUTION = 1;
struct ObjectGuid {
    using LowType = uint32;
    uint32 id;
    uint32 GetCounter() const { return id; }
};
class WorldSession;
struct PlayerMenu {
    WorldSession* session;
    explicit PlayerMenu(WorldSession* p): session(p) {}
};
struct Player {
    WorldSession* m_session = nullptr;
    ObjectGuid guid {73};
    PlayerMenu* PlayerTalkClass = nullptr;
    uint32 honor = 77;
    uint32 today = 13;
    bool inWorld = true;
    ~Player() { delete PlayerTalkClass; }
    ObjectGuid GetGUID() const { return guid; }
    WorldSession* GetSession() const { return m_session; }
    uint32 GetHonorPoints() const { return honor; }
    uint32 GetUInt32Value(int) const { return today; }
    __PLAYER_SET_SESSION__
};
class WorldSession {
public:
    Player* _player = nullptr;
    uint32 m_GUIDLow = 0;
    int reconnectHelpers = 0;
    Player* GetPlayer() const { return _player; }
    uint32 GetGuidLow() const { return m_GUIDLow; }
    void SetPlayer(Player* player);
    void HandlePlayerLoginToCharInWorld(Player* p) {
        ++reconnectHelpers;
        if (p != _player) throw std::runtime_error("reconnect helper received different Player");
    }
    void TransferExisting(WorldSession* sess, Player* p) {
__TRANSFER__
    }
};
struct HonorSnapshot {
    uint32 Honor = 0;
    uint32 TodayContribution = 0;
};
struct BattlegroundHonorSummary {
    uint64_t ExcessHonor = 0;
    uint64_t RequestedCopper = 0;
    uint64_t AwardedCopper = 0;
};
std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;
std::unordered_map<ObjectGuid::LowType, BattlegroundHonorSummary> BattlegroundHonorSummaries;
void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
struct PlayerScript {
    virtual ~PlayerScript() = default;
    virtual void OnPlayerLogin(Player*) {}
    virtual void OnPlayerLogout(Player*) {}
};
void StoreHonorSnapshot(Player* player);\nclass HonorHooks : public PlayerScript {
public:
__MODULE_LOGIN__
__MODULE_LOGOUT__
};
}
"""
SUFFIX = r"""
int main() {
    try {
        Player p;
        WorldSession oldSession, newSession;
        oldSession.SetPlayer(&p);
        p.SetSession(&oldSession);
        p.PlayerTalkClass = new PlayerMenu(&oldSession);
        HonorHooks honor;
        honor.OnPlayerLogin(&p); // Actual module login hook body on initial normal login (dummy)
        auto id = p.GetGUID().GetCounter();
        require(HonorSnapshots.at(id).TodayContribution == 13, "ordinary login snapshot not set");
        BattlegroundHonorSummaries[id] = {4,40,40};

        p.today = 23; // dummy accumulated contribution between updates
        auto* originalPlayer = &p;
        newSession.TransferExisting(&oldSession, &p);
        require(&p == originalPlayer, "object identity changed");
        require(oldSession.GetPlayer() == nullptr, "old WorldSession did not detach");
        require(oldSession.GetGuidLow() == id, "old WorldSession GUID unexpectedly cleared");
        require(newSession.GetPlayer() == originalPlayer, "new WorldSession lost same Player");
        require(newSession.GetGuidLow() == id, "new WorldSession GUID differs");
        require(p.GetSession() == &newSession, "Player session still points to old session");
        require(p.PlayerTalkClass && p.PlayerTalkClass->session == &newSession,
                "PlayerMenu still bound to old session");
        require(newSession.reconnectHelpers == 1, "original reconnect helper not dispatched");
        require(HonorSnapshots.at(id).TodayContribution == 13,
                "new network session improperly reset previous honor snapshot");
        require(BattlegroundHonorSummaries.at(id).AwardedCopper == 40,
                "new network session improperly cleared BG summary");
        std::cout << "PASS: original same Player identity moved to new WorldSession; old low GUID retained\n";
        std::cout << "PASS: module snapshot/BG summary unchanged WITHOUT normal login callback\n";

        honor.OnPlayerLogout(&p); // Explicit dummy normal logout hook, NOT an auto reconnect hook
        require(HonorSnapshots.empty() && BattlegroundHonorSummaries.empty(),
                "original module normal logout did not erase maps");
        honor.OnPlayerLogin(&p);
        require(HonorSnapshots.at(id).TodayContribution == 23, "explicit normal login not resnapshotted");
        require(BattlegroundHonorSummaries.empty(), "explicit login summary not cleared");
        std::cout << "PASS: original module login/logout callback bodies work when explicitly called\n";
        std::cout << "LIMIT: synthetic transfer assumes real guards passed; no socket, database, full handler, Worldserver or live race\n";
        return 0;
    } catch (std::exception const& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
"""

def compile_fixture(parts):
    sequence, setter, store, on_login, on_logout = parts
    # Insert original source directly; dummy object declarations are NOT original core.
    text = (PREFIX.replace("__PLAYER_SET_SESSION__", ORIGINAL_INLINE)
            .replace("__TRANSFER__", sequence)
            .replace("__MODULE_LOGIN__", on_login)
            .replace("__MODULE_LOGOUT__", on_logout)
            + "\n" + setter + "\n" + store + "\n" + SUFFIX)
    with tempfile.TemporaryDirectory(prefix="p13_r15_") as tmp:
        root = pathlib.Path(tmp)
        source = root / "reconnect.cpp"
        source.write_text(text)
        for name, standard, flags in [
            ("c++17", "c++17", []),
            ("c++20", "c++20", []),
            ("c++20-ubsan", "c++20", ["-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all"]),
        ]:
            out = root / name
            subprocess.run(["g++", "-std=" + standard, "-Wall", "-Wextra",
                            "-Werror", "-pedantic", *flags, str(source), "-o", str(out)], check=True)
            result = subprocess.check_output([str(out)], text=True)
            assert result.count("PASS:") == 3 and "LIMIT:" in result, result
            print("PASS: R15 " + name + " literal original transfer/setters/module callbacks")

def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    mod, core = map(pathlib.Path, argv[1:])
    assert git(core, "rev-parse", "HEAD") == CORE_SHA, "core checkout not pinned"
    git(mod, "merge-base", "--is-ancestor", MOD_SHA, "HEAD")
    assert git(mod, "rev-parse", MOD_SHA + ":" + MODULE) == BLOBS[MODULE]
    assert git(mod, "rev-parse", "HEAD:" + MODULE) == BLOBS[MODULE]
    for file in (HANDLER, SESSION, SESS_MGR, PLAYER_H):
        assert git(core, "rev-parse", "HEAD:" + file) == BLOBS[file], "source blob drift: " + file
    contents = [(mod / MODULE).read_text()] + [(core / p).read_text()
              for p in (HANDLER, SESSION, SESS_MGR, PLAYER_H)]
    parts = check_contract(*contents)
    print("PASS: R15 exact five pinned blobs and real offline/reattach/normal-login callbacks")
    negative_guards(contents)
    compile_fixture(parts)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, AssertionError, RuntimeError, subprocess.CalledProcessError) as err:
        print("FAIL: " + str(err))
        sys.exit(1)
