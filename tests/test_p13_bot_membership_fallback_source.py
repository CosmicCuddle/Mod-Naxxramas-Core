#!/usr/bin/env python3
"""P13-R6: exact pinned RandomBot/AddClass fallback source witness.

This compiles original GetPlayerbotAI, IsSelfBot, IsRealPlayer,
IsRandomBot(Player* + LowType), IsAddclassBot(Player* + LowType),
PlayerbotAIConfig::IsInRandomAccountList and HonorOverflow IsPlayerBot.

In-memory fake CharacterCache and IsAccountType provide test-only data;
their real production source/SQL contracts are separately checked. No
production DB lookup, real player, real award, Worldserver, config reload,
or owner data is executed. C++20 is required by pinned currentBots.contains.
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
DATABASE = PB / "src/Db/PlayerbotsDatabase.cpp"
MODULE = ROOT / "src/Systems/HonorOverflow.cpp"

PIN = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"


def extract(src: str, signature: str) -> str:
    if src.count(signature) != 1:
        raise AssertionError(f"Expected unique original source: {signature!r}")
    start = src.index(signature)
    brace = src.find("{", start)
    if brace == -1:
        raise AssertionError(f"No body for {signature}")
    level = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            level += 1
        elif src[i] == "}":
            level -= 1
            if level == 0:
                return src[start:i + 1]
    raise AssertionError(f"Unmatched source body {signature}")


CPP = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using uint32 = std::uint32_t;
using uint8 = std::uint8_t;
using std::find;
enum class HighGuid { Player };
enum : uint8 { CLASS_WARRIOR = 1, CLASS_DRUID = 11 };
struct ObjectGuid {
    using LowType = uint32;
    LowType id = 777;
    bool operator==(ObjectGuid const& rhs) const { return id == rhs.id; }
    template<HighGuid H> static ObjectGuid Create(LowType id) {
        static_assert(H == HighGuid::Player);
        return {id};
    }
    LowType GetCounter() const { return id; }
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
struct PlayerbotAI : PlayerbotAIBase {
    Player* master = nullptr;
    bool IsBotAI() override { return true; }
    Player* GetMaster() const { return master; }
};
struct PlayerbotAIConfig {
    bool Enabled = true;
    std::vector<uint32> RandomBotAccounts;
    bool IsInRandomAccountList(uint32);
};
PlayerbotAIConfig sPlayerbotAIConfig;
struct PlayerbotsMgr {
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    PlayerbotAI* GetPlayerbotAI(Player*);
};
PlayerbotsMgr manager;
PlayerbotsMgr* sPlayerbotsMgr = &manager;
#define GET_PLAYERBOT_AI(player) sPlayerbotsMgr->GetPlayerbotAI(player)
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1

struct CharacterCache {
    std::unordered_map<ObjectGuid, uint32> accounts;
    uint32 GetCharacterAccountIdByGuid(ObjectGuid const& id) const {
        auto it = accounts.find(id);
        return it == accounts.end() ? 0 : it->second;
    }
};
CharacterCache cache;
CharacterCache* sCharacterCache = &cache;
struct RandomPlayerbotMgr {
    std::unordered_set<ObjectGuid::LowType> currentBots;
    std::unordered_set<ObjectGuid> addclassCache[24];
    std::unordered_set<uint32> accountTypes2;
    bool IsRandomBot(Player*);
    bool IsRandomBot(ObjectGuid::LowType);
    bool IsAddclassBot(Player*);
    bool IsAddclassBot(ObjectGuid::LowType);
    // Stub for independently verified production SQL query: NO DB IO.
    bool IsAccountType(uint32 accountId, uint8 type) {
        return type == 2 && accountTypes2.contains(accountId);
    }
    // Only index-mapping stub to support original production cache loop.
    uint8 GetTeamClassIdx(uint8 alliance, uint8 claz) {
        return uint8(alliance * 12 + claz);
    }
};
RandomPlayerbotMgr sRandomPlayerbotMgr;

__GETTER__
__IS_SELF__
__IS_REAL__
__RANDOM_ACCOUNT__
__IS_RANDOM_PLAYER__
__IS_RANDOM_LOW__
__IS_ADD_PLAYER__
__IS_ADD_LOW__
__IS_MOD_BOT__

void Scenario(char const* name, bool enabled, bool attached, bool self,
              bool randomAccount, bool currentBot, bool addCache, bool type2,
              bool nullPlayer) {
    manager._playerbotsAIMap.clear();
    sRandomPlayerbotMgr.currentBots.clear();
    for (auto& set : sRandomPlayerbotMgr.addclassCache) set.clear();
    sRandomPlayerbotMgr.accountTypes2.clear();
    sPlayerbotAIConfig.RandomBotAccounts.clear();
    cache.accounts.clear();
    sPlayerbotAIConfig.Enabled = enabled;

    Player player;
    Player externalMaster;
    Player* p = nullPlayer ? nullptr : &player;
    PlayerbotAI ai;
    ai.master = self ? &player : &externalMaster;
    uint32 accountId = 900;
    cache.accounts[player.GetGUID()] = accountId;
    if (attached && p) manager._playerbotsAIMap[player.GetGUID()] = &ai;
    if (randomAccount) sPlayerbotAIConfig.RandomBotAccounts.push_back(accountId);
    if (currentBot) sRandomPlayerbotMgr.currentBots.insert(player.GetGUID().GetCounter());
    if (addCache) sRandomPlayerbotMgr.addclassCache[1].insert(player.GetGUID());
    if (type2) sRandomPlayerbotMgr.accountTypes2.insert(accountId);

    bool modBot = IsPlayerBot(p);
    bool real = IsRealPlayer(p);
    bool selfbot = IsSelfBot(p);
    bool randomBot = sRandomPlayerbotMgr.IsRandomBot(p);
    bool addclass = sRandomPlayerbotMgr.IsAddclassBot(p);
    bool fallbackAny = randomBot || addclass;
    bool hypotheticalExclusion = modBot || fallbackAny;
    std::cout << name << " " << modBot << " " << real << " " << selfbot
              << " " << randomBot << " " << addclass << " " << fallbackAny
              << " " << hypotheticalExclusion << " "
              << manager._playerbotsAIMap.size() << "\n";
}
int main() {
    Scenario("human_enabled", true, false, false, false, false, false, false, false);
    Scenario("human_masked", false, false, false, false, false, false, false, false);
    Scenario("self_visible", true, true, true, false, false, false, false, false);
    Scenario("self_masked", false, true, true, false, false, false, false, false);
    Scenario("random_visible", true, true, false, true, true, false, false, false);
    Scenario("random_masked", false, true, false, true, true, false, false, false);
    Scenario("random_missing_current", false, true, false, true, false, false, false, false);
    Scenario("random_missing_account", false, true, false, false, true, false, false, false);
    Scenario("addcache_visible", true, true, false, false, false, true, false, false);
    Scenario("addcache_masked", false, true, false, false, false, true, false, false);
    Scenario("addtype_masked", false, true, false, false, false, false, true, false);
    Scenario("human_type2", false, false, false, false, false, false, true, false);
    Scenario("self_visible_tagged", true, true, true, true, true, true, true, false);
    Scenario("self_masked_tagged", false, true, true, true, true, true, true, false);
    Scenario("null_player", false, false, false, true, true, true, true, true);
}
"""

