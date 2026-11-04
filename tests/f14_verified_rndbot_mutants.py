"""F14: must-fail mutants for src/Systems/F14VerifiedRandomBotPolicy.h.

Usage: python3 -I tests/f14_verified_rndbot_mutants.py src/Systems/F14VerifiedRandomBotPolicy.h <scratch dir>
Each mutant must make tests/f14_verified_rndbot_policy_tests.cpp fail to
compile (a static_assert) or fail at run time. Exits non-zero if any survives.
"""
import pathlib
import shutil
import subprocess
import sys

src_path = pathlib.Path(sys.argv[1])
src = src_path.read_text()
out = pathlib.Path(sys.argv[2])

muts = [
    ("era: any known era hides",
     "if (observer.era != ObserverEra::Vanilla)", "if (observer.era == ObserverEra::Unknown)"),
    ("era: check dropped",
     "        if (observer.era != ObserverEra::Vanilla)\n            return false;\n", ""),
    ("gm: check dropped",
     "        if (!observer.confirmedNonGameMaster)\n            return false;\n", ""),
    ("own row: check dropped",
     "        if (!row.confirmedNotObserver)\n            return false;\n", ""),
    ("race: check dropped",
     "        if (!IsTbcRace(row.race))\n            return false;\n", ""),
    ("race: Draenei not TBC",
     "        return race == NaxxramasPlayerIdentity::RACE_BLOODELF ||\n               race == NaxxramasPlayerIdentity::RACE_DRAENEI;",
     "        return race == NaxxramasPlayerIdentity::RACE_BLOODELF;"),
    ("identity: any bot hides",
     "if (row.identity != Identity::RandomBot)",
     "if (row.identity != Identity::RandomBot && row.identity != Identity::AltBot)"),
    ("identity: Unknown hides",
     "if (row.identity != Identity::RandomBot)",
     "if (row.identity != Identity::RandomBot && row.identity != Identity::Unknown)"),
    ("identity: check dropped",
     "        if (row.identity != Identity::RandomBot)\n            return false;\n", ""),
    ("verification ignored",
     "        return row.verifiedSelectedRandomBot;", "        return true;"),
    ("default era Vanilla",
     "        ObserverEra era = ObserverEra::Unknown;", "        ObserverEra era = ObserverEra::Vanilla;"),
    ("default non-GM confirmed",
     "        bool confirmedNonGameMaster = false;", "        bool confirmedNonGameMaster = true;"),
    ("default not-observer confirmed",
     "        bool confirmedNotObserver = false;", "        bool confirmedNotObserver = true;"),
    ("default verified",
     "        bool verifiedSelectedRandomBot = false;", "        bool verifiedSelectedRandomBot = true;"),
    ("default identity RandomBot",
     "        Identity identity = Identity::Unknown;", "        Identity identity = Identity::RandomBot;"),
    ("never hides",
     "        return row.verifiedSelectedRandomBot;", "        return false;"),
]

inc = out / "inc"
inc.mkdir(parents=True, exist_ok=True)
# The policy header includes the unchanged #197 header from the same directory.
shutil.copy(src_path.parent / "PlayerIdentityPolicy.h", inc / "PlayerIdentityPolicy.h")

caught = 0
for name, before, after in muts:
    assert src.count(before) == 1, name
    text = src.replace(before, after)
    assert text != src, name
    (inc / "F14VerifiedRandomBotPolicy.h").write_text(text)
    b = subprocess.run(["g++", "-std=c++20", "-pthread", f"-I{inc}",
                        "tests/f14_verified_rndbot_policy_tests.cpp", "-o", str(out / "m")],
                       capture_output=True, text=True)
    if b.returncode != 0:
        print("CAUGHT(compile)", name)
        caught += 1
        continue
    r = subprocess.run([str(out / "m")], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print("CAUGHT", name)
        caught += 1
    else:
        print("SURVIVED", name)
print(f"{caught}/{len(muts)} mutants caught")
sys.exit(0 if caught == len(muts) else 1)
