#!/usr/bin/env python3
"""P13-R8: original HonorOverflow reloadable globals and map-worker source audit.

Distinct from R1 (Playerbots config-masked identity) and R7 (unordered_map
container safety). Extract and EXECUTE the original config listener's body
only in SERIAL, disposable C++17/20 UBSan cases, and verify pinned core
reload/worker source calls plus the original global read/write sites.

DO NOT use this test as proof that reload actually overlaps map tasks.
DO NOT deliberately execute concurrent plain-variable data races.
"""
from __future__ import annotations

import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "src/Systems/HonorOverflow.cpp"
CORE = ROOT / "pinned-core"
WORLD = CORE / "src/server/game/World/World.cpp"
MAPMGR = CORE / "src/server/game/Maps/MapMgr.cpp"
UPDATER = CORE / "src/server/game/Maps/MapUpdater.cpp"
MAP = CORE / "src/server/game/Maps/Map.cpp"
PLAYER = CORE / "src/server/game/Entities/Player/PlayerUpdates.cpp"

GLOBALS = (
    "bool HonorOverflowEnabled = true;",
    "uint32 HonorOverflowCopperPerHonor = 10;",
    "bool HonorOverflowNotify = true;",
    "bool HonorOverflowIncludeBots = false;",
)
OPTIONS = (
    '"NaxxramasCore.HonorOverflow.Enabled"',
    '"NaxxramasCore.HonorOverflow.CopperPerHonor"',
    '"NaxxramasCore.HonorOverflow.Notify"',
    '"NaxxramasCore.HonorOverflow.IncludeBots"',
)


def method(source: str, signature: str) -> str:
    if source.count(signature) != 1:
        raise AssertionError("Expected exactly one signature: " + signature)
    i = source.index(signature)
    opening = source.find("{", i + len(signature))
    if opening == -1:
        raise AssertionError("Missing body for " + signature)
    depth = 0
    for k in range(opening, len(source)):
        if source[k] == "{":
            depth += 1
        elif source[k] == "}":
            depth -= 1
            if depth == 0:
                return source[i:k + 1]
    raise AssertionError("Unterminated body for " + signature)


def check_module(source: str) -> str:
    # A future code change MUST reopen the finding rather than being silently
    # mislabelled unsynchronised by this fixture.
    for token in GLOBALS:
        if source.count(token) != 1:
            raise AssertionError("Plain mutable global source drift: " + token)
    for guard in ("std::atomic", "std::mutex", "std::shared_mutex",
                  "std::lock_guard", "std::unique_lock", "std::scoped_lock",
                  "thread_local"):
        if guard in source:
            raise AssertionError("Possible synchronization/ownership change: " + guard)

    reload_body = method(source, "void OnBeforeConfigLoad(bool /*reload*/) override")
    for name, option in zip(
        ("HonorOverflowEnabled", "HonorOverflowCopperPerHonor",
         "HonorOverflowNotify", "HonorOverflowIncludeBots"), OPTIONS
    ):
        if reload_body.count(name + " =") != 1 or reload_body.count(option) != 1:
            raise AssertionError("Original config writer drift for " + name)

    process = method(source, "void ProcessHonorOverflow(Player* player, bool forceBattlegroundSummary = false)")
    summary = method(source, "void SendBattlegroundSummary(Player* player)")
    for needle in ("!HonorOverflowEnabled", "HonorOverflowCopperPerHonor == 0",
                   "!HonorOverflowIncludeBots", "* HonorOverflowCopperPerHonor",
                   "!HonorOverflowNotify"):
        target = summary if needle == "!HonorOverflowNotify" else process
        if needle not in target:
            raise AssertionError("Original module reader drift: " + needle)
    if "void OnPlayerUpdate(Player* player, uint32 /*diff*/) override" not in source or \
       "ProcessHonorOverflow(player);" not in source:
        raise AssertionError("Module player-update entry point changed")
    print("MODULE: four plain globals are assigned in original config hook")
    print("MODULE: update and summary paths consume these same globals")
    return reload_body