# mod-bot, IsRealPlayer, IsSelfBot, RandomBot, AddclassBot,
# any fallback, hypothetical union, attached AI map record.
EXPECTED: dict[str, tuple[int, ...]] = {
    "human_enabled": (0, 1, 0, 0, 0, 0, 0, 0),
    "human_masked": (0, 1, 0, 0, 0, 0, 0, 0),
    "self_visible": (1, 0, 1, 0, 0, 0, 1, 1),
    "self_masked": (0, 1, 0, 0, 0, 0, 0, 1),
    "random_visible": (1, 0, 0, 1, 0, 1, 1, 1),
    "random_masked": (0, 1, 0, 1, 0, 1, 1, 1),
    "random_missing_current": (0, 1, 0, 0, 0, 0, 0, 1),
    "random_missing_account": (0, 1, 0, 0, 0, 0, 0, 1),
    "addcache_visible": (1, 0, 0, 0, 1, 1, 1, 1),
    "addcache_masked": (0, 1, 0, 0, 1, 1, 1, 1),
    "addtype_masked": (0, 1, 0, 0, 1, 1, 1, 1),
    "human_type2": (0, 1, 0, 0, 1, 1, 1, 0),
    "self_visible_tagged": (1, 0, 1, 0, 0, 0, 1, 1),
    "self_masked_tagged": (0, 1, 0, 1, 1, 1, 1, 1),
    "null_player": (0, 0, 0, 0, 0, 0, 0, 0),
}


