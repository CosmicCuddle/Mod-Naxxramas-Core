#!/usr/bin/env python3
"""P13-R6: execute pinned RandomBot/AddClass fallback membership source.

C++20 source-only fixture. No owner account, database, or Worldserver accessed.
Original functions are extracted unchanged; in-memory CharacterCache and
IsAccountType stubs model dependency return values. Membership may persist
under config masking, but it is neither exhaustive nor positive proof of AI.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PB = ROOT / "pinned-playerbots"
MGR = PB / "src/Bot/PlayerbotMgr.cpp"
RANDOM = PB / "src/Bot/RandomPlayerbotMgr.cpp"
AI = PB / "src/Bot/PlayerbotAI.cpp"
CONFIG = PB / "src/PlayerbotAIConfig.cpp"
MODULE = ROOT / "src/Systems/HonorOverflow.cpp"
PIN = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"


def extract(text: str, signature: str) -> str:
    if text.count(signature) != 1:
        raise AssertionError(f"expected unique pinned signature {signature!r}")
    start = text.index(signature)
    opening = text.find("{", start)
    if opening == -1:
        raise AssertionError(f"missing opening brace for {signature}")
    depth = 0
    for i in range(opening, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"unterminated source function {signature}")


CPP = r"""
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using namespace std;
enum class HighGuid { Player };
constexpr uint8 CLASS_WARRIOR = 1;
constexpr uint8 CLASS_DRUID = 11;
struct ObjectGuid {
    using LowType = uint32;
    LowType id = 0;
    template<HighGuid H> static ObjectGuid Create(LowType n) { return {n}; }
    LowType GetCounter() const { return id; }
    bool operator==(ObjectGuid const& rhs) const { return id == rhs.id; }
};
namespace std {
template<> struct hash<ObjectGuid> {
    size_t operator()(ObjectGuid const& g) const { return hash<uint32>{}(g.id); }
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
struct PlayerbotAI : PlayerbotAIBase {
    Player* master = nullptr;
    bool IsBotAI() override { return true; }
    Player* GetMaster() { return master; }
};
struct PlayerbotAIConfig {
    bool Enabled = true;
    vector<uint32> RandomBotAccounts;
    bool IsInRandomAccountList(uint32 id);
};
PlayerbotAIConfig sPlayerbotAIConfig;
struct CharacterCacheFixture {
    unordered_map<uint32, uint32> accountByGuid;
    uint32 GetCharacterAccountIdByGuid(ObjectGuid guid) const {
        auto it = accountByGuid.find(guid.GetCounter());
        return it != accountByGuid.end() ? it->second : 0;
    }
};
CharacterCacheFixture cache;
CharacterCacheFixture* sCharacterCache = &cache;
struct PlayerbotsMgr {
    unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    PlayerbotAI* GetPlayerbotAI(Player*);
};
PlayerbotsMgr mgr;
PlayerbotsMgr* sPlayerbotsMgr = &mgr;
#define GET_PLAYERBOT_AI(player) sPlayerbotsMgr->GetPlayerbotAI(player)
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1
struct RandomPlayerbotMgr {
    unordered_set<ObjectGuid::LowType> currentBots;
    array<unordered_set<ObjectGuid>, 24> addclassCache{};
    unordered_set<uint32> accountTypeTwo;
    static size_t GetTeamClassIdx(uint8 isAlliance, uint8 claz) {
        return (isAlliance ? 12u : 0u) + static_cast<size_t>(claz);
    }
    bool IsAccountType(uint32 accountId, uint8 type) const {
        // Test-only in-memory DB reply. Real query body verified separately.
        return type == 2 && accountTypeTwo.contains(accountId);
    }
    bool IsRandomBot(Player* bot);
    bool IsRandomBot(ObjectGuid::LowType bot);
    bool IsAddclassBot(Player* bot);
    bool IsAddclassBot(ObjectGuid::LowType bot);
};
RandomPlayerbotMgr sRandomPlayerbotMgr;

__GET_AI__
__IS_SELF__
__IS_MOD_BOT__
__ACCOUNT_LIST__
__RANDOM_PLAYER__
__RANDOM_GUID__
__ADDCLASS_PLAYER__
__ADDCLASS_GUID__

void Scenario(char const* name, bool enabled, bool aiAttached, bool selfBot,
              uint32 account, bool randomAccount, bool currentBot,
              bool addclassCacheHit, bool addclassAccount) {
    mgr._playerbotsAIMap.clear();
    cache.accountByGuid.clear();
    sPlayerbotAIConfig.RandomBotAccounts.clear();
    sRandomPlayerbotMgr.currentBots.clear();
    sRandomPlayerbotMgr.accountTypeTwo.clear();
    for (auto& it : sRandomPlayerbotMgr.addclassCache) it.clear();
    sPlayerbotAIConfig.Enabled = enabled;

    Player player{{33}};
    Player externalMaster{{88}};
    PlayerbotAI ai;
    ai.master = selfBot ? &player : &externalMaster;
    if (aiAttached) mgr._playerbotsAIMap.emplace(player.GetGUID(), &ai);
    cache.accountByGuid.emplace(player.GetGUID().GetCounter(), account);
    if (randomAccount) sPlayerbotAIConfig.RandomBotAccounts.push_back(account);
    if (currentBot) sRandomPlayerbotMgr.currentBots.emplace(player.GetGUID().GetCounter());
    if (addclassCacheHit) sRandomPlayerbotMgr.addclassCache[1].insert(player.GetGUID());
    if (addclassAccount) sRandomPlayerbotMgr.accountTypeTwo.insert(account);

    bool visibleBot = IsPlayerBot(&player);
    bool self = IsSelfBot(&player);
    bool randomBot = sRandomPlayerbotMgr.IsRandomBot(&player);
    bool addclassBot = sRandomPlayerbotMgr.IsAddclassBot(&player);
    bool combined = visibleBot || randomBot || addclassBot;
    std::cout << name << " " << visibleBot << " " << self
              << " " << randomBot << " " << addclassBot
              << " " << combined << " " << mgr._playerbotsAIMap.size() << "\n";
}
int main() {
    Scenario("human_on", true,false,false,101,false,false,false,false);
    Scenario("human_off", false,false,false,101,false,false,false,false);
    Scenario("random_on",true,true,false,201,true,true,false,false);
    Scenario("random_masked",false,true,false,201,true,true,false,false);
    Scenario("random_not_current",false,true,false,201,true,false,false,false);
    Scenario("random_not_listed",false,true,false,201,false,true,false,false);
    Scenario("addclass_cache_on",true,true,false,301,false,false,true,false);
    Scenario("addclass_cache_masked",false,true,false,301,false,false,true,false);
    Scenario("addclass_account_masked",false,true,false,301,false,false,false,true);
    Scenario("addclass_label_only",false,false,false,301,false,false,false,true);
    Scenario("selfbot_on",true,true,true,101,false,false,false,false);
    Scenario("selfbot_masked",false,true,true,101,false,false,false,false);
    Scenario("selfbot_masked_label",false,true,true,201,true,true,false,false);
    Scenario("random_zero_account",false,true,false,0,false,true,false,false);
}
"""
# Visible-bot, SelfBot, RandomBot, AddclassBot, union, attached map size
EXPECTED = {
    "human_on": (0,0,0,0,0,0),
    "human_off": (0,0,0,0,0,0),
    "random_on": (1,0,1,0,1,1),
    "random_masked": (0,0,1,0,1,1),
    "random_not_current": (0,0,0,0,0,1),
    "random_not_listed": (0,0,0,0,0,1),
    "addclass_cache_on": (1,0,0,1,1,1),
    "addclass_cache_masked": (0,0,0,1,1,1),
    "addclass_account_masked": (0,0,0,1,1,1),
    "addclass_label_only": (0,0,0,1,1,0),
    "selfbot_on": (1,1,0,0,1,1),
    "selfbot_masked": (0,0,0,0,0,1),
    "selfbot_masked_label": (0,0,1,0,1,1),
    "random_zero_account": (0,0,0,0,0,1),
}


def main() -> None:
    mgr = MGR.read_text(encoding="utf-8")
    rnd = RANDOM.read_text(encoding="utf-8")
    ai = AI.read_text(encoding="utf-8")
    cfg = CONFIG.read_text(encoding="utf-8")
    mod = MODULE.read_text(encoding="utf-8")
    functions = {
        "GET_AI": extract(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)"),
        "IS_SELF": extract(ai, "bool IsSelfBot(Player* player)"),
        "IS_MOD_BOT": extract(mod, "    bool IsPlayerBot(Player* player)"),
        "ACCOUNT_LIST": extract(cfg, "bool PlayerbotAIConfig::IsInRandomAccountList(uint32 id)"),
        "RANDOM_PLAYER": extract(rnd, "bool RandomPlayerbotMgr::IsRandomBot(Player* bot)"),
        "RANDOM_GUID": extract(rnd, "bool RandomPlayerbotMgr::IsRandomBot(ObjectGuid::LowType bot)"),
        "ADDCLASS_PLAYER": extract(rnd, "bool RandomPlayerbotMgr::IsAddclassBot(Player* bot)"),
        "ADDCLASS_GUID": extract(rnd, "bool RandomPlayerbotMgr::IsAddclassBot(ObjectGuid::LowType bot)"),
    }
    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in functions["GET_AI"]:
        raise AssertionError("Pinned getter no longer masks AI")
    if "return botAI && botAI->GetMaster() == player;" not in functions["IS_SELF"]:
        raise AssertionError("Pinned self identity differs")
    if "return GET_PLAYERBOT_AI(player) != nullptr;" not in functions["IS_MOD_BOT"]:
        raise AssertionError("Actual HonorOverflow identity differs")
    if "return IsRandomBot(bot->GetGUID().GetCounter());" not in functions["RANDOM_PLAYER"]:
        raise AssertionError("RandomBot Player* no longer falls back to LowType")
    if "currentBots.contains(bot)" not in functions["RANDOM_GUID"] or \
       "IsInRandomAccountList" not in functions["RANDOM_GUID"]:
        raise AssertionError("RandomBot member and account dual gate changed")
    if "return IsAddclassBot(bot->GetGUID().GetCounter());" not in functions["ADDCLASS_PLAYER"]:
        raise AssertionError("AddClass Player* no longer falls back to LowType")
    if "addclassCache[GetTeamClassIdx(isAlliance, claz)].find(guid)" not in functions["ADDCLASS_GUID"] or \
       "IsAccountType(accountId, 2)" not in functions["ADDCLASS_GUID"]:
        raise AssertionError("AddClass GUID or account type source changed")
    account_check = extract(rnd, "bool RandomPlayerbotMgr::IsAccountType(uint32 accountId, uint8 accountType)")
    if "PlayerbotsDatabase.Query(stmt) != nullptr;" not in account_check or \
       "PLAYERBOTS_SEL_ACCOUNT_TYPE_BY_ACCOUNT_AND_TYPE" not in account_check:
        raise AssertionError("Source-backed DB account-type query changed")
    if "RandomBotAccounts.begin()" not in functions["ACCOUNT_LIST"]:
        raise AssertionError("Random account membership no longer from config list")

    cpp = CPP
    for marker, body in functions.items():
        cpp = cpp.replace("__" + marker + "__", body)
    with tempfile.TemporaryDirectory(prefix="p13-r6-member-") as temp:
        src = pathlib.Path(temp) / "membership.cpp"
        exe = pathlib.Path(temp) / "membership"
        src.write_text(cpp, encoding="utf-8")
        subprocess.run(
            ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic",
             "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all",
             str(src), "-o", str(exe)], check=True,
        )
        actual = {}
        for line in subprocess.check_output([str(exe)], text=True).splitlines():
            match = re.fullmatch(r"([a-z_]+) ([01]) ([01]) ([01]) ([01]) ([01]) ([01])", line)
            if match is None:
                raise AssertionError(f"Unexpected fixture output {line!r}")
            name, *columns = match.groups()
            if name in actual:
                raise AssertionError("Duplicate fixture name")
            actual[name] = tuple(map(int, columns))
        if actual != EXPECTED:
            raise AssertionError(f"Unexpected pinned membership results: {actual}")
        print(f"PASS: C++20 {len(actual)} pinned Random/AddClass fallback cases with UBSan")
        print("POSITIVE: masked known RandomBot/AddClass membership still visible")
        print("EXPECTED CONDITIONAL RED: masked SelfBot with no category invisible to union")
        print("CAVEAT: account/category label can mark a character with NO attached AI")
        print("SOURCE: account-type query verified, actual DB is NEVER contacted")
    print(f"PIN: pinned Playerbots {PIN}")
    print("NO LIVE CLAIM: no player server, no money, no owner account or data")


if __name__ == "__main__":
    main()
