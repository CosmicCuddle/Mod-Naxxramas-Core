"""P7: must-fail mutants for src/Systems/ConfigFlagSnapshot.h.

Usage: python3 -I tests/config_flag_snapshot_mutants.py <scratch dir>
Exits 1 if any mutant survives tests/config_flag_snapshot_tests.cpp (the
plain-bool mutant under ThreadSanitizer).
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/Systems/ConfigFlagSnapshot.h").read_text()
OUT = pathlib.Path(sys.argv[1])
MUTANTS = [
    ("store ignored", "void Store(bool value) { _value.store(value, std::memory_order_relaxed); }",
     "void Store(bool value) { (void)value; }", False),
    ("initial ignored", "constexpr explicit Flag(bool initial) : _value(initial) {}",
     "constexpr explicit Flag(bool initial) : _value(!initial) {}", False),
    ("plain bool (race)", "        std::atomic<bool> _value;", "        bool _value;", True),
]
caught = 0
for name, old, new, tsan in MUTANTS:
    assert SRC.count(old) == 1, name
    text = SRC.replace(old, new)
    if tsan:
        text = (text.replace("_value.store(value, std::memory_order_relaxed);", "_value = value;")
                    .replace("return _value.load(std::memory_order_relaxed);", "return _value;"))
    work = OUT / "m"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "ConfigFlagSnapshot.h").write_text(text)
    flags = ["-fsanitize=thread", "-g", "-O1"] if tsan else []
    b = subprocess.run(["g++", "-std=c++20", "-pthread", *flags, f"-I{work}",
                        "tests/config_flag_snapshot_tests.cpp", "-o", str(work / "t")],
                       cwd=ROOT, capture_output=True, text=True)
    failed = b.returncode != 0 or subprocess.run(
        [str(work / "t")], capture_output=True, env={"TSAN_OPTIONS": "halt_on_error=1"}).returncode != 0
    print(("CAUGHT " if failed else "SURVIVED ") + name)
    caught += failed
print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