def main() -> None:
    mgr = MGR.read_text(encoding="utf-8")
    rnd = RANDOM.read_text(encoding="utf-8")
    ai = AI.read_text(encoding="utf-8")
    conf = CONFIG.read_text(encoding="utf-8")
    db = DATABASE.read_text(encoding="utf-8")
    mod = MODULE.read_text(encoding="utf-8")

    funcs = {
        "__GETTER__": extract(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)"),
        "__IS_SELF__": extract(ai, "bool IsSelfBot(Player* player)"),
        "__IS_REAL__": extract(ai, "bool IsRealPlayer(Player* player)"),
        "__RANDOM_ACCOUNT__": extract(conf, "bool PlayerbotAIConfig::IsInRandomAccountList(uint32 id)"),
        "__IS_RANDOM_PLAYER__": extract(rnd, "bool RandomPlayerbotMgr::IsRandomBot(Player* bot)"),
        "__IS_RANDOM_LOW__": extract(rnd, "bool RandomPlayerbotMgr::IsRandomBot(ObjectGuid::LowType bot)"),
        "__IS_ADD_PLAYER__": extract(rnd, "bool RandomPlayerbotMgr::IsAddclassBot(Player* bot)"),
        "__IS_ADD_LOW__": extract(rnd, "bool RandomPlayerbotMgr::IsAddclassBot(ObjectGuid::LowType bot)"),
        "__IS_MOD_BOT__": extract(mod, "    bool IsPlayerBot(Player* player)"),
    }
    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in funcs["__GETTER__"]:
        raise AssertionError("Pinned getter no longer masks AI")
    if "return botAI && botAI->GetMaster() == player;" not in funcs["__IS_SELF__"]:
        raise AssertionError("Pinned SelfBot identity contract changed")
    if "return player && !GET_PLAYERBOT_AI(player);" not in funcs["__IS_REAL__"]:
        raise AssertionError("Pinned real-player helper changed")
    if "return GET_PLAYERBOT_AI(player) != nullptr;" not in funcs["__IS_MOD_BOT__"]:
        raise AssertionError("HonorOverflow exclusion source changed")
    if "currentBots.contains(bot)" not in funcs["__IS_RANDOM_LOW__"]:
        raise AssertionError("Pinned random-currentBots membership changed")
    if "IsInRandomAccountList" not in funcs["__IS_RANDOM_LOW__"]:
        raise AssertionError("Pinned random-account requirement changed")
    if "if (IsSelfBot(bot))" not in funcs["__IS_ADD_PLAYER__"] or \
       "if (IsSelfBot(bot))" not in funcs["__IS_RANDOM_PLAYER__"]:
        raise AssertionError("Source loses visible SelfBot exception")
    if "addclassCache[GetTeamClassIdx(isAlliance, claz)]" not in funcs["__IS_ADD_LOW__"] or \
       "IsAccountType(accountId, 2)" not in funcs["__IS_ADD_LOW__"]:
        raise AssertionError("Pinned AddClass GUID-cache/account-type fallback changed")
    # The sole DB call is a stub. Make the real source contract explicit.
    account_type = extract(rnd, "bool RandomPlayerbotMgr::IsAccountType(uint32 accountId, uint8 accountType)")
    if "PlayerbotsDatabase.Query(stmt) != nullptr" not in account_type or \
       "PLAYERBOTS_SEL_ACCOUNT_TYPE_BY_ACCOUNT_AND_TYPE" not in account_type:
        raise AssertionError("Pinned AddClass account type DB check differs")
    if "FROM playerbots_account_type WHERE" not in db or \
       "PLAYERBOTS_SEL_ACCOUNT_TYPE_BY_ACCOUNT_AND_TYPE" not in db:
        raise AssertionError("Pinned AccountType DB prepared query not found")

    cpp = CPP
    for name, body in funcs.items():
        cpp = cpp.replace(name, body)

    with tempfile.TemporaryDirectory(prefix="p13-membership-cxx20-") as folder:
        code = pathlib.Path(folder) / "membership.cpp"
        binary = pathlib.Path(folder) / "membership"
        code.write_text(cpp, encoding="utf-8")
        subprocess.run(
            ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic",
             "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all",
             str(code), "-o", str(binary)], check=True,
        )
        actual = {}
        for line in subprocess.check_output([str(binary)], text=True).splitlines():
            m = re.fullmatch(r"([a-z][a-z_0-9]*)((?: [01]){8})", line)
            if m is None:
                raise AssertionError(f"Unexpected source fixture output {line!r}")
            label = m.group(1)
            if label in actual:
                raise AssertionError(f"Duplicate test case {label}")
            actual[label] = tuple(map(int, m.group(2).strip().split()))
        if actual != EXPECTED:
            errors = {k: (EXPECTED.get(k), v) for k, v in actual.items()
                      if EXPECTED.get(k) != v}
            raise AssertionError(f"C++20 source witness mismatch: {errors}")

    print(f"PASS: c++20, {len(actual)} literal RandomBot/AddClass membership scenarios")
    print("POSITIVE PARTIAL: masked RandomBot in currentBots+account list still detected")
    print("POSITIVE PARTIAL: masked AddClass GUID-cache or account type still detected")
    print("EXPECTED CONDITIONAL RED: masked unlisted SelfBot remains invisible to all")
    print("CAUTION: account-type fallback can classify synthetic no-AI player")
    print("LIMIT: CharacterCache/account-type DB are in-memory stubs, no actual DB queries")
    print("LIMIT: no universal bot identity, no reward, config reload or owner gameplay")
    print(f"PIN: Playerbots {PIN} / HonorOverflow parent source unchanged")


if __name__ == "__main__":
    main()
