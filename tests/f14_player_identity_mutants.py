"""F14 P1: must-fail mutants for src/Systems/PlayerIdentityPolicy.h.

Usage: python3 -I tests/f14_player_identity_mutants.py src/Systems/PlayerIdentityPolicy.h <scratch dir>
Each mutant must make tests/f14_player_identity_policy_tests.cpp fail (the
lock mutant under ThreadSanitizer). Exits non-zero if any mutant survives.
"""
import subprocess, sys, pathlib, shutil
src = pathlib.Path(sys.argv[1]).read_text()
out = pathlib.Path(sys.argv[2])
muts = [
 ("human without socket", "        if (f.socketOpen)\n        {", "        if (true)\n        {"),
 ("drop random contradiction", "            if (f.randomBotListed)\n                return Identity::Unknown;          // contradiction\n", ""),
 ("foreign AI on socket -> human", "            return Identity::Unknown;              // socket owned, AI mastered elsewhere", "            return Identity::Human;"),
 ("ignore playerbotsEnabled", "if (!f.playerbotsEnabled || !f.botAiAttached", "if (!f.botAiAttached"),
 ("no-AI socketless -> AltBot", "if (!f.playerbotsEnabled || !f.botAiAttached || f.botMasterIsSelf)", "if (!f.playerbotsEnabled || f.botMasterIsSelf)"),
 ("drop inWorld", "if (!f.inWorld || !f.hasSession)", "if (!f.hasSession)"),
 ("swap random/alt", "return f.randomBotListed ? Identity::RandomBot : Identity::AltBot;", "return f.randomBotListed ? Identity::AltBot : Identity::RandomBot;"),
 ("parse default B", "return raw == 1 ? Policy::HideBotsOnly : Policy::HideAllTbcRaces;", "return raw == 0 ? Policy::HideAllTbcRaces : Policy::HideBotsOnly;"),
 ("unknown shown under B", "        if (identity == Identity::Human)\n            return false;", "        if (identity == Identity::Human || identity == Identity::Unknown)\n            return false;"),
 ("selfbot shown by default", "if (identity == Identity::SelfBot && config.selfBotCountsAsHuman)", "if (identity == Identity::SelfBot)"),
 ("observer row hidden", "if (!IsTbcRace(race) || rowIsObserver)", "if (!IsTbcRace(race))"),
 ("bogus policy shows", "if (config.policy != Policy::HideBotsOnly)", "if (config.policy == Policy::HideAllTbcRaces)"),
 ("draenei not TBC", "return race == RACE_BLOODELF || race == RACE_DRAENEI;\n    }\n\n    // rowIsObserver", "return race == RACE_BLOODELF;\n    }\n\n    // rowIsObserver"),
 ("duplicate keeps first", "                    if (!inserted)\n                        it->second = Identity::Unknown;\n", "                    (void)it; (void)inserted;\n"),
 ("guid 0 accepted", "if (!snapshot || !snapshot->valid || guidLow == 0)", "if (!snapshot || !snapshot->valid)"),
 ("partial publish over cap", "            if (rows.size() <= MAX_ENTRIES)", "            if (true)"),
 ("cap off by one", "            if (rows.size() <= MAX_ENTRIES)", "            if (rows.size() < MAX_ENTRIES)"),
 ("no staleness", "if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)", "if (now < snapshot->sampledAt)"),
 ("future accepted", "if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)", "if (now >= snapshot->sampledAt && now - snapshot->sampledAt > maxAge)"),
 ("invalidate no-op", "            _current.reset();", "            (void)0;"),
 ("merge instead of replace (keep old)", "            _current = std::move(next);", "            if (!_current) _current = std::move(next);"),
]
tsan_muts = [
 ("lookup without lock", "            {\n                std::lock_guard<std::mutex> lock(_mutex);\n                snapshot = _current;\n            }", "            snapshot = _current;"),
]
inc = out / "inc"; inc.mkdir(parents=True, exist_ok=True)
caught = 0; total = 0
def run(name, text, tsan):
    global caught, total
    total += 1
    assert text != src, name
    (inc / "PlayerIdentityPolicy.h").write_text(text)
    flags = ["-fsanitize=thread", "-O1", "-g"] if tsan else []
    b = subprocess.run(["g++", "-std=c++20", "-pthread", *flags, f"-I{inc}", "tests/f14_player_identity_policy_tests.cpp", "-o", str(out / "m")], capture_output=True, text=True)
    if b.returncode != 0:
        print("CAUGHT(compile)", name); caught += 1; return
    r = subprocess.run([str(out / "m")], capture_output=True, text=True, env={"TSAN_OPTIONS": "halt_on_error=1"}, timeout=300)
    if r.returncode != 0: print("CAUGHT", name); caught += 1
    else: print("SURVIVED", name)
for n, a, b in muts:
    assert src.count(a) == 1, n
    run(n, src.replace(a, b), False)
for n, a, b in tsan_muts:
    assert src.count(a) == 1, n
    run(n, src.replace(a, b), True)
print(f"{caught}/{total} mutants caught")
sys.exit(0 if caught == total else 1)
