"""Must-fail mutants for the P4-H follow-on harnesses.

Usage: A04_CORE=/path/to/pinned/core python3 -I tests/p4_h_interop/mutants.py

SEAM mutants change a temporary copy of the real #272
src/Systems/MasterLootQuestGive.cpp (the extracted bodies come from it).
GO mutants change a temporary copy of the real #272 header. At least one
check must fail for each.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_interop  # noqa: E402

SYSTEMS = build_interop.ROOT / "src" / "Systems"

SEAM_MUTANTS = [
    ("master looter not checked",
     "group->GetMasterLooterGuid() != leader->GetGUID() || ", ""),
    ("loot method not checked",
     " || group->GetLootMethod() != MASTER_LOOT", ""),
    ("missing target not passed through",
     "        if (!target)\n            return true;\n", ""),
    ("loot GUID not compared",
     "        if (leader->GetLootGUID() != lootGuid)\n            return true;\n", ""),
    ("raid and play time not checked",
     "        if (!leader->IsInRaidWith(target) || target->HasPlayerFlag(PLAYER_FLAGS_NO_PLAY_TIME))\n            return true;\n", ""),
    ("range not checked",
     "        if (slot >= loot->items.size() + loot->quest_items.size())\n            return true;\n", ""),
    ("gameobject loot ignored",
     "        else if (lootGuid.IsGameObject())\n", "        else if (false)\n"),
    ("already looted lets the core run",
     "                leader->SendEquipError(EQUIP_ERR_ALREADY_LOOTED, nullptr, nullptr);\n                return false;\n",
     "                return true;\n"),
    ("error reply dropped",
     "                leader->SendLootError(lootGuid, outcome.error);\n", ""),
    ("given lets the core run too",
     "            case NaxxramasMasterLootQuestGive::Result::Given:\n                return false;\n",
     "            case NaxxramasMasterLootQuestGive::Result::Given:\n                return true;\n"),
    ("enable switch ignored",
     "            !s_masterLootQuestGiveEnabled.load(std::memory_order_relaxed) ||\n", ""),
    ("packet fields read out of order",
     "        copy >> lootGuid >> slot >> targetGuid;\n", "        copy >> lootGuid >> targetGuid >> slot;\n"),
]

GO_MUTANTS = [
    ("leader's slot sent to every looter",
     "        loot.NotifyQuestItemRemoved(row.index);\n", "        loot.NotifyItemRemoved(slot);\n"),
    ("zero-count still awarded",
     "        if (item.count == 0 || row.is_looted || item.is_looted)\n",
     "        if (row.is_looted || item.is_looted)\n"),
    ("shared looted flag not checked",
     "        if (item.count == 0 || row.is_looted || item.is_looted)\n", "        if (row.is_looted)\n"),
    ("normal slots taken over",
     "        if (slot < loot.items.size())\n", "        if (false)\n"),
]


def failed_checks(output):
    return [cid for verdict, cid in build_interop.parse_checks(output) if verdict == "FAIL"]


def main():
    core = Path(os.environ["A04_CORE"])
    caught = total = 0
    cpp = (SYSTEMS / "MasterLootQuestGive.cpp").read_text()
    header = (SYSTEMS / "MasterLootQuestGive.h").read_text()
    for kind, source, mutants in (("seam", cpp, SEAM_MUTANTS), ("go", header, GO_MUTANTS)):
        for name, old, new in mutants:
            total += 1
            if source.count(old) != 1:
                print(f"ANCHOR NOT UNIQUE: {name}")
                return 1
            with tempfile.TemporaryDirectory(prefix="p4-hi-mutant-") as tmp:
                tmp = Path(tmp)
                if kind == "seam":
                    mutated = tmp / "MasterLootQuestGive.cpp"
                    mutated.write_text(source.replace(old, new))
                    compiled, rc, output = build_interop.run_seam(core, tmp / "out", module_cpp=mutated)
                else:
                    inc = tmp / "inc"
                    inc.mkdir()
                    (inc / "MasterLootQuestGive.h").write_text(source.replace(old, new))
                    compiled, rc, output = build_interop.run_go(core, tmp / "out", header_include=inc)
            if not compiled:
                print(f"NOT COMPILED {kind}: {name}\n{output[-1500:]}")
                continue
            failed = failed_checks(output)
            if rc != 0 and failed:
                caught += 1
                print(f"CAUGHT {kind}: {name}: {len(failed)} check(s) failed, first {failed[0]}")
            elif rc is not None and rc < 0:
                # Killed by a signal (e.g. a null target dereferenced): the real
                # Worldserver would crash the same way, so the mutant is caught.
                caught += 1
                print(f"CAUGHT {kind}: {name}: crashed (signal {-rc})")
            else:
                print(f"SURVIVED {kind}: {name}")
    print(f"{caught}/{total} interop mutants caught")
    return 0 if caught == total else 1


if __name__ == "__main__":
    sys.exit(main())