def check_core(sources: dict[str, str]) -> None:
    load = method(sources["world"], "void World::LoadConfigSettings(bool reload)")
    for token in ("sConfigMgr->Reload()", "sScriptMgr->OnBeforeConfigLoad(reload);"):
        if token not in load:
            raise AssertionError("Pinned world config reload callback drift: " + token)
    mgr = method(sources["mapmgr"], "void MapMgr::Update(uint32 diff)")
    for token in ("m_updater.schedule_update(*iter->second", "m_updater.wait();"):
        if token not in mgr:
            raise AssertionError("Pinned map scheduling boundary drift: " + token)
    activation = method(sources["updater"], "void MapUpdater::activate(std::size_t num_threads)")
    worker = method(sources["updater"], "void MapUpdater::WorkerThread()")
    if "std::thread(&MapUpdater::WorkerThread, this)" not in activation or \
       "request->call();" not in worker or \
       "m_map.Update(m_diff, s_diff);" not in sources["updater"]:
        raise AssertionError("Pinned map workers or map request call changed")
    if "player->Update(s_diff);" not in method(
        sources["map"], "void Map::Update(const uint32 t_diff, const uint32 s_diff, bool  /*thread*/)"
    ):
        raise AssertionError("Pinned Map::Update player call changed")
    if "sScriptMgr->OnPlayerUpdate(this, p_time);" not in method(
        sources["player"], "void Player::Update(uint32 p_time)"
    ):
        raise AssertionError("Pinned Player::Update player hook changed")
    print("PINNED CORE: World config calls OnBeforeConfigLoad; map workers call Player::Update")
    print("PINNED CORE: MapMgr::Update waits for scheduled tasks; actual reload timing not settled")


CPP = r"""
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
using uint32 = std::uint32_t;

__GLOBALS__

struct ConfigMgrMock {
    bool enabled = true, notify = true, includeBots = false;
    uint32 rate = 10;
    template<class T> T GetOption(char const* key, T fallback) const {
        std::string name(key);
        if (name == "NaxxramasCore.HonorOverflow.Enabled") return static_cast<T>(enabled);
        if (name == "NaxxramasCore.HonorOverflow.CopperPerHonor") return static_cast<T>(rate);
        if (name == "NaxxramasCore.HonorOverflow.Notify") return static_cast<T>(notify);
        if (name == "NaxxramasCore.HonorOverflow.IncludeBots") return static_cast<T>(includeBots);
        return fallback;
    }
};
ConfigMgrMock config;
ConfigMgrMock* sConfigMgr = &config;

struct ConfigBase {
    virtual ~ConfigBase() = default;
    virtual void OnBeforeConfigLoad(bool) = 0;
};
struct ConfigListener : ConfigBase {
__ORIGINAL_HOOK__
};

void check(bool enabled, uint32 rate, bool notify, bool bots) {
    assert(HonorOverflowEnabled == enabled);
    assert(HonorOverflowCopperPerHonor == rate);
    assert(HonorOverflowNotify == notify);
    assert(HonorOverflowIncludeBots == bots);
}
int main() {
    ConfigListener listener;
    check(true, 10, true, false);
    listener.OnBeforeConfigLoad(false);
    check(true, 10, true, false);
    config.enabled = false;
    config.rate = 55;
    config.notify = false;
    config.includeBots = true;
    listener.OnBeforeConfigLoad(true);
    check(false, 55, false, true);
    config.enabled = true;
    config.rate = 0;
    config.notify = true;
    config.includeBots = false;
    listener.OnBeforeConfigLoad(true);
    check(true, 0, true, false);
    std::cout << "PASS: literal module config hook; serial initial/load/two reload snapshots\n";
}
"""


def check_negative_guards(source: str, sources: dict[str, str]) -> None:
    mutants = [
        (source.replace(GLOBALS[0], "std::atomic<bool> HonorOverflowEnabled{true};"),
         "plain global replaced with atomic"),
        (source.replace("!HonorOverflowIncludeBots", "false /*removed inclusion read*/"),
         "module reader absent"),
    ]
    for mutated, label in mutants:
        try:
            check_module(mutated)
        except AssertionError:
            print("CAUGHT source drift: " + label)
        else:
            raise AssertionError("Guard missed " + label)
    changed = dict(sources)
    changed["world"] = sources["world"].replace(
        "sScriptMgr->OnBeforeConfigLoad(reload);",
        "/* callback removed */")
    try:
        check_core(changed)
    except AssertionError:
        print("CAUGHT source drift: world reload callback absent")
    else:
        raise AssertionError("Guard missed world callback removal")



