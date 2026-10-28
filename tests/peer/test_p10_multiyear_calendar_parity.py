#!/usr/bin/env python3
"""Part34 P10 independent source-extracted multi-year calendar parity gate.

No module C++, config, database or author test is modified. Compile the
actual four scheduler functions at frozen main and CS03's P10 HEAD in
separate disposable standard C++ executables. Compare every ordinary
schedule trace per timezone and standard, then probe the P10 extreme guards.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PATH = "src/Systems/HonorReset.cpp"
BASE = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
P10 = "e3fe22bfec18c55be0bf60fc459f19c3f940f5ae"
NAMES = ("GetLocalTime", "BuildAnchorTime", "AddWeeks", "GetLatestScheduledReset")

def extract(source, name):
    p = re.search(r"^\s*(?:bool|std::time_t)\s+" + re.escape(name) + r"\s*\(",
                  source, re.M)
    assert p, f"missing source function: {name}"
    begin = source.index("{", p.start())
    depth = 0
    for end in range(begin, len(source)):
        if source[end] == "{": depth += 1
        if source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[p.start():end + 1].strip()
    raise AssertionError("unterminated source function " + name)

def git_show(rev):
    return subprocess.run(["git", "show", f"{rev}:{PATH}"], cwd=ROOT,
                          capture_output=True, text=True, check=True,
                          timeout=20).stdout

CPP = r'''
#include <algorithm>
#include <cstdint>
#include <cstdlib>
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
@EXTRA@
@FUNCTIONS@
}
void Fail(char const* why) {
    std::cerr << "FAIL: " << why << "\n";
    std::exit(3);
}
void Check(bool value, char const* reason) { if (!value) Fail(reason); }

int main(int argc, char** argv) {
    Check(argc == 2, "expected ordinary or edge");
    std::string mode = argv[1];
    std::uint64_t total = 0;
    for (char const* date : {"2010-01-06", "2020-01-01", "2024-01-03",
                             "2026-10-07", "2030-01-02"}) {
        HonorResetAnchorDate = date;
        std::time_t anchor = 0;
        Check(BuildAnchorTime(anchor), "Wednesday anchor validation failed");
        if (mode == "ordinary") {
            for (uint32 weeks : {1u, 2u, 3u, 4u, 7u, 13u, 26u, 52u, 104u}) {
                HonorResetIntervalWeeks = weeks;
                for (int day = 0; day <= 2200; day += 7) {
                    std::time_t now = anchor + std::time_t(day) * 86400 + 123;
                    std::time_t prior = GetLatestScheduledReset(now);
                    Check(prior >= anchor && prior <= now,
                          "ordinary scheduled reset not in valid interval");
                    std::time_t next = AddWeeks(prior, weeks);
                    Check(next > now && next > prior,
                          "ordinary schedule not strictly advancing");
                    std::tm wall = {};
                    Check(GetLocalTime(prior, wall),
                          "ordinary scheduled time cannot be converted");
                    Check(wall.tm_wday == 3 && wall.tm_hour == 6 &&
                          wall.tm_min == 0, "Wednesday 06:00 local parity");
                    std::cout << date << "/" << weeks << "/" << day
                              << "=" << static_cast<long long>(prior) << "\n";
                    ++total;
                }
            }
        } else if (mode == "edge") {
            // This mode is run against revised P10 only.
            HonorResetIntervalWeeks = std::numeric_limits<uint32>::max();
            std::time_t now = anchor + std::time_t(2200) * 86400 + 123;
            Check(AddWeeks(anchor, HonorResetIntervalWeeks) ==
                  static_cast<std::time_t>(-1), "UINT32_MAX must fail closed");
            Check(GetLatestScheduledReset(now) == anchor,
                  "UINT32_MAX must preserve one anchor reset");
            ++total;
            for (uint32 weeks : {MAX_INTERVAL_WEEKS + 1u, 306783379u,
                                 613566757u}) {
                HonorResetIntervalWeeks = weeks;
                Check(AddWeeks(anchor, weeks) == static_cast<std::time_t>(-1),
                      "unrepresentable weeks unexpectedly accepted");
                Check(GetLatestScheduledReset(now) == anchor,
                      "unrepresentable weeks did not return anchor");
                ++total;
            }
            HonorResetIntervalWeeks = 0;
            Check(GetLatestScheduledReset(now) == anchor,
                  "zero interval did not terminate at anchor");
            ++total;
            std::cout << date << " / edge : " << total << "\n";
        } else Fail("invalid mode");
    }
    if (mode == "ordinary")
        Check(total == 5ULL * 9ULL * 315ULL,
              "not all ordinary calendar probe cases completed");
    else
        Check(total == 25ULL, "not all edge cases completed");
    std::cout << "PASS: " << mode << " calendar probes " << total << "\n";
    return 0;
}
'''

def build(src, output, fixed, std):
    exact = [extract(src, x) for x in NAMES]
    extra = ""
    if fixed:
        const = re.search(
            r"constexpr\s+uint32\s+MAX_INTERVAL_WEEKS\s*=\s*"
            r"static_cast<uint32>\s*\(\s*\(\s*std::numeric_limits<int>::max\(\)"
            r"\s*-\s*31\s*\)\s*/\s*7\s*\)\s*;",
            src
        )
        assert const, "P10 max-interval source guard drift"
        assert "if (weeks > MAX_INTERVAL_WEEKS)" in exact[2]
        assert "if (nextReset <= scheduledReset)" in exact[3]
        extra = const.group(0)
    else:
        assert "MAX_INTERVAL_WEEKS" not in src, "frozen source mismatch"
        assert "if (weeks > MAX_INTERVAL_WEEKS)" not in exact[2]
        # Harness-only symbol for edge-mode code that is NEVER executed on
        # baseline. The extracted four original functions remain untouched.
        extra = "constexpr uint32 MAX_INTERVAL_WEEKS = 306783373u;"
    code = CPP.replace("@EXTRA@", extra).replace("@FUNCTIONS@", "\n\n".join(exact))
    file = output.with_suffix(".cpp")
    file.write_text(code)
    compile_result = subprocess.run(["g++", f"-std={std}", "-O1", "-Wall", "-Wextra",
                                     "-Werror", "-pedantic", "-Wconversion",
                                     str(file), "-o", str(output)],
                                    capture_output=True, text=True, timeout=50)
    assert compile_result.returncode == 0, (
        f"source test compile failed for {std}: {compile_result.stderr}"
    )

def run(exe, mode, tz):
    result = subprocess.run([str(exe), mode], check=True, capture_output=True,
                            text=True, timeout=30, env={**os.environ, "TZ": tz})
    lines = result.stdout.strip().splitlines()
    assert lines[-1].startswith(f"PASS: {mode} calendar probes ")
    return result.stdout

def main():
    frozen = git_show(BASE)
    new = (ROOT / PATH).read_text()
    assert git_show(P10) == new, "checked out source not exact CS03 P10 author head"
    assert "HonorResetEnabled = false" in frozen and "HonorResetEnabled = false" in new
    assert 'NaxxramasCore.HonorReset.IntervalWeeks' in frozen
    with tempfile.TemporaryDirectory(prefix="p10-multiyear-peer-") as temp:
        root = Path(temp)
        for std in ("c++17", "c++20"):
            before, after = root / f"{std}-main", root / f"{std}-p10"
            build(frozen, before, False, std)
            build(new, after, True, std)
            for tz in ("UTC", "Europe/London"):
                old = run(before, "ordinary", tz)
                updated = run(after, "ordinary", tz)
                assert old == updated, (
                    f"ordinary schedule drift {std}/{tz}: "
                    f"{hashlib.sha256(old.encode()).hexdigest()} vs "
                    f"{hashlib.sha256(updated.encode()).hexdigest()}"
                )
                assert "PASS: ordinary calendar probes 14175" in updated
                edge = run(after, "edge", tz)
                assert "PASS: edge calendar probes 25" in edge
                print(f"PASS {std}/{tz}: 14,175 old/new ordinary reset dates "
                      "identical; 25 fail-closed edge checks")
    print("PASS: exact-source P10 multi-year old-vs-new schedule parity and extreme bounds; no production changes")

if __name__ == "__main__":
    main()
