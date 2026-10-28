#!/usr/bin/env python3
"""P13-R1: actual-source reload-to-config-mask conditional test (NO gameplay).

Extracts *literal* pinned Playerbots getter and module IsPlayerBot functions.
Only the DISABLED prologue of PlayerbotAIConfig::Initialize and the call
sites inside command reload blocks are extracted: full Initialize, config
file reload, command registration, map lifecycle and live timing are NOT
executed. This is not a proof of runtime reachability, live bots or copper.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "src/Systems/HonorOverflow.cpp"
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"
PB = ROOT / "pinned-playerbots"
MGR = PB / "src/Bot/PlayerbotMgr.cpp"
CFG = PB / "src/PlayerbotAIConfig.cpp"
RND = PB / "src/Bot/RandomPlayerbotMgr.cpp"


def function(src: str, marker: str) -> str:
    if src.count(marker) != 1:
        raise AssertionError(f"Expected unique source marker {marker!r}")
    start = src.index(marker)
    begin = src.find("{", start)
    if begin < 0:
        raise AssertionError(f"Missing body for {marker}")
    depth = 0
    for i in range(begin, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(f"Unterminated source: {marker}")


def reload_block(src: str, condition: str) -> str:
    marker = f'if ({condition})'
    if src.count(marker) != 1:
        raise AssertionError(f"Expected one reload block {marker!r}")
    return function(src, marker)


HARNESS = r"""
#include <cstdint>
#include <iostream>
#include <string>
#include <unordered_map>
using uint32 = std::uint32_t;
struct ObjectGuid {
    uint32 id = 7;
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
    ObjectGuid GetGUID() const { return {}; }
};
struct PlayerbotAIBase {
    virtual ~PlayerbotAIBase() = default;
    virtual bool IsBotAI() { return false; }
};
struct PlayerbotAI final : PlayerbotAIBase {
    bool IsBotAI() override { return true; }
};
struct ConfigMgrMock {
    bool loadedEnabled = true;
    template<class T> T GetOption(char const*, T) const {
        return static_cast<T>(loadedEnabled);
    }
};
ConfigMgrMock config;
ConfigMgrMock* sConfigMgr = &config;
#define LOG_INFO(...) do {} while (false)
struct PlayerbotAIConfig {
    bool Enabled = true;
    bool Initialize();
};
PlayerbotAIConfig sPlayerbotAIConfig;
bool PlayerbotAIConfig::Initialize()
{
    __DISABLED_INIT_GUARD__
    // Test-only tail for enabled path; does NOT stand in for full Initialize.
    return true;
}
struct PlayerbotsMgr {
    std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;
    PlayerbotAI* GetPlayerbotAI(Player*);
};
PlayerbotsMgr manager;
PlayerbotsMgr* sPlayerbotsMgr = &manager;
#define GET_PLAYERBOT_AI(player) sPlayerbotsMgr->GetPlayerbotAI(player)
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1

__REAL_GETTER__
__REAL_IS_BOT__

