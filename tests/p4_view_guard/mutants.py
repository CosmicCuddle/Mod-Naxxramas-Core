"""Must-fail mutants of the module's real guard header.

Usage: A04_CORE=/path/to/pinned/core python3 -I tests/p4_view_guard/mutants.py

Each mutant changes src/Systems/QuestLootViewGuard.h in a temporary copy that
the harness then includes instead of the real one. At least one check must
fail. Exits 1 if any mutant survives or does not compile.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_guard  # noqa: E402

HEADER = build_guard.ROOT / "src" / "Systems" / "QuestLootViewGuard.h"

MUTANTS = [
    ("guard marks nothing",
     "                row.is_looted = true;\n", "                (void)row;\n"),
    ("guard ignores showInLoot (hides rows the core shows)",
     "            if (!hasQuestForItem && !showInLoot)\n", "            if (!hasQuestForItem)\n"),
    ("guard also writes the shared flag",
     "                row.is_looted = true;\n",
     "                row.is_looted = true;\n                loot.quest_items[row.index].is_looted = true;\n"),
    ("guard reads the wrong player's list",
     "questLists.find(viewer->GetGUID());", "questLists.begin();"),
]


def main():
    core = Path(os.environ["A04_CORE"])
    source = HEADER.read_text()
    caught = 0
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            print(f"ANCHOR NOT UNIQUE: {name}")
            return 1
        with tempfile.TemporaryDirectory(prefix="p4-guard-mutant-") as tmp:
            inc = Path(tmp) / "inc"
            inc.mkdir()
            (inc / "QuestLootViewGuard.h").write_text(source.replace(old, new))
            compiled, rc, output = build_guard.run(core, Path(tmp) / "out", guard_include=inc)
            if not compiled:
                print(f"NOT COMPILED {name}:\n{output[-1500:]}")
                continue
            failed = [cid for verdict, cid in build_guard.parse_checks(output) if verdict == "FAIL"]
            if rc != 0 and failed:
                caught += 1
                print(f"CAUGHT {name}: {len(failed)} check(s) failed, first {failed[0]}")
            else:
                print(f"SURVIVED {name}")
    print(f"{caught}/{len(MUTANTS)} guard mutants caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
