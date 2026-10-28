"""F14 P12: pinned Playerbots source facts behind f14_selfbot_masking_tests.cpp.

Usage: python3 -I tests/f14_selfbot_masking_facts.py <mod-playerbots checkout>

Checks the checkout is d750b4b, then that each fact the C++ test models still
holds at the cited lines. Every fact is also run against a mutated copy of
its own source (negative fixture) and must fail there, so a checker that
matches too loosely is caught.
"""
from pathlib import Path
import re
import subprocess
import sys

PIN = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"

MGR_CPP = "src/Bot/PlayerbotMgr.cpp"
MGR_H = "src/Bot/PlayerbotMgr.h"
RND_CPP = "src/Bot/RandomPlayerbotMgr.cpp"
CFG_CPP = "src/PlayerbotAIConfig.cpp"
PB_CPP = "src/Script/Playerbots.cpp"
PB_H = "src/Script/Playerbots.h"
FILES = (MGR_CPP, MGR_H, RND_CPP, CFG_CPP, PB_CPP, PB_H)
# Any call of the config's Initialize, however the singleton is spelled.
INIT_CALL = re.compile(r"(?:sPlayerbotAIConfig|PlayerbotAIConfig::\w+\(\))\s*(?:\.|->)\s*Initialize\s*\(")


def lines(src, path, first, last):
    """Lines first..last (1-based, inclusive) joined, whitespace-normalised."""
    chunk = src[path].splitlines()[first - 1:last]
    return " ".join(" ".join(chunk).split())


def has(src, path, first, last, *needles):
    text = lines(src, path, first, last)
    return all(n in text for n in needles)