void GMReloadCall() {
    __GM_RELOAD_CALL__
}
void ConsoleReloadCall() {
    __CONSOLE_RELOAD_CALL__
}
void Scenario(char const* label, bool attached, bool initial, bool next,
              bool permitted, bool console) {
    manager._playerbotsAIMap.clear();
    sPlayerbotAIConfig.Enabled = initial;
    config.loadedEnabled = next;
    Player p;
    PlayerbotAI ai;
    if (attached)
        manager._playerbotsAIMap.emplace(p.GetGUID(), &ai);
    bool before = IsPlayerBot(&p);
    bool invoked = false;
    if (console) {
        // Actual pinned console handler rejects commands with Enabled=false.
        if (sPlayerbotAIConfig.Enabled) {
            ConsoleReloadCall();
            invoked = true;
        }
    } else if (permitted) {
        // GM-only branch of actual playerbot command is modeled here.
        GMReloadCall();
        invoked = true;
    }
    bool after = IsPlayerBot(&p);
    std::cout << label << " " << before << " " << after << " "
              << manager._playerbotsAIMap.size() << " "
              << invoked << " " << sPlayerbotAIConfig.Enabled << "\n";
}
int main() {
    Scenario("gm_masked_bot", true, true, false, true, false);
    Scenario("gm_permission_denied", true, true, false, false, false);
    Scenario("console_masked_bot", true, true, false, true, true);
    Scenario("gm_enabled_bot", true, true, true, true, false);
    Scenario("human_disabled", false, true, false, true, false);
    Scenario("unattached_disabled", false, true, false, true, false);
    Scenario("console_already_disabled", true, false, true, true, true);
}
"""

EXPECTED = {
    "gm_masked_bot": (1, 0, 1, 1, 0),
    "gm_permission_denied": (1, 1, 1, 0, 1),
    "console_masked_bot": (1, 0, 1, 1, 0),
    "gm_enabled_bot": (1, 1, 1, 1, 1),
    "human_disabled": (0, 0, 0, 1, 0),
    "unattached_disabled": (0, 0, 0, 1, 0),
    "console_already_disabled": (0, 0, 1, 0, 0),
}


def main() -> None:
    module = MOD.read_text(encoding="utf-8")
    conf = CONF.read_text(encoding="utf-8")
    mgr = MGR.read_text(encoding="utf-8")
    cfg = CFG.read_text(encoding="utf-8")
    rnd = RND.read_text(encoding="utf-8")
    get_ai = function(mgr, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
    is_bot = function(module, "    bool IsPlayerBot(Player* player)")
    init = function(cfg, "bool PlayerbotAIConfig::Initialize()")
    guard_match = re.search(
        r'Enabled = sConfigMgr->GetOption<bool>\("Playerbots.Enabled", true\);'
        r'\s*if \(!Enabled\)\s*\{[^{}]*return false;\s*\}',
        init,
        re.S,
    )
    if not guard_match:
        raise AssertionError("Pinned Initialize disabled early return changed")
    if "_playerbotsAIMap.find(player->GetGUID())" not in get_ai:
        raise AssertionError("Pinned getter map lookup changed")
    if "if (!(sPlayerbotAIConfig.Enabled) || !player)" not in get_ai:
        raise AssertionError("Getter no longer masks attached bots")
    if "GET_PLAYERBOT_AI(player) != nullptr" not in is_bot:
        raise AssertionError("Module bot predicate changed")

    gm = reload_block(mgr, '!strcmp(cmd, "reload")')
    console = reload_block(rnd, 'cmd == "reload"')
    if "master->CanBeGameMaster()" not in gm:
        raise AssertionError("GM branch permission check missing")
    if "if (!sPlayerbotAIConfig.Enabled)" not in function(
        rnd, "bool RandomPlayerbotMgr::HandlePlayerbotConsoleCommand("
    ):
        raise AssertionError("Console enabled precondition changed")
    for label, block in (("GM", gm), ("console", console)):
        if block.count("sPlayerbotAIConfig.Initialize();") != 1:
            raise AssertionError(f"{label} no longer calls Initialize exactly once")
        if "_playerbotsAIMap" in block or "RemovePlayerBotData" in block:
            raise AssertionError(f"{label} reload now directly clears an AI map")

    # This is a distinct source/default discrepancy, NOT the effective owner config.
    if not re.search(r"(?m)^NaxxramasCore\.HonorOverflow\.Enabled\s*=\s*1\s*$", conf):
        raise AssertionError("Distributed HonorOverflow default no longer equals 1")
    if '"NaxxramasCore.HonorOverflow.Enabled",\n                true' not in module:
        raise AssertionError("HonorOverflow fallback enabled-by-default changed")
    print("AUDIT: distributed HonorOverflow Enabled=1 and C++ absent-option fallback=true")
    print("AUDIT: owner's actual live effective configuration is UNKNOWN")

    source = (HARNESS
        .replace("__DISABLED_INIT_GUARD__", guard_match.group())
        .replace("__REAL_GETTER__", get_ai)
        .replace("__REAL_IS_BOT__", is_bot)
        .replace("__GM_RELOAD_CALL__", "sPlayerbotAIConfig.Initialize();")
        .replace("__CONSOLE_RELOAD_CALL__", "sPlayerbotAIConfig.Initialize();"))

    with tempfile.TemporaryDirectory(prefix="p13-reload-transition-") as d:
        for standard in ("c++17", "c++20"):
            cpp = pathlib.Path(d) / ("transition_" + standard + ".cpp")
            binary = pathlib.Path(d) / ("transition_" + standard)
            cpp.write_text(source, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-Wall", "-Wextra", "-Werror",
                 "-pedantic", "-O1", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(cpp), "-o", str(binary)],
                check=True,
            )
            actual = {}
            for line in subprocess.check_output([str(binary)], text=True).splitlines():
                m = re.fullmatch(r"([a-z_]+) ([01]) ([01]) (\d+) ([01]) ([01])", line)
                if not m:
                    raise AssertionError(f"Unexpected program output {line!r}")
                key, *values = m.groups()
                if key in actual:
                    raise AssertionError("Duplicate case " + key)
                actual[key] = tuple(map(int, values))
            if actual != EXPECTED:
                raise AssertionError(f"{standard} transition oracle differs: {actual}")
            print(f"PASS: {standard}, {len(actual)} conditional transition cases")
            print("EXPECTED CONDITIONAL RED: config-masked retained map bot looks human")
    print("LIMITATION: code paths are source-consistent, not a verified live reload")
    print("No honor granted, no live bot, no SQL, no production code change")


if __name__ == "__main__":
    main()
