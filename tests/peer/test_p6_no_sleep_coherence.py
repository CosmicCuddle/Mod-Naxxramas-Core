#!/usr/bin/env python3
"""Part34 CS01 independent P6 coherence witness, with no timing sleeps.

Reads the exact CS03 P6 SettingsSnapshot production header at the checked-out
commit and instruments disposable copies only. Synchronisation uses condition
variables to PROVE a reader is scheduled while the writer is paused, rather
than assuming a 300ms sleep schedules it. No module C++ is modified.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "src/Racials/Forsaken/TouchOfTheGraveSettings.h"

STORE = "_enabled.store(s.enabled, std::memory_order_release);"
LOAD = "s.enabled = _enabled.load(std::memory_order_acquire);"
ODD = "if (before & 1u)"
RECHECK = "if (_sequence.load(std::memory_order_relaxed) == before)"
ODD_STORE = "_sequence.store(seq + 1, std::memory_order_relaxed);"

HARNESS = r'''
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <thread>
namespace NaxxramasTouchOfTheGrave {
void PeerAfterFirstStore();
void PeerAfterFirstLoad();
void PeerSawOdd();
}
#include "TouchOfTheGraveSettings.h"

using namespace NaxxramasTouchOfTheGrave;

struct Gate {
    std::mutex lock;
    std::condition_variable condition;
    bool entered = false;
    bool released = false;
    bool Pause() {
        std::unique_lock<std::mutex> hold(lock);
        entered = true;
        condition.notify_all();
        return condition.wait_for(hold, std::chrono::seconds(10),
                                  [&]{ return released; });
    }
    bool WaitEntered() {
        std::unique_lock<std::mutex> hold(lock);
        return condition.wait_for(hold, std::chrono::seconds(10),
                                  [&]{ return entered; });
    }
    void Release() {
        std::lock_guard<std::mutex> hold(lock);
        released = true;
        condition.notify_all();
    }
};

Gate storeGate, loadGate;
std::atomic<int> mode{0};
std::atomic<int> loadCalls{0};
std::mutex eventMutex;
std::condition_variable events;
std::atomic<bool> sawOdd{false};
std::atomic<bool> readerDone{false};

namespace NaxxramasTouchOfTheGrave {
void PeerAfterFirstStore() {
    if (mode.load() == 1 && !storeGate.Pause()) std::terminate();
}
void PeerAfterFirstLoad() {
    if (mode.load() == 2 && loadCalls.fetch_add(1) == 0 &&
        !loadGate.Pause()) std::terminate();
}
void PeerSawOdd() {
    if (mode.load() == 1) {
        sawOdd.store(true);
        events.notify_all();
    }
}
}

bool Same(IpSettings const& a, IpSettings const& b) {
    return a.enabled == b.enabled &&
           a.progressionLimit == b.progressionLimit &&
           a.vanillaPower == b.vanillaPower &&
           a.tbcPower == b.tbcPower &&
           a.vanillaHealing == b.vanillaHealing &&
           a.tbcHealing == b.tbcHealing;
}

int main() {
    IpSettings const a{true, 4, 1.10f, 1.20f, 1.30f, 1.40f};
    IpSettings const b{false, 16, 2.10f, 2.20f, 2.30f, 2.40f};
    SettingsSnapshot snap;
    snap.Store(a);

    // W: known mid-write window. Wait until the reader demonstrably
    // observed the odd sequence (or finished incorrectly) before releasing
    // the paused writer. No scheduler sleep or "reader probably ran" test.
    mode.store(1);
    std::thread writer([&] { snap.Store(b); });
    if (!storeGate.WaitEntered()) {
        storeGate.Release();
        writer.join();
        std::puts("FAIL W: writer never paused");
        return 21;
    }

    IpSettings seen{};
    std::thread reader([&] {
        seen = snap.Load();
        readerDone.store(true);
        events.notify_all();
    });
    bool observed = false;
    {
        std::unique_lock<std::mutex> hold(eventMutex);
        observed = events.wait_for(hold, std::chrono::seconds(10), [&]{
            return sawOdd.load() || readerDone.load();
        });
    }
    bool const returnedDuringStore = readerDone.load();
    bool const observedOdd = sawOdd.load();
    storeGate.Release();
    writer.join();
    reader.join();
    mode.store(0);

    if (!observed) { std::puts("FAIL W: no scheduled reader observation"); return 22; }
    if (returnedDuringStore || !observedOdd) {
        std::puts("EXPECTED-RED W: reader returned during an active Store or never observed odd");
        return 23;
    }
    if (!Same(seen, b)) { std::puts("FAIL W: not generation B"); return 24; }
    std::puts("PASS W: reader saw odd before writer release; whole B returned");

    // R: reader has sampled a generation-A field. Complete B Store while
    // the reader is parked, then require a retry, not a mixed publication.
    snap.Store(a);
    mode.store(2);
    IpSettings got{};
    std::thread secondReader([&]{ got = snap.Load(); });
    if (!loadGate.WaitEntered()) {
        loadGate.Release();
        secondReader.join();
        std::puts("FAIL R: reader never paused");
        return 25;
    }
    snap.Store(b);
    loadGate.Release();
    secondReader.join();
    mode.store(0);

    if (!Same(got, b) || loadCalls.load() < 2) {
        std::puts("EXPECTED-RED R: old/new fields returned or no sequence retry");
        return 26;
    }
    std::puts("PASS R: cross-generation reader forced to retry; whole B returned");
    return 0;
}
'''

def instrument(src: str) -> str:
    for text in (STORE, LOAD, ODD, RECHECK, ODD_STORE):
        assert src.count(text) == 1, f"exact source contract changed: {text}"
    src = src.replace(STORE, STORE + "\n            PeerAfterFirstStore();", 1)
    src = src.replace(LOAD, LOAD + "\n                PeerAfterFirstLoad();", 1)
    # Keep the original read / odd test and insert a source-only observation.
    src = src.replace(
        "if (before & 1u)\n                    continue;",
        "if (before & 1u)\n                {\n                    PeerSawOdd();\n                    continue;\n                }",
        1,
    )
    assert src.count("PeerSawOdd();") == 1
    return src

def execute(folder: Path, header: str, std: str, expected: str, label: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "TouchOfTheGraveSettings.h").write_text(header)
    (folder / "witness.cpp").write_text(HARNESS)
    target = folder / "witness"
    subprocess.run([
        "g++", f"-std={std}", "-O1", "-pthread",
        "-Wall", "-Wextra", "-Werror", "-pedantic",
        "-I", str(folder), str(folder / "witness.cpp"), "-o", str(target),
    ], check=True, capture_output=True, text=True, timeout=40)
    p = subprocess.run([str(target)], capture_output=True, text=True, timeout=32)
    if expected == "green":
        assert p.returncode == 0, f"{label} expected pass: {p.returncode}: {p.stdout} {p.stderr}"
        assert "PASS W: reader saw odd before writer release" in p.stdout
        assert "PASS R: cross-generation reader forced to retry" in p.stdout
    elif expected == "w-red":
        assert p.returncode == 23, f"{label} W control failed: {p.returncode}: {p.stdout} {p.stderr}"
        assert "EXPECTED-RED W" in p.stdout
    elif expected == "r-red":
        assert p.returncode == 26, f"{label} R control failed: {p.returncode}: {p.stdout} {p.stderr}"
        assert "EXPECTED-RED R" in p.stdout
    else:
        raise AssertionError("unexpected expectation")
    print(std, label, "PASS" if expected == "green" else "EXPECTED-RED", p.returncode)

def main() -> None:
    original = HEADER.read_text(encoding="utf-8")
    base = instrument(original)  # Instrument BEFORE mutating exact source conditions.
    cases = [
        ("current", base, "green"),
        ("missing-odd-guard", base.replace(ODD, "if (false && (before & 1u))", 1), "w-red"),
        ("missing-final-recheck", base.replace(RECHECK, "if (true)", 1), "r-red"),
        ("writer-never-odd", base.replace(ODD_STORE, "_sequence.store(seq, std::memory_order_relaxed);", 1), "w-red"),
    ]
    with tempfile.TemporaryDirectory(prefix="p6-peer-no-sleep-") as tmp:
        root = Path(tmp)
        for std in ("c++17", "c++20"):
            for label, header, expectation in cases:
                execute(root / std / label, header, std, expectation, label)
    print("PASS: source-backed P6 CV-gated no-sleep coherence proof + 3 RED controls")

if __name__ == "__main__":
    main()
