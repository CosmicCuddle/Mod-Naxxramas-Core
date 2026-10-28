#!/usr/bin/env python3
"""Source-backed, test-only ForcedPvP reload / map-worker race witness.

This is NOT a fix or proof the owner's reload and map callbacks overlap.
It extracts the exact original namespace bool declarations and full
IsConfiguredForcedPvPZone function from protected-main source. Only the
test harness creates a simultaneous writer/reader schedule.

Negative: original non-atomic bools must produce a ThreadSanitizer race.
Positive control: test-only atomic projection must remain TSAN-clean.
Neither projection is production source or proposed game-policy approval.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "src/Systems/ForcedPvP.cpp"
NAMES = (
    "ForcedPvPEnabled",
    "ForcedPvPSilithus",
    "ForcedPvPEasternPlaguelands",
    "ForcedPvPIncludeBots",
    "ForcedPvPNotify",
)
KEY_SUFFIXES = (
    "Enabled",
    "Silithus",
    "EasternPlaguelands",
    "IncludeBots",
    "Notify",
)

CPP = r"""
#include <atomic>
#include <cstdint>
#include <iostream>
#include <thread>
#include <vector>
using uint32 = std::uint32_t;
constexpr uint32 AREA_SILITHUS = 1; // mock symbolic fixture ID, not gameplay data
constexpr uint32 AREA_EASTERN_PLAGUELANDS = 2;
namespace {
@DECLARATIONS@
@REAL_FUNCTION@
}
int main() {
    std::atomic<bool> start{false};
    std::atomic<int> ready{0};
    std::atomic<std::uint64_t> result{0};
    std::vector<std::thread> readers;
    readers.reserve(8);
    for (int index = 0; index < 8; ++index) {
        readers.emplace_back([&] {
            ready.fetch_add(1, std::memory_order_release);
            while (!start.load(std::memory_order_acquire)) std::this_thread::yield();
            std::uint64_t total = 0;
            for (int i = 0; i < 100000; ++i) {
                total += IsConfiguredForcedPvPZone(AREA_SILITHUS) ? 1 : 0;
                total += IsConfiguredForcedPvPZone(AREA_EASTERN_PLAGUELANDS) ? 1 : 0;
            }
            result.fetch_add(total, std::memory_order_relaxed);
        });
    }
    std::thread writer([&] {
        while (ready.load(std::memory_order_acquire) != 8) std::this_thread::yield();
        start.store(true, std::memory_order_release);
        for (int i = 0; i < 100000; ++i) {
            // Same five globals written by the exact source config hook.
            ForcedPvPEnabled = (i & 1) == 0;
            ForcedPvPSilithus = (i & 1) != 0;
            ForcedPvPEasternPlaguelands = (i & 1) == 0;
            ForcedPvPIncludeBots = (i & 1) != 0;
            ForcedPvPNotify = (i & 1) == 0;
        }
    });
    writer.join();
    for (auto& t : readers) t.join();
    std::cout << "PASS: source-derived ForcedPvP hook model completed, result="
              << result.load() << "\n";
}
"""

def extract_function(source: str, name: str) -> str:
    match = re.search(r"\bbool\s+" + re.escape(name) + r"\s*\(uint32 zoneId\)\s*\{", source)
    if match is None:
        raise AssertionError(f"original function changed or absent: {name}")
    brace = source.index("{", match.start())
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():pos + 1]
    raise AssertionError("unbalanced original C++ function")

def original_fragments() -> tuple[str, str]:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    declarations = []
    for name, key in zip(NAMES, KEY_SUFFIXES):
        # Exact original namespace-global, not an inferred reimplementation.
        matches = re.findall(r"^\s*bool\s+" + re.escape(name) + r"\s*=\s*(true|false)\s*;", source, re.M)
        if len(matches) != 1:
            raise AssertionError(f"original plain-bool declaration changed: {name}")
        declarations.append(f"bool {name} = {matches[0]};")
        pattern = (
            re.escape(name) + r"\s*=\s*sConfigMgr->GetOption<bool>\s*\(\s*"
            + re.escape('"NaxxramasCore.ForcedPvP.' + key + '"')
        )
        if len(re.findall(pattern, source)) != 1:
            raise AssertionError(f"world config write not located: {name}")
    assert "WORLDHOOK_ON_BEFORE_CONFIG_LOAD" in source
    assert "PLAYERHOOK_ON_UPDATE_ZONE" in source
    assert "PLAYERHOOK_ON_AFTER_UPDATE" in source
    function = extract_function(source, "IsConfiguredForcedPvPZone")
    for expected in ("ForcedPvPEnabled", "ForcedPvPSilithus", "ForcedPvPEasternPlaguelands"):
        assert expected in function, f"read path changed: {expected}"
    return "\n".join(declarations), function

def compile_and_run(root: Path, name: str, code: str, expect_race: bool) -> None:
    path = root / f"{name}.cpp"
    binary = root / name
    path.write_text(code, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
         "-pedantic", "-pthread", "-fsanitize=thread", str(path), "-o", str(binary)],
        check=True, capture_output=True, text=True, timeout=45,
    )
    run = subprocess.run(
        [str(binary)], capture_output=True, text=True,
        timeout=70, env={"TSAN_OPTIONS": "halt_on_error=1:exitcode=66"},
    )
    if expect_race:
        assert run.returncode == 66, (
            f"EXPECTED RACE RED missing, exit {run.returncode}\n{run.stderr[-2000:]}"
        )
        assert "ThreadSanitizer: data race" in run.stderr, (
            f"not a TSAN data-race diagnosis:\n{run.stderr[-2000:]}"
        )
        print("EXPECTED-RED: original source bools trigger ThreadSanitizer data race")
    else:
        assert run.returncode == 0, f"unexpected control failure {run.returncode}: {run.stderr[-2000:]}"
        assert "ThreadSanitizer" not in run.stderr
        assert "PASS: source-derived ForcedPvP hook model completed" in run.stdout
        print("PASS: test-only atomic-bool control is ThreadSanitizer-clean")

def main() -> None:
    declarations, function = original_fragments()
    original = CPP.replace("@DECLARATIONS@", declarations).replace("@REAL_FUNCTION@", function)
    # A model only: atomic declarations, same unmodified reader function body.
    # Atomic<bool>'s implicit conversion provides its load; assignments its store.
    atomic_declarations = declarations.replace("bool ForcedPvP", "std::atomic<bool> ForcedPvP")
    control = CPP.replace("@DECLARATIONS@", atomic_declarations).replace("@REAL_FUNCTION@", function)
    assert original != control
    with tempfile.TemporaryDirectory(prefix="forcedpvp-source-witness-") as tmp:
        root = Path(tmp)
        compile_and_run(root, "legacy", original, expect_race=True)
        compile_and_run(root, "atomic-control", control, expect_race=False)
    print("PASS: original ForcedPvP source race witness; no production files modified")

if __name__ == "__main__":
    main()
