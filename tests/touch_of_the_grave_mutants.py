"""P6: must-fail mutants for src/Racials/Forsaken/TouchOfTheGraveSettings.h.

Usage: python3 -I tests/touch_of_the_grave_mutants.py <scratch dir>
Each mutant must make tests/touch_of_the_grave_settings_tests.cpp fail (the
atomic mutant under ThreadSanitizer). Exits 1 if any survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "src/Racials/Forsaken/TouchOfTheGraveSettings.h"
SRC = HEADER.read_text()
OUT = pathlib.Path(sys.argv[1])
MUTANTS = [
    ("pre-TBC stage 7", "PROGRESSION_PRE_TBC = 8;", "PROGRESSION_PRE_TBC = 7;", False),
    ("TBC tier 5 stage 12", "PROGRESSION_TBC_TIER_5 = 13;", "PROGRESSION_TBC_TIER_5 = 12;", False),
    ("level gate off by one", "if (level <= 10)", "if (level <= 11)", False),
    ("limit ignored", "if (progressionLimit && requiredProgression > progressionLimit)",
     "if (false && requiredProgression > progressionLimit)", False),
    ("required 0 passes", "        if (!requiredProgression)\n            return false;\n", "", False),
    ("disabled not honoured", "        if (!enabled)\n            return 1.0f;\n", "", False),
    ("tbc returns vanilla", "            return tbcAdjustment;", "            return vanillaAdjustment;", False),
    ("divisor 60", "(float(level) - 10.0f) / 50.0f", "(float(level) - 10.0f) / 60.0f", False),
    ("default disabled", "bool enabled = true;", "bool enabled = false;", False),
    ("default adjustment 0.9", "float vanillaHealing = 1.0f;", "float vanillaHealing = 0.9f;", False),
    ("healing not stored", "            _vanillaHealing.store(s.vanillaHealing, std::memory_order_relaxed);\n", "", False),
    ("limit not loaded", "            s.progressionLimit = _progressionLimit.load(std::memory_order_relaxed);\n", "", False),
    ("plain float (race)", "        std::atomic<float> _vanillaPower{IpSettings{}.vanillaPower};",
     "        float _vanillaPower{IpSettings{}.vanillaPower};", True),
]
caught = 0
for name, old, new, tsan in MUTANTS:
    assert SRC.count(old) == 1, name
    text = SRC.replace(old, new)
    if tsan:
        text = (text.replace("_vanillaPower.store(s.vanillaPower, std::memory_order_relaxed);",
                             "_vanillaPower = s.vanillaPower;")
                    .replace("s.vanillaPower = _vanillaPower.load(std::memory_order_relaxed);",
                             "s.vanillaPower = _vanillaPower;"))
    work = OUT / "m"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "TouchOfTheGraveSettings.h").write_text(text)
    flags = ["-fsanitize=thread", "-g", "-O1"] if tsan else ["-O1"]
    build = subprocess.run(["g++", "-std=c++20", "-pthread", *flags, f"-I{work}",
                            "tests/touch_of_the_grave_settings_tests.cpp", "-o", str(work / "t")],
                           cwd=ROOT, capture_output=True, text=True)
    failed = build.returncode != 0 or subprocess.run(
        [str(work / "t")], capture_output=True, env={"TSAN_OPTIONS": "halt_on_error=1"}).returncode != 0
    print(("CAUGHT " if failed else "SURVIVED ") + name)
    caught += failed
print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
