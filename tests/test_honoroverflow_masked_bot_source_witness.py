#!/usr/bin/env python3
"""P13: exact HonorOverflow and pinned Playerbots getter source-execution witness.

Extract unmodified production C++ functions and compile in a small C++17/20
test TU. Configuration-masked AI visibility is a SOURCE-CONSISTENT conditional
scenario, not a claim that such a player state was seen in a live world.

An EXPECTED RED demonstrates that IncludeBots=false cannot prove exclusion
when the Playerbots getter is masked by Enabled=false. No real money awarded.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/Systems/HonorOverflow.cpp"
PLAYERBOTS = ROOT / "pinned-playerbots/src/Bot/PlayerbotMgr.cpp"
MODULE_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
PB_SHA = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"


def extract(source: str, signature: str) -> str:
    if source.count(signature) != 1:
        raise AssertionError(f"Expected exactly one unmodified function: {signature}")
    start = source.index(signature)
    beginning = source.find("{", start)
    if beginning < 0:
        raise AssertionError("No function body")
    level = 0
    for i in range(beginning, len(source)):
        if source[i] == "{":
            level += 1
        elif source[i] == "}":
            level -= 1
            if level == 0:
                return source[start:i + 1]
    raise AssertionError("Unclosed source function")


HARNESS = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <string>
#include <unordered_map>
#include <utility>
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
using int32 = std::int32_t;

struct ObjectGuid {
    using LowType = uint32;
    uint32 id = 9;
    uint32 GetCounter() const { return id; }
    bool operator==(ObjectGuid const& that) const { return id == that.id; }
};
namespace std {
    template <> struct hash<ObjectGuid> {
        std::size_t operator()(ObjectGuid const& guid) const {
            return std::hash<uint32>{}(guid.id);
        }
    };
}
struct Session {};
struct Player {
    ObjectGuid guid{};
    uint32 honor = 100;
    uint32 today = 50;
    uint32 money = 0;
    bool inBG = false;
    Session session;

    ObjectGuid GetGUID() const { return guid; }
    uint32 GetHonorPoints() const { return honor; }
    uint32 GetUInt32Value(uint32) const { return today; }
    uint32 GetMoney() const { return money; }
    void ModifyMoney(int32 delta) { money += static_cast<uint32>(delta); }
    bool InBattleground() const { return inBG; }
    Session* GetSession() { return &session; }
};
struct PlayerbotAIBase {
    virtual ~PlayerbotAIBase() = default;
    virtual bool IsBotAI() { return false; }
};
struct PlayerbotAI final : PlayerbotAIBase {
    bool IsBotAI() override { return true; }
};
struct FakePlayerbotsConfig { bool Enabled = true; };
FakePlayerbotsConfig sPlayerbotAIConfig;
struct PlayerbotsMgr {
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    PlayerbotAI* GetPlayerbotAI(Player*);
};
PlayerbotsMgr manager;
PlayerbotsMgr* sPlayerbotsMgr = &manager;
#define GET_PLAYERBOT_AI(player) sPlayerbotsMgr->GetPlayerbotAI(player)
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1

struct HonorSnapshot {
    uint32 Honor = 0;
    uint32 TodayContribution = 0;
};
struct BattlegroundHonorSummary {
    uint64 ExcessHonor = 0;
    uint64 RequestedCopper = 0;
    uint64 AwardedCopper = 0;
};
std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;
std::unordered_map<ObjectGuid::LowType, BattlegroundHonorSummary> BattlegroundHonorSummaries;

bool HonorOverflowEnabled = true;
uint32 HonorOverflowCopperPerHonor = 10;
bool HonorOverflowNotify = false;
bool HonorOverflowIncludeBots = false;
constexpr uint32 PLAYER_FIELD_TODAY_CONTRIBUTION = 1;
constexpr uint32 CONFIG_MAX_HONOR_POINTS = 2;
constexpr uint32 MAX_MONEY_AMOUNT = 1000;
struct WorldSim {
    uint32 getIntConfig(uint32) const { return 100; }
};
WorldSim world;
WorldSim* sWorld = &world;
struct ChatHandler {
    explicit ChatHandler(Session*) {}
    template<typename... Args>
    void PSendSysMessage(char const*, Args...) {}
};
std::string FormatMoney(uint64) { return "mock"; }

__PB_GETTER__
__HONOR_IS_BOT__
__HONOR_SNAPSHOT__
__HONOR_BG_SUMMARY__
__HONOR_PROCESS__

void Scenario(char const* name, bool attached, bool pbEnabled, bool includeBots,
              bool featureEnabled, bool cappedHonor, uint32 initialMoney,
              bool gainToday, bool repeat) {
    manager._playerbotsAIMap.clear();
    HonorSnapshots.clear();
    BattlegroundHonorSummaries.clear();
    sPlayerbotAIConfig.Enabled = pbEnabled;
    HonorOverflowIncludeBots = includeBots;
    HonorOverflowEnabled = featureEnabled;

    Player p;
    p.honor = cappedHonor ? 100u : 99u;
    p.money = initialMoney;
    PlayerbotAI botAI;
    if (attached)
        manager._playerbotsAIMap.emplace(p.GetGUID(), &botAI);

    StoreHonorSnapshot(&p);
    p.today = gainToday ? 70u : 50u;
    bool const detectedBot = IsPlayerBot(&p);
    uint32 const before = p.money;
    ProcessHonorOverflow(&p);
    if (repeat)
        ProcessHonorOverflow(&p);

    std::cout << name << " " << detectedBot << " "
              << (p.money - before) << " "
              << (HonorSnapshots.at(p.GetGUID().GetCounter()).TodayContribution)
              << " " << manager._playerbotsAIMap.size() << "\n";
}
int main() {
    Scenario("attached_visible_excluded", true, true, false, true, true, 0, true, false);
    Scenario("attached_masked_excluded", true, false, false, true, true, 0, true, false);
    Scenario("attached_masked_included", true, false, true, true, true, 0, true, false);
    Scenario("attached_visible_included", true, true, true, true, true, 0, true, false);
    Scenario("ordinary_human_disabled", false, false, false, true, true, 0, true, false);
    Scenario("masked_below_honor_cap", true, false, false, true, false, 0, true, false);
    Scenario("masked_at_money_cap", true, false, false, true, true, 1000, true, false);
    Scenario("masked_near_money_cap", true, false, false, true, true, 980, true, false);
    Scenario("masked_feature_disabled", true, false, false, false, true, 0, true, false);
    Scenario("masked_no_new_honor", true, false, false, true, true, 0, false, false);
    Scenario("masked_repeat_no_double", true, false, false, true, true, 0, true, true);
}
"""

