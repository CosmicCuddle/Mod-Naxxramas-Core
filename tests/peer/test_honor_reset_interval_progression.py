#!/usr/bin/env python3
"""P10 independent HonorReset scheduling progression witness.

Read the immutable-module source and copy its exact four date functions into
a disposable standard-C++ fixture. Add a loop tripwire ONLY to the copied
GetLatestScheduledReset function, to prevent hanging CI. All original
production C++ / SQL / config / Worldserver are unchanged.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[2] / "src/Systems/HonorReset.cpp"

NAMES = ("GetLocalTime", "BuildAnchorTime", "AddWeeks", "GetLatestScheduledReset")

def function(source: str, name: str) -> str:
    begin = re.search(
        r"^\s*(?:bool|std::time_t)\s+" + re.escape(name) + r"\s*\(",
        source, re.M,
    )
    assert begin, f"missing/changed source function {name}"
    opening = source.find("{", begin.start())
    assert opening >= 0
    depth = 0
    for end in range(opening, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[begin.start():end + 1].strip()
    raise AssertionError("unclosed C++ function " + name)

MAIN = r"""
#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
using uint32 = std::uint32_t;
namespace {
uint32 HonorResetIntervalWeeks = 2;
uint32 HonorResetDayOfWeek = 3;
uint32 HonorResetHour = 6;
uint32 HonorResetMinute = 0;
std::string HonorResetAnchorDate = "2026-10-07";
@FUNCTIONS@
}

void Require(bool ok, char const* reason) {
    if (!ok) { std::cerr << "UNEXPECTED: " << reason << "\n"; std::exit(1); }
}
int main() {
    std::tm date = {};
    date.tm_year = 2026 - 1900;
    date.tm_mon = 9;
    date.tm_mday = 28;
    date.tm_hour = 7;
    date.tm_isdst = -1;
    std::time_t now = std::mktime(&date);
    Require(now != -1, "fixture date could not be built");
    std::time_t anchor = 0;
    Require(BuildAnchorTime(anchor), "original anchor not accepted");

    HonorResetIntervalWeeks = 2;
    std::time_t prior = GetLatestScheduledReset(now);
    Require(prior != -2 && prior > anchor && prior < now, "ordinary fortnightly progression failed");
    std::time_t next = AddWeeks(prior, 2);
    Require(next > now, "ordinary next reset not after fixture now");
    std::cout << "PASS: original two-week progression reaches the last scheduled reset\n";

    // Current config validation only enforces a minimum of one, not a maximum.
    HonorResetIntervalWeeks = std::numeric_limits<uint32>::max();
    std::time_t backwards = AddWeeks(anchor, HonorResetIntervalWeeks);
    Require(backwards < anchor, "extreme interval unexpectedly progressed forward");
    std::cout << "WITNESS: UINT32_MAX interval moves AddWeeks backwards\n";

    // The original while(true) may never terminate for this input. Test-only
    // loop tripwire returns -2 after 20 repeated iterations so no CI hangs.
    std::time_t bounded = GetLatestScheduledReset(now);
    Require(bounded == -2, "expected no-progress loop tripwire not reached");
    std::cout << "EXPECTED-RED: original GetLatestScheduledReset fails to terminate within 20 steps\n";
    std::cout << "PASS: HonorReset calendar nonprogress witness; production unchanged\n";
    return 0;
}
"""

def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "HonorResetEnabled = false" in source, "default-off source guard drift"
    assert '"NaxxramasCore.HonorReset.IntervalWeeks"' in source
    validation = re.search(
        r"HonorResetIntervalWeeks\s*=\s*std::max<uint32>\s*\(\s*1\s*,\s*"
        r"sConfigMgr->GetOption<uint32>\s*\(\s*"
        r'"NaxxramasCore.HonorReset.IntervalWeeks"\s*,\s*2\s*\)\s*\)\s*;',
        source,
    )
    assert validation, "original positive-min-only interval validation changed"
    extracted = {name: function(source, name) for name in NAMES}
    original_add = extracted["AddWeeks"]
    assert "local.tm_mday += static_cast<int>(weeks * 7);" in original_add
    original_loop = extracted["GetLatestScheduledReset"]
    assert original_loop.count("while (true)") == 1
    assert "if (nextReset > now)" in original_loop
    # Bounded one-control replacement inside disposable test copy ONLY.
    bounded_loop = original_loop.replace(
        "while (true)",
        "uint32 loopTripwire = 0;\n        while (true)",
        1,
    ).replace(
        "while (true)\n        {",
        "while (true)\n        {\n            if (++loopTripwire > 20) return static_cast<std::time_t>(-2);",
        1,
    )
    assert "loopTripwire > 20" in bounded_loop, "source format changed"
    extracted["GetLatestScheduledReset"] = bounded_loop
    code = MAIN.replace("@FUNCTIONS@", "\n\n".join(extracted.values()))
    with tempfile.TemporaryDirectory(prefix="honor-reset-interval-") as directory:
        root = Path(directory)
        cpp = root / "witness.cpp"
        cpp.write_text(code, encoding="utf-8")
        for std in ("c++17", "c++20"):
            exe = root / std
            subprocess.run(
                ["g++", f"-std={std}", "-O1", "-Wall", "-Wextra",
                 "-Werror", "-pedantic", "-Wconversion", str(cpp), "-o", str(exe)],
                check=True, capture_output=True, text=True, timeout=40,
            )
            env = dict(os.environ, TZ="UTC")
            r = subprocess.run([str(exe)], capture_output=True, text=True,
                               env=env, check=True, timeout=20)
            assert "WITNESS: UINT32_MAX interval moves AddWeeks backwards" in r.stdout
            assert "EXPECTED-RED: original GetLatestScheduledReset fails to terminate within 20 steps" in r.stdout
            print(std + ": " + r.stdout.strip().replace("\n", "\n" + std + ": "))
    print("PASS: isolated source-bound scheduler regression witness (no DB, SQL or live server)")

if __name__ == "__main__":
    main()
