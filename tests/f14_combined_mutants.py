"""F14 P15: must-fail mutants for f14_combined_matrix_tests.cpp.

Usage: python3 -I tests/f14_combined_mutants.py <staged dir> <scratch dir>

<staged dir> is the output of f14_combined_inputs.py. Each mutant changes
one composed property: the P12 classifier rule (decision options M2 and M3),
the P14 seam, board freshness, or the tick order. The test must then fail.
The tick-order race is built with ThreadSanitizer, which must report it.
Exits 1 if any mutant survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST = "tests/f14_combined_matrix_tests.cpp"
POLICY = "src/Systems/PlayerIdentityPolicy.h"
MGR_STUB = "tests/f14_facts_stubs/playerbots/PlayerbotMgr.h"
STAGED, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

ASAN = ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
TSAN = ["-fsanitize=thread"]

MUTANTS = [
    ("M2 fail closed while Playerbots is off", POLICY, ASAN,
     "        if (f.socketOpen)\n        {\n",
     "        if (f.socketOpen)\n        {\n            if (!f.playerbotsEnabled)\n"
     "                return Identity::Unknown;\n"),
    ("M3 ungated AI lookup", MGR_STUB, ASAN,
     "if (!sPlayerbotAIConfig.Enabled || !player)", "if (!player)"),
    ("seam ignores identity", TEST, ASAN,
     "? board->Lookup(static_cast<std::uint32_t>(guid), now, maxAge)", "? Identity::Unknown"),
    ("observer row not exempt", TEST, ASAN,
     "return HideTbcRow(policy, race, rowIsObserver, identity);",
     "return HideTbcRow(policy, race, false, identity);"),
    ("stale board trusted", POLICY, ASAN,
     "if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)",
     "if (now < snapshot->sampledAt)"),
    ("future board trusted", POLICY, ASAN,
     "if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)",
     "if (now - snapshot->sampledAt > maxAge)"),
    ("SelfBot option ignored", POLICY, ASAN,
     "if (identity == Identity::SelfBot && config.selfBotCountsAsHuman)", "if (false)"),
    ("board published before the map phase", TEST, ASAN,
     "        rows = BuildWhoRows(c);                                   // W1: world thread, L1170\n",
     "        rows = BuildWhoRows(c);                                   // W1: world thread, L1170\n"
     "        if (publish) PublishBoard(board, c, now);\n"),
    ("who rows rebuilt during the map phase (TSAN)", TEST, TSAN,
     "        for (auto& th : workers) th.join();                       // MapMgr.cpp L280\n",
     "        rows = BuildWhoRows(c);\n"
     "        for (auto& th : workers) th.join();                       // MapMgr.cpp L280\n"),
]


def fresh(work):
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(ROOT / "src/Systems", work / "src/Systems")
    shutil.copytree(ROOT / "tests/f14_facts_stubs", work / "tests/f14_facts_stubs")
    shutil.copytree(STAGED / "seam", work / "seam")
    shutil.copy(ROOT / TEST, work / TEST)


def build_and_run(work, flags):
    exe = work / "t"
    build = subprocess.run(
        ["g++", "-std=c++20", "-O1", "-g", "-pthread", *flags, f"-I{work / 'seam'}",
         f"-I{work / 'src/Systems'}", f"-I{work / 'tests/f14_facts_stubs/core'}",
         f"-I{work / 'tests/f14_facts_stubs/playerbots'}", str(work / TEST), "-o", str(exe)],
        capture_output=True, text=True)
    if build.returncode != 0:
        return False, ["build failed"]
    run = subprocess.run([str(exe)], capture_output=True, text=True,
                         env={"TSAN_OPTIONS": "halt_on_error=1 exitcode=66"})
    if "WARNING: ThreadSanitizer: data race" in run.stderr:
        return False, ["ThreadSanitizer: data race"]
    return run.returncode == 0, run.stdout.strip().splitlines()[-1:] or [f"rc={run.returncode}"]


work = OUT / "p15m"
for flags in (ASAN, TSAN):
    fresh(work)
    ok, last = build_and_run(work, flags)
    if not ok:
        print(f"BASELINE FAILED ({flags[0]}): {last}")
        sys.exit(1)

caught = 0
for name, target, flags, old, new in MUTANTS:
    fresh(work)
    text = (work / target).read_text()
    assert text.count(old) == 1, f"anchor not unique: {name}"
    (work / target).write_text(text.replace(old, new))
    passed, last = build_and_run(work, flags)
    print(("SURVIVED " if passed else "CAUGHT ") + f"{name}: {last}")
    caught += not passed

print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
