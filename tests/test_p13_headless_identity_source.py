#!/usr/bin/env python3
"""P13-R5: pinned core IsHeadless vs config-masked Playerbot identity.

Compiles the actual unmodified WorldSession::IsHeadless() inline method,
pinned Playerbots getter and two helper functions, and module HonorOverflow
IsPlayerBot under C++17 and C++20 strict UBSan.

The disposable session constructor ONLY models the pinned core expression
_headless(!sock); original core constructor and bot session factory are
independently checked as original source anchors. No actual Worldserver,
Playerbot/WorldSocket session, money or owner configuration is run.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "pinned-core"
PB = ROOT / "pinned-playerbots"
CORE_H = CORE / "src/server/game/Server/WorldSession.h"
CORE_CPP = CORE / "src/server/game/Server/WorldSession.cpp"
PB_MGR = PB / "src/Bot/PlayerbotMgr.cpp"
PB_AI = PB / "src/Bot/PlayerbotAI.cpp"
PB_SCRIPT = PB / "src/Script/Playerbots.cpp"
MODULE = ROOT / "src/Systems/HonorOverflow.cpp"

CORE_PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
PB_PIN = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"


def extract(src: str, signature: str) -> str:
    if src.count(signature) != 1:
        raise AssertionError(f"Expected precisely one source signature: {signature!r}")
    start = src.index(signature)
    brace = src.find("{", start)
    if brace == -1:
        raise AssertionError("Missing function opening brace")
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(f"Unclosed function {signature}")


CPP = r"""
#include <cstdint>
#include <iostream>
#include <memory>
#include <unordered_map>
using uint32 = std::uint32_t;
struct WorldSession {
    // Disposable model of pinned _headless(!sock), NOT the production ctor.
    explicit WorldSession(bool hasSocket) : _headless(!hasSocket) {}
    __HEADLESS__
private:
    bool const _headless;
};
struct ObjectGuid {
    uint32 value = 7;
    bool operator==(ObjectGuid const& rhs) const { return value == rhs.value; }
};
namespace std {
template<> struct hash<ObjectGuid> {
    size_t operator()(ObjectGuid const& guid) const {
        return std::hash<uint32>{}(guid.value);
    }
};
}
struct Player {
    WorldSession* session = nullptr;
    ObjectGuid guid{};
    WorldSession* GetSession() const { return session; }
    ObjectGuid GetGUID() const { return guid; }
};
struct PlayerbotAIBase {
    virtual ~PlayerbotAIBase() = default;
    virtual bool IsBotAI() { return false; }
};
struct PlayerbotAI : PlayerbotAIBase {
    Player* master = nullptr;
    bool IsBotAI() override { return true; }
    Player* GetMaster() const { return master; }
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
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1

__GET_AI__
__IS_REAL__
__IS_SELF__
__IS_MOD_BOT__

void Scenario(char const* name, bool hasSocket, bool enabled,
              bool attachedAI, bool selfBot, bool nullPlayer) {
    manager._playerbotsAIMap.clear();
    sPlayerbotAIConfig.Enabled = enabled;
    WorldSession session(hasSocket);
    Player character;
    Player externalMaster;
    character.session = &session;
    Player* player = nullPlayer ? nullptr : &character;
    PlayerbotAI ai;
    ai.master = selfBot ? &character : &externalMaster;
    if (player && attachedAI)
        manager._playerbotsAIMap.emplace(player->GetGUID(), &ai);
    bool headless = player && player->GetSession() &&
                    player->GetSession()->IsHeadless();
    bool real = IsRealPlayer(player);
    bool self = IsSelfBot(player);
    bool moduleBot = IsPlayerBot(player);
    // This is the bot exclusion only. HonorOverflow still has other gates.
    bool sourceBotExclusionAllows = player && !IsPlayerBot(player);
    // Hypothetical safety filter ONLY; not a proposed or approved code change.
    bool hypotheticalHeadlessFenceAllows = player && !headless && !IsPlayerBot(player);
    std::cout << name << " " << headless << " " << real << " " << self
              << " " << moduleBot << " " << sourceBotExclusionAllows
              << " " << hypotheticalHeadlessFenceAllows << " "
              << manager._playerbotsAIMap.size() << "\n";
}
int main() {
    Scenario("normal_human_enabled", true, true, false, false, false);
    Scenario("normal_human_disabled", true, false, false, false, false);
    Scenario("selfbot_enabled", true, true, true, true, false);
    Scenario("selfbot_masked", true, false, true, true, false);
    Scenario("headless_bot_enabled", false, true, true, false, false);
    Scenario("headless_bot_masked", false, false, true, false, false);
    Scenario("headless_nobot_enabled", false, true, false, false, false);
    Scenario("headless_nobot_disabled", false, false, false, false, false);
    Scenario("null_enabled", true, true, false, false, true);
    Scenario("null_disabled", false, false, false, false, true);
}
"""

# Columns: IsHeadless, IsRealPlayer, IsSelfBot, IsPlayerBot,
#          original !IsPlayerBot exclusion, hypothetical !headless && !bot,
#          retained-map count. Neither represents actual full reward gates.
EXPECTED = {
    "normal_human_enabled": (0, 1, 0, 0, 1, 1, 0),
    "normal_human_disabled": (0, 1, 0, 0, 1, 1, 0),
    "selfbot_enabled": (0, 0, 1, 1, 0, 0, 1),
    "selfbot_masked": (0, 1, 0, 0, 1, 1, 1),
    "headless_bot_enabled": (1, 0, 0, 1, 0, 0, 1),
    "headless_bot_masked": (1, 1, 0, 0, 1, 0, 1),
    "headless_nobot_enabled": (1, 1, 0, 0, 1, 0, 0),
    "headless_nobot_disabled": (1, 1, 0, 0, 1, 0, 0),
    "null_enabled": (0, 0, 0, 0, 0, 0, 0),
    "null_disabled": (0, 0, 0, 0, 0, 0, 0),
}


def main() -> None:
    head = CORE_H.read_text(encoding="utf-8")
    core = CORE_CPP.read_text(encoding="utf-8")
    mgr = PB_MGR.read_text(encoding="utf-8")
    ai = PB_AI.read_text(encoding="utf-8")
    script = PB_SCRIPT.read_text(encoding="utf-8")
    module = MODULE.read_text(encoding="utf-8")

    getter = extract(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
    isreal = extract(ai, "bool IsRealPlayer(Player* player)")
    isself = extract(ai, "bool IsSelfBot(Player* player)")
    ismodulebot = extract(module, "    bool IsPlayerBot(Player* player)")
    isheadless = extract(head, "[[nodiscard]] bool IsHeadless() const")
    if not re.search(r"bool const _headless\s*;", head):
        raise AssertionError("Pinned core headless field not immutable")
    if "_headless(!sock)" not in core:
        raise AssertionError("Pinned core WorldSession socket constructor changed")
    if "return _headless;" not in isheadless:
        raise AssertionError("Pinned core IsHeadless no longer uses immutable field")
    if not re.search(
        r'WorldSession\(\s*accountId,\s*"",\s*0x0,\s*nullptr,',
        mgr,
    ):
        raise AssertionError("Pinned PlayerbotHolder no longer creates no-socket bot")
    onlogin = extract(script, "void OnPlayerLogin(Player* player) override")
    if "if (!player->GetSession()->IsHeadless())" not in onlogin:
        raise AssertionError("Pinned Playerbots login headless distinction changed")
    selfcommand = extract(mgr, 'if (!strcmp(cmd, "self"))')
    if "PlayerbotsMgr::instance().AddPlayerbotData(master, true);" not in selfcommand or \
       "GET_PLAYERBOT_AI(master)->SetMaster(master);" not in selfcommand:
        raise AssertionError("Pinned SelfBot attaches to the same master Player")
    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in getter:
        raise AssertionError("Pinned AI lookup mask changed")
    if "return player && !GET_PLAYERBOT_AI(player);" not in isreal:
        raise AssertionError("Pinned real player helper changed")
    if "return botAI && botAI->GetMaster() == player;" not in isself:
        raise AssertionError("Pinned SelfBot helper changed")
    if "return GET_PLAYERBOT_AI(player) != nullptr;" not in ismodulebot:
        raise AssertionError("Pinned HonorOverflow IsPlayerBot changed")

    print("PINNED CORE: IsHeadless reads immutable !sock-at-construction")
    print("PINNED PLAYERBOTS: headless bot WorldSession created with null socket")
    print("PINNED PLAYERBOTS: SelfBot attaches AI to client-backed master/player")
    code = (CPP.replace("__HEADLESS__", isheadless)
            .replace("__GET_AI__", getter)
            .replace("__IS_REAL__", isreal)
            .replace("__IS_SELF__", isself)
            .replace("__IS_MOD_BOT__", ismodulebot))
    with tempfile.TemporaryDirectory(prefix="p13-headless-core-") as temp:
        for standard in ("c++17", "c++20"):
            path = pathlib.Path(temp) / (standard + ".cpp")
            binary = pathlib.Path(temp) / standard
            path.write_text(code, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(path), "-o", str(binary)],
                check=True,
            )
            actual: dict[str, tuple[int, ...]] = {}
            output = subprocess.check_output([str(binary)], text=True)
            for line in output.splitlines():
                m = re.fullmatch(
                    r"([a-z_]+) ([01]) ([01]) ([01]) ([01]) ([01]) ([01]) ([01])",
                    line,
                )
                if not m:
                    raise AssertionError(f"Unexpected fixture output {line!r}")
                name, *nums = m.groups()
                if name in actual:
                    raise AssertionError(f"Duplicate fixture case {name}")
                actual[name] = tuple(map(int, nums))
            if actual != EXPECTED:
                raise AssertionError(f"{standard} unexpected source outcome {actual}")
            print(f"PASS: {standard} {len(actual)} literal core/session/helper combinations")
            print("POSITIVE: masked headless bot excluded by hypothetical headless fence")
            print("EXPECTED CONDITIONAL RED: masked client-backed SelfBot still eligible")
            print("CONTROL: human with Playerbots disabled stays eligible, null excluded")

    print(f"CORE PIN {CORE_PIN}, PLAYERBOTS PIN {PB_PIN}")
    print("LIMIT: headless means no socket at session creation, NOT positive bot identity")
    print("LIMIT: hypothetical filter never implemented or approved")
    print("NO LIVE CLAIM: no Worldserver, actual honor award, real reload or owner data")


if __name__ == "__main__":
    main()
