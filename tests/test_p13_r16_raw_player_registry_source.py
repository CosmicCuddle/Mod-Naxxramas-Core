#!/usr/bin/env python3
"""P13-R16 original Player registry and source-level lifecycle inventory.

Read ONLY pinned repository commits; run C++17/C++20/UBSan dummy registry.
No real Player dereference after retirement, no concurrent UAF, no Worldserver.
Usage: python3 -I tests/test_p13_r16_raw_player_registry_source.py . pinned-core
"""
from __future__ import annotations
import pathlib
import subprocess
import sys
import tempfile

MOD_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD = "src/Systems/HonorOverflow.cpp"
ACCESS_CPP = "src/server/game/Globals/ObjectAccessor.cpp"
ACCESS_H = "src/server/game/Globals/ObjectAccessor.h"
PLAYER = "src/server/game/Entities/Player/Player.cpp"
SCRIPT_MGR = "src/server/game/Scripting/ScriptMgr.h"
WORLD = "src/server/game/World/World.cpp"
MAPMGR = "src/server/game/Maps/MapMgr.cpp"
MISC_CPP = "src/server/game/Scripting/ScriptDefines/MiscScript.cpp"
MISC_H = "src/server/game/Scripting/ScriptDefines/MiscScript.h"
BLOBS = {
 MOD: "d4f70c511ac5a3e32c7e6b8f913d095915da707c",
 ACCESS_CPP: "8b15ce734d8f6624a29fe12e23c6917d77e1919d",
 ACCESS_H: "d7d2aaa8a723770686512f98498339d9219d9c1d",
 PLAYER: "138e7eab4905ec366338a54cc18e6cfe749a3670",
 SCRIPT_MGR: "7f0f30d3ca46cb290636c33ca8e1b2b9c0ffa1f8",
 WORLD: "a001fcaf3b00fdecefb80f95f1ec3c1ae14116fe",
 MAPMGR: "46f627a10515001f7edfd956ccdbf4359a267400",
 MISC_CPP: "a41a3f0d9f48d0c4319a585c591ba7ec722fc37b",
 MISC_H: "9ed20ab2304fed3bceb20a7e8dc704e529897365",
}

def git(repo: pathlib.Path, *args: str, no_match: bool = False) -> str:
    x = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if x.returncode not in ((0, 1) if no_match else (0,)):
        raise RuntimeError(f"git {args!r} failed: {x.stderr[:500]}")
    return x.stdout.strip()

def function(text: str, signature: str) -> str:
    start = text.index(signature)
    left = text.index("{", start)
    depth = 0
    for pos in range(left, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos + 1]
    raise AssertionError(f"unbalanced original function {signature}")

def contract(mod, cpp, h, player, mgr, world, mapmgr, misc_cpp, misc_h):
    ins = function(cpp, "void HashMapHolder<T>::Insert(T* o)")
    rem = function(cpp, "void HashMapHolder<T>::Remove(T* o)")
    find = function(cpp, "T* HashMapHolder<T>::Find(ObjectGuid guid)")
    find_player = function(cpp, "Player* ObjectAccessor::FindPlayer(ObjectGuid const guid)")
    find_connected = function(cpp, "Player* ObjectAccessor::FindConnectedPlayer(ObjectGuid const guid)")
    get_container = function(cpp, "auto HashMapHolder<T>::GetContainer() -> MapType&")
    get_lock = function(cpp, "std::shared_mutex* HashMapHolder<T>::GetLock()")
    assert "ACCESS LIKE THAT IS NOT THREAD SAFE" in h
    assert "when using this, you must use the hashmapholder's lock" in h
    assert "static T* Find(ObjectGuid guid);" in h
    assert "static std::shared_mutex* GetLock();" in h
    assert "std::shared_lock<std::shared_mutex> lock(*GetLock());" in find
    assert "return (itr != GetContainer().end()) ? itr->second : nullptr;" in find
    assert "std::unique_lock<std::shared_mutex> lock(*GetLock());" in ins
    assert "std::unique_lock<std::shared_mutex> lock(*GetLock());" in rem
    assert "GetContainer()[o->GetGUID()] = o;" in ins
    assert "GetContainer().erase(o->GetGUID());" in rem
    assert "Player* player = HashMapHolder<Player>::Find(guid);" in find_player
    assert "return player && player->IsInWorld() ? player : nullptr;" in find_player
    assert "return HashMapHolder<Player>::Find(guid);" in find_connected
    assert "OnConstructPlayer(this);" in player and "OnDestructPlayer(this);" in player
    ctor = function(player, "Player::Player(WorldSession* session)")
    dtor = function(player, "Player::~Player()")
    assert "sScriptMgr->OnConstructPlayer(this);" in ctor
    assert "sScriptMgr->OnDestructPlayer(this);" in dtor
    assert "void OnConstructPlayer(Player* origin);" in mgr
    assert "void OnDestructPlayer(Player* origin);" in mgr
    w = function(world, "void World::Update(uint32 diff)")
    assert w.index("sWorldSessionMgr->UpdateSessions(diff);") < w.index("sMapMgr->Update(diff);") < w.index("sBattlegroundMgr->Update(diff);")
    m = function(mapmgr, "void MapMgr::Update(uint32 diff)")
    assert "m_updater.wait();" in m
    assert "m_updater.schedule_update" in m
    construct = function(misc_cpp, "void ScriptMgr::OnConstructPlayer(Player* origin)")
    destruct = function(misc_cpp, "void ScriptMgr::OnDestructPlayer(Player* origin)")
    assert "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_CONSTRUCT_PLAYER, script->OnConstructPlayer(origin));" in construct
    assert "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_DESTRUCT_PLAYER, script->OnDestructPlayer(origin));" in destruct
    assert "MISCHOOK_ON_CONSTRUCT_PLAYER," in misc_h and "MISCHOOK_ON_DESTRUCT_PLAYER," in misc_h
    assert "virtual void OnConstructPlayer(Player* /*origin*/) { }" in misc_h
    assert "virtual void OnDestructPlayer(Player* /*origin*/) { }" in misc_h
    assert "ScriptRegistry<MiscScript>::AddScript(this, std::move(enabledHooks));" in misc_cpp
    assert "std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;" in mod
    assert "std::unordered_map<ObjectGuid::LowType, BattlegroundHonorSummary> BattlegroundHonorSummaries;" in mod
    return ins, rem, find, get_container, get_lock

