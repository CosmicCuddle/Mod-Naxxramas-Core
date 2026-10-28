"""P11: BotRaidConsumables.cpp differs from main only in TopUpToCount's accounting.

Needs git history for BASE_MAIN.
"""
from pathlib import Path
import difflib
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE_MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
PATH = "src/Systems/BotRaidConsumables.cpp"


def main_source(path):
    return subprocess.run(["git", "show", f"{BASE_MAIN}:{path}"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


class TopUpScope(unittest.TestCase):
    def test_only_the_accounting_lines_change(self):
        old = main_source(PATH).splitlines()
        new = (ROOT / PATH).read_text().splitlines()
        diff = [l for l in difflib.unified_diff(old, new, lineterm="", n=0)
                if not l.startswith(("---", "+++", "@@"))]
        removed = sorted(l[1:].strip() for l in diff if l.startswith("-"))
        added = sorted(l[1:].strip() for l in diff
                       if l.startswith("+") and l[1:].strip() and not l[1:].strip().startswith("//"))
        self.assertEqual(removed, sorted(["stats.ItemsAdded += amountToAdd;",
                                          "stats.ReagentsAdded += amountToAdd;"]))
        self.assertEqual(added, sorted([
            "uint32 const afterCount =",
            "bot->GetItemCount(itemId, false);",
            "uint32 const added =",
            "afterCount > currentCount",
            "? std::min<uint32>(afterCount - currentCount, amountToAdd)",
            ": 0;",
            "stats.ItemsAdded += added;",
            "stats.ReagentsAdded += added;",
        ]))

    def test_grant_call_and_failure_text_unchanged(self):
        src = (ROOT / PATH).read_text()
        self.assertEqual(src.count("if (!bot->AddItem(itemId, amountToAdd))"), 1)
        self.assertIn('"AddItem could not add the requested quantity");', src)

    def test_config_and_loader_untouched(self):
        for path in ("conf/mod_naxxramas_core.conf.dist", "src/NaxxramasCore_loader.cpp"):
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_text(), main_source(path))


if __name__ == "__main__":
    unittest.main()
