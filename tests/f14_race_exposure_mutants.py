"""F14 P16: must-fail mutants for f14_race_exposure_tests.cpp.

Usage: python3 -I tests/f14_race_exposure_mutants.py <extract dir> <scratch dir>

<extract dir> is the output of f14_race_exposure_extract.py. Each mutant
changes the extracted name-query function or #145's writer the way a future
fix (or a regression) would, and the test must then fail. That shows the
counterexample really depends on today's source.
Exits 1 if any mutant survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST = "f14_race_exposure_tests.cpp"
INC = "SendNameQueryOpcode.inc"
WHO = "WhoListingPolicy.h"
EXTRACT, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

MUTANTS = [
    ("name query masks race", INC,
     "    nameQueryResponse.Race = player ? player->getRace() : playerData->Race;\n",
     "    nameQueryResponse.Race = RACE_NONE;\n"),
    ("name query uses the cache over the live player", INC,
     "    nameQueryResponse.Race = player ? player->getRace() : playerData->Race;\n",
     "    nameQueryResponse.Race = playerData->Race;\n"),
    ("name query refuses offline characters", INC,
     "    Player* player = ObjectAccessor::FindConnectedPlayer(guid);\n",
     "    Player* player = ObjectAccessor::FindConnectedPlayer(guid);\n"
     "    if (!player) { nameQueryResponse.NameUnknown = true; SendPacket(nameQueryResponse.Write()); return; }\n"),
    ("name query depends on the asker", INC,
     "    nameQueryResponse.Class = player ? player->getClass() : playerData->Class;\n",
     "    nameQueryResponse.Class = player ? player->getClass() : playerData->Class;\n"
     "    if (observerName == \"vanilla observer\") nameQueryResponse.Race = RACE_NONE;\n"),
    ("#145 writer stops hiding TBC rows", WHO,
     "        return race == RACE_BLOODELF || race == RACE_DRAENEI;\n",
     "        return false;\n"),
]


def fresh(work):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for name in (INC, WHO):
        shutil.copy(EXTRACT / name, work / name)
    shutil.copy(ROOT / "tests" / TEST, work / TEST)


def build_and_run(work):
    exe = work / "t"
    build = subprocess.run(["g++", "-std=c++20", "-O1", "-fsanitize=address,undefined",
                            "-fno-sanitize-recover=all", f"-I{work}", str(work / TEST), "-o", str(exe)],
                           capture_output=True, text=True)
    if build.returncode != 0:
        return False, ["build failed"]
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    return run.returncode == 0, run.stdout.strip().splitlines()[-1:] or [f"rc={run.returncode}"]


work = OUT / "p16m"
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
