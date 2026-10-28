"""P10: must-fail mutants for the HonorReset interval bound and progress guard.

Usage: python3 -I tests/honor_reset_mutants.py <scratch dir>
Each mutant must make tests/honor_reset_schedule_tests.cpp fail or hang
(killed by a timeout). Exits 1 if any mutant survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/Systems/HonorReset.cpp").read_text()
OUT = pathlib.Path(sys.argv[1])
MUTANTS = [
    ("bound removed", "        if (weeks > MAX_INTERVAL_WEEKS)\n            return static_cast<std::time_t>(-1);\n", ""),
    ("bound ignores tm_mday headroom", "(std::numeric_limits<int>::max() - 31) / 7", "std::numeric_limits<int>::max() / 7"),
    ("bound off by one", "if (weeks > MAX_INTERVAL_WEEKS)", "if (weeks > MAX_INTERVAL_WEEKS + 1)"),
    ("progress guard removed", "            if (nextReset <= scheduledReset)\n                return scheduledReset;\n", ""),
    ("progress guard strict", "if (nextReset <= scheduledReset)", "if (nextReset < scheduledReset)"),
]
caught = 0
for name, old, new in MUTANTS:
    assert SRC.count(old) == 1, name
    work = OUT / "m"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "HonorReset.cpp").write_text(SRC.replace(old, new))
    b = subprocess.run(["g++", "-std=c++17", "-O1", "-Itests/honor_reset_stubs", f"-I{work}",
                        "tests/honor_reset_schedule_tests.cpp", "-Wl,--wrap=time", "-o", str(work / "t")],
                       cwd=ROOT, capture_output=True, text=True)
    if b.returncode != 0:
        failed = True
    else:
        try:
            failed = subprocess.run([str(work / "t")], capture_output=True, timeout=20).returncode != 0
        except subprocess.TimeoutExpired:
            failed = True
    print(("CAUGHT " if failed else "SURVIVED ") + name)
    caught += failed
print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
