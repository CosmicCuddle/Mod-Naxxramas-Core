#!/usr/bin/env python3
"""P13-R7: source-anchored shared HonorOverflow state/threading safety audit.

Proves that the SAME two process-global unordered_maps serve multiple players
through original helper bodies and that pinned Grimfeather maps can dispatch
Player::Update/OnPlayerUpdate from multiple worker threads.

The C++ fixture is intentionally SINGLE-THREADED: executing real concurrent
unsynchronized unordered_map writes would be undefined behavior and could
make this safety regression itself flaky. This is a SOURCE-LEVEL POTENTIAL
DATA-RACE finding, NOT a live crash, data race observation or proposed fix.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "pinned-core"
MOD = ROOT / "src/Systems/HonorOverflow.cpp"
CONFIG = CORE / "src/server/game/World/WorldConfig.cpp"
MGR = CORE / "src/server/game/Maps/MapMgr.cpp"
UPDATER = CORE / "src/server/game/Maps/MapUpdater.cpp"
MAP = CORE / "src/server/game/Maps/Map.cpp"
PLAYER = CORE / "src/server/game/Entities/Player/PlayerUpdates.cpp"


def func(src: str, sig: str) -> str:
    if src.count(sig) != 1:
        raise AssertionError(f"Missing or duplicated source signature {sig!r}")
    begin = src.index(sig)
    left = src.find("{", begin)
    if left < 0:
        raise AssertionError(f"Missing body {sig}")
    depth = 0
    for i in range(left, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[begin:i + 1]
    raise AssertionError(f"Unclosed body {sig}")


CPP = r"""
#include <cassert>
#include <cstdint>
#include <iostream>
#include <unordered_map>

using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
constexpr uint32 PLAYER_FIELD_TODAY_CONTRIBUTION = 10;

struct ObjectGuid {
    using LowType = uint32;
    LowType low = 0;
    LowType GetCounter() const { return low; }
};
struct Player {
    ObjectGuid guid{};
    uint32 honor = 0, contribution = 0;
    ObjectGuid GetGUID() const { return guid; }
    uint32 GetHonorPoints() const { return honor; }
    uint32 GetUInt32Value(uint32 field) const {
        assert(field == PLAYER_FIELD_TODAY_CONTRIBUTION);
        return contribution;
    }
};
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

// BOTH helper implementations below are unmodified module production source:
__STORE__
__ADD_BG__