def negative_guards(src):
    candidates = [
        ("lookup lock removed", 1, "std::shared_lock<std::shared_mutex> lock(*GetLock());", "/* unguarded */"),
        ("lookup now returns ownership wrapper", 1, "return (itr != GetContainer().end()) ? itr->second : nullptr;", "return nullptr;"),
        ("registry removal suppressed", 1, "GetContainer().erase(o->GetGUID());", "/* no remove */"),
        ("lookup warning erased", 2, "ACCESS LIKE THAT IS NOT THREAD SAFE", "THREAD SAFE"),
        ("Player destructor signal removed", 3, "sScriptMgr->OnDestructPlayer(this);", "/* removed */"),
        ("Player constructor signal removed", 3, "sScriptMgr->OnConstructPlayer(this);", "/* removed */"),
        ("script lifecycle declaration removed", 4, "void OnDestructPlayer(Player* origin);", "/* no hook */"),
        ("map update join removed", 6, "m_updater.wait();", "/* no join */"),
        ("HonorOverflow shared map state changed", 0, "std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;",
         "/* replaced state */"),
        ("MiscScript constructor dispatch bypassed", 7, "CALL_ENABLED_HOOKS(MiscScript, MISCHOOK_ON_CONSTRUCT_PLAYER, script->OnConstructPlayer(origin));", "/* missing dispatch */"),
        ("MiscScript destructor hook disabled", 8, "MISCHOOK_ON_DESTRUCT_PLAYER,", "/* no destructor hook */"),
    ]
    for name, i, old, replacement in candidates:
        assert old in src[i], name
        mutated = src.copy()
        mutated[i] = mutated[i].replace(old, replacement, 1)
        try:
            contract(*mutated)
        except (ValueError, AssertionError):
            print("CAUGHT R16 SOURCE DRIFT: " + name)
        else:
            raise AssertionError("missed mutant: " + name)

def lifecycle_inventory(core: pathlib.Path):
    # Search immutable tracked source, not unreliable GitHub indexed code search.
    for name in ("OnConstructPlayer", "OnDestructPlayer"):
        output = git(core, "grep", "-I", "-n", "-F", name, CORE_SHA, "--", "src", "modules", no_match=True)
        found = []
        for match in output.splitlines():
            if not match:
                continue
            parts = match.split(":", 3)
            assert len(parts) == 4 and parts[0] == CORE_SHA
            path = parts[1]
            if path.endswith((".cpp", ".cc", ".h", ".hpp", ".cxx", ".hxx")):
                found.append((path, int(parts[2]), parts[3].strip()))
        assert len(found) >= 2 and len(found) < 100, (name, found)
        for path, line, detail in found:
            print(f"LIFECYCLE-HOOK {name} {path}:{line}: {detail[:170]}")
        definition = [(path, line) for path, line, detail in found
                      if "ScriptMgr::" + name + "(" in detail]
        print(f"HOOK-SUMMARY {name} source_lines={len(found)} scriptmgr_definition_lines={len(definition)}")
        # Report what the tree proves, WITHOUT assuming a working script hook.
        if definition:
            print(f"FINDING {name}: definition reference(s) exist in pinned tracked source")
        else:
            print(f"LIMIT {name}: no direct ScriptMgr method definition spelling in scanned tracked source")
    print("PASS: R16 actual pinned construct/destruct source-name inventory")