def check_standard_ingress(sources: dict[str, str]) -> None:
    """Source-guard the standard pinned reload ingress paths and tick order.

    These checks establish sequential callbacks for the IN-SCOPE standard
    ingress paths; they do not establish that no other caller can invoke
    World::LoadConfigSettings or prove owner-runtime behavior.
    """
    update = method(sources["world"], "void World::Update(uint32 diff)")
    stages = (
        "sWorldSessionMgr->UpdateSessions(diff);",
        "sMapMgr->Update(diff);",
        "ProcessCliCommands();",
        "sScriptMgr->OnWorldUpdate(diff);",
    )
    positions = [update.index(token) for token in stages]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise AssertionError("World tick order drift: session -> map -> CLI -> world scripts")
    mgr = method(sources["mapmgr"], "void MapMgr::Update(uint32 diff)")
    schedule = mgr.index("m_updater.schedule_update(*iter->second")
    done = mgr.index("m_updater.wait();")
    if schedule >= done:
        raise AssertionError("Map-worker completion/wait boundary drift")

    config = method(sources["reload"], "static bool HandleReloadConfigCommand(ChatHandler* handler)")
    if "sWorld->LoadConfigSettings(true);" not in config:
        raise AssertionError("Registered config reload no longer calls World::LoadConfigSettings")
    if '"config",                        HandleReloadConfigCommand' not in sources["reload"]:
        raise AssertionError("Registered reload config command binding drift")
    # .reload all intentionally DOES NOT call the config-reload handler.
    reload_all = method(sources["reload"], "static bool HandleReloadAllCommand(ChatHandler* handler)")
    if "HandleReloadConfigCommand" in reload_all or "LoadConfigSettings(" in reload_all:
        raise AssertionError("Reload-all command now also reloads config; re-review timing")
    world_cli = method(sources["world"], "void World::ProcessCliCommands()")
    if "_cliCmdQueue.next(command)" not in world_cli or \
       "handler.ParseCommands(command->m_command);" not in world_cli:
        raise AssertionError("Queued CLI command dispatch drift")
    for entry, marker in (
        ("cli", "sWorld->QueueCliCommand(new CliCommandHolder("),
        ("ra", "sWorld->QueueCliCommand(cmd);"),
        ("soap", "sWorld->QueueCliCommand(new CliCommandHolder("),
    ):
        if marker not in sources[entry]:
            raise AssertionError("Standard " + entry + " command queue drift")

    # GM in-game messages are unsafe opcodes, handled during the world
    # session update, rather than directly within the map-worker phase.
    if "DEFINE_HANDLER(CMSG_MESSAGECHAT," not in sources["opcodes"]:
        raise AssertionError("Missing chat opcode registration")
    chat_registration = next(
        line for line in sources["opcodes"].splitlines()
        if "DEFINE_HANDLER(CMSG_MESSAGECHAT," in line
    )
    if "PROCESS_THREADUNSAFE" not in chat_registration or \
       "&WorldSession::HandleMessagechatOpcode" not in chat_registration:
        raise AssertionError("GM chat opcode processing-place drift")
    map_filter = method(sources["session"], "bool MapSessionFilter::Process(WorldPacket* packet)")
    if "if (opHandle->ProcessingPlace == PROCESS_THREADUNSAFE)" not in map_filter or \
       "return false;" not in map_filter:
        raise AssertionError("Map packet filter no longer excludes thread-unsafe chat")
    world_filter = method(sources["session"], "bool WorldSessionFilter::Process(WorldPacket* packet)")
    if "if (opHandle->ProcessingPlace == PROCESS_THREADUNSAFE)" not in world_filter or \
       "return true;" not in world_filter:
        raise AssertionError("World packet filter thread-unsafe processing drift")
    sessions = method(sources["sessions"], "void WorldSessionMgr::UpdateSessions(uint32 const diff)")
    if "WorldSessionFilter updater(pSession);" not in sessions or \
       "pSession->Update(diff, updater)" not in sessions:
        raise AssertionError("World-session packet-processing source drift")
    map_update = method(sources["map"], "void Map::Update(const uint32 t_diff, const uint32 s_diff, bool  /*thread*/)")
    if "MapSessionFilter updater(session);" not in map_update or \
       "session->Update(s_diff, updater);" not in map_update:
        raise AssertionError("Map-session packet filter use drift")
    if "ChatHandler(this).ParseCommands(msg.c_str())" not in sources["chat_handler"]:
        raise AssertionError("GM chat does not reach ChatHandler::ParseCommands")
    # The main loop calls World::Update on its game-loop thread.
    if "sWorld->Update(diff);" not in sources["main"] or \
       "WorldUpdateLoop();" not in sources["main"]:
        raise AssertionError("World update-loop root drift")

    print("STANDARD ROUTES: in-game GM chat -> world session before map; CLI/RA/SOAP -> queued world CLI after map")
    print("STANDARD TICK: MapUpdater waits for completion before queued config reload")
    print("STANDARD RESULT: no map-worker/config reload overlap in inspected normal ingress")
    print("LIMIT: direct/custom/other threads invoking reload not exhaustively audited")


