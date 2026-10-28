"""F14 P14: must-fail mutants for f14_visibility_seam_tests.cpp.

Usage: python3 -I tests/f14_visibility_seam_mutants.py <extract dir> <scratch dir>

<extract dir> is the output of f14_visibility_seam_extract.py. Each mutant
breaks one property of the proposed seam (in the test context, the extracted
seam header or a copy of #202's policy header) and the test must then fail.
Exits 1 if any mutant survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST = "f14_visibility_seam_tests.cpp"
POLICY = "PlayerIdentityPolicy.h"
SEAM = "WhoListingSeam.h"
EXTRACT, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

MUTANTS = [
    ("identity ignored", TEST,
     "? board->Lookup(static_cast<std::uint32_t>(guid), now, maxAge)",
     "? Identity::Unknown"),
    ("board keyed by the wrong value", TEST,
     "board->Lookup(static_cast<std::uint32_t>(guid), now, maxAge)",
     "board->Lookup(static_cast<std::uint32_t>(guid >> 1), now, maxAge)"),
    ("observer row not exempt", TEST,
     "return HideTbcRow(policy, race, rowIsObserver, identity);",
     "return HideTbcRow(policy, race, false, identity);"),
    ("hiding with the feature off", SEAM,
     "if (hide && ctx.HideRowFor(", "if (ctx.HideRowFor("),
    ("stale board trusted", POLICY,
     "if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)",
     "if (now < snapshot->sampledAt)"),
    ("future board trusted", POLICY,
     "if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)",
     "if (now - snapshot->sampledAt > maxAge)"),
    ("Unknown shown under B", POLICY,
     "        if (identity == Identity::Human)\n            return false;\n",
     "        if (identity == Identity::Human || identity == Identity::Unknown)\n            return false;\n"),
    ("SelfBot option ignored", POLICY,
     "if (identity == Identity::SelfBot && config.selfBotCountsAsHuman)",
     "if (false)"),
    ("over-full snapshot published partially", POLICY,
     "            if (rows.size() <= MAX_ENTRIES)\n",
     "            if (true)\n"),
]


def fresh(work):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for name in ("WhoListingPolicy.h", SEAM):
        shutil.copy(EXTRACT / name, work / name)
    shutil.copy(ROOT / "src/Systems" / POLICY, work / POLICY)
    shutil.copy(ROOT / "tests" / TEST, work / TEST)


def build_and_run(work):
    exe = work / "t"
    build = subprocess.run(["g++", "-std=c++20", "-O1", f"-I{work}", str(work / TEST), "-o", str(exe)],
                           capture_output=True, text=True)
    if build.returncode != 0:
        return False, ["build failed"]
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    return run.returncode == 0, run.stdout.strip().splitlines()[-1:] or ["(no output)"]


work = OUT / "p14m"
fresh(work)
ok, last = build_and_run(work)
if not ok:
    print(f"BASELINE FAILED: {last}")
    sys.exit(1)

caught = 0
for name, target, old, new in MUTANTS:
    fresh(work)
    text = (work / target).read_text()
    assert text.count(old) == 1, f"anchor not unique: {name}"
    (work / target).write_text(text.replace(old, new))
    passed, last = build_and_run(work)
    print(("SURVIVED " if passed else "CAUGHT ") + f"{name}: {last}")
    caught += not passed

print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
