"""P6: deterministic six-field coherence witness for TouchOfTheGraveSettings.h.

Approach adapted from CS01's #209: a disposable copy of the header gets
pause hooks inserted after the first field store (writer) and after the
first field load (reader), making two interleavings deterministic:

  W  writer paused mid-Store: a concurrent Load must NOT return until the
     writer finishes, and must then return the whole new generation.
  R  reader paused mid-Load while a whole Store happens: the Load must
     retry and return the whole new generation, never a mix.

Run on: the current header (must PASS), the original P6 header at 20767b4
(must FAIL: it mixes), and seqlock mutants (must FAIL).
Usage: python3 -I tests/touch_of_the_grave_coherence_witness.py <scratch dir>
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER_PATH = "src/Racials/Forsaken/TouchOfTheGraveSettings.h"
OLD_P6 = "20767b49f4a89da3cc46986305f1b32f880c01c5"
STORE = "_enabled.store(s.enabled, std::memory_order_release);"
LOAD = "s.enabled = _enabled.load(std::memory_order_acquire);"

HARNESS = r'''
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <thread>

namespace NaxxramasTouchOfTheGrave { void AfterFirstStore(); void AfterFirstLoad(); }
#include "TouchOfTheGraveSettings.h"

using namespace NaxxramasTouchOfTheGrave;

struct Gate
{
    std::mutex m;
    std::condition_variable cv;
    bool entered = false;
    bool released = false;
    void Pause() { std::unique_lock<std::mutex> l(m); entered = true; cv.notify_all(); cv.wait(l, [&] { return released; }); }
    void AwaitEntered() { std::unique_lock<std::mutex> l(m); cv.wait(l, [&] { return entered; }); }
    void Release() { std::lock_guard<std::mutex> l(m); released = true; cv.notify_all(); }
};

std::atomic<int> mode{0};
std::atomic<int> loadHookCalls{0};
Gate storeGate, loadGate;
namespace NaxxramasTouchOfTheGrave {
void AfterFirstStore() { if (mode.load() == 1) storeGate.Pause(); }
void AfterFirstLoad() { if (mode.load() == 2 && loadHookCalls.fetch_add(1) == 0) loadGate.Pause(); }
}

bool Same(IpSettings const& x, IpSettings const& y)
{
    return x.enabled == y.enabled && x.progressionLimit == y.progressionLimit &&
           x.vanillaPower == y.vanillaPower && x.tbcPower == y.tbcPower &&
           x.vanillaHealing == y.vanillaHealing && x.tbcHealing == y.tbcHealing;
}

int main()
{
    IpSettings const a{true, 4, 1.10f, 1.20f, 1.30f, 1.40f};
    IpSettings const b{false, 16, 2.10f, 2.20f, 2.30f, 2.40f};
    SettingsSnapshot snap;

    // W: writer paused after its first field store.
    snap.Store(a);
    mode.store(1);
    std::thread writer([&] { snap.Store(b); });
    storeGate.AwaitEntered();
    std::atomic<bool> readerDone{false};
    IpSettings seen{};
    std::thread reader([&] { seen = snap.Load(); readerDone.store(true); });
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    bool const returnedMidWrite = readerDone.load();
    storeGate.Release();
    writer.join();
    reader.join();
    mode.store(0);
    if (returnedMidWrite) { std::printf("RED W: Load returned during a Store\n"); return 11; }
    if (!Same(seen, b)) { std::printf("RED W: Load after Store was not generation B\n"); return 12; }

    // R: reader paused after its first field load; a whole Store happens.
    snap.Store(a);
    mode.store(2);
    IpSettings got{};
    std::thread r2([&] { got = snap.Load(); });
    loadGate.AwaitEntered();
    snap.Store(b);
    loadGate.Release();
    r2.join();
    mode.store(0);
    if (!Same(got, b)) { std::printf("RED R: Load returned a mixed or stale generation\n"); return 13; }
    if (loadHookCalls.load() < 2) { std::printf("RED R: Load did not retry\n"); return 14; }

    std::printf("PASS: six-field coherence witness (W and R)\n");
    return 0;
}
'''


def instrument(text):
    # The original P6 header used relaxed ordering; the current one uses
    # release/acquire. Hook whichever form this header has, exactly once.
    store = STORE if STORE in text else STORE.replace("release", "relaxed")
    load = LOAD if LOAD in text else LOAD.replace("acquire", "relaxed")
    assert text.count(store) == 1 and text.count(load) == 1
    text = text.replace(store, store + "\n            AfterFirstStore();", 1)
    return text.replace(load, load + "\n                AfterFirstLoad();", 1)


def run(label, header_text, work, std):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "TouchOfTheGraveSettings.h").write_text(instrument(header_text))
    (work / "witness.cpp").write_text(HARNESS)
    exe = work / "w"
    subprocess.run(["g++", f"-std={std}", "-O1", "-pthread", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    f"-I{work}", str(work / "witness.cpp"), "-o", str(exe)], check=True)
    try:
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        out, code = r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        out, code = "TIMEOUT", 99
    print(f"{std} {label}: exit {code} {out}")
    return code


def main():
    out = pathlib.Path(sys.argv[1])
    current = (ROOT / HEADER_PATH).read_text()
    old = subprocess.run(["git", "show", f"{OLD_P6}:{HEADER_PATH}"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    mutants = {
        "no odd-sequence wait": ("                if (before & 1u)\n                    continue;                                    // write in progress\n", ""),
        "no sequence recheck": ("                if (_sequence.load(std::memory_order_relaxed) == before)\n                    return s;                                    // no Store overlapped\n",
                                "                (void)before;\n                return s;\n"),
        "writer never odd": ("            _sequence.store(seq + 1, std::memory_order_relaxed); // odd: writing\n", ""),
    }
    ok = True
    for std in ("c++17", "c++20"):
        ok &= run("current", current, out / "cur", std) == 0
        ok &= run("original P6 20767b4 (expected RED)", old, out / "old", std) != 0
        for name, (a, b) in mutants.items():
            assert current.count(a) == 1, name
            ok &= run(f"mutant '{name}' (expected RED)", current.replace(a, b), out / "mut", std) != 0
    print("PASS: coherence witness green on current, red on original P6 and 3 mutants" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