# Each fact: (id, description, predicate, mutation used as negative fixture).
# A mutation is (path, old, new); the predicate must be False after it.
FACTS = [
    ("F1", "GetPlayerbotAI returns nullptr while !Enabled (PlayerbotMgr.cpp L1858-L1862)",
     lambda s: has(s, MGR_CPP, 1858, 1862, "PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)",
                   "if (!(sPlayerbotAIConfig.Enabled) || !player)", "return nullptr;"),
     (MGR_CPP, "if (!(sPlayerbotAIConfig.Enabled) || !player)\n    {\n        return nullptr;\n    }\n    // if",
      "if (!player)\n    {\n        return nullptr;\n    }\n    // if")),
    ("F2", "GetPlayerbotMgr is gated the same way (PlayerbotMgr.cpp L1878-L1882)",
     lambda s: has(s, MGR_CPP, 1878, 1882, "PlayerbotMgr* PlayerbotsMgr::GetPlayerbotMgr(Player* player)",
                   "if (!(sPlayerbotAIConfig.Enabled) || !player)", "return nullptr;"),
     (MGR_CPP, "PlayerbotMgr* PlayerbotsMgr::GetPlayerbotMgr(Player* player)\n{\n    if (!(sPlayerbotAIConfig.Enabled) || !player)",
      "PlayerbotMgr* PlayerbotsMgr::GetPlayerbotMgr(Player* player)\n{\n    if (!player)")),
    ("F3", "the AI is ticked only through the gated lookup (Playerbots.cpp L248-L254)",
     lambda s: has(s, PB_CPP, 248, 254, "void OnPlayerAfterUpdate(Player* player, uint32 diff) override",
                   "PlayerbotAI* const botAI = PlayerbotsMgr::instance().GetPlayerbotAI(player);",
                   "if (botAI != nullptr)", "botAI->UpdateAI(diff);"),
     (PB_CPP, "if (botAI != nullptr)\n        {\n            botAI->UpdateAI(diff);",
      "if (true)\n        {\n            botAI->UpdateAI(diff);")),
    ("F4", "macros route through the gated accessors (Playerbots.h L31-L32)",
     lambda s: has(s, PB_H, 31, 32, "#define GET_PLAYERBOT_AI(object) sPlayerbotsMgr.GetPlayerbotAI(object)",
                   "#define GET_PLAYERBOT_MGR(object) sPlayerbotsMgr.GetPlayerbotMgr(object)"),
     (PB_H, "#define GET_PLAYERBOT_AI(object) sPlayerbotsMgr.GetPlayerbotAI(object)",
      "#define GET_PLAYERBOT_AI(object) sPlayerbotsMgr.GetPlayerbotAIUngated(object)")),
    ("F5", "chat entry refuses every bot command while !Enabled (PlayerbotMgr.cpp L927-L931)",
     lambda s: has(s, MGR_CPP, 927, 931, "PlayerbotMgr* mgr = GET_PLAYERBOT_MGR(player);", "if (!mgr)",
                   'handler->PSendSysMessage("You cannot control bots yet");', "return false;"),
     (MGR_CPP, '    if (!mgr)\n    {\n        handler->PSendSysMessage("You cannot control bots yet");',
      '    if (false)\n    {\n        handler->PSendSysMessage("You cannot control bots yet");')),
    ("F6", "self toggle deletes the AI or attaches one as its own master (PlayerbotMgr.cpp L1100-L1120)",
     lambda s: has(s, MGR_CPP, 1100, 1120, 'if (!strcmp(cmd, "self"))', "if (GET_PLAYERBOT_AI(master))",
                   "delete GET_PLAYERBOT_AI(master);", "PlayerbotsMgr::instance().AddPlayerbotData(master, true);",
                   "GET_PLAYERBOT_AI(master)->SetMaster(master);"),
     (MGR_CPP, "            delete GET_PLAYERBOT_AI(master);\n", "")),
    ("F7", "SelfBotLevel > 2 auto-selfs at login (PlayerbotMgr.cpp L1733-L1734)",
     lambda s: has(s, MGR_CPP, 1733, 1734, "if (sPlayerbotAIConfig.SelfBotLevel > 2)",
                   'HandlePlayerbotCommand("self", player);'),
     (MGR_CPP, "if (sPlayerbotAIConfig.SelfBotLevel > 2)\n        HandlePlayerbotCommand(\"self\", player);",
      "if (sPlayerbotAIConfig.SelfBotLevel > 2)\n        return;")),
    ("F8", "Initialize sets Enabled from Playerbots.Enabled (PlayerbotAIConfig.cpp L79-L83)",
     lambda s: has(s, CFG_CPP, 79, 83, "bool PlayerbotAIConfig::Initialize()",
                   'Enabled = sConfigMgr->GetOption<bool>("Playerbots.Enabled", true);'),
     (CFG_CPP, 'Enabled = sConfigMgr->GetOption<bool>("Playerbots.Enabled", true);', 'Enabled = true;')),
    ("F9", "bot reload re-runs Initialize, behind the L927 gate (PlayerbotMgr.cpp L1074-L1079)",
     lambda s: has(s, MGR_CPP, 1074, 1079, 'if (!strcmp(cmd, "reload"))', "sPlayerbotAIConfig.Initialize();"),
     (MGR_CPP, "            sPlayerbotAIConfig.Initialize();\n            messages.push_back(\"Config reloaded.\");",
      "            messages.push_back(\"Config reloaded.\");")),
    ("F10", "rndbot reload re-runs Initialize, behind an Enabled gate (RandomPlayerbotMgr.cpp L2503-L2506, L2532-L2534)",
     lambda s: has(s, RND_CPP, 2501, 2506, "bool RandomPlayerbotMgr::HandlePlayerbotConsoleCommand(",
                   "if (!sPlayerbotAIConfig.Enabled)", "return false;")
     and has(s, RND_CPP, 2532, 2535, 'if (cmd == "reload")', "sPlayerbotAIConfig.Initialize();"),
     (RND_CPP, "{\n    if (!sPlayerbotAIConfig.Enabled)\n    {\n        LOG_ERROR(\"playerbots\", \"Playerbots system is currently disabled!\");",
      "{\n    if (false)\n    {\n        LOG_ERROR(\"playerbots\", \"Playerbots system is currently disabled!\");")),
    ("F11", "Initialize has exactly three callers in src/: startup, bot reload, rndbot reload",
     lambda s: sorted((p, n) for p in s for n, l in enumerate(s[p].splitlines(), 1)
                      if INIT_CALL.search(l))
     == sorted([(PB_CPP, 531), (MGR_CPP, 1079), (RND_CPP, 2534)]),
     (MGR_CPP, 'if (!strcmp(cmd, "reload"))', 'sPlayerbotAIConfig.Initialize(); if (!strcmp(cmd, "reload"))')),
    ("F12", "the AI map is private; the header exposes only the gated getters (PlayerbotMgr.h L122-L137)",
     lambda s: has(s, MGR_H, 122, 137, "PlayerbotAI* GetPlayerbotAI(Player* player);",
                   "PlayerbotMgr* GetPlayerbotMgr(Player* player);", "private:",
                   "std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;")
     and lines(s, MGR_H, 122, 137).index("private:") < lines(s, MGR_H, 122, 137).index("_playerbotsAIMap")
     and "_playerbotsAIMap" not in "".join(l for l in s[MGR_H].splitlines()[:121]),
     (MGR_H, "private:\n    PlayerbotsMgr() = default;", "public:\n    PlayerbotsMgr() = default;")),
    ("F13", "IsRandomBot(Player*) says false for a SelfBot (RandomPlayerbotMgr.cpp L2239-L2244)",
     lambda s: has(s, RND_CPP, 2239, 2244, "bool RandomPlayerbotMgr::IsRandomBot(Player* bot)",
                   "if (bot && GET_PLAYERBOT_AI(bot))", "if (IsSelfBot(bot))", "return false;"),
     (RND_CPP, "IsRandomBot(Player* bot)\n{\n    if (bot && GET_PLAYERBOT_AI(bot))\n    {\n        if (IsSelfBot(bot))\n            return false;",
      "IsRandomBot(Player* bot)\n{\n    if (bot && GET_PLAYERBOT_AI(bot))\n    {\n        if (IsSelfBot(bot))\n            return true;")),
]


def load(root):
    """Every .cpp/.h under src/ (F11 scans them all), keyed by relative path."""
    src = {f.relative_to(root).as_posix(): f.read_text(errors="replace")
           for f in sorted((root / "src").rglob("*")) if f.suffix in (".cpp", ".h")}
    missing = [p for p in FILES if p not in src]
    if missing:
        raise SystemExit(f"missing pinned files: {missing}")
    return src


def run(src):
    return [(fid, desc, bool(pred(src))) for fid, desc, pred, _ in FACTS]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    root = Path(argv[1])
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != PIN:
        print(f"WRONG PIN: {head} != {PIN}")
        return 1
    src = load(root)
    bad = 0
    for fid, desc, ok in run(src):
        print(f"{'OK  ' if ok else 'FAIL'} {fid}: {desc}")
        bad += not ok
    caught = 0
    for fid, _, pred, (path, old, new) in FACTS:
        if src[path].count(old) != 1:
            print(f"FIXTURE {fid}: mutation anchor not unique in {path}")
            bad += 1
            continue
        mutated = dict(src, **{path: src[path].replace(old, new)})
        if pred(mutated):
            print(f"FIXTURE {fid}: mutated source still passes")
            bad += 1
        else:
            caught += 1
    print(f"{caught}/{len(FACTS)} negative fixtures caught")
    if bad:
        print(f"FAILED: {bad}")
        return 1
    print(f"PASS: {len(FACTS)} pinned Playerbots facts at {PIN[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