PREFIX = r"""
#include <cstdint>
#include <iostream>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <stdexcept>
#include <type_traits>
#include <unordered_map>
using uint32 = std::uint32_t;
struct ObjectGuid {
    uint32 value;
    bool operator==(ObjectGuid const& other) const { return value == other.value; }
};
namespace std {
template<> struct hash<ObjectGuid> {
    size_t operator()(ObjectGuid const& x) const noexcept { return hash<uint32>()(x.value); }
};
}
struct Player {
    ObjectGuid guid;
    bool online = true;
    ObjectGuid GetGUID() const { return guid; }
    bool IsInWorld() const { return online; }
};
struct MotionTransport { ObjectGuid guid; ObjectGuid GetGUID() const { return guid; } };
template<class T>
class HashMapHolder {
public:
    using MapType = std::unordered_map<ObjectGuid, T*>;
    static void Insert(T*);
    static void Remove(T*);
    static T* Find(ObjectGuid);
    static MapType& GetContainer();
    static std::shared_mutex* GetLock();
};
"""
SUFFIX = r"""
int main() {
    try {
        Player first {{41}, true};
        Player second {{41}, true};
        HashMapHolder<Player>::Insert(&first);
        Player* oldView = HashMapHolder<Player>::Find({41});
        if (oldView != &first) throw std::runtime_error("first lookup failed");
        HashMapHolder<Player>::Remove(&first);
        // Retain the returned pointer value for equality only; do not dereference or free it.
        HashMapHolder<Player>::Insert(&second);
        Player* currentView = HashMapHolder<Player>::Find({41});
        if (currentView != &second || oldView == currentView)
            throw std::runtime_error("same-GUID replacement did not yield new raw pointer");
        HashMapHolder<Player>::Remove(&second);
        if (HashMapHolder<Player>::Find({41}) != nullptr)
            throw std::runtime_error("removed GUID still in original registry");
        std::cout << "PASS: original locked HashMapHolder methods return non-owning raw Player pointers\n";
        std::cout << "PASS: dummy SAME GUID can map to a different live Player object after removal/reinsert\n";
        std::cout << "LIMIT: no lifetime safety implied, no UAF, no concurrent lookup/destroy or native Worldserver\n";
        return 0;
    } catch (std::exception const& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
"""

def compile_dummy(parts):
    ins, rem, find, container, lock = parts
    source = PREFIX + "\n".join("template<class T>\n" + method for method in [ins, rem, find, container, lock]) + SUFFIX
    with tempfile.TemporaryDirectory(prefix="p13_r16_") as d:
        p = pathlib.Path(d)
        file = p / "registry.cpp"
        file.write_text(source)
        for label, std, args in (
            ("c++17", "c++17", []),
            ("c++20", "c++20", []),
            ("c++20-ubsan", "c++20", ["-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all"]),
        ):
            dest = p / label
            subprocess.run(["g++", "-std=" + std, "-Wall", "-Wextra", "-Werror",
                            "-pedantic", "-pthread", *args, str(file), "-o", str(dest)], check=True)
            output = subprocess.check_output([str(dest)], text=True)
            assert output.count("PASS:") == 2 and "LIMIT: no lifetime safety implied" in output
            print("PASS: R16 " + label + " original registry method dummy pointer witness")

def main(args):
    if len(args) != 3:
        print(__doc__)
        return 2
    mod, core = map(pathlib.Path, args[1:])
    git(mod, "merge-base", "--is-ancestor", MOD_SHA, "HEAD")
    assert git(core, "rev-parse", "HEAD") == CORE_SHA
    for path, blob in BLOBS.items():
        root, rev = (mod, MOD_SHA) if path == MOD else (core, CORE_SHA)
        assert git(root, "rev-parse", rev + ":" + path) == blob, path
    assert git(mod, "rev-parse", "HEAD:" + MOD) == BLOBS[MOD]
    sources = [(mod / MOD).read_text()] + [(core / p).read_text()
               for p in (ACCESS_CPP, ACCESS_H, PLAYER, SCRIPT_MGR, WORLD, MAPMGR, MISC_CPP, MISC_H)]
    parts = contract(*sources)
    print("PASS: R16 exactly nine pinned original source blobs and registry/world/misc dispatch guards")
    negative_guards(sources)
    lifecycle_inventory(core)
    compile_dummy(parts)
    print("PASS: R16 scoped original-source registry and world-tick seam research")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print("FAIL: " + str(error))
        sys.exit(1)
