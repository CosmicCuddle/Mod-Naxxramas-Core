#!/usr/bin/env python3
"""P13-R11 original source-slice C++ sequence witness (nonproduction).
Usage: python3 -I tests/test_p13_r11_rejected_award_lifecycle.py . pinned-core
No real Worldserver, player, money or installed configuration is used.
"""
import pathlib
import subprocess
import sys
import tempfile

MOD_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD_FILE = "src/Systems/HonorOverflow.cpp"
CORE_FILE = "src/server/game/Entities/Player/Player.cpp"
MOD_BLOB = "d4f70c511ac5a3e32c7e6b8f913d095915da707c"
CORE_BLOB = "138e7eab4905ec366338a54cc18e6cfe749a3670"

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def extract(src, anchor):
    begin = src.index(anchor)
    left = src.index("{", begin)
    depth = 0
    for pos in range(left, len(src)):
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
            if depth == 0:
                return src[begin:pos + 1]
    raise AssertionError("unbalanced C++ source: " + anchor)

def verify(mod, core):
    stores = extract(mod, "    void StoreHonorSnapshot(Player* player)")
    adds = extract(mod, "    void AddBattlegroundSummary(")
    sends = extract(mod, "    void SendBattlegroundSummary(Player* player)")
    processes = extract(mod, "    void ProcessHonorOverflow(Player* player, bool forceBattlegroundSummary = false)")
    money = extract(core, "bool Player::ModifyMoney(int32 amount, bool sendError /*= true*/)")
    login = extract(mod, "    void OnPlayerLogin(Player* player) override")
    logout = extract(mod, "    void OnPlayerLogout(Player* player) override")
    end = extract(mod, "    void OnBattlegroundEndReward(")
    leave = extract(mod, "    void OnBattlegroundRemovePlayerAtLeave(")
    assert "HonorSnapshots[player->GetGUID().GetCounter()]" in stores
    a = processes.index("itr->second.TodayContribution = currentTodayContribution;")
    b = processes.index("if (!HonorOverflowEnabled || HonorOverflowCopperPerHonor == 0)")
    c = processes.index("uint32 earnedHonor = 0;")
    d = processes.index("if (rewardCopper > 0)")
    e = processes.index("player->ModifyMoney(static_cast<int32>(rewardCopper));")
    f = processes.index("AddBattlegroundSummary(")
    assert a < b < c < d < e < f, "snapshot/credit/BG state order drift"
    assert "earnedHonor =\n                currentTodayContribution - previous.TodayContribution;" in processes
    assert "if (earnedHonor == 0)\n            return;" in processes
    assert "if (rewardCopper > 0)\n            player->ModifyMoney(static_cast<int32>(rewardCopper));" in processes
    assert "if (player->ModifyMoney(" not in processes
    assert "forceBattlegroundSummary || player->InBattleground()" in processes
    assert "summary.AwardedCopper += awardedCopper;" in adds
    assert "BattlegroundHonorSummaries.erase(itr);" in sends
    assert "StoreHonorSnapshot(player);" in login
    assert "BattlegroundHonorSummaries.erase(" in login
    assert "HonorSnapshots.erase(guid);" in logout
    assert "BattlegroundHonorSummaries.erase(guid);" in logout
    assert end.index("ProcessHonorOverflow(player, true);") < end.index("SendBattlegroundSummary(player);")
    assert leave.index("ProcessHonorOverflow(player, true);") < leave.index("SendBattlegroundSummary(player);")
    hook = money.index("sScriptMgr->OnPlayerMoneyChanged(this, amount);")
    trial = money.index("if (uint32 trialMoneyCap")
    ordinary = money.index("if (GetMoney() < uint32(MAX_MONEY_AMOUNT - amount))")
    assert hook < trial < ordinary, "money hook/rejection ordering drift"
    assert "return false;" in money
    return stores, adds, sends, processes, money

def mutation_guards(mod, core):
    replacements = [
        ("snapshot after payout", "mod", "itr->second.TodayContribution = currentTodayContribution;", "/* eliminated snapshot */"),
        ("retry unchanged contribution", "mod", "if (earnedHonor == 0)\n            return;", "if (earnedHonor == 999999)\n            return;"),
        ("check declined money", "mod", "player->ModifyMoney(static_cast<int32>(rewardCopper));", "if (!player->ModifyMoney(static_cast<int32>(rewardCopper))) return;"),
        ("BG no forced last capture", "mod", "ProcessHonorOverflow(player, true);", "ProcessHonorOverflow(player, false);"),
        ("BG no close erase", "mod", "BattlegroundHonorSummaries.erase(itr);", "/* do not close BG summary */"),
        ("pre-admission hook removed", "core", "sScriptMgr->OnPlayerMoneyChanged(this, amount);", "/* hook removed */"),
    ]
    for label, which, old, new in replacements:
        src = mod if which == "mod" else core
        assert src.count(old) >= 1, label
        candidate = src.replace(old, new)
        try:
            verify(candidate, core) if which == "mod" else verify(mod, candidate)
        except (AssertionError, ValueError):
            print("CAUGHT DRIFT: " + label)
        else:
            raise AssertionError("mutation survived: " + label)

