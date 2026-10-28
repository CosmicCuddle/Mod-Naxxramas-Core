#!/usr/bin/env python3
"""P13-R2: pinned Playerbots config-masked destruction cleanup source witness.

Executes literal GetPlayerbotAI, GetPlayerbotMgr, RemovePlayerBotData,
and PlayerbotsMiscScript::OnDestructPlayer against disposable C++ objects.
Mock object destructors implement only the source-verified map-erasure side
effect of the real destructors. A missing erase under masking is an
EXPECTED CONDITIONAL RED, not an observed server leak or crash.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PB = ROOT / "pinned-playerbots"
MGR = PB / "src/Bot/PlayerbotMgr.cpp"
AI = PB / "src/Bot/PlayerbotAI.cpp"
SCRIPT = PB / "src/Script/Playerbots.cpp"


def extract(src: str, signature: str) -> str:
    if src.count(signature) != 1:
        raise AssertionError(f"Expected exactly one source signature {signature}")
    start = src.index(signature)
    begin = src.find("{", start)
    if begin == -1:
        raise AssertionError(f"Body missing for {signature}")
    depth = 0
    for i in range(begin, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError("No matching closing brace")


CPP = r"""
#include <cstdint>
#include <iostream>
#include <string>
#include <unordered_map>
using uint32 = std::uint32_t;
struct ObjectGuid {
    uint32 id = 11;
    bool operator==(ObjectGuid const& other) const { return id == other.id; }
};
namespace std {
    template<> struct hash<ObjectGuid> {
        std::size_t operator()(ObjectGuid const& guid) const {
            return std::hash<uint32>{}(guid.id);
        }
    };
}
struct Player {
    ObjectGuid guid{};
    ObjectGuid GetGUID() const { return guid; }
};
struct PlayerbotAIBase {
    virtual ~PlayerbotAIBase() = default;
    virtual bool IsBotAI() { return false; }
};
struct PlayerbotAI;
struct PlayerbotMgr;
struct Config {
    bool Enabled = true;
};
Config sPlayerbotAIConfig;
struct PlayerbotsMgr {
    static PlayerbotsMgr& instance();
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsMgrMap;
    void RemovePlayerBotData(ObjectGuid const&, bool);
    PlayerbotAI* GetPlayerbotAI(Player*);
    PlayerbotMgr* GetPlayerbotMgr(Player*);
};
PlayerbotsMgr gManager;
PlayerbotsMgr& PlayerbotsMgr::instance() { return gManager; }
PlayerbotsMgr* sPlayerbotsMgr = &gManager;
struct PlayerbotAI : PlayerbotAIBase {
    Player* bot;
    static int deleted;
    explicit PlayerbotAI(Player* p) : bot(p) {}
    bool IsBotAI() override { return true; }
    ~PlayerbotAI() override;
};
struct PlayerbotMgr : PlayerbotAIBase {
    Player* master;
    static int deleted;
    explicit PlayerbotMgr(Player* p) : master(p) {}
    ~PlayerbotMgr() override;
};
int PlayerbotAI::deleted = 0;
int PlayerbotMgr::deleted = 0;

// Exact unmodified pinned source:
__REMOVE__
__GET_AI__
__GET_MGR__

// Stub destructors ONLY mirror the real pinned destructors' map-removal
// calls; the production destructor bodies have additional dependencies.
PlayerbotAI::~PlayerbotAI() {
    if (bot)
        PlayerbotsMgr::instance().RemovePlayerBotData(bot->GetGUID(), true);
    ++deleted;
}
PlayerbotMgr::~PlayerbotMgr() {
    if (master)
        PlayerbotsMgr::instance().RemovePlayerBotData(master->GetGUID(), false);
    ++deleted;
}
#define GET_PLAYERBOT_MGR(player) sPlayerbotsMgr->GetPlayerbotMgr(player)
struct MockMiscScript {
    __ON_DESTRUCT__
};

