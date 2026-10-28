"""P11: must-fail mutants for the TopUpToCount observed-delta accounting.

Usage: python3 -I tests/topup_observed_delta_mutants.py <scratch dir>
Each mutant of src/Systems/BotRaidConsumables.cpp must make
tests/topup_observed_delta_tests.py fail. Exits 1 if any survives.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/Systems/BotRaidConsumables.cpp").read_text()
OUT = pathlib.Path(sys.argv[1])
MUTANTS = [
    ("requested amount again", "        stats.ItemsAdded += added;\n", "        stats.ItemsAdded += amountToAdd;\n"),
    ("reagents use request", "            stats.ReagentsAdded += added;\n", "            stats.ReagentsAdded += amountToAdd;\n"),
    ("no cap at request", "? std::min<uint32>(afterCount - currentCount, amountToAdd)", "? (afterCount - currentCount)"),
    ("no underflow guard", "afterCount > currentCount\n", "true\n"),
    ("total count, not delta", "? std::min<uint32>(afterCount - currentCount, amountToAdd)", "? std::min<uint32>(afterCount, amountToAdd)"),
]
caught = 0
for name, old, new in MUTANTS:
    assert SRC.count(old) == 1, name
    work = OUT / "m"
    work.mkdir(parents=True, exist_ok=True)
    mutated = work / "BotRaidConsumables.cpp"
    mutated.write_text(SRC.replace(old, new))
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tests/topup_observed_delta_tests.py"),
                        str(work / "build"), "--source", str(mutated)], capture_output=True, text=True)
    failed = r.returncode != 0
    print(("CAUGHT " if failed else "SURVIVED ") + name)
    caught += failed
print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