int main() {
    Player a{{11}, 100, 5};
    Player b{{22}, 250, 9};
    StoreHonorSnapshot(&a);
    StoreHonorSnapshot(&b);
    assert(HonorSnapshots.size() == 2);
    assert(HonorSnapshots.at(11).Honor == 100);
    assert(HonorSnapshots.at(22).TodayContribution == 9);

    a.honor = 120;
    a.contribution = 6;
    StoreHonorSnapshot(&a);
    assert(HonorSnapshots.size() == 2);
    assert(HonorSnapshots.at(11).Honor == 120);
    assert(HonorSnapshots.at(22).Honor == 250);

    AddBattlegroundSummary(&a, 5, 50, 40);
    AddBattlegroundSummary(&b, 2, 20, 20);
    AddBattlegroundSummary(&a, 3, 30, 25);
    assert(BattlegroundHonorSummaries.size() == 2);
    assert(BattlegroundHonorSummaries.at(11).ExcessHonor == 8);
    assert(BattlegroundHonorSummaries.at(11).RequestedCopper == 80);
    assert(BattlegroundHonorSummaries.at(11).AwardedCopper == 65);
    assert(BattlegroundHonorSummaries.at(22).AwardedCopper == 20);
    std::cout << "PASS: exact module functions share two process-global maps across GUIDs\n";
}
"""


def inspect_core(s: dict[str, str]) -> None:
    if 'SetConfigValue<uint32>(CONFIG_NUMTHREADS, "MapUpdate.Threads", 1);' not in s["config"]:
        raise AssertionError("Thread-count config source anchor changed")
    init = func(s["mgr"], "void MapMgr::Initialize()")
    if "sWorld->getIntConfig(CONFIG_NUMTHREADS)" not in init or \
       "m_updater.activate(num_threads)" not in init:
        raise AssertionError("MapMgr no longer launches worker pool from CONFIG_NUMTHREADS")
    update = func(s["mgr"], "void MapMgr::Update(uint32 diff)")
    if "m_updater.schedule_update(*iter->second" not in update or \
       "m_updater.wait();" not in update:
        raise AssertionError("MapMgr dispatch or wait source changed")
    activate = func(s["updater"], "void MapUpdater::activate(std::size_t num_threads)")
    worker = func(s["updater"], "void MapUpdater::WorkerThread()")
    if "std::thread(&MapUpdater::WorkerThread, this)" not in activate or \
       "request->call();" not in worker:
        raise AssertionError("MapUpdater workers or request execution changed")
    if "void call() override" not in s["updater"] or \
       "m_map.Update(m_diff, s_diff);" not in s["updater"]:
        raise AssertionError("MapUpdateRequest no longer calls Map::Update")
    map_update = func(s["map"], "void Map::Update(const uint32 t_diff, const uint32 s_diff, bool  /*thread*/)")
    if "player->Update(s_diff);" not in map_update:
        raise AssertionError("Map player update call removed")
    player_update = func(s["player"], "void Player::Update(uint32 p_time)")
    if "sScriptMgr->OnPlayerUpdate(this, p_time);" not in player_update:
        raise AssertionError("Player OnPlayerUpdate callback changed")
    print("PINNED CORE: MapUpdate.Threads -> multiple map workers -> Player::Update")
    print("PINNED CORE: Player::Update invokes OnPlayerUpdate inside the map task")


def inspect_module(source: str) -> tuple[str, str]:
    declarations = (
        "std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;",
        "std::unordered_map<ObjectGuid::LowType, BattlegroundHonorSummary> BattlegroundHonorSummaries;",
    )
    for token in declarations:
        if source.count(token) != 1:
            raise AssertionError(f"Module shared map declaration changed: {token}")
    # If synchronisation is added, force re-review instead of incorrectly
    # continuing to report an unmitigated source-level risk.
    for token in ("std::mutex", "std::shared_mutex", "std::lock_guard",
                  "std::unique_lock", "std::scoped_lock", "thread_local"):
        if token in source:
            raise AssertionError(f"Potential mitigation {token} requires fresh review")
    store = func(source, "void StoreHonorSnapshot(Player* player)")
    bg = func(source, "void AddBattlegroundSummary(")
    process = func(source, "void ProcessHonorOverflow(Player* player, bool forceBattlegroundSummary = false)")
    for check in (
        "HonorSnapshots[player->GetGUID().GetCounter()]",
        "player->GetHonorPoints()",
        "PLAYER_FIELD_TODAY_CONTRIBUTION",
    ):
        if check not in store:
            raise AssertionError(f"StoreHonorSnapshot source changed: {check}")
    for check in (
        "BattlegroundHonorSummaries[player->GetGUID().GetCounter()]",
        "summary.ExcessHonor += excessHonor",
        "summary.RequestedCopper += requestedCopper",
        "summary.AwardedCopper += awardedCopper",
    ):
        if check not in bg:
            raise AssertionError(f"AddBattlegroundSummary source changed: {check}")
    if "HonorSnapshots.find(guid)" not in process or \
       "itr->second.Honor = currentHonor" not in process or \
       "itr->second.TodayContribution = currentTodayContribution" not in process or \
       "AddBattlegroundSummary(" not in process:
        raise AssertionError("ProcessHonorOverflow source read/write chain changed")
    if "PLAYERHOOK_ON_UPDATE" not in source or \
       "void OnPlayerUpdate(Player* player, uint32 /*diff*/) override" not in source or \
       "ProcessHonorOverflow(player);" not in source:
        raise AssertionError("HonorOverflow PlayerScript hook contract changed")
    if "HonorSnapshots.erase(guid);" not in source or \
       "BattlegroundHonorSummaries.erase(guid);" not in source:
        raise AssertionError("Logout/summary cleanup changed")
    print("MODULE: global unordered_map mutations are not synchronized in this file")
    print("MODULE: update hook and BG/teardown callbacks access those shared maps")
    return store, bg


def main() -> None:
    s = {
        "config": CONFIG.read_text(encoding="utf-8"),
        "mgr": MGR.read_text(encoding="utf-8"),
        "updater": UPDATER.read_text(encoding="utf-8"),
        "map": MAP.read_text(encoding="utf-8"),
        "player": PLAYER.read_text(encoding="utf-8"),
    }
    inspect_core(s)
    store, bg = inspect_module(MOD.read_text(encoding="utf-8"))
    program = CPP.replace("__STORE__", store).replace("__ADD_BG__", bg)
    with tempfile.TemporaryDirectory(prefix="p13-shared-state-") as directory:
        for standard in ("c++17", "c++20"):
            src = pathlib.Path(directory) / (standard + ".cpp")
            exe = pathlib.Path(directory) / standard
            src.write_text(program, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(src), "-o", str(exe)],
                check=True,
            )
            output = subprocess.check_output([str(exe)], text=True).strip()
            if output != "PASS: exact module functions share two process-global maps across GUIDs":
                raise AssertionError(f"Unexpected fixture result {output!r}")
            print(f"PASS: {standard} literal source, two GUIDs, both shared state maps")
    print("SOURCE-LEVEL POTENTIAL DATA RACE: multi-map updates may overlap")
    print("LIMITATION: static thread chain; deterministic fixture runs single-thread")
    print("NOT PROVEN: live overlap, actual race event, crash, corruption or payout")
    print("No production patch, no owner config/DB/game/server activity")


if __name__ == "__main__":
    main()