void Scenario(char const* name, bool haveAI, bool haveMgr, bool enabled,
              bool unmaskBeforeDestruct) {
    gManager._playerbotsAIMap.clear();
    gManager._playerbotsMgrMap.clear();
    PlayerbotAI::deleted = 0;
    PlayerbotMgr::deleted = 0;
    sPlayerbotAIConfig.Enabled = enabled;
    Player oldPlayer;
    Player newPlayer;
    PlayerbotAI* ai = haveAI ? new PlayerbotAI(&oldPlayer) : nullptr;
    PlayerbotMgr* mgr = haveMgr ? new PlayerbotMgr(&oldPlayer) : nullptr;
    if (ai)
        gManager._playerbotsAIMap.emplace(oldPlayer.GetGUID(), ai);
    if (mgr)
        gManager._playerbotsMgrMap.emplace(oldPlayer.GetGUID(), mgr);

    // The same GUID but DIFFERENT object illustrates possible stale binding.
    // No new player is actually logged in and no stale pointer is dereferenced.
    if (unmaskBeforeDestruct)
        sPlayerbotAIConfig.Enabled = true;
    MockMiscScript script;
    script.OnDestructPlayer(&oldPlayer);
    int aiRows = static_cast<int>(gManager._playerbotsAIMap.size());
    int mgrRows = static_cast<int>(gManager._playerbotsMgrMap.size());
    int deletedAI = PlayerbotAI::deleted;
    int deletedMgr = PlayerbotMgr::deleted;

    sPlayerbotAIConfig.Enabled = true;
    bool stale = (ai && gManager.GetPlayerbotAI(&newPlayer) == ai) ||
                 (mgr && gManager.GetPlayerbotMgr(&newPlayer) == mgr);
    std::cout << name << " " << aiRows << " " << mgrRows << " "
              << deletedAI << " " << deletedMgr << " " << stale << "\n";

    // Fixture-only disposal: no real player is destroyed or owner touched.
    if (aiRows && ai) delete ai;
    if (mgrRows && mgr) delete mgr;
    if (!gManager._playerbotsAIMap.empty() || !gManager._playerbotsMgrMap.empty())
        throw "Fixture map cleanup failed";
}
int main() {
    Scenario("enabled_both_cleaned", true, true, true, false);
    Scenario("disabled_both_skipped", true, true, false, false);
    Scenario("disabled_empty", false, false, false, false);
    Scenario("enabled_ai_cleaned", true, false, true, false);
    Scenario("enabled_mgr_cleaned", false, true, true, false);
    Scenario("disabled_ai_skipped", true, false, false, false);
    Scenario("disabled_mgr_skipped", false, true, false, false);
    Scenario("disabled_then_unmasked", true, true, false, true);
    sPlayerbotAIConfig.Enabled = false;
    MockMiscScript script;
    script.OnDestructPlayer(nullptr);
    std::cout << "null_player 0 0 0 0 0\n";
}
"""

EXPECTED = {
    "enabled_both_cleaned": (0, 0, 1, 1, 0),
    "disabled_both_skipped": (1, 1, 0, 0, 1),
    "disabled_empty": (0, 0, 0, 0, 0),
    "enabled_ai_cleaned": (0, 0, 1, 0, 0),
    "enabled_mgr_cleaned": (0, 0, 0, 1, 0),
    "disabled_ai_skipped": (1, 0, 0, 0, 1),
    "disabled_mgr_skipped": (0, 1, 0, 0, 1),
    "disabled_then_unmasked": (0, 0, 1, 1, 0),
    "null_player": (0, 0, 0, 0, 0),
}


def main() -> None:
    mgr = MGR.read_text(encoding="utf-8")
    ai = AI.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    get_ai = extract(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
    get_mgr = extract(mgr, "PlayerbotMgr* PlayerbotsMgr::GetPlayerbotMgr(Player* player)")
    remove = extract(mgr, "void PlayerbotsMgr::RemovePlayerBotData(ObjectGuid const& guid, bool is_AI)")
    on_destruct = extract(script, "void OnDestructPlayer(Player* player) override")
    ai_destruct = extract(ai, "PlayerbotAI::~PlayerbotAI()")
    mgr_destruct = extract(mgr, "PlayerbotMgr::~PlayerbotMgr()")

    for getter in (get_ai, get_mgr):
        if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in getter:
            raise AssertionError("Enabled mask differs from pinned source")
    if "MISCHOOK_ON_DESTRUCT_PLAYER" not in script or \
            "PlayerbotsMiscScript : public MiscScript" not in script:
        raise AssertionError("Pinned player destruction callback registration changed")
    if "PlayerbotsMgr::instance().GetPlayerbotAI(player)" not in on_destruct or \
            "GET_PLAYERBOT_MGR(player)" not in on_destruct:
        raise AssertionError("Destruction handler now uses a different lookup")
    if on_destruct.count("delete botAI;") != 1 or \
            on_destruct.count("delete playerbotMgr;") != 1:
        raise AssertionError("Destruction handler cleanup behavior changed")
    if "RemovePlayerBotData(bot->GetGUID(), true)" not in ai_destruct or \
            "RemovePlayerBotData(master->GetGUID(), false)" not in mgr_destruct:
        raise AssertionError("Production destructor map cleanup is not source-matched")
    if "_playerbotsAIMap.erase(itr)" not in remove or \
            "_playerbotsMgrMap.erase(itr)" not in remove:
        raise AssertionError("Pinned RemovePlayerBotData implementation changed")

    compiled = (CPP.replace("__REMOVE__", remove)
                .replace("__GET_AI__", get_ai)
                .replace("__GET_MGR__", get_mgr)
                .replace("__ON_DESTRUCT__",
                         on_destruct.replace(" override", "", 1)))
    with tempfile.TemporaryDirectory(prefix="p13-masked-destruct-") as directory:
        for standard in ("c++17", "c++20"):
            file = pathlib.Path(directory) / f"destruct-{standard}.cpp"
            exe = pathlib.Path(directory) / f"destruct-{standard}"
            file.write_text(compiled, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(file), "-o", str(exe)],
                check=True,
            )
            rows = {}
            for line in subprocess.check_output([str(exe)], text=True).splitlines():
                m = re.fullmatch(r"([a-z_]+) ([01]) ([01]) ([01]) ([01]) ([01])", line)
                if m is None:
                    raise AssertionError(f"Unexpected source harness output {line!r}")
                key, *value = m.groups()
                if key in rows:
                    raise AssertionError(f"Duplicate case {key}")
                rows[key] = tuple(map(int, value))
            if rows != EXPECTED:
                raise AssertionError(f"{standard} cleanup model mismatch: {rows}")
            print(f"PASS: {standard}, {len(rows)} pinned getter/destruct source scenarios")
            print("EXPECTED CONDITIONAL RED: disabled GetPlayerbotAI/GetPlayerbotMgr "
                  "skip the registered OnDestructPlayer deletion path")
            print("POSITIVE: enabled callbacks erase both map records")
    print("NO LIVE CLAIM: other lifecycle cleanup and actual reload timing UNKNOWN")
    print("No owner data, no gameplay, no external code modification")


if __name__ == "__main__":
    main()
