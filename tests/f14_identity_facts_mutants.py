"""F14 P5: must-fail mutants for src/Systems/PlayerIdentityFacts.cpp.

Usage: python3 -I tests/f14_identity_facts_mutants.py <scratch dir>
Each mutant must make tests/f14_identity_facts_adapter_tests.cpp fail in
the with-Playerbots or without-Playerbots build. Exits 1 if any survives.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/Systems/PlayerIdentityFacts.cpp").read_text()
OUT = pathlib.Path(sys.argv[1])
MUTANTS = [
    ("socket ignored", "facts.socketOpen = session && !session->IsSocketClosed();",
     "facts.socketOpen = session != nullptr;"),
    ("closed socket read as open", "facts.socketOpen = session && !session->IsSocketClosed();",
     "facts.socketOpen = session && session->IsSocketClosed();"),
    ("enabled forced on", "facts.playerbotsEnabled = sPlayerbotAIConfig.Enabled;",
     "facts.playerbotsEnabled = true;"),
    ("master always self", "facts.botMasterIsSelf = ai->GetMaster() == player;",
     "facts.botMasterIsSelf = true;"),
    ("master never self", "facts.botMasterIsSelf = ai->GetMaster() == player;",
     "facts.botMasterIsSelf = false;"),
    ("random never listed", "facts.randomBotListed = sRandomPlayerbotMgr.IsRandomBot(player);",
     "facts.randomBotListed = false;"),
    ("in world forced", "facts.inWorld = player->IsInWorld();", "facts.inWorld = true;"),
    ("session forced", "facts.hasSession = session != nullptr;", "facts.hasSession = true;"),
    ("null player not guarded", "        if (!player)\n            return facts;\n", ""),
    ("no-header build claims human",
     "        (void)player; // No Playerbots in this build: never claim an identity.",
     "        if (player && player->GetSession()) { facts.inWorld = facts.hasSession = true;"
     " facts.socketOpen = !player->GetSession()->IsSocketClosed(); }"),
    ("no-header build reports playerbots", "return NAXXRAMAS_IDENTITY_HAS_PLAYERBOTS != 0;", "return true;"),
    ("ai attached ignored", "            facts.botAiAttached = true;\n", ""),
]

caught = 0
for name, old, new in MUTANTS:
    assert SRC.count(old) == 1, name
    work = OUT / "m"
    if work.exists():
        shutil.rmtree(work)
    (work / "src").mkdir(parents=True)
    shutil.copy(ROOT / "src/Systems/PlayerIdentityPolicy.h", work / "src")
    shutil.copy(ROOT / "src/Systems/PlayerIdentityFacts.h", work / "src")
    (work / "src/PlayerIdentityFacts.cpp").write_text(SRC.replace(old, new))
    failed = False
    for extra in (["-Itests/f14_facts_stubs/playerbots"], ["-DEXPECT_NO_PLAYERBOTS"]):
        exe = work / "t"
        build = subprocess.run(
            ["g++", "-std=c++20", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             f"-I{work / 'src'}", "-Itests/f14_facts_stubs/core", *extra,
             "tests/f14_identity_facts_adapter_tests.cpp", "-o", str(exe)],
            cwd=ROOT, capture_output=True, text=True)
        if build.returncode != 0 or subprocess.run([str(exe)], capture_output=True).returncode != 0:
            failed = True
            break
    print(("CAUGHT " if failed else "SURVIVED ") + name)
    caught += failed
print(f"{caught}/{len(MUTANTS)} mutants caught")
sys.exit(0 if caught == len(MUTANTS) else 1)
