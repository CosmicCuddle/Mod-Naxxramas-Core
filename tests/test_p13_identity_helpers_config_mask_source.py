#!/usr/bin/env python3
"""P13-R4: actual-source identity helper masking regression, NOT a runtime fix.

Extract unchanged Playerbots GetPlayerbotAI / IsRealPlayer / IsSelfBot and
module HonorOverflow IsPlayerBot. Compile all four together in C++17/20.
Show why IsRealPlayer is NOT a config-independent positive human signal.

Also statically assert original Grimfeather core config reload and pinned
Playerbots config-init / command reload anchors. The full core reload and
real player/AI lifecycle are NOT executed or claimed reachable.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PB = ROOT / "pinned-playerbots"
CORE = ROOT / "pinned-core"
MGR = PB / "src/Bot/PlayerbotMgr.cpp"
AI = PB / "src/Bot/PlayerbotAI.cpp"
PBCFG = PB / "src/PlayerbotAIConfig.cpp"
PBRANDOM = PB / "src/Bot/RandomPlayerbotMgr.cpp"
PBWORLD = PB / "src/Script/Playerbots.cpp"
CORE_WORLD = CORE / "src/server/game/World/World.cpp"
CORE_RELOAD = CORE / "src/server/scripts/Commands/cs_reload.cpp"
MODULE = ROOT / "src/Systems/HonorOverflow.cpp"

PIN_PLAYERBOTS = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"
PIN_CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"


def function(src: str, signature: str) -> str:
    if src.count(signature) != 1:
        raise AssertionError(f"Expected unique pinned source signature {signature!r}")
    pos = src.index(signature)
    start = src.find("{", pos)
    if start == -1:
        raise AssertionError("Missing function opening brace")
    level = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            level += 1
        elif src[i] == "}":
            level -= 1
            if level == 0:
                return src[pos:i + 1]
    raise AssertionError("Unterminated pinned function")


CPP = r"""
#include <cstdint>
#include <iostream>
#include <unordered_map>
using uint32 = std::uint32_t;
struct ObjectGuid {
    uint32 id = 23;
    bool operator==(ObjectGuid const& other) const { return id == other.id; }
};
namespace std {
template<> struct hash<ObjectGuid> {
    size_t operator()(ObjectGuid const& guid) const {
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
struct Config { bool Enabled = true; };
Config sPlayerbotAIConfig;
struct PlayerbotsMgr {
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    PlayerbotAI* GetPlayerbotAI(Player*);
};
PlayerbotsMgr instance;
PlayerbotsMgr* sPlayerbotsMgr = &instance;
#define GET_PLAYERBOT_AI(player) sPlayerbotsMgr->GetPlayerbotAI(player)
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1

__GETTER__
__IS_REAL__
__IS_SELF__
__IS_MODULE_BOT__

void Scenario(char const* name, bool enabled, bool attached,
              bool selfBot, bool nullPlayer) {
    instance._playerbotsAIMap.clear();
    sPlayerbotAIConfig.Enabled = enabled;
    Player human;
    Player master;
    Player* player = nullPlayer ? nullptr : &human;
    PlayerbotAI ai;
    ai.master = selfBot ? &human : &master;
    if (player && attached)
        instance._playerbotsAIMap.emplace(player->GetGUID(), &ai);

    bool const real = IsRealPlayer(player);
    bool const self = IsSelfBot(player);
    bool const moduleBot = IsPlayerBot(player);
    bool const humanOnlyShortcut = IsRealPlayer(player);
    bool const originalMoneyEligibility = player && !IsPlayerBot(player);
    std::cout << name << " " << real << " " << self << " "
              << moduleBot << " " << humanOnlyShortcut << " "
              << originalMoneyEligibility << " "
              << instance._playerbotsAIMap.size() << "\n";
}
int main() {
    Scenario("normal_human_enabled", true, false, false, false);
    Scenario("normal_human_disabled", false, false, false, false);
    Scenario("selfbot_visible", true, true, true, false);
    Scenario("selfbot_masked", false, true, true, false);
    Scenario("other_bot_visible", true, true, false, false);
    Scenario("other_bot_masked", false, true, false, false);
    Scenario("null_enabled", true, false, false, true);
    Scenario("null_disabled", false, false, false, true);
}
"""

# 1 = true; columns: real, self, module bot, unsafe 'real' shortcut,
# hypothetical IncludeBots=false money eligibility, retained map size
EXPECTED = {
    "normal_human_enabled": (1, 0, 0, 1, 1, 0),
    "normal_human_disabled": (1, 0, 0, 1, 1, 0),
    "selfbot_visible": (0, 1, 1, 0, 0, 1),
    "selfbot_masked": (1, 0, 0, 1, 1, 1),
    "other_bot_visible": (0, 0, 1, 0, 0, 1),
    "other_bot_masked": (1, 0, 0, 1, 1, 1),
    "null_enabled": (0, 0, 0, 0, 0, 0),
    "null_disabled": (0, 0, 0, 0, 0, 0),
}


def verify_source_chain() -> None:
    world = CORE_WORLD.read_text(encoding="utf-8")
    reloads = CORE_RELOAD.read_text(encoding="utf-8")
    pbconfig = PBCFG.read_text(encoding="utf-8")
    pbmgr = MGR.read_text(encoding="utf-8")
    pb_random = PBRANDOM.read_text(encoding="utf-8")
    pbworld = PBWORLD.read_text(encoding="utf-8")

    core_load = function(world, "void World::LoadConfigSettings(bool reload)")
    core_command = function(reloads, "static bool HandleReloadConfigCommand(ChatHandler* handler)")
    pb_init = function(pbconfig, "bool PlayerbotAIConfig::Initialize()")
    pb_gm_reload = function(pbmgr, 'if (!strcmp(cmd, "reload"))')
    pb_random_reload = function(pb_random, 'if (cmd == "reload")')

    if "sConfigMgr->Reload()" not in core_load or \
       "sScriptMgr->OnBeforeConfigLoad(reload)" not in core_load or \
       "sScriptMgr->OnAfterConfigLoad(reload)" not in core_load:
        raise AssertionError("Pinned core World::LoadConfigSettings chain changed")
    if "sWorld->LoadConfigSettings(true);" not in core_command:
        raise AssertionError("Pinned core .reload config no longer calls world loader")
    if not re.search(
        r'Enabled = sConfigMgr->GetOption<bool>\("Playerbots.Enabled", true\);'
        r'\s*if \(!Enabled\)\s*\{[^{}]*return false;',
        pb_init, re.S
    ):
        raise AssertionError("Playerbots Initialize disabled early return changed")
    for where, src in (("GM reload", pb_gm_reload), ("random reload", pb_random_reload)):
        if src.count("sPlayerbotAIConfig.Initialize();") != 1:
            raise AssertionError(f"Pinned {where} no longer invokes Initialize")
    if "void OnBeforeWorldInitialized() override" not in pbworld or \
       "sPlayerbotAIConfig.Initialize();" not in pbworld:
        raise AssertionError("Pinned Playerbots initial world-config load changed")
    print("SOURCE: core .reload config -> ConfigMgr::Reload / before+after callbacks")
    print("SOURCE: separate Playerbots GM/console reload -> PlayerbotAIConfig::Initialize")
    print("LIMIT: executing separate commands, file reload timing and AI lifetime NOT proven")


def main() -> None:
    mgr = MGR.read_text(encoding="utf-8")
    ai = AI.read_text(encoding="utf-8")
    mod = MODULE.read_text(encoding="utf-8")
    getter = function(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
    is_real = function(ai, "bool IsRealPlayer(Player* player)")
    is_self = function(ai, "bool IsSelfBot(Player* player)")
    mod_bot = function(mod, "    bool IsPlayerBot(Player* player)")
    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in getter:
        raise AssertionError("Pinned getter not masked as expected")
    if "return player && !GET_PLAYERBOT_AI(player);" not in is_real:
        raise AssertionError("Pinned IsRealPlayer changed")
    if "PlayerbotAI* botAI = GET_PLAYERBOT_AI(player);" not in is_self or \
       "return botAI && botAI->GetMaster() == player;" not in is_self:
        raise AssertionError("Pinned IsSelfBot changed")
    if "return GET_PLAYERBOT_AI(player) != nullptr;" not in mod_bot:
        raise AssertionError("Module HonorOverflow bot identity predicate changed")

    verify_source_chain()
    cpp = (CPP.replace("__GETTER__", getter)
           .replace("__IS_REAL__", is_real)
           .replace("__IS_SELF__", is_self)
           .replace("__IS_MODULE_BOT__", mod_bot))
    with tempfile.TemporaryDirectory(prefix="p13-identity-safety-") as d:
        for standard in ("c++17", "c++20"):
            f = pathlib.Path(d) / (standard + ".cpp")
            binary = pathlib.Path(d) / standard
            f.write_text(cpp, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(f), "-o", str(binary)],
                check=True
            )
            actual = {}
            for line in subprocess.check_output([str(binary)], text=True).splitlines():
                m = re.fullmatch(r"([a-z_]+) ([01]) ([01]) ([01]) ([01]) ([01]) ([01])", line)
                if not m:
                    raise AssertionError(f"Unexpected fixture output {line!r}")
                name, *nums = m.groups()
                if name in actual:
                    raise AssertionError("Duplicate case")
                actual[name] = tuple(int(v) for v in nums)
            if actual != EXPECTED:
                raise AssertionError(f"{standard} identity-source mismatch {actual}")
            print(f"PASS: {standard}, {len(actual)} literal getter/human/SelfBot/module cases")
            print("EXPECTED CONDITIONAL SAFETY RED: masked SelfBot == ordinary human by helpers")
            print("POSITIVE: actual unmasked SelfBot excluded, ordinary disabled-PB human eligible")
    print(f"PIN: Playerbots {PIN_PLAYERBOTS} core {PIN_CORE}")
    print("NO LIVE CLAIM: retention synthetic, no real money, reload or gameplay")


if __name__ == "__main__":
    main()
