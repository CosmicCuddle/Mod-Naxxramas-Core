"""Must-fail mutants of the module's real sparkle-guard header.

Usage: A04_CORE=/path/to/pinned/core python3 -I tests/p4_h2_sparkle/mutants.py

Each mutant changes src/Systems/QuestLootSparkleGuard.h in a temporary copy
(next to unchanged copies of the headers it includes). At least one check
must fail.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_sparkle  # noqa: E402

SYSTEMS = build_sparkle.ROOT / "src" / "Systems"
HEADER = SYSTEMS / "QuestLootSparkleGuard.h"

MUTANTS = [
    ("locked quest rows count as something",
     "            if (slot < normalRows || slotType != LOOT_SLOT_TYPE_LOCKED)\n",
     "            if (true)\n"),
    ("locked normal rows count as nothing",
     "            if (slot < normalRows || slotType != LOOT_SLOT_TYPE_LOCKED)\n",
     "            if (slotType != LOOT_SLOT_TYPE_LOCKED)\n"),
    ("gold ignored",
     "        if (view.read<uint32>() != 0)               // gold\n            return true;\n",
     "        view.read<uint32>();\n"),
    ("guard skips the view guard helper",
     "        NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);\n", ""),
    ("passive read keeps the personal-row write (no restore)",
     "                    saved.first->is_looted = saved.second;\n", "                    (void)saved;\n"),
    ("view always offers something",
     "        return false;\n    }\n}\n\n#endif\n", "        return true;\n    }\n}\n\n#endif\n"),
]


def main():
    core = Path(os.environ["A04_CORE"])
    source = HEADER.read_text()
    caught = 0
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            print(f"ANCHOR NOT UNIQUE: {name}")
            return 1
        with tempfile.TemporaryDirectory(prefix="p4-h2-mutant-") as tmp:
            inc = Path(tmp) / "inc"
            inc.mkdir()
            for dep in ("QuestLootViewGuard.h", "QuestLootPickupAuthorization.h"):
                shutil.copy(SYSTEMS / dep, inc / dep)
            (inc / "QuestLootSparkleGuard.h").write_text(source.replace(old, new))
            compiled, rc, output = build_sparkle.run(core, Path(tmp) / "out", header_include=inc)
            if not compiled:
                print(f"NOT COMPILED {name}:\n{output[-1500:]}")
                continue
            failed = [cid for verdict, cid in build_sparkle.parse_checks(output) if verdict == "FAIL"]
            if rc != 0 and failed:
                caught += 1
                print(f"CAUGHT {name}: {len(failed)} check(s) failed, first {failed[0]}")
            else:
                print(f"SURVIVED {name}")
    print(f"{caught}/{len(MUTANTS)} sparkle mutants caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
