#!/usr/bin/env python3
"""P13-R12 pinned original C++ money-hook mutation witness (NONPRODUCTION).
Usage: python3 -I tests/test_p13_r12_money_hook_mutation_source.py . pinned-core
Six hypothetical hook cases; no owner Worldserver, scripts, account or currency.
"""
import pathlib
import subprocess
import sys
import tempfile

MOD_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD_FILE = "src/Systems/HonorOverflow.cpp"
CORE_MONEY = "src/server/game/Entities/Player/Player.cpp"
CORE_DECL = "src/server/game/Scripting/ScriptDefines/PlayerScript.h"
CORE_DISPATCH = "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp"
CORE_MACROS = "src/server/game/Scripting/ScriptMgrMacros.h"
BLOBS = {
    MOD_FILE: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
    CORE_MONEY: "138e7eab4905ec366338a54cc18e6cfe749a3670",
    CORE_DECL: "0d2314edf7715f383bbab996c6c5fc010b282308",
    CORE_DISPATCH: "4ac4571a3d7d8c0f3f27e8477ff5d7f0734e6e05",
    CORE_MACROS: "80895976796c2cc0219256b5b653d3e05c7c908c",
}

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def method(text, anchor):
    start = text.index(anchor)
    left = text.index("{", start)
    depth = 0
    for i in range(left, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError("Unbalanced original method: " + anchor)

def source_contract(mod, money_src, decl, dispatch_src, macros_src):
    money = method(money_src, "bool Player::ModifyMoney(int32 amount, bool sendError /*= true*/)")
    dispatch = method(dispatch_src, "void ScriptMgr::OnPlayerMoneyChanged(Player* player, int32& amount)")
    bg = method(mod, "    void AddBattlegroundSummary(")
    reward = mod[mod.index("        uint64 requestedCopper ="):
                 mod.index("        bool useBattlegroundSummary =")]
    assert "virtual void OnPlayerMoneyChanged(Player* /*player*/, int32& /*amount*/) { }" in decl, "ref signature changed"
    assert "PLAYERHOOK_ON_MONEY_CHANGED," in decl, "hook enum removed"
    assert "CALL_ENABLED_HOOKS(PlayerScript, PLAYERHOOK_ON_MONEY_CHANGED, script->OnPlayerMoneyChanged(player, amount));" in dispatch, "ref not forwarded"
    assert "sScriptMgr->OnPlayerMoneyChanged(this, amount);" in money
    assert money.index("sScriptMgr->OnPlayerMoneyChanged(this, amount);") < money.index("if (amount < 0)")
    assert money.index("if (amount < 0)") < money.index("if (uint32 trialMoneyCap")
    assert "if (GetMoney() < uint32(MAX_MONEY_AMOUNT - amount))" in money, "strict cap rule changed"
    assert "if (rewardCopper > 0)\n            player->ModifyMoney(static_cast<int32>(rewardCopper));" in reward
    assert "AddBattlegroundSummary(" in mod
    assert "summary.AwardedCopper += awardedCopper;" in bg
    block = macros_src[macros_src.index("#define CALL_ENABLED_HOOKS("):
                       macros_src.index("\n\n", macros_src.index("#define CALL_ENABLED_HOOKS("))]
    assert "ScriptRegistry<scriptType>::EnabledHooks[hookType]" in block
    assert "for (auto const& script : ScriptRegistry<scriptType>::EnabledHooks[hookType]) { action; }" in block
    return money, dispatch, bg, reward, block

def mutants(mod, money, decl, dispatch, macros):
    changes = [
        ("core bypasses mutable hook", 1, "sScriptMgr->OnPlayerMoneyChanged(this, amount);", "/* callback removed */"),
        ("hook parameter becomes value", 2, "int32& /*amount*/", "int32 /*amount*/"),
        ("dispatcher no longer forwards amount", 3, "script->OnPlayerMoneyChanged(player, amount)", "script->OnPlayerMoneyChanged(player, 0)"),
        ("enabled dispatch iteration disabled", 4, "for (auto const& script : ScriptRegistry<scriptType>::EnabledHooks[hookType]) { action; }", "/* hooks skipped */"),
        ("module begins checking return", 0, "player->ModifyMoney(static_cast<int32>(rewardCopper));", "if (!player->ModifyMoney(static_cast<int32>(rewardCopper))) return;"),
    ]
    sources = [mod, money, decl, dispatch, macros]
    for label, idx, old, new in changes:
        assert old in sources[idx], "mutant anchor missing: " + label
        modified = sources.copy()
        modified[idx] = modified[idx].replace(old, new, 1)
        try:
            source_contract(*modified)
        except (ValueError, AssertionError):
            print("CAUGHT SOURCE DRIFT: " + label)
        else:
            raise AssertionError("Source mutant survived: " + label)

PREFIX = r"""
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <vector>
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
using int32 = std::int32_t;
constexpr uint32 MAX_MONEY_AMOUNT = 1000; // Synthetic, NOT AzerothCore production maximum!
constexpr int CONFIG_TRIAL_MONEY_CAP = 1;
constexpr int EQUIP_ERR_TOO_MUCH_GOLD = 2;
constexpr int PLAYERHOOK_ON_MONEY_CHANGED = 0;
uint32 HonorOverflowCopperPerHonor = 1; // Synthetic, NOT installed rate!
struct Session { bool trial = false; bool IsTrialAccount() const { return trial; } };
struct World { uint32 cap = 0; uint32 getIntConfig(int) const { return cap; } } world;
World* sWorld = &world;
struct Guid { uint32 GetCounter() const { return 41; } };
class Player;
struct PlayerScript {
    virtual ~PlayerScript() = default;
    virtual void OnPlayerMoneyChanged(Player*, int32&) = 0;
};
template<typename T>
struct ScriptRegistry {
    static inline std::array<std::vector<T*>, 1> EnabledHooks {};
};
class ScriptMgr {
public:
    void OnPlayerMoneyChanged(Player* player, int32& amount);
};
ScriptMgr dispatchManager;
ScriptMgr* sScriptMgr = &dispatchManager;
class Player {
public:
    Player(uint32 start, bool trial = false) : money(start) { sess.trial = trial; }
    uint32 GetMoney() const { return money; }
    void SetMoney(uint32 value) { money = value; }
    Session* GetSession() { return &sess; }
    Guid GetGUID() const { return {}; }
    void SendEquipError(int, void*, void*) { ++errors; }
    bool ModifyMoney(int32 amount, bool sendError = true);
    int errors = 0;
private:
    uint32 money;
    Session sess;
};
struct BattlegroundHonorSummary {
    uint64 ExcessHonor = 0, RequestedCopper = 0, AwardedCopper = 0;
};
std::unordered_map<uint32, BattlegroundHonorSummary> BattlegroundHonorSummaries;
void require(bool okay, char const* reason) {
    if (!okay) throw std::runtime_error(reason);
}
"""

SUFFIX = r"""
struct Hook : PlayerScript {
    enum Mode { None, Half, Zero, Double, Reverse, DoubleIntoCap } mode;
    int called = 0;
    explicit Hook(Mode m) : mode(m) {}
    void OnPlayerMoneyChanged(Player*, int32& amount) override {
        ++called;
        switch (mode) {
            case None: break;
            case Half: amount /= 2; break;
            case Zero: amount = 0; break;
            case Double: case DoubleIntoCap: amount *= 2; break;
            case Reverse: amount = -amount; break;
        }
    }
};
struct Result { uint32 proposed; int64_t delta; uint64 summarized; int hookCalls; int errors; };
Result invoke(uint32 initialMoney, uint32 honor, Hook* hook) {
    BattlegroundHonorSummaries.clear();
    ScriptRegistry<PlayerScript>::EnabledHooks[0].clear();
    if (hook) ScriptRegistry<PlayerScript>::EnabledHooks[0].push_back(hook);
    Player playerObject(initialMoney);
    Player* player = &playerObject;
    uint32 excessHonor = honor;
__REWARD__
    AddBattlegroundSummary(&player, excessHonor, requestedCopper, rewardCopper);
    return {rewardCopper, static_cast<int64_t>(player->GetMoney()) -
        static_cast<int64_t>(initialMoney),
        BattlegroundHonorSummaries.at(41).AwardedCopper, hook ? hook->called : 0,
        player->errors};
}
void match(char const* label, Result const& x, uint32 proposed, int64_t credited, int hooks, int errorCount) {
    require(x.proposed == proposed && x.summarized == proposed, "module proposed mismatch");
    require(x.delta == credited, "money hook's modified actual amount mismatch");
    require(x.hookCalls == hooks && x.errors == errorCount, "hook/errors mismatch");
    std::cout << "CASE: " << label << " proposed=" << x.proposed
              << " actual_delta=" << x.delta << "\n";
}
int main() {
    try {
        match("no-hook", invoke(100, 200, nullptr), 200, 200, 0, 0);
        Hook half(Hook::Half);
        match("half", invoke(100, 200, &half), 200, 100, 1, 0);
        Hook zero(Hook::Zero);
        match("zero", invoke(100, 200, &zero), 200, 0, 1, 0);
        Hook amplify(Hook::Double);
        match("double", invoke(100, 200, &amplify), 200, 400, 1, 0);
        Hook reverse(Hook::Reverse);
        match("negative", invoke(500, 200, &reverse), 200, -200, 1, 0);
        Hook cap(Hook::DoubleIntoCap);
        match("hook-induced-equality-cap", invoke(800, 100, &cap), 100, 0, 1, 1);
        std::cout << "PASS: R12 six scenarios with original money, dispatch, macro and proposal\n";
        std::cout << "LIMIT: hypothetical mutant PlayerScript objects, NOT installed addon/core scripts or owner runtime\n";
        return 0;
    } catch (std::exception const& error) {
        std::cerr << "FAIL: " << error.what() << "\n";
        return 1;
    }
}
"""

def compile_cases(parts):
    money, dispatch, bg, reward, macro = parts
    cpp = PREFIX + "\n" + macro + "\n" + money + "\n" + dispatch + "\n" + bg + "\n" + SUFFIX.replace("__REWARD__", reward)
    with tempfile.TemporaryDirectory(prefix="p13_r12_") as d:
        p = pathlib.Path(d)
        source = p / "synthetic.cpp"
        source.write_text(cpp)
        for label, args in [
            ("c++17", []),
            ("c++20", []),
            ("c++20-ubsan", ["-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all"]),
        ]:
            exe = p / label
            std = "c++20" if label.endswith("-ubsan") else label
            subprocess.run(["g++", "-std=" + std, "-Wall", "-Wextra", "-Werror",
                            "-pedantic", *args, str(source), "-o", str(exe)], check=True)
            result = subprocess.check_output([str(exe)], text=True)
            assert len([line for line in result.splitlines() if line.startswith("CASE:")]) == 6, result
            assert "PASS: R12 six scenarios with original money, dispatch, macro and proposal" in result
            assert "LIMIT:" in result
            print("PASS: " + label + " original-body mutable-hook 6-case witness")

def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    mod, core = [pathlib.Path(v) for v in argv[1:]]
    assert git(core, "rev-parse", "HEAD") == CORE_SHA
    assert git(mod, "rev-parse", MOD_SHA + ":" + MOD_FILE) == BLOBS[MOD_FILE]
    assert git(mod, "rev-parse", "HEAD:" + MOD_FILE) == BLOBS[MOD_FILE]
    subprocess.run(["git", "-C", str(mod), "merge-base", "--is-ancestor", MOD_SHA, "HEAD"], check=True)
    for file in (CORE_MONEY, CORE_DECL, CORE_DISPATCH, CORE_MACROS):
        assert git(core, "rev-parse", "HEAD:" + file) == BLOBS[file], "source drift: " + file
    sources = [(mod / MOD_FILE).read_text()] + [(core / p).read_text()
               for p in (CORE_MONEY, CORE_DECL, CORE_DISPATCH, CORE_MACROS)]
    parts = source_contract(*sources)
    print("PASS: R12 five original source blobs and mutable pre-credit hook dispatch")
    mutants(*sources)
    compile_cases(parts)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError, ValueError, subprocess.CalledProcessError) as error:
        print("FAIL: " + str(error))
        sys.exit(1)
