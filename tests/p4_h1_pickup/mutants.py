"""Must-fail mutants of the module's real pickup-authorization header.

Usage: A04_CORE=/path/to/pinned/core python3 -I tests/p4_h1_pickup/mutants.py

Each mutant changes src/Systems/QuestLootPickupAuthorization.h in a
temporary copy (next to an unchanged copy of QuestLootViewGuard.h) that the
harness includes instead of the real one. At least one check must fail.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pickup  # noqa: E402

SYSTEMS = build_pickup.ROOT / "src" / "Systems"
HEADER = SYSTEMS / "QuestLootPickupAuthorization.h"

MUTANTS = [
    ("check allows any slot",
     "        return false;\n    }\n}\n\n#endif\n", "        return true;\n    }\n}\n\n#endif\n"),
    ("check skips the view guard (shared side effect)",
     "        NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);\n", ""),
    ("master looter gets restricted rights",
     "isMasterLooter ? MASTER_PERMISSION : RESTRICTED_PERMISSION", "RESTRICTED_PERMISSION"),
    ("another group gets loot rights",
     "            if (!inRecipientGroup)\n                return NONE_PERMISSION;\n", ""),
    ("round robin treated as group loot",
     "                case ROUND_ROBIN:\n                    return ROUND_ROBIN_PERMISSION;\n", ""),
]


def main():
    core = Path(os.environ["A04_CORE"])
    source = HEADER.read_text()
    caught = 0
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            print(f"ANCHOR NOT UNIQUE: {name}")
            return 1
        with tempfile.TemporaryDirectory(prefix="p4-h1-mutant-") as tmp:
            inc = Path(tmp) / "inc"
            inc.mkdir()
            shutil.copy(SYSTEMS / "QuestLootViewGuard.h", inc / "QuestLootViewGuard.h")
            (inc / "QuestLootPickupAuthorization.h").write_text(source.replace(old, new))
            compiled, rc, output = build_pickup.run(core, Path(tmp) / "out", header_include=inc)
            if not compiled:
                print(f"NOT COMPILED {name}:\n{output[-1500:]}")
                continue
            failed = [cid for verdict, cid in build_pickup.parse_checks(output) if verdict == "FAIL"]
            if rc != 0 and failed:
                caught += 1
                print(f"CAUGHT {name}: {len(failed)} check(s) failed, first {failed[0]}")
            else:
                print(f"SURVIVED {name}")
    print(f"{caught}/{len(MUTANTS)} pickup mutants caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