PREFIX = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
using int32 = std::int32_t;
namespace ObjectGuid { using LowType = uint32; }
constexpr uint32 MAX_MONEY_AMOUNT = 1000; // synthetic cap ONLY
constexpr int CONFIG_TRIAL_MONEY_CAP = 1;
constexpr int CONFIG_MAX_HONOR_POINTS = 2;
constexpr int PLAYER_FIELD_TODAY_CONTRIBUTION = 3;
constexpr int EQUIP_ERR_TOO_MUCH_GOLD = 4;
bool HonorOverflowEnabled = true;
uint32 HonorOverflowCopperPerHonor = 1; // synthetic rate ONLY
bool HonorOverflowNotify = true;
bool HonorOverflowIncludeBots = false;
struct HonorSnapshot { uint32 Honor = 0; uint32 TodayContribution = 0; };
struct BattlegroundHonorSummary {
    uint64 ExcessHonor = 0, RequestedCopper = 0, AwardedCopper = 0;
};
std::unordered_map<uint32, HonorSnapshot> HonorSnapshots;
std::unordered_map<uint32, BattlegroundHonorSummary> BattlegroundHonorSummaries;
struct Session {
    bool trial = false;
    bool IsTrialAccount() const { return trial; }
};
struct World {
    uint32 trialCap = 0;
    uint32 getIntConfig(int option) const {
        return option == CONFIG_TRIAL_MONEY_CAP ? trialCap : 100;
    }
} world;
World* sWorld = &world;
struct Guid {
    uint32 id = 0;
    uint32 GetCounter() const { return id; }
};
class Player;
struct Scripts {
    int calls = 0;
    void OnPlayerMoneyChanged(Player*, int32) { ++calls; }
} scripts;
Scripts* sScriptMgr = &scripts;
class Player {
public:
    Player(uint32 identifier, uint32 balance, bool trial = false)
        : guid{identifier}, money(balance) { session.trial = trial; }
    uint32 GetMoney() const { return money; }
    void SetMoney(uint32 value) { money = value; }
    uint32 GetHonorPoints() const { return honor; }
    uint32 GetUInt32Value(int) const { return today; }
    Guid GetGUID() const { return guid; }
    Session* GetSession() { return &session; }
    bool InBattleground() const { return inBattleground; }
    void SendEquipError(int, void*, void*) { ++errors; }
    bool ModifyMoney(int32 amount, bool sendError = true);
    uint32 honor = 100, today = 0, errors = 0;
    bool inBattleground = false;
private:
    Guid guid;
    uint32 money;
    Session session;
};
bool IsPlayerBot(Player*) { return false; }
int messages = 0;
struct ChatHandler {
    explicit ChatHandler(Session*) {}
    template<class... Args>
    void PSendSysMessage(char const*, Args&&...) { ++messages; }
};
std::string FormatMoney(uint64) { return "toy-money"; }
void check(bool ok, char const* msg) {
    if (!ok) throw std::runtime_error(msg);
}
"""

SUFFIX = r"""
void reset() {
    HonorSnapshots.clear();
    BattlegroundHonorSummaries.clear();
    scripts.calls = 0;
    messages = 0;
    world.trialCap = 0;
    HonorOverflowNotify = true;
}
int main() {
    try {
        // A declined positive award consumes this already-observed contribution.
        reset();
        Player ordinary(10, 900);
        StoreHonorSnapshot(&ordinary);
        ordinary.today = 100;
        ProcessHonorOverflow(&ordinary);
        check(ordinary.GetMoney() == 900 && ordinary.errors == 1,
              "ordinary exact-cap rejection absent");
        check(scripts.calls == 1, "pre-admission money script hook not fired");
        check(HonorSnapshots[10].TodayContribution == 100,
              "rejected event not snapshotted");
        ProcessHonorOverflow(&ordinary);
        check(scripts.calls == 1 && ordinary.GetMoney() == 900,
              "unchanged honor retried after rejected credit");
        // A genuinely new contribution gets its own award attempt; old 100 do not replay.
        ordinary.today = 101;
        ProcessHonorOverflow(&ordinary);
        check(ordinary.GetMoney() == 901 && scripts.calls == 2,
              "new contribution not separately evaluated");
        std::cout << "PASS: rejected ordinary cap snapshot finality and new-only attempt\n";

        reset();
        world.trialCap = 600;
        Player trial(11, 500, true);
        StoreHonorSnapshot(&trial);
        trial.today = 200;
        ProcessHonorOverflow(&trial);
        ProcessHonorOverflow(&trial);
        check(trial.GetMoney() == 500 && scripts.calls == 1 && trial.errors == 1,
              "trial cap rejected contribution retried");
        check(HonorSnapshots[11].TodayContribution == 200,
              "trial rejected contribution not consumed");
        std::cout << "PASS: trial rejection hook precedes refusal, no unchanged retry\n";

        reset();
        Player bg(12, 900);
        bg.inBattleground = true;
        StoreHonorSnapshot(&bg);
        bg.today = 100;
        ProcessHonorOverflow(&bg);
        check(BattlegroundHonorSummaries[12].AwardedCopper == 100,
              "BG proposed credit not present");
        check(bg.GetMoney() == 900 && scripts.calls == 1,
              "BG rejected money unexpectedly credited");
        check(messages == 0, "BG sent premature immediate message");
        bg.inBattleground = false; // pinned leave hook uses force=true
        ProcessHonorOverflow(&bg, true);
        SendBattlegroundSummary(&bg);
        check(messages == 1 && BattlegroundHonorSummaries.count(12) == 0,
              "BG leave summary not closed exactly once");
        SendBattlegroundSummary(&bg);
        check(messages == 1, "duplicate BG close sent a second summary");
        std::cout << "PASS: BG forced end/leave flush once, reports proposed not credited\n";

        reset();
        Player quiet(13, 900);
        quiet.inBattleground = true;
        StoreHonorSnapshot(&quiet);
        quiet.today = 100;
        ProcessHonorOverflow(&quiet);
        check(BattlegroundHonorSummaries.count(13) == 1,
              "quiet BG did not accumulate summary");
        HonorOverflowNotify = false;
        SendBattlegroundSummary(&quiet);
        check(messages == 0 && BattlegroundHonorSummaries.count(13) == 0,
              "disabled notification should still clear BG summary");
        HonorOverflowNotify = true;
        SendBattlegroundSummary(&quiet);
        check(messages == 0, "suppressed summary was replayed");
        std::cout << "PASS: BG summary erased even when notifications disabled\n";
        std::cout << "LIMIT: literal source slices + synthetic Player, no thread/race/real server proof\n";
        return 0;
    } catch (std::exception const& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
"""

def run_witness(parts):
    stores, adds, sends, processes, money = parts
    cpp = PREFIX + "\n" + money + "\n" + stores + "\n" + adds + "\n" + sends + "\n" + processes + "\n" + SUFFIX
    with tempfile.TemporaryDirectory(prefix="p13_r11_") as td:
        root = pathlib.Path(td)
        src = root / "witness.cpp"
        src.write_text(cpp)
        for label, flags in [
            ("c++17", []),
            ("c++20", []),
            ("c++20-ubsan", ["-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all"]),
        ]:
            out = root / label
            standard = "c++20" if label == "c++20-ubsan" else label
            subprocess.run(["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                            "-pedantic", *flags, str(src), "-o", str(out)], check=True)
            output = subprocess.check_output([str(out)], text=True)
            assert output.count("PASS:") == 4, output
            assert "LIMIT:" in output
            print("PASS: " + label + " R11 original-source lifecycle sequence")

def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    modroot, coreroot = map(pathlib.Path, argv[1:])
    assert git(coreroot, "rev-parse", "HEAD") == CORE_SHA
    assert git(coreroot, "rev-parse", "HEAD:" + CORE_FILE) == CORE_BLOB
    assert git(modroot, "rev-parse", MOD_SHA + ":" + MOD_FILE) == MOD_BLOB
    assert git(modroot, "rev-parse", "HEAD:" + MOD_FILE) == MOD_BLOB
    subprocess.run(["git", "-C", str(modroot), "merge-base", "--is-ancestor",
                    MOD_SHA, "HEAD"], check=True)
    mod = (modroot / MOD_FILE).read_text()
    core = (coreroot / CORE_FILE).read_text()
    parts = verify(mod, core)
    print("PASS: R11 pinned original money, snapshot, BG close and logout source guards")
    mutation_guards(mod, core)
    run_witness(parts)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError, ValueError, subprocess.CalledProcessError) as err:
        print("FAIL: " + str(err))
        sys.exit(1)
