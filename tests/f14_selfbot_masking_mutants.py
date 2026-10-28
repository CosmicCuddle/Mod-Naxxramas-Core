"""F14 P12: must-fail mutants (red controls) for f14_selfbot_masking_tests.cpp.

Usage: python3 -I tests/f14_selfbot_masking_mutants.py <scratch dir>

Each mutant changes one modelled source fact, or applies one of the
decision-matrix options (M2, M3) to a copy of the real code, and the test must
then fail. That shows the test pins today's behaviour rather than passing for
any behaviour. Exits 1 if any mutant survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST = "tests/f14_selfbot_masking_tests.cpp"
MGR_STUB = "tests/f14_facts_stubs/playerbots/PlayerbotMgr.h"
POLICY = "src/Systems/PlayerIdentityPolicy.h"
OUT = pathlib.Path(sys.argv[1])

MUTANTS = [
    # Option M3: a Playerbots accessor that ignores Enabled (not in d750b4b).
    ("M3 ungated AI lookup", MGR_STUB,
     "if (!sPlayerbotAIConfig.Enabled || !player)", "if (!player)"),
    # Option M2: fail closed for every socket owner while Playerbots is off.
    ("M2 fail closed while disabled", POLICY,
     "        if (f.socketOpen)\n        {\n",
     "        if (f.socketOpen)\n        {\n            if (!f.playerbotsEnabled)\n"
     "                return Identity::Unknown;\n"),
    ("reload not gated (masking reversible in-process)", TEST,
     "bool CanReloadPlayerbotsConfig() { return sPlayerbotAIConfig.Enabled; }",
     "bool CanReloadPlayerbotsConfig() { return true; }"),
    ("toggle not gated", TEST,
     "bool CanUsePlayerbotCommand() { return sPlayerbotAIConfig.Enabled; }",
     "bool CanUsePlayerbotCommand() { return true; }"),
    ("masked AI still ticked", TEST,
     "return PlayerbotsMgr::instance().GetPlayerbotAI(player) ? 1 : 0;",
     "return PlayerbotsMgr::instance().ais.count(player) ? 1 : 0;"),
    ("self toggle never disarms", TEST,
     "        if (PlayerbotsMgr::instance().GetPlayerbotAI(master))\n            ais.erase(master);\n",
     "        if (PlayerbotsMgr::instance().GetPlayerbotAI(master))\n            ;\n"),
    ("restart keeps the AI map", TEST,
     "        PlayerbotsMgr::instance().ais.clear();\n", ""),
    ("SelfBot counted as human by default", TEST,
     "PolicyConfig const B{Policy::HideBotsOnly, false};",
     "PolicyConfig const B{Policy::HideBotsOnly, true};"),
]


def build_and_run(work):
    exe = work / "t"
    build = subprocess.run(
        ["g++", "-std=c++20", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
         f"-I{work / 'src/Systems'}", f"-I{work / 'tests/f14_facts_stubs/core'}",
         f"-I{work / 'tests/f14_facts_stubs/playerbots'}", str(work / TEST), "-o", str(exe)],
        capture_output=True, text=True)
    if build.returncode != 0:
        return False, "build failed"
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    return run.returncode == 0, run.stdout.strip().splitlines()[-1:] or ["(no output)"]


def fresh(work):
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(ROOT / "src/Systems", work / "src/Systems")
    shutil.copytree(ROOT / "tests/f14_facts_stubs", work / "tests/f14_facts_stubs")
    (work / "tests").mkdir(exist_ok=True)
    shutil.copy(ROOT / TEST, work / TEST)


work = OUT / "p12m"
fresh(work)
ok, last = build_and_run(work)
if not ok:
    print(f"BASELINE FAILED: {last}")
    sys.exit(1)

caught = 0
for name, path, old, new in MUTANTS:
    fresh(work)
    text = (work / path).read_text()
    assert text.count(old) == 1, f"anchor not unique: {name}"
    (work / path).write_text(text.replace(old, new))
    passed, last = build_and_run(work)
    print(("SURVIVED " if passed else "CAUGHT ") + f"{name}: {last}")
    caught += not passed

print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
