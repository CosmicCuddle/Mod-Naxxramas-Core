"""Must-fail mutants of the module's real Master Loot quest-give header.

Usage: A04_CORE=/path/to/pinned/core python3 -I tests/p4_h_master_loot/mutants.py

Each mutant changes src/Systems/MasterLootQuestGive.h in a temporary copy
that the harness includes instead of the real one. At least one check must
fail.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_master_loot  # noqa: E402

HEADER = build_master_loot.ROOT / "src" / "Systems" / "MasterLootQuestGive.h"

MUTANTS = [
    ("notify with the leader's slot (stock)",
     "        loot.NotifyQuestItemRemoved(row.index);\n", "        loot.NotifyItemRemoved(slot);\n"),
    ("global quest index (stock)",
     "        LootItem& item = loot.quest_items[row.index];\n", "        LootItem& item = loot.quest_items[questSlot];\n"),
    ("zero-count still awarded",
     "        if (item.count == 0 || row.is_looted || item.is_looted)\n",
     "        if (row.is_looted || item.is_looted)\n"),
    ("shared looted flag not checked",
     "        if (item.count == 0 || row.is_looted || item.is_looted)\n", "        if (row.is_looted)\n"),
    ("FFA quest copy given",
     "        if (item.freeforall)\n            return {Result::Error, LOOT_ERROR_MASTER_OTHER};\n", ""),
    ("item not marked looted",
     "        item.is_looted = true;\n", ""),
    ("unlooted count not lowered",
     "        --loot.unlootedCount;\n", ""),
    ("inventory full reported as other",
     "                return {Result::Error, LOOT_ERROR_MASTER_INV_FULL};\n",
     "                return {Result::Error, LOOT_ERROR_MASTER_OTHER};\n"),
    ("target eligibility skipped",
     "        if (!item.AllowedForPlayer(target, loot.sourceWorldObjectGUID))\n"
     "            msg = EQUIP_ERR_YOU_CAN_NEVER_USE_THAT_ITEM;\n", ""),
    ("normal slots taken over",
     "        if (slot < loot.items.size())\n", "        if (false)\n"),
]


def main():
    core = Path(os.environ["A04_CORE"])
    source = HEADER.read_text()
    caught = 0
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            print(f"ANCHOR NOT UNIQUE: {name}")
            return 1
        with tempfile.TemporaryDirectory(prefix="p4-h-mutant-") as tmp:
            inc = Path(tmp) / "inc"
            inc.mkdir()
            (inc / "MasterLootQuestGive.h").write_text(source.replace(old, new))
            compiled, rc, output = build_master_loot.run(core, Path(tmp) / "out", header_include=inc)
            if not compiled:
                print(f"NOT COMPILED {name}:\n{output[-1500:]}")
                continue
            failed = [cid for verdict, cid in build_master_loot.parse_checks(output) if verdict == "FAIL"]
            if rc != 0 and failed:
                caught += 1
                print(f"CAUGHT {name}: {len(failed)} check(s) failed, first {failed[0]}")
            else:
                print(f"SURVIVED {name}")
    print(f"{caught}/{len(MUTANTS)} master loot mutants caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