def check_standard_ingress_negative(sources: dict[str, str]) -> None:
    chat_line = next(line for line in sources["opcodes"].splitlines()
                     if "DEFINE_HANDLER(CMSG_MESSAGECHAT," in line)
    edits = (
        ("opcodes", chat_line, chat_line.replace("PROCESS_THREADUNSAFE", "PROCESS_THREADSAFE"),
         "GM chat processing class"),
        ("world", "ProcessCliCommands();", "/* unqueued */", "world CLI phase"),
        ("mapmgr", "m_updater.wait();", "/* no wait */", "map worker join"),
        ("reload", "sWorld->LoadConfigSettings(true);", "/* no reload */", "config command"),
        ("ra", "sWorld->QueueCliCommand(cmd);", "/* direct RA */", "remote access queued command"),
    )
    for key, before, after, label in edits:
        if before not in sources[key]:
            raise AssertionError("Missing negative-test mutation anchor: " + label)
        changed = dict(sources)
        changed[key] = sources[key].replace(before, after, 1)
        try:
            check_standard_ingress(changed)
        except (AssertionError, StopIteration, ValueError):
            print("CAUGHT standard-route drift: " + label)
        else:
            raise AssertionError("Drift checker missed " + label)


def main() -> None:
    module_source = MOD.read_text(encoding="utf-8")
    sources = {
        name: path.read_text(encoding="utf-8")
        for name, path in (
            ("world", WORLD), ("mapmgr", MAPMGR), ("updater", UPDATER),
            ("map", MAP), ("player", PLAYER),
            ("reload", CORE / "src/server/scripts/Commands/cs_reload.cpp"),
            ("cli", CORE / "src/server/apps/worldserver/CommandLine/CliRunnable.cpp"),
            ("ra", CORE / "src/server/apps/worldserver/RemoteAccess/RASession.cpp"),
            ("soap", CORE / "src/server/apps/worldserver/ACSoap/ACSoap.cpp"),
            ("opcodes", CORE / "src/server/game/Server/Protocol/Opcodes.cpp"),
            ("session", CORE / "src/server/game/Server/WorldSession.cpp"),
            ("sessions", CORE / "src/server/game/Server/WorldSessionMgr.cpp"),
            ("chat_handler", CORE / "src/server/game/Handlers/ChatHandler.cpp"),
            ("main", CORE / "src/server/apps/worldserver/Main.cpp"),
        )
    }
    hook = check_module(module_source)
    check_core(sources)
    check_negative_guards(module_source, sources)
    check_standard_ingress(sources)
    check_standard_ingress_negative(sources)
    program = CPP.replace("__GLOBALS__", "\n".join(GLOBALS)).replace("__ORIGINAL_HOOK__", hook)
    with tempfile.TemporaryDirectory(prefix="p13-r8-config-") as directory:
        for standard in ("c++17", "c++20"):
            src = pathlib.Path(directory) / (standard + ".cpp")
            exe = pathlib.Path(directory) / standard
            src.write_text(program, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + standard, "-O1", "-Wall", "-Wextra",
                 "-Werror", "-pedantic", "-fsanitize=undefined",
                 "-fno-sanitize-recover=all", str(src), "-o", str(exe)],
                check=True,
            )
            expected = "PASS: literal module config hook; serial initial/load/two reload snapshots"
            result = subprocess.check_output([str(exe)], text=True).strip()
            if result != expected:
                raise AssertionError("Unexpected compiled source result: " + result)
            print("PASS: " + standard + " original hook, 4 variables, serial snapshots")
    print("FINDING: unsynchronized plain read/write sites exist in pinned source")
    print("UNPROVEN: actual reload overlap with map workers, data race or live incident")
    print("NOT an owner config change, thread safety fix, production build or gameplay test")


if __name__ == "__main__":
    main()
