#!/usr/bin/env python3
"""P13-R3 source-only Playerbots logout path under config-masked getter.

Execute pinned literal GetPlayerbotAI and PlayerbotHolder::LogoutAllBots
with a call-counting test-only LogoutPlayerBot substitute. The test does
NOT invoke the real logout helper or destruct a WorldSession; its real
getter-based early return is separately checked against pinned source.
All bots, player state, and AI objects are disposable mock fixtures.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PB = ROOT / "pinned-playerbots"
MGR = PB / "src/Bot/PlayerbotMgr.cpp"
SCRIPT = PB / "src/Script/Playerbots.cpp"
RANDOM = PB / "src/Bot/RandomPlayerbotMgr.cpp"


def function(src: str, signature: str) -> str:
    if src.count(signature) != 1:
        raise AssertionError(f"Expected unique source signature: {signature}")
    start = src.index(signature)
    opening = src.find("{", start)
    if opening == -1:
        raise AssertionError(f"No body found: {signature}")
    depth = 0
    for i in range(opening, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if not depth:
                return src[start:i + 1]
    raise AssertionError(f"Unbalanced original source: {signature}")


CPP = r"""
#include <cstdint>
#include <iostream>
#include <string>
#include <unordered_map>
using uint32 = std::uint32_t;
struct ObjectGuid {
    uint32 id = 0;
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
    bool self = false;
    ObjectGuid GetGUID() const { return guid; }
};
struct PlayerbotAIBase {
    virtual ~PlayerbotAIBase() = default;
    virtual bool IsBotAI() { return false; }
};
struct PlayerbotAI : PlayerbotAIBase {
    bool IsBotAI() override { return true; }
};
struct Config { bool Enabled = true; };
Config sPlayerbotAIConfig;
struct PlayerbotsMgr {
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    PlayerbotAI* GetPlayerbotAI(Player*);
};
PlayerbotsMgr manager;
PlayerbotsMgr* sPlayerbotsMgr = &manager;
#define GET_PLAYERBOT_AI(player) sPlayerbotsMgr->GetPlayerbotAI(player)
bool IsSelfBot(Player* player) { return player->self; }
using PlayerBotMap = std::unordered_map<ObjectGuid, Player*>;
struct PlayerbotHolder {
    PlayerBotMap playerBots;
    int calls = 0;
    void LogoutAllBots();
    void LogoutPlayerBot(ObjectGuid guid) {
        // Test-only call counter / holder removal, NOT the real logout code.
        ++calls;
        playerBots.erase(guid);
    }
};

__GET_AI__
__ALL_LOGOUT__

