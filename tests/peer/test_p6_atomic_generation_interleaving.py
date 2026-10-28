#!/usr/bin/env python3
"""Part34 independent P6 six-field atomic generation witness.

No production files are changed. A disposable copy of Claude's exact header gets
scheduling hooks inserted *after* existing atomic store/load statements. This
makes two otherwise allowed thread interleavings deterministic rather than
probabilistic. Demonstrates potential mixed generations, not any live bug.
"""
from pathlib import Path
import os
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "src/Racials/Forsaken/TouchOfTheGraveSettings.h"
FIELDS = ("enabled", "progressionLimit", "vanillaPower", "tbcPower", "vanillaHealing", "tbcHealing")

CPP = r'''
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>

namespace NaxxramasTouchOfTheGrave {
void TestAfterEnabledStore();
void TestAfterEnabledLoad();
}
#include "instrumented_grave.h"

struct Gate {
    std::mutex mutex;
    std::condition_variable cv;
    bool entered = false;
    bool released = false;
    void Pause() {
        std::unique_lock<std::mutex> lk(mutex);
        entered = true;
        cv.notify_all();
        cv.wait(lk, [this] { return released; });
    }
    void Await() {
        std::unique_lock<std::mutex> lk(mutex);
        cv.wait(lk, [this] { return entered; });
    }
    void Release() {
        std::lock_guard<std::mutex> lk(mutex);
        released = true;
        cv.notify_all();
    }
};

std::atomic<int> hookMode{0};
Gate storeGate, loadGate;
namespace NaxxramasTouchOfTheGrave {
void TestAfterEnabledStore() { if (hookMode.load() == 1) storeGate.Pause(); }
void TestAfterEnabledLoad() { if (hookMode.load() == 2) loadGate.Pause(); }
}

using NaxxramasTouchOfTheGrave::IpSettings;
using NaxxramasTouchOfTheGrave::SettingsSnapshot;

bool Equal(IpSettings const& a, IpSettings const& b) {
    return a.enabled == b.enabled && a.progressionLimit == b.progressionLimit &&
           a.vanillaPower == b.vanillaPower && a.tbcPower == b.tbcPower &&
           a.vanillaHealing == b.vanillaHealing && a.tbcHealing == b.tbcHealing;
}
void Require(bool ok, char const* message) {
    if (!ok) { std::cerr << "UNEXPECTED: " << message << '\n'; std::exit(2); }
}
int main(int argc, char** argv) {
    IpSettings a{true, 4, 1.10f, 1.20f, 1.30f, 1.40f};
    IpSettings b{false, 16, 2.10f, 2.20f, 2.30f, 2.40f};
    SettingsSnapshot settings;
    settings.Store(a);
    Require(Equal(settings.Load(), a), "baseline A not coherent");
    settings.Store(b);
    Require(Equal(settings.Load(), b), "baseline B not coherent");

    // Writer stops after publishing new enabled, before remaining five stores.
    settings.Store(a);
    hookMode.store(1);
    std::thread writer([&] { settings.Store(b); });
    storeGate.Await();
    IpSettings mixedDuringStore = settings.Load();
    Require(mixedDuringStore.enabled == b.enabled, "new enabled not observed");
    Require(mixedDuringStore.progressionLimit == a.progressionLimit, "old progression not observed");
    Require(mixedDuringStore.vanillaPower == a.vanillaPower, "old adjustment not observed");
    storeGate.Release();
    writer.join();
    hookMode.store(0);
    Require(Equal(settings.Load(), b), "post-store B not coherent");

    // Reader stops after sampling old enabled; writer finishes all six stores.
    settings.Store(a);
    hookMode.store(2);
    IpSettings mixedDuringLoad{};
    std::thread reader([&] { mixedDuringLoad = settings.Load(); });
    loadGate.Await();
    settings.Store(b);
    loadGate.Release();
    reader.join();
    hookMode.store(0);
    Require(mixedDuringLoad.enabled == a.enabled, "old enabled not observed");
    Require(mixedDuringLoad.progressionLimit == b.progressionLimit, "new progression not observed");
    Require(mixedDuringLoad.vanillaHealing == b.vanillaHealing, "new healing not observed");

    const bool firstMixed = !Equal(mixedDuringStore, a) && !Equal(mixedDuringStore, b);
    const bool secondMixed = !Equal(mixedDuringLoad, a) && !Equal(mixedDuringLoad, b);
    Require(firstMixed && secondMixed, "the instrumented real operations did not mix");
    std::cout << "PASS: serial baseline both generations\n";
    std::cout << "WITNESS: store pause yields new enabled / five old fields\n";
    std::cout << "WITNESS: load pause yields old enabled / five new fields\n";
    if (argc > 1 && std::string(argv[1]) == "--require-coherent") {
        std::cout << "EXPECTED-RED: coherent six-field generation contract violated\n";
        return 23;
    }
    std::cout << "PASS: two deterministic mixed-generation witnesses\n";
    return 0;
}
'''

def main() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    for field in FIELDS:
        store = f"_{field}.store(s.{field}, std::memory_order_relaxed);"
        load = f"s.{field} = _{field}.load(std::memory_order_relaxed);"
        assert content.count(store) == 1, f"source store drift: {store}"
        assert content.count(load) == 1, f"source load drift: {load}"
    assert "class SettingsSnapshot" in content
    store = "_enabled.store(s.enabled, std::memory_order_relaxed);"
    load = "s.enabled = _enabled.load(std::memory_order_relaxed);"
    instrumented = content.replace(store, store + "\n            TestAfterEnabledStore();", 1)
    instrumented = instrumented.replace(load, load + "\n            TestAfterEnabledLoad();", 1)
    assert instrumented != content
    with tempfile.TemporaryDirectory(prefix="p6-generation-") as d:
        root = Path(d)
        (root / "instrumented_grave.h").write_text(instrumented, encoding="utf-8")
        (root / "witness.cpp").write_text(CPP, encoding="utf-8")
        for standard in ("c++17", "c++20"):
            binary = root / ("witness-" + standard)
            subprocess.run([os.environ.get("CXX", "g++"), f"-std={standard}", "-O1", "-pthread", "-Wall", "-Wextra", "-Werror", "-pedantic", str(root / "witness.cpp"), "-o", str(binary)], check=True)
            positive = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            expected = subprocess.run([str(binary), "--require-coherent"], capture_output=True, text=True)
            assert expected.returncode == 23, f"expected coherence RED, got {expected.returncode}: {expected.stderr}"
            assert "EXPECTED-RED: coherent six-field generation contract violated" in expected.stdout
            print(f"{standard}: {positive.stdout.strip()}")
            print(f"{standard}: EXPECTED-RED strict coherence assertion (exit 23)")
    print("PASS: P6 controlled generation interleaving; no production header modified")

if __name__ == "__main__":
    main()