# (bot classification seen through unchanged module, simulated copper granted,
#  stored TodayContribution, retained AI-map entry)
EXPECTED = {
    "attached_visible_excluded": (1, 0, 70, 1),
    "attached_masked_excluded": (0, 200, 70, 1),  # EXPECTED SAFETY RED: money to masked bot
    "attached_masked_included": (0, 200, 70, 1),
    "attached_visible_included": (1, 200, 70, 1),
    "ordinary_human_disabled": (0, 200, 70, 0),
    "masked_below_honor_cap": (0, 0, 70, 1),
    "masked_at_money_cap": (0, 0, 70, 1),
    "masked_near_money_cap": (0, 20, 70, 1),
    "masked_feature_disabled": (0, 0, 70, 1),
    "masked_no_new_honor": (0, 0, 50, 1),
    "masked_repeat_no_double": (0, 200, 70, 1),
}


def main() -> None:
    modsrc = MODULE.read_text(encoding="utf-8")
    pbsrc = PLAYERBOTS.read_text(encoding="utf-8")
    getter = extract(pbsrc, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in getter:
        raise AssertionError("Playerbots getter no longer config-masked")
    if "_playerbotsAIMap.find(player->GetGUID())" not in getter:
        raise AssertionError("Pinned AI map source drifted")

    is_bot = extract(modsrc, "    bool IsPlayerBot(Player* player)")
    snap = extract(modsrc, "    void StoreHonorSnapshot(Player* player)")
    bg = extract(modsrc, "    void AddBattlegroundSummary(")
    process = extract(modsrc, "    void ProcessHonorOverflow(")
    for needle in (
        "GET_PLAYERBOT_AI(player) != nullptr",
        "if (!HonorOverflowIncludeBots && IsPlayerBot(player))",
        "player->ModifyMoney(static_cast<int32>(rewardCopper))",
        "itr->second.TodayContribution = currentTodayContribution",
    ):
        if needle not in "\n".join((is_bot, process)):
            raise AssertionError(f"HonorOverflow source contract drifted: {needle}")
    source = (HARNESS
        .replace("__PB_GETTER__", getter)
        .replace("__HONOR_IS_BOT__", is_bot)
        .replace("__HONOR_SNAPSHOT__", snap)
        .replace("__HONOR_BG_SUMMARY__", bg)
        .replace("__HONOR_PROCESS__", process))

    with tempfile.TemporaryDirectory(prefix="naxx-honor-masked-bot-") as directory:
        for standard in ("c++17", "c++20"):
            cpp = pathlib.Path(directory) / f"witness_{standard}.cpp"
            binary = pathlib.Path(directory) / f"witness_{standard}"
            cpp.write_text(source, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(cpp), "-o", str(binary)],
                check=True)
            output = subprocess.check_output([str(binary)], text=True)
            actual = {}
            for line in output.splitlines():
                m = re.fullmatch(r"([a-z_]+) ([01]) (\d+) (\d+) (\d+)", line)
                if not m:
                    raise AssertionError(f"Unexpected C++ source output {line!r}")
                label, *values = m.groups()
                if label in actual:
                    raise AssertionError(f"Repeated case: {label}")
                actual[label] = tuple(map(int, values))
            if actual != EXPECTED:
                raise AssertionError(f"{standard} source witness drift: {actual} != {EXPECTED}")
            print(f"PASS: {standard} {len(actual)} actual HonorOverflow + Playerbots source cases")
            print("EXPECTED SAFETY RED: retained attached bot + config masked getter => "
                  f"{actual['attached_masked_excluded'][1]} mock copper even with IncludeBots=false")
            print("POSITIVE: normal human with Playerbots disabled still "
                  f"earns {actual['ordinary_human_disabled'][1]} mock copper")
    print(f"PASS: pinned source predicates Mod {MODULE_SHA}, Playerbots {PB_SHA}")
    print("Scope: source-extracted C++ with synthetic state; NOT live money or runtime reachability")


if __name__ == "__main__":
    main()