void Scenario(char const* name, bool enabled, bool aAttached,
              bool bAttached, bool aSelf, bool bSelf,
              bool aPresent, bool bPresent) {
    manager._playerbotsAIMap.clear();
    sPlayerbotAIConfig.Enabled = enabled;
    Player a{{12}, aSelf};
    Player b{{13}, bSelf};
    PlayerbotAI aiA, aiB;
    if (aAttached)
        manager._playerbotsAIMap.emplace(a.GetGUID(), &aiA);
    if (bAttached)
        manager._playerbotsAIMap.emplace(b.GetGUID(), &aiB);
    PlayerbotHolder holder;
    if (aPresent) holder.playerBots.emplace(a.GetGUID(), &a);
    if (bPresent) holder.playerBots.emplace(b.GetGUID(), &b);
    int before = static_cast<int>(holder.playerBots.size());
    holder.LogoutAllBots();
    std::cout << name << " " << before << " " << holder.calls << " "
              << holder.playerBots.size() << " "
              << manager._playerbotsAIMap.size() << "\n";
}
int main() {
    Scenario("enabled_single", true, true, false, false, false, true, false);
    Scenario("disabled_single", false, true, false, false, false, true, false);
    Scenario("enabled_two", true, true, true, false, false, true, true);
    Scenario("disabled_two", false, true, true, false, false, true, true);
    Scenario("enabled_selfbot", true, true, true, true, false, true, true);
    Scenario("disabled_selfbot", false, true, true, true, false, true, true);
    Scenario("enabled_missing_ai", true, false, false, false, false, true, false);
    Scenario("enabled_empty", true, false, false, false, false, false, false);
    Scenario("disabled_empty", false, false, false, false, false, false, false);
}
"""

EXPECTED = {
    "enabled_single": (1, 1, 0, 1),
    "disabled_single": (1, 0, 1, 1),
    "enabled_two": (2, 2, 0, 2),
    "disabled_two": (2, 0, 2, 2),
    "enabled_selfbot": (2, 1, 1, 2),
    "disabled_selfbot": (2, 0, 2, 2),
    "enabled_missing_ai": (1, 0, 1, 0),
    "enabled_empty": (0, 0, 0, 0),
    "disabled_empty": (0, 0, 0, 0),
}


def main() -> None:
    mgr = MGR.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    rnd = RANDOM.read_text(encoding="utf-8")

    getter = function(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
    all_logout = function(mgr, "void PlayerbotHolder::LogoutAllBots()")
    logout = function(mgr, "void PlayerbotHolder::LogoutPlayerBot(ObjectGuid guid)")
    disable = function(mgr, "void PlayerbotHolder::DisablePlayerBot(ObjectGuid guid)")
    before_logout = function(script, "void OnPlayerBeforeLogout(Player* player) override")
    random_logout = function(rnd, "void RandomPlayerbotMgr::OnPlayerLogout(Player* player)")
    shutdown = function(script, "void OnShutdown() override")
    update = function(script, "void OnPlayerAfterUpdate(Player* player, uint32 diff) override")

    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in getter:
        raise AssertionError("Pinned getter masking changed")
    if "PlayerBotMap bots = playerBots;" not in all_logout or \
            "if (!botAI || IsSelfBot(bot))" not in all_logout:
        raise AssertionError("Pinned bulk logout bot-filtering changed")
    for label, fn in (("LogoutPlayerBot", logout), ("DisablePlayerBot", disable)):
        if not re.search(
            r"PlayerbotAI\*\s+botAI\s*=\s*GET_PLAYERBOT_AI\(bot\);"
            r"\s*if \(!botAI\)\s*(?:\{\s*)?return;",
            fn,
        ):
            raise AssertionError(f"{label} no longer skips config-hidden bots")
    if "sRandomPlayerbotMgr.LogoutAllBots();" not in shutdown:
        raise AssertionError("Pinned shutdown no longer goes through bulk logout")
    if "sRandomPlayerbotMgr.OnPlayerLogout(player);" not in before_logout:
        raise AssertionError("Pinned owner logout path changed")
    if "DisablePlayerBot(player->GetGUID());" not in random_logout:
        raise AssertionError("Pinned random bot logout path changed")
    if "PlayerbotsMgr::instance().GetPlayerbotAI(player)" not in update:
        raise AssertionError("Pinned player AI update lookup changed")

    code = CPP.replace("__GET_AI__", getter).replace("__ALL_LOGOUT__", all_logout)
    with tempfile.TemporaryDirectory(prefix="p13-logout-source-") as folder:
        for standard in ("c++17", "c++20"):
            cpp = pathlib.Path(folder) / (standard + ".cpp")
            exe = pathlib.Path(folder) / standard
            cpp.write_text(code, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(cpp), "-o", str(exe)],
                check=True,
            )
            actual = {}
            for line in subprocess.check_output([str(exe)], text=True).splitlines():
                parsed = re.fullmatch(r"([a-z_]+) (\d+) (\d+) (\d+) (\d+)", line)
                if not parsed:
                    raise AssertionError(f"Unexpected output {line!r}")
                label, *values = parsed.groups()
                if label in actual:
                    raise AssertionError(f"Duplicate case {label}")
                actual[label] = tuple(map(int, values))
            if actual != EXPECTED:
                raise AssertionError(f"{standard} fixture drift: {actual} != {EXPECTED}")
            print(f"PASS: {standard} {len(actual)} actual bulk-logout source scenarios")
            print("EXPECTED CONDITIONAL RED: config-masked attached bots skipped in bulk logout")
            print("POSITIVE: enabled normal bots reach logout call; enabled SelfBot excluded")
    print("SOURCE CONTRACT: per-bot logout, disable, owner logout, shutdown and update checked")
    print("LIMIT: mock LogoutPlayerBot counts calls; no real session, player deletion or server")
    print("No gameplay proof, memory incident, owner DB, settings change or production fix")


if __name__ == "__main__":
    main()
